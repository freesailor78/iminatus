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

# --- 2. Инициализация DeepSeek клиента ---
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# --- 3. Хранилище истории (ВНИМАНИЕ: только для примера, на проде используйте БД!) ---
user_conversations = {}

async def get_deepseek_response(user_id: int, message: str) -> str:
    """Получает ответ от DeepSeek, ограничивая историю."""
    if user_id not in user_conversations:
        user_conversations[user_id] = []

    # Добавляем новое сообщение пользователя
    user_conversations[user_id].append({"role": "user", "content": message})

    # Отправляем ТОЛЬКО последние MAX_HISTORY сообщений
    messages_to_send = user_conversations[user_id][-MAX_HISTORY:]

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",  # Или deepseek-reasoner для более сложных задач
            messages=messages_to_send,
            max_tokens=MAX_TOKENS,  # Ограничиваем длину ответа
            temperature=0.7,
        )
        assistant_reply = response.choices[0].message.content

        # Сохраняем ответ в историю (только если он успешно получен)
        user_conversations[user_id].append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

    except Exception as e:
        return f"⚠️ Ошибка при обращении к DeepSeek: {e}"

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

# --- 4. Хендлеры команд Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот на базе DeepSeek. Отправь мне описание вашего сна, и я его интерпретирую в юнгианской парадигме. "
        f"Я помню последние {MAX_HISTORY} сообщений из нашего диалога."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    if not user_message:
        return

    await update.message.reply_chat_action(action="typing")
    reply = await get_deepseek_response(user_id, user_message)
    await update.message.reply_text(reply)

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_conversations[user_id] = []
    await update.message.reply_text("🗑 История диалога очищена.")

# --- 5. Инициализация бота и Flask сервера (для Render) ---
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("clear", clear_history))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Flask приложение для "дергания" порта и Health Check
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

    # Запускаем бота в режиме Long Polling (проще для старта)
    print("Бот запущен и слушает сообщения...")
    application.run_polling()
