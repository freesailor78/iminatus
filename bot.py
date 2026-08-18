import os
import asyncio
from datetime import datetime, timedelta
import flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# --- 1. Конфигурация из переменных окружения ---
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
MAX_HISTORY = int(os.environ.get("MAX_HISTORY_MESSAGES", 5))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS_PER_REPLY", 1024))
PORT = int(os.environ.get("PORT", 5000))
FREE_QUESTIONS_LIMIT = 3  # Бесплатных вопросов в сутки

# --- 2. Инициализация DeepSeek клиента ---
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# --- 3. Хранилище данных пользователей (ВНИМАНИЕ: только для примера, на проде используйте БД!) ---
user_conversations = {}
# Новая структура для хранения информации о запросах пользователя
# { user_id: {"date": "YYYY-MM-DD", "count": 0} }
user_daily_requests = {}

# --- СИСТЕМНЫЙ ПРОМПТ (юнгианский психолог) ---
SYSTEM_PROMPT = """
Ты — опытный юнгианский психолог. Помогай анализировать и расшифровывать сны через архетипы, символы и концепции аналитической психологии (Тень, Персона, Анима/Анимус, Самость).

Твоя задача:
1. Внимательно выслушать сон.
2. Выделить ключевые символы и их архетипическое значение.
3. Задать 1-2 наводящих вопроса, чтобы помочь пользователю заглянуть глубже в своё бессознательное.
4. В конце дай короткий вывод простыми, почти ироничными словами, мудро, с лёгким сарказмом и узнаваемой интонацией.

Важно:
- Отвечай на "Вы", уважительно, но с мягким юмором.
- Не ставь диагнозов и не давай прямых советов — только направляй к инсайту.
"""

# --- Вспомогательная функция для работы с лимитами ---
def get_user_requests_today(user_id: int) -> tuple:
    """
    Проверяет, сколько запросов сделал пользователь сегодня.
    Возвращает (количество_сегодня, остаток_лимита, можно_ли_спросить)
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Если пользователя нет в словаре или его данные за старый день, сбрасываем
    if user_id not in user_daily_requests or user_daily_requests[user_id]["date"] != today_str:
        user_daily_requests[user_id] = {"date": today_str, "count": 0}
    
    current_count = user_daily_requests[user_id]["count"]
    remaining = FREE_QUESTIONS_LIMIT - current_count
    can_ask = remaining > 0
    
    return current_count, remaining, can_ask

# --- 4. Основная функция для работы с DeepSeek ---
async def get_deepseek_response(user_id: int, message: str) -> str:
    """Получает ответ от DeepSeek с учётом системного промпта и истории."""
    # Инициализация истории для пользователя, если её нет
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}  # Системный промпт всегда в начале
        ]

    # Добавляем новое сообщение пользователя
    user_conversations[user_id].append({"role": "user", "content": message})

    # Отправляем ТОЛЬКО последние MAX_HISTORY сообщений, но системный промпт всегда первый
    history = user_conversations[user_id]
    messages_to_send = [history[0]] + history[-MAX_HISTORY:]

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages_to_send,
            max_tokens=MAX_TOKENS,
            temperature=0.7,
        )
        assistant_reply = response.choices[0].message.content

        # Сохраняем ответ в историю
        user_conversations[user_id].append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

    except Exception as e:
        return f"⚠️ Ошибка при обращении к DeepSeek: {e}"

# --- 5. Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _, remaining, _ = get_user_requests_today(user_id)
    
    await update.message.reply_text(
        f"👋 Привет! Я — юнгианский аналитик снов.\n\n"
        f"🔮 Отправьте мне описание вашего сна, и я помогу его интерпретировать.\n"
        f"🎁 У вас есть {remaining} бесплатных вопросов на сегодня.\n"
        f"⏳ Лимит ({FREE_QUESTIONS_LIMIT} вопросов) обновляется каждый день.\n\n"
        f"Команды:\n"
        f"/start — показать это сообщение\n"
        f"/clear — очистить историю диалога (не влияет на лимит)"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    if not user_message:
        return

    # Получаем актуальные данные о лимитах
    current_count, remaining, can_ask = get_user_requests_today(user_id)

    if can_ask:
        # Разрешаем вопрос
        await update.message.reply_chat_action(action="typing")
        reply = await get_deepseek_response(user_id, user_message)
        
        # Увеличиваем счётчик использованных вопросов
        user_daily_requests[user_id]["count"] += 1
        
        # Отправляем ответ с уведомлением об остатке
        new_remaining = remaining - 1
        await update.message.reply_text(
            f"{reply}\n\n✨ Осталось бесплатных вопросов на сегодня: {new_remaining}"
        )
    else:
        # Лимит исчерпан
        await update.message.reply_text(
            f"😔 Вы исчерпали дневной лимит вопросов ({FREE_QUESTIONS_LIMIT}).\n\n"
            f"⏳ Лимит обновится завтра. Возвращайтесь!\n\n"
            f"А пока поразмышляйте над тем, что вы уже узнали о своих снах. 🧠"
        )

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_conversations:
        # Сохраняем только системный промпт, очищая историю
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    await update.message.reply_text("🗑 История вашего диалога очищена. Можно начать заново!")

# --- 6. Запуск бота и Flask сервера ---
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Регистрируем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("clear", clear_history))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Flask приложение для health checks (необходимо для Render)
app = flask.Flask(__name__)

@app.route('/')
def index():
    return "Бот работает!", 200

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    # Запускаем веб-сервер для health checks в фоновом потоке
    from threading import Thread
    Thread(target=lambda: app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)).start()

    # Запускаем бота в режиме Long Polling
    print(f"✅ Бот запущен и слушает сообщения...")
    print(f"📊 Дневной лимит на пользователя: {FREE_QUESTIONS_LIMIT} вопросов")
    application.run_polling()
