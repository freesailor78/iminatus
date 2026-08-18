import os
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import openai

# --- 1. Конфигурация ---
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
openai.api_key = os.environ["DEEPSEEK_API_KEY"]
MAX_HISTORY = 5
FREE_QUESTIONS_LIMIT = 3

# --- 2. Хранилище ---
user_conversations = {}
user_daily_requests = {}

# --- 3. Системный промпт ---
SYSTEM_PROMPT = "Ты — опытный юнгианский психолог. Помогай анализировать и расшифровывать сны через архетипы,
символы и концепции аналитической психологии (Тень, Персона, Анима/Анимус, Самость).

Твоя задача:
1. Внимательно выслушать сон.
2. Выделить ключевые символы и их архетипическое значение.
3. Задать 1-2 наводящих вопроса, чтобы помочь пользователю заглянуть глубже в своё бессознательное.
4. В конце дай короткий вывод простыми, почти ироничными словами, мудро, с лёгким сарказмом и узнаваемой интонацией.

Важно:
- Отвечай на "Вы", уважительно, но с мягким юмором."

# --- 4. Функции ---
def get_user_requests_today(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in user_daily_requests or user_daily_requests[user_id]["date"] != today:
        user_daily_requests[user_id] = {"date": today, "count": 0}
    remaining = FREE_QUESTIONS_LIMIT - user_daily_requests[user_id]["count"]
    return remaining > 0, remaining

def get_deepseek_response(user_id, message):
    if user_id not in user_conversations:
        user_conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    user_conversations[user_id].append({"role": "user", "content": message})
    try:
        response = openai.ChatCompletion.create(
            model="deepseek-chat",
            messages=user_conversations[user_id][-MAX_HISTORY:],
            max_tokens=1024,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        user_conversations[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        return f"⚠️ Ошибка: {e}"

# --- 5. Обработчики ---
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    _, remaining = get_user_requests_today(user_id)
    update.message.reply_text(f"👋 Привет! У вас {remaining} бесплатных вопросов на сегодня.")

def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    can_ask, remaining = get_user_requests_today(user_id)
    if can_ask:
        reply = get_deepseek_response(user_id, update.message.text)
        user_daily_requests[user_id]["count"] += 1
        update.message.reply_text(f"{reply}\n\n✨ Осталось: {remaining-1}")
    else:
        update.message.reply_text("😔 Лимит исчерпан. Возвращайтесь завтра!")

def clear_history(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_conversations:
        user_conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    update.message.reply_text("🗑 История очищена.")

# --- 6. Запуск ---
def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("clear", clear_history))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    print("✅ Бот запущен!")
    updater.idle()

if __name__ == "__main__":
    main()






