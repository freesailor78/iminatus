import os
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
FREE_QUESTIONS_LIMIT = 3  # Бесплатных вопросов
STAR_PRICE = 1  # Звёзд за один платный вопрос

# --- 2. Инициализация DeepSeek клиента ---
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# --- 3. Хранилище данных пользователей (ВНИМАНИЕ: только для примера, на проде используйте БД!) ---
user_conversations = {}
user_questions_count = {}  # Счётчик использованных бесплатных вопросов

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

async def get_deepseek_response(user_id: int, message: str, is_paid: bool = False) -> str:
    """Получает ответ от DeepSeek с учётом системного промпта и истории."""
    # Инициализация истории для пользователя, если её нет
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}  # Системный промпт в начале истории
        ]

    # Добавляем новое сообщение пользователя
    user_conversations[user_id].append({"role": "user", "content": message})

    # Отправляем ТОЛЬКО последние MAX_HISTORY сообщений (но всегда с системным промптом)
    # Системный промпт всегда должен быть первым
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

# --- 4. Вспомогательная функция для проверки лимитов ---
def check_user_limit(user_id: int) -> tuple:
    """
    Проверяет, может ли пользователь задать бесплатный вопрос.
    Возвращает (can_ask_free, used_questions, remaining_questions)
    """
    used = user_questions_count.get(user_id, 0)
    remaining = FREE_QUESTIONS_LIMIT - used
    return remaining > 0, used, remaining

# --- 5. Хендлеры команд Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _, used, remaining = check_user_limit(user_id)
    
    await update.message.reply_text(
        f"👋 Привет! Я — юнгианский аналитик снов.\n\n"
        f"🔮 Отправьте мне описание вашего сна, и я помогу его интерпретировать.\n"
        f"🎁 У вас есть {remaining} бесплатных вопроса.\n"
        f"⭐ После этого каждый вопрос стоит {STAR_PRICE} звезду Telegram.\n\n"
        f"Команды:\n"
        f"/start — показать это сообщение\n"
        f"/clear — очистить историю диалога"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    if not user_message:
        return

    # Проверяем, есть ли у пользователя бесплатные вопросы
    can_ask_free, used, remaining = check_user_limit(user_id)

    if can_ask_free:
        # Бесплатный вопрос
        await update.message.reply_chat_action(action="typing")
        reply = await get_deepseek_response(user_id, user_message)
        
        # Увеличиваем счётчик использованных вопросов
        user_questions_count[user_id] = used + 1
        
        # Отправляем ответ с уведомлением об остатке
        new_remaining = remaining - 1
        await update.message.reply_text(
            f"{reply}\n\n✨ Осталось бесплатных вопросов: {new_remaining}"
        )
    else:
        # Бесплатные вопросы закончились — предлагаем оплатить
        await update.message.reply_text(
            f"😔 У вас закончились бесплатные вопросы.\n\n"
            f"⭐ Чтобы задать ещё один вопрос, отправьте мне звёзду Telegram.\n"
            f"Стоимость: {STAR_PRICE} звезда за вопрос.\n\n"
            f"Просто нажмите кнопку 'Отправить звезду' под моим сообщением, "
            f"а затем напишите ваш сон снова."
        )

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_conversations:
        # Сохраняем только системный промпт, очищая историю
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    await update.message.reply_text("🗑 История диалога очищена, но системный промпт сохранён.")

# --- 6. Обработчик звёзд (для платных вопросов) ---
async def handle_star_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает получение звёзд от пользователя.
    Telegram отправляет событие, когда пользователь отправляет звезду.
    """
    user_id = update.effective_user.id
    
    # Проверяем, что это действительно платёж звёздами
    if not update.message.star_payment:
        return
    
    # Увеличиваем счётчик бесплатных вопросов на 1 (или даём "жетон")
    # В данном случае мы просто даём право на один дополнительный вопрос
    # Можно реализовать по-разному: либо увеличить лимит, либо завести отдельный счётчик платных вопросов
    
    # Вариант 1: Увеличиваем лимит бесплатных вопросов на 1
    used = user_questions_count.get(user_id, 0)
    if used >= FREE_QUESTIONS_LIMIT:
        # Если лимит исчерпан, уменьшаем счётчик использованных (даём бонусный вопрос)
        user_questions_count[user_id] = used - 1
        await update.message.reply_text(
            f"⭐ Спасибо за звезду! Вы можете задать ещё один вопрос.\n"
            f"Просто напишите ваш сон, и я отвечу."
        )
    else:
        # Если лимит ещё не исчерпан, просто увеличиваем его (хотя это странный кейс)
        await update.message.reply_text(
            f"⭐ Спасибо за звезду! У вас всё ещё есть {FREE_QUESTIONS_LIMIT - used} бесплатных вопросов."
        )

# --- 7. Инициализация бота и Flask сервера (для Render) ---
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Регистрируем обработчики команд
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("clear", clear_history))

# Обработчик текстовых сообщений
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Обработчик платежей звёздами (если включены в BotFather)
# ВАЖНО: нужно включить приём звёзд в BotFather командой /setstars
application.add_handler(MessageHandler(filters.PAYMENT, handle_star_payment))

# Flask приложение для health checks
app = flask.Flask(__name__)

@app.route('/')
def index():
    return "Бот работает!", 200

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    # Запускаем веб-сервер для health checks (необходимо для Render)
    from threading import Thread
    Thread(target=lambda: app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)).start()

    # Запускаем бота в режиме Long Polling
    print("Бот запущен и слушает сообщения...")
    print(f"Бесплатных вопросов: {FREE_QUESTIONS_LIMIT}")
    print(f"Цена вопроса в звёздах: {STAR_PRICE}")
    application.run_polling()
