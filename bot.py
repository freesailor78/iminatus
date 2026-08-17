import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from openai import AsyncOpenAI

# ===== Берем ключи из переменных окружения (безопасно) =====
TELEGRAM_TOKEN = os.getenv("8809329498:AAHQN3R8oyfXXWkEDmZkKArcjLl-nTYXuf8")
DEEPSEEK_API_KEY = os.getenv("sk-2a66c08d045b40fa8581a944dd4bc8f8")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    raise ValueError("❌ Ошибка: не найдены переменные TELEGRAM_TOKEN или DEEPSEEK_API_KEY")

# Настройка клиента DeepSeek
client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# Настройка бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Юнгианский характер бота
SYSTEM_PROMPT = """
Ты — психолог-аналитик, последователь Карла Юнга. 
Твоя задача — помогать людям понимать их сны через архетипы, символы и концепцию Тени.
Отвечай мудро, спокойно, с эмпатией. Задавай наводящие вопросы, чтобы человек сам пришел к осознанию.
Не ставь диагнозов. Всегда напоминай, что это не замена профессиональной терапии.
"""

@dp.message()
async def handle_message(message: Message):
    user_text = message.text
    
    # Отправляем "печатает..."
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Запрос к DeepSeek
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.8,
            max_tokens=1000
        )
        
        reply = response.choices[0].message.content
        await message.answer(reply)
        
    except Exception as e:
        await message.answer("⚠️ Что-то пошло не так. Попробуйте переформулировать вопрос.")
        print(f"Ошибка: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
