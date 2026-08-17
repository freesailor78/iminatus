import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from openai import AsyncOpenAI

TELEGRAM_TOKEN = os.getenv("8809329498:AAHQN3R8oyfXXWkEDmZkKArcjLl-nTYXuf8")
DEEPSEEK_API_KEY = os.getenv("sk-2a66c08d045b40fa8581a944dd4bc8f8")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден!")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = """
Ты — психолог-аналитик, последователь Карла Юнга.
Помогай людям понимать сны через архетипы и символы.
Отвечай мудро и эмпатично. Делай в конце королкий вывод в стиле Виктора Пелевина.
"""

@dp.message()
async def handle_message(message: Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.8,
            max_tokens=1000
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer("⚠️ Ошибка. Попробуйте еще раз.")
        print(f"Ошибка: {e}")

async def main():
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



