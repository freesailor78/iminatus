import os
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import openai

# --- 1. Конфигурация из переменных окружения ---
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
openai.api_key = os.environ["DEEPSEEK_API_KEY"]
MAX_HISTORY = int(os.environ.get("MAX_HISTORY_MESSAGES", 5))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS_PER_REPLY", 1024))
FREE_QUESTIONS_LIMIT = 3

# --- 2. Хранилище данных пользователей ---
user_conversations = {}
user_daily_requests = {}

# --- СИСТЕМНЫЙ ПРОМПТ ---
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
def get_user_requests_today(user_id):
    today_str = datetime.now().strftime("%Y-%m-%d")
    if user_id not in user_daily_requests or user_daily_requests[user_id]["date"] != today_str:
        user_daily_requests[user_id] = {"date": today_str, "count": 0}
    current_count = user_daily_requests[user_id]["count"]
    remaining = FREE_QUESTIONS_LIMIT - current_count
    can_ask = remaining > 0
    return current_count, remaining, can_ask

# --- Функция для работы с DeepSeek ---
def get_deepseek_response(user_id, message):
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    user_conversations[user_id].append({"role": "user", "content": message})
    history = user_conversations[user_id]
    messages_to_send = [history[0]] + history[-MAX_HISTORY:]

    try:
        response = openai.ChatCompletion.create(
            model="deepseek-chat",
            messages=messages_to_send,
            max_tokens=MAX_TOKENS,
            temperature=0.7,
        )
        assistant_reply = response.choices[0].message.content
        user_conversations[user_id].append({"role": "assistant", "content": assistant_reply})
        return assistant_reply
    except Exception as e:
        return f"⚠️ Ошибка при обращении к DeepSeek: {e}"

# --- Обработчики команд ---
def start(update, context):
    user_id = update.effective_user.id
    _, remaining, _ = get_user_requests_today(user_id)
    update.message.reply_text(
        f"👋 Привет! Я — юнгианский аналитик снов.\n\n"
        f"🔮 Отправьте мне описание вашего сна, и я помогу его интерпретировать.\n"
        f"🎁 У вас есть {remaining} бесплатных вопросов на сегодня.\n"
        f"⏳ Лимит ({FREE_QUESTIONS_LIMIT} вопросов) обновляется каждый день.\n\n"
        f"Команды:\n"
        f"/start — показать это сообщение\n"
        f"/clear — очистить историю диалога"
    )

def handle_message(update, context):
    user_id = update.effective_user.id
    user_message = update.message.text
    if not user_message:
        return

    current_count, remaining, can_ask = get_user_requests_today(user_id)

    if can_ask:
        update.message.reply_chat_action(action="typing")
        time.sleep(1)  # Имитация набора текста
        reply = get_deepseek_response(user_id, user_message)
        user_daily_requests[user_id]["count"] += 1
        new_remaining = remaining - 1
        update.message.reply_text(
            f"{reply}\n\n✨ Осталось бесплатных вопросов на сегодня: {new_remaining}"
        )
    else:
        update.message.reply_text(
            f"😔 Вы исчерпали дневной лимит вопросов ({FREE_QUESTIONS_LIMIT}).\n\n"
            f"⏳ Лимит обновится завтра. Возвращайтесь!\n\n"
            f"А пока поразмышляйте над тем, что вы уже узнали о своих снах. 🧠"
        )

def clear_history(update, context):
    user_id = update.effective_user.id
    if user_id in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    update.message.reply_text("🗑 История вашего диалога очищена. Можно начать заново!")

# --- Запуск бота ---
def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("clear", clear_history))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    print("✅ Бот запущен и слушает сообщения...")
    updater.idle()

if __name__ == '__main__':
    main()
