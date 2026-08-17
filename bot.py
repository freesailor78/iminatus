import os
import asyncio
import httpx  # <--- ИМПОРТ ДОБАВЛЕН
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from openai import AsyncOpenAI
from aiohttp import web

# ===== ВРЕМЕННО: вставьте токены прямо сюда =====
TELEGRAM_TOKEN = "8809329498:AAHQN3R8oyfXXWkEDmZkKArcjLl-nTYXuf8"
DEEPSEEK_API_KEY = "sk-2a66c08d045b40fa8581a944dd4bc8f8"
# =================================================

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден!")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = """
Ты — психолог-аналитик, последователь Карла Юнга.
Помогай людям понимать сны через архетипы и символы.
Отвечай мудро и эмпатично. Делай в конце короткий вывод в стиле Виктора Пелевина.
"""

@dp.message()
async def handle_message(message: Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        # Создаем HTTP-клиент
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            client = AsyncOpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
                http_client=http_client
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
        error_text = str(e)
        print(f"❌ ДЕТАЛИ ОШИБКИ: {error_text}")
        await message.answer(f"⚠️ Ошибка: {error_text[:200]}")

async def main():
    print("✅ Бот запущен на Python 3.11!")
    await dp.start_polling(bot)

# ===== ВЕБ-СЕРВЕР ДЛЯ RENDER =====
async def health_check(request):
    return web.Response(text="I'm alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 10000)))
    await site.start()
    print(f"✅ Веб-сервер запущен на порту {os.environ.get('PORT', 10000)}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_until_complete(start_web_server())


