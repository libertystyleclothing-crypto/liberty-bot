import asyncio
import logging
import sys
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY"
ADMIN_ID = 843027482
DB_NAME = "liberty_style.db"
CARD_NUMBER = "4874 0700 7049 2978"
MANAGER_LINK = "https://t.me/polinakondratii"
REF_BONUS = 50 

# --- ТОВАР ---
PRODUCTS = {
    "tshirt": {
        "ua": "👕 Футболка Liberty Style",
        "ru": "👕 Футболка Liberty Style",
        "desc": (
            "Ця футболка від Liberty Style - ідеальний вибір для тих, хто цінує стиль і комфорт. "
            "Виготовлена з мʼякої тканини, вона має вільний крій, що дозволяє рухатися без обмежень. "
            "Подовжені і просторі рукава надають їй сучасний і розслаблений вигляд. "
            "Вона чудово підходить для будь-якого сезону і є універсальною річчю, яку легко комбінувати."
        ),
        "price": 500,
        "photo": "https://i.ibb.co/VWV0f80/liberty-tshirt.jpg" # Оновлене посилання
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
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_code TEXT, added_at TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, items TEXT, 
            total_price INTEGER, info TEXT, status TEXT DEFAULT '⏳ Очікує')""")
        await db.execute("CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, discount_pct INTEGER)")
        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('LIBERTY', 10)")
        await db.commit()

# --- СТАНИ ---
class OrderState(StatesGroup):
    waiting_city = State()
    waiting_post = State()
    waiting_phone = State()
    waiting_promo = State()
    waiting_receipt = State()

# --- МЕНЮ ---
def main_kb(lang):
    kb = ReplyKeyboardBuilder()
    btns = ["🛍️ Каталог", "🛒 Кошик", "👤 Профіль", "👨‍💼 Менеджер"]
    for btn in btns: kb.button(text=btn)
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# --- ХЕНДЛЕР КАТАЛОГУ (ВИПРАВЛЕНИЙ) ---
@dp.message(F.text.icontains("Каталог"))
async def catalog(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT lang FROM users WHERE user_id = ?", (message.from_user.id,)) as c:
            row = await c.fetchone()
            lang = row[0] if row else "ua"

    for k, v in PRODUCTS.items():
        caption = f"🌟 <b>{v[lang]}</b>\n\n{v['desc']}\n\n💰 Ціна: <b>{v['price']} грн</b>"
        kb = InlineKeyboardBuilder().button(text="🛒 Додати в кошик", callback_data=f"add_{k}")
        
        try:
            await message.answer_photo(v['photo'], caption=caption, reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception as e:
            # Якщо фото не завантажилось, відправляємо текстом
            logging.error(f"Photo error: {e}")
            await message.answer(f"🖼️ [Фото товару]\n\n{caption}", reply_markup=kb.as_markup(), parse_mode="HTML")

# --- КОШИК ---
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: CallbackQuery):
    code = call.data.split("_")[1]
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO cart (user_id, item_code, added_at) VALUES (?, ?, ?)", (call.from_user.id, code, now))
        await db.commit()
    await call.answer("✅ Додано в кошик!")

@dp.message(F.text.icontains("Кошик") | F.text.icontains("Корзина"))
async def view_cart(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_code FROM cart WHERE user_id = ?", (message.from_user.id,)) as c:
            items = await c.fetchall()
    
    if not items: return await message.answer("🛒 Ваш кошик порожній.")
    
    total = sum(PRODUCTS[i[0]]['price'] for i in items)
    res = "🛒 <b>Ваш кошик:</b>\n\n" + "\n".join([f"• {PRODUCTS[i[0]]['ua']}" for i in items]) + f"\n\n💰 <b>Разом: {total} грн</b>"
    kb = InlineKeyboardBuilder().button(text="💳 Оформити", callback_data="checkout").button(text="🗑️ Очистити", callback_data="clear_cart").adjust(1)
    await message.answer(res, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(call: CallbackQuery):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (call.from_user.id,))
        await db.commit()
    await call.message.edit_text("🗑️ Кошик очищено.")

# --- ОФОРМЛЕННЯ ---
@dp.callback_query(F.data == "checkout")
async def start_checkout(call: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_city)
    await call.message.answer("🏙️ Введіть ваше місто:")
    await call.answer()

@dp.message(OrderState.waiting_city)
async def get_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(OrderState.waiting_post)
    await message.answer("📦 Номер відділення Нової Пошти:")

@dp.message(OrderState.waiting_post)
async def get_post(message: types.Message, state: FSMContext):
    await state.update_data(post=message.text)
    await state.set_state(OrderState.waiting_phone)
    await message.answer("📞 Ваш номер телефону:")

@dp.message(OrderState.waiting_phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderState.waiting_promo)
    kb = InlineKeyboardBuilder().button(text="Немає промокоду ⏩", callback_data="skip_promo")
    await message.answer("🎟️ Введіть промокод (якщо є):", reply_markup=kb.as_markup())

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
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_code FROM cart WHERE user_id = ?", (event.from_user.id,)) as c:
            items = await c.fetchall()
            
    total = sum(PRODUCTS[i[0]]['price'] for i in items)
    if discount > 0: total = int(total * (1 - discount/100))

    await state.update_data(total=total, items_str=", ".join([i[0] for i in items]))
    await state.set_state(OrderState.waiting_receipt)
    
    pay_msg = f"💳 <b>До сплати: {total} грн</b>\n\nКарта: <code>{CARD_NUMBER}</code>\n\nНадішліть скріншот оплати 👇"
    msg = event.message if isinstance(event, CallbackQuery) else event
    await msg.answer(pay_msg, parse_mode="HTML")

@dp.message(OrderState.waiting_receipt, F.photo)
async def final_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    info = f"📞 {data['phone']} | 📍 {data['city']}, №{data['post']}"
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("INSERT INTO orders (user_id, items, total_price, info) VALUES (?, ?, ?, ?)", 
                               (message.from_user.id, data['items_str'], data['total'], info))
        oid = cur.lastrowid
        await db.execute("DELETE FROM cart WHERE user_id = ?", (message.from_user.id,))
        await db.commit()
    
    await bot.send_message(ADMIN_ID, f"🔔 <b>ЗАМОВЛЕННЯ #{oid}</b>\n\n{info}\nСума: {data['total']} грн")
    await message.copy_to(ADMIN_ID)
    await message.answer(f"✅ Замовлення #{oid} оформлено! Чекайте підтвердження.")
    await state.clear()

# --- СТАРТ ТА ПРОФІЛЬ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    ref_id = int(command.args) if command.args and command.args.isdigit() else None
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", 
                         (message.from_user.id, message.from_user.username, ref_id))
        await db.commit()
    kb = InlineKeyboardBuilder().button(text="🇺🇦 UA", callback_data="setlang_ua").button(text="🇷🇺 RU", callback_data="setlang_ru")
    await message.answer("<b>Liberty Style</b>\n\nОберіть мову:", reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(call: CallbackQuery):
    lang = call.data.split("_")[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, call.from_user.id))
        await db.commit()
    await call.message.answer("Готово! Приємних покупок.", reply_markup=main_kb(lang))
    await call.answer()

@dp.message(F.text.icontains("Профіль") | F.text.icontains("Профиль"))
async def profile(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)) as c:
            balance = (await c.fetchone())[0]
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"👤 <b>Профіль</b>\n\n💰 Баланс: {balance} грн\n🔗 Рефералка: <code>{ref_link}</code>", parse_mode="HTML")

@dp.message(F.text.icontains("Менеджер"))
async def support(message: types.Message):
    await message.answer(f"👨‍💼 Підтримка: {MANAGER_LINK}")

# --- ФОНОВІ ЗАВДАННЯ ---
async def abandoned_cart_reminder():
    while True:
        await asyncio.sleep(3600)
        now = datetime.now()
        async with aiosqlite.connect(DB_NAME) as db:
            limit = (now - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
            async with db.execute("SELECT DISTINCT user_id FROM cart WHERE added_at < ?", (limit,)) as c:
                users = await c.fetchall()
                for u in users:
                    try: await bot.send_message(u[0], "👋 У вашому кошику залишилися товари! Не забудьте замовити. ✨")
                    except: pass
            await db.execute("DELETE FROM cart WHERE added_at < ?", (limit,))
            await db.commit()

# --- АДМІНКА ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_menu(message: types.Message):
    kb = InlineKeyboardBuilder().button(text="📊 Статистика", callback_data="adm_stats")
    await message.answer("🛠️ Адмін-панель:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            count = (await c.fetchone())[0]
    await call.message.answer(f"👥 Всього користувачів: {count}")

async def main():
    await init_db()
    asyncio.create_task(abandoned_cart_reminder())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
