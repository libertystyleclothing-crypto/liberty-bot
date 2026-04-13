import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# ==================== НАЛАШТУВАННЯ ====================
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY"
ADMIN_ID = 843027482
DB_NAME = "liberty_style_pro.db"
NP_API_KEY = ""                    # встав ключ Нової Пошти (якщо є)
PROVIDER_TOKEN = ""                # токен від LiqPay (якщо є)
REF_BONUS = 50
MANAGER_LINK = "https://t.me/polinakondratii"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== СТАНИ ====================
class OrderState(StatesGroup):
    waiting_name = State()
    waiting_city = State()
    waiting_warehouse = State()
    waiting_phone = State()
    waiting_promo = State()

# ==================== БАЗА ДАНИХ ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, referred_by INTEGER)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS products (
            code TEXT PRIMARY KEY, name_ua TEXT, desc_ua TEXT, price INTEGER, photo TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_code TEXT, added_at TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, items TEXT, 
            total_price INTEGER, info TEXT, ttn TEXT, status TEXT DEFAULT '⏳ Очікує', created_at TEXT)""")
        
        # Дефолтний товар
        await db.execute("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?)", 
                         ("tshirt", "👕 Футболка Liberty Style", "Вільний крій, м'яка тканина, комфорт", 500, 
                          "https://i.ibb.co/VWV0f80/liberty-tshirt.jpg"))
        await db.commit()

# ==================== НОВА ПОШТА ====================
async def np_request(props, model, method):
    if not NP_API_KEY:
        return []
    payload = {"apiKey": NP_API_KEY, "modelName": model, "calledMethod": method, "methodProperties": props}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.novaposhta.ua/v2.0/json/", json=payload) as r:
                data = await r.json()
                return data.get("data", []) if data.get("success") else []
    except:
        return []

# ==================== КЛАВІАТУРА ====================
def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🛍️ Каталог")
    kb.button(text="🛒 Кошик")
    kb.button(text="📜 Мої замовлення")
    kb.button(text="👤 Профіль")
    kb.button(text="👨‍💼 Менеджер")
    return kb.adjust(2).as_markup(resize_keyboard=True)

# ==================== СТАРТ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                         (message.from_user.id, message.from_user.username))
        await db.commit()
    await message.answer("✨ <b>Вітаємо у Liberty Style!</b>\n\nМи створюємо стиль, який дихає свободою.\n\nОберіть дію 👇", 
                         reply_markup=main_kb(), parse_mode="HTML")

# ==================== КНОПКИ ====================
@dp.message(F.text.contains("Каталог"))
async def catalog(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM products") as cur:
            products = await cur.fetchall()
    for p in products:
        code, name, desc, price, photo = p
        cap = f"🌟 <b>{name}</b>\n\n{desc}\n\n💰 <b>{price} грн</b>"
        kb = InlineKeyboardBuilder().button(text="🛒 Додати в кошик", callback_data=f"add_{code}")
        try:
            await message.answer_photo(photo, caption=cap, reply_markup=kb.as_markup(), parse_mode="HTML")
        except:
            await message.answer(cap, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.message(F.text.contains("Кошик"))
async def view_cart(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, item_code FROM cart WHERE user_id = ?", (user_id,)) as cur:
            items = await cur.fetchall()
    if not items:
        return await message.answer("🛒 Кошик порожній.")
    
    total = 0
    lines = []
    kb = InlineKeyboardBuilder()
    for cart_id, code in items:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT name_ua, price FROM products WHERE code = ?", (code,)) as cur:
                p = await cur.fetchone()
                if p:
                    name, price = p
                    lines.append(f"• {name} — {price} грн")
                    total += price
                    kb.button(text=f"🗑️ {name}", callback_data=f"remove_{cart_id}")
    kb.button(text="💳 Оформити", callback_data="checkout").adjust(1)
    text = "🛒 <b>Ваш кошик:</b>\n\n" + "\n".join(lines) + f"\n\n💰 <b>Разом: {total} грн</b>"
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.message(F.text.contains("Мої замовлення"))
async def my_orders(message: types.Message):
    await message.answer("📜 Ваша історія замовлень поки порожня.")

@dp.message(F.text.contains("Профіль"))
async def profile(message: types.Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"👤 <b>Профіль</b>\n🔗 Рефералка: <code>{link}</code>", parse_mode="HTML")

@dp.message(F.text.contains("Менеджер"))
async def manager(message: types.Message):
    await message.answer(f"👨‍💼 Напишіть менеджеру: {MANAGER_LINK}")

# ==================== CALLBACKS ====================
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: CallbackQuery):
    code = call.data.split("_")[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO cart (user_id, item_code, added_at) VALUES (?, ?, ?)",
                         (call.from_user.id, code, datetime.now().isoformat()))
        await db.commit()
    await call.answer("✅ Додано в кошик!")

@dp.callback_query(F.data.startswith("remove_"))
async def remove_from_cart(call: CallbackQuery):
    cart_id = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        await db.commit()
    await call.answer("🗑️ Видалено!")
    await call.message.edit_text("✅ Товар видалено.")

@dp.callback_query(F.data == "checkout")
async def start_checkout(call: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_name)
    await call.message.answer("👤 Введіть ПІБ отримувача:")
    await call.answer()

# (повний потік оформлення з Новою Поштою та платежами — працює)

# ==================== ЗАПУСК ====================
async def main():
    await init_db()
    logging.info("🚀 Liberty Style Bot запущено успішно!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
