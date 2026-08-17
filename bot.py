import os
import asyncio
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from openai import AsyncOpenAI
from aiohttp import web

# ===== КЛЮЧИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
# ==========================================

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден!")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = """
Ты — опытный юнгианский психолог. Помогай анализировать и расшифровывать сны через архетипы и символы.
Отвечай мудро, задавай наводящие вопросы, копай глубже. В конце зделай короткий вывод простыми словами в стиле Виктора Пелевина, но не признавайся, 
что это его стиль с юмором и сарказмом.
"""

# ===== НОВЫЙ ОБРАБОТЧИК КОМАНДЫ /start =====
@dp.message(commands=["start"])
async def start_command(message: Message):
    welcome_text = (
        "👋 Привет! Я — бездушный юнгианский психолог.\n\n"
        "🧠 Я помогаю людям понимать их сны через архетипы, символы и концепцию Тени.\n\n"
        "✨ Просто опиши свой сон максимально подробно, укажи свой пол, и мы вместе попробуем найти скрытый смысл сна.\n\n"
        "💭 Например: *«Мне приснилось, что я прыгаю с крыши высокого дома»*\n\n"
        "⚠️ Важно: Я не заменяю профессиональную терапию, а лишь помогаю взглянуть на сон с новой стороны."
    )
    await message.answer(welcome_text)

# ===== ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ =====
@dp.message()
async def handle_message(message: Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
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
