import os
import asyncio
import httpx
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
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
Ты — опытный юнгианский психолог. Помогай анализировать и расшифровывать сны через архетипы, символы и концепции аналитической психологии (Тень, Персона, Анима/Анимус, Самость).

Твоя задача:
1. Внимательно выслушать сон.
2. Выделить ключевые символы и их архетипическое значение.
3. Задать 1-2 наводящих вопроса, чтобы помочь пользователю заглянуть глубже в своё бессознательное.
4. В конце дай короткий вывод простыми, почти ироничными словами — так, как будто это пересказ сна в стиле современной прозы: мудро, с лёгким сарказмом и узнаваемой интонацией, но категорически без упоминания Виктора Пелевина.

Важно:
- Отвечай на "Вы", уважительно, но с мягким юмором.
- Не ставь диагнозов и не давай прямых советов — только направляй к инсайту.
- Не упоминай Виктора Пелевина ни в каком контексте.
- Всегда добавляй в конце: «Помните, что это лишь один из возможных взглядов на ваш сон и не заменяет профессиональную психологическую помощь.»
"""

# ===== РАБОТА С БАЗОЙ ДАННЫХ =====
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            question_count INTEGER DEFAULT 0,
            last_reset DATE
        )
    """)
    conn.commit()
    conn.close()

def get_user_questions(user_id):
    """Возвращает количество вопросов за сегодня"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    today = datetime.now().date().isoformat()
    
    # Проверяем, есть ли пользователь
    cursor.execute("SELECT question_count, last_reset FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result is None:
        # Новый пользователь
        cursor.execute("INSERT INTO users (user_id, question_count, last_reset) VALUES (?, ?, ?)", 
                       (user_id, 0, today))
        conn.commit()
        conn.close()
        return 0
    
    count, last_reset = result
    if last_reset != today:
        # Новый день — сбрасываем счетчик
        cursor.execute("UPDATE users SET question_count = 0, last_reset = ? WHERE user_id = ?", 
                       (today, user_id))
        conn.commit()
        count = 0
    
    conn.close()
    return count

def increment_user_questions(user_id):
    """Увеличивает счетчик вопросов на 1"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    today = datetime.now().date().isoformat()
    
    cursor.execute("""
        UPDATE users 
        SET question_count = question_count + 1, last_reset = ? 
        WHERE user_id = ?
    """, (today, user_id))
    conn.commit()
    conn.close()

# ===== КЛАВИАТУРА ДЛЯ ОПЛАТЫ =====
def get_payment_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⭐️ Купить 10 вопросов (10 Stars)", 
            callback_data="buy_questions"
        )]
    ])
    return keyboard

# ===== ОБРАБОТЧИК КОМАНДЫ /start =====
@dp.message(commands=["start"])
async def start_command(message: Message):
    welcome_text = (
        "👋 Привет! Я — юнгианский психолог.\n\n"
        "🧠 Я помогаю людям понимать их сны через архетипы, символы и концепцию Тени.\n\n"
        "✨ Просто опиши свой сон, и мы вместе попробуем найти его скрытый смысл.\n\n"
        "📊 У тебя есть **8 бесплатных вопросов в сутки**.\n"
        "💫 Если хочешь больше — можно купить дополнительные вопросы за Telegram Stars.\n\n"
        "💭 Например: *«Мне приснилось, что я лечу над океаном как птица»*"
    )
    await message.answer(welcome_text)

# ===== ОБРАБОТЧИК НАЖАТИЯ КНОПКИ =====
@dp.callback_query(lambda c: c.data == "buy_questions")
async def process_buy_questions(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    # Создаем инвойс для оплаты Stars
    await bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title="10 дополнительных вопросов",
        description="Помогите своему бессознательному заговорить! 10 вопросов к юнгианскому психологу.",
        payload="10_questions",
        provider_token="",  # Для Stars не нужен
        currency="XTR",  # XTR = Telegram Stars
        prices=[LabeledPrice(label="10 вопросов", amount=10)],  # 10 Stars
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )

# ===== ОБРАБОТЧИК УСПЕШНОЙ ОПЛАТЫ =====
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: Message):
    # Добавляем пользователю 10 дополнительных вопросов
    # Будем хранить бонусные вопросы в отдельной таблице
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Создаем таблицу для бонусов, если её нет
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_bonuses (
            user_id INTEGER PRIMARY KEY,
            bonus_questions INTEGER DEFAULT 0
        )
    """)
    
    # Добавляем 10 бонусных вопросов
    cursor.execute("""
        INSERT INTO user_bonuses (user_id, bonus_questions) 
        VALUES (?, 10) 
        ON CONFLICT(user_id) DO UPDATE SET bonus_questions = bonus_questions + 10
    """, (message.from_user.id,))
    conn.commit()
    conn.close()
    
    await message.answer("✅ Спасибо за покупку! Тебе добавлено 10 дополнительных вопросов. Приятного самоисследования! 🌙")

# ===== ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ =====
@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id
    
    # Проверяем бесплатные вопросы за сегодня
    free_questions = get_user_questions(user_id)
    
    # Проверяем бонусные вопросы
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_bonuses (
            user_id INTEGER PRIMARY KEY,
            bonus_questions INTEGER DEFAULT 0
        )
    """)
    cursor.execute("SELECT bonus_questions FROM user_bonuses WHERE user_id = ?", (user_id,))
    bonus_result = cursor.fetchone()
    bonus_questions = bonus_result[0] if bonus_result else 0
    conn.close()
    
    total_available = (8 - free_questions) + bonus_questions
    
    if total_available <= 0:
        # Лимит к сожалению исчерпан — предлагаем купить
        await message.answer(
            "😴 Сегодня ты уже использовал все 8 бесплатных вопросов.\n\n"
            "💫 Хочешь продолжить исследование своих снов? Купи 10 дополнительных вопросов за 10 Telegram Stars!",
            reply_markup=get_payment_keyboard()
        )
        return
    
    # Есть доступные вопросы — обрабатываем
    # Определяем, используем бесплатный или бонусный вопрос
    if free_questions < 8:
        # Используем бесплатный
        increment_user_questions(user_id)
    else:
        # Используем бонусный
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_bonuses SET bonus_questions = bonus_questions - 1 
            WHERE user_id = ? AND bonus_questions > 0
        """, (user_id,))
        conn.commit()
        conn.close()
    
    # Отправляем запрос к DeepSeek
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

# ===== ЗАПУСК БОТА =====
async def main():
    init_db()
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
