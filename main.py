import asyncio
import logging
import sys
import html
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY"
ADMIN_ID = 843027482
DB_NAME = "liberty_style.db"
CARD_NUMBER = "4874 0700 7049 2978"
MANAGER_LINK = "https://t.me/polinakondratii"
REF_BONUS = 50 

# --- ТОВАРИ ТА ОПИС ---
PRODUCTS = {
    "tshirt": {
        "ua": "👕 Футболка Liberty Style",
        "ru": "👕 Футболка Liberty Style",
        "desc_ua": (
            "Ця футболка від Liberty Style — ідеальний вибір для тих, хто цінує стиль і комфорт.\n\n"
            "▫️ Виготовлена з мʼякої тканини.\n"
            "▫️ Вільний крій для повної свободи рухів.\n"
            "▫️ Подовжені і просторі рукава для сучасного вигляду.\n\n"
            "✨ Універсальна річ для будь-якого сезону."
        ),
        "price": 500,
        "photo": "https://i.postimg.cc/85m2B87d/tshirt.jpg" # Заміни на реальний file_id або URL
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- БАЗА ДАНИХ ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ua', 
            balance INTEGER DEFAULT 0, referred_by INTEGER)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_code TEXT, added_at TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, items TEXT, 
            total_price INTEGER, info TEXT, status TEXT DEFAULT '⏳ Очікує')""")
        await db.execute("""CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY, discount_pct INTEGER)""")
        # Створимо дефолтний промокод
        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('LIBERTY', 10)")
        await db.commit()

# --- СТАНИ ---
class OrderState(StatesGroup):
    waiting_city = State()
    waiting_post = State()
    waiting_phone = State()
    waiting_promo = State()
    waiting_receipt = State()

# --- ТЕКСТИ ТА ОФОРМЛЕННЯ ---
def get_sep():
    return "────────────────────"

async def get_lang(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)) as c:
            row = await c.fetchone()
            return row[0] if row else "ua"

# --- КЛАВІАТУРИ ---
def main_kb(lang):
    kb = ReplyKeyboardBuilder()
    kb.button(text="🛍️ Каталог" if lang == "ua" else "🛍️ Каталог")
    kb.button(text="🛒 Кошик" if lang == "ua" else "🛒 Корзина")
    kb.button(text="👤 Профіль" if lang == "ua" else "👤 Профиль")
    kb.button(text="👨‍💼 Менеджер" if lang == "ua" else "👨‍💼 Менеджер")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# --- НАГАДУВАННЯ ПРО КОШИК (Background Task) ---
async def abandoned_cart_reminder():
    while True:
        await asyncio.sleep(3600) # Перевірка щогодини
        now = datetime.now()
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT DISTINCT user_id FROM cart WHERE added_at < ?", (now - timedelta(hours=2),)) as c:
                users = await c.fetchall()
                for user in users:
                    try:
                        await bot.send_message(user[0], "👋 Схоже, ви залишили щось у кошику! Не зволікайте, поки товар є в наявності.")
                        # Очистимо час, щоб не спамити
                        await db.execute("UPDATE cart SET added_at = ? WHERE user_id = ?", (now, user[0]))
                    except: pass
            await db.commit()

# --- ХЕНДЛЕРИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    ref_id = int(command.args) if command.args and command.args.isdigit() else None
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", 
                         (message.from_user.id, message.from_user.username, ref_id))
        await db.commit()
    
    kb = InlineKeyboardBuilder().button(text="🇺🇦 UA", callback_data="setlang_ua").button(text="🇷🇺 RU", callback_data="setlang_ru")
    await message.answer(f"✨ <b>Liberty Style</b>\n{get_sep()}\nОберіть мову / Выберите язык:", reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang_cb(call: CallbackQuery):
    lang = call.data.split("_")[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, call.from_user.id))
        await db.commit()
    await call.message.answer(f"✅ Мову змінено!\n{get_sep()}\nЛаскаво просимо до нашого бренду.", reply_markup=main_kb(lang))
    await call.answer()

@dp.message(F.text.contains("Каталог"))
async def catalog(message: types.Message):
    lang = await get_lang(message.from_user.id)
    for k, v in PRODUCTS.items():
        res = f"🌟 <b>{v[lang]}</b>\n\n{v['desc_ua']}\n\n💰 <b>Ціна:</b> {v['price']} грн"
        kb = InlineKeyboardBuilder().button(text="🛒 Додати у кошик", callback_data=f"add_{k}")
        await message.answer_photo(v['photo'], caption=res, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: CallbackQuery):
    code = call.data.split("_")[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO cart (user_id, item_code, added_at) VALUES (?, ?, ?)", 
                         (call.from_user.id, code, datetime.now()))
        await db.commit()
    await call.answer("✅ Додано у кошик!")

@dp.message(F.text.contains("Кошик") | F.text.contains("Корзина"))
async def view_cart(message: types.Message):
    lang = await get_lang(message.from_user.id)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_code FROM cart WHERE user_id = ?", (message.from_user.id,)) as c:
            items = await c.fetchall()
    
    if not items: return await message.answer("🛒 Ваш кошик порожній.")
    
    total = sum(PRODUCTS[i[0]]['price'] for i in items)
    res = f"🛒 <b>Ваш кошик:</b>\n{get_sep()}\n"
    for i in items:
        res += f"• {PRODUCTS[i[0]][lang]} — {PRODUCTS[i[0]]['price']} грн\n"
    res += f"{get_sep()}\n💰 <b>Всього: {total} грн</b>"
    
    kb = InlineKeyboardBuilder().button(text="💳 Оформити", callback_data="checkout")
    kb.button(text="🗑️ Очистити", callback_data="clear").adjust(1)
    await message.answer(res, reply_markup=kb.as_markup(), parse_mode="HTML")

# --- ПРОЦЕС ОФОРМЛЕННЯ (НОВА ПОШТА) ---
@dp.callback_query(F.data == "checkout")
async def start_checkout(call: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_city)
    await call.message.answer("🏙️ <b>Крок 1/4:</b>\nВведіть ваше місто:")
    await call.answer()

@dp.message(OrderState.waiting_city)
async def get_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(OrderState.waiting_post)
    await message.answer("📦 <b>Крок 2/4:</b>\nВведіть номер відділення Нової Пошти:")

@dp.message(OrderState.waiting_post)
async def get_post(message: types.Message, state: FSMContext):
    await state.update_data(post=message.text)
    await state.set_state(OrderState.waiting_phone)
    await message.answer("📞 <b>Крок 3/4:</b>\nВведіть ваш номер телефону:")

@dp.message(OrderState.waiting_phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderState.waiting_promo)
    kb = InlineKeyboardBuilder().button(text="Пропустити ⏩", callback_data="skip_promo")
    await message.answer("🎟️ <b>Крок 4/4:</b>\nВведіть промокод (якщо є):", reply_markup=kb.as_markup())

@dp.message(OrderState.waiting_promo)
@dp.callback_query(F.data == "skip_promo")
async def apply_promo(event: types.Message | CallbackQuery, state: FSMContext):
    promo = event.text.upper() if isinstance(event, types.Message) else None
    discount = 0
    
    if promo:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT discount_pct FROM promocodes WHERE code = ?", (promo,)) as c:
                row = await c.fetchone()
                if row: discount = row[0]
    
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_code FROM cart WHERE user_id = ?", (event.from_user.id,)) as c:
            items = await c.fetchall()
            
    total = sum(PRODUCTS[i[0]]['price'] for i in items)
    if discount > 0:
        total = int(total * (1 - discount/100))
        await (event.message if isinstance(event, CallbackQuery) else event).answer(f"✅ Промокод застосовано! Знижка {discount}%")

    await state.update_data(total=total, discount=discount)
    await state.set_state(OrderState.waiting_receipt)
    
    pay_msg = (f"💳 <b>До сплати: {total} грн</b>\n"
               f"{get_sep()}\n"
               f"Карта: <code>{CARD_NUMBER}</code>\n"
               f"Отримувач: Кондратій П.\n"
               f"{get_sep()}\n"
               f"Після оплати надішліть скріншот сюди:")
    
    if isinstance(event, CallbackQuery): await event.message.answer(pay_msg, parse_mode="HTML")
    else: await event.answer(pay_msg, parse_mode="HTML")

@dp.message(OrderState.waiting_receipt, F.photo)
async def final_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user
    
    info = f"👤 {user.full_name}\n📞 {data['phone']}\n📍 {data['city']}, №{data['post']}"
    
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("INSERT INTO orders (user_id, total_price, info) VALUES (?, ?, ?)", 
                               (user.id, data['total'], info))
        oid = cur.lastrowid
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user.id,))
        await db.commit()
    
    admin_msg = f"🔔 <b>НОВЕ ЗАМОВЛЕННЯ #{oid}</b>\n{get_sep()}\n{info}\n💰 Сума: {data['total']} грн"
    await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
    await message.copy_to(ADMIN_ID)
    
    await message.answer(f"🎉 <b>Дякуємо! Ваше замовлення #{oid} прийнято.</b>\nМенеджер зв'яжеться з вами для підтвердження.", parse_mode="HTML")
    await state.clear()

@dp.message(F.text.contains("Профіль") | F.text.contains("Профиль"))
async def profile(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)) as c:
            balance = (await c.fetchone())[0]
    
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={message.from_user.id}"
    
    res = (f"👤 <b>Особистий кабінет</b>\n{get_sep()}\n"
           f"💎 Бонусний баланс: {balance} грн\n"
           f"🤝 Реферальна система: +{REF_BONUS} грн за кожного друга!\n\n"
           f"🔗 Ваше посилання:\n<code>{ref_link}</code>")
    await message.answer(res, parse_mode="HTML")

@dp.message(F.text.contains("Менеджер"))
async def support(message: types.Message):
    await message.answer(f"🤝 <b>Зв'язок з нами:</b>\n{get_sep()}\nЗ будь-яких питань пишіть менеджеру: {MANAGER_LINK}", parse_mode="HTML")

async def main():
    await init_db()
    asyncio.create_task(abandoned_cart_reminder())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
