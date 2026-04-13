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
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/White_blouse.jpg/480px-White_blouse.jpg"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- БАЗА ДАНИХ (Зберігання всього) ---
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
        await db.execute("CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, discount_pct INTEGER)")
        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('LIBERTY', 10)")
        await db.commit()

# --- СТАНИ ОФОРМЛЕННЯ ---
class OrderState(StatesGroup):
    waiting_city = State()
    waiting_post = State()
    waiting_phone = State()
    waiting_promo = State()
    waiting_receipt = State()

# --- ДОПОМІЖНІ ФУНКЦІЇ ---
async def get_lang(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)) as c:
            row = await c.fetchone()
            return row[0] if row else "ua"

def main_kb(lang):
    kb = ReplyKeyboardBuilder()
    btns = ["🛍️ Каталог", "🛒 Кошик", "👤 Профіль", "👨‍💼 Менеджер"] if lang == "ua" else ["🛍️ Каталог", "🛒 Корзина", "👤 Профиль", "👨‍💼 Менеджер"]
    for btn in btns: kb.button(text=btn)
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# --- 1. НАГАДУВАННЯ ПРО КОШИК (Фонові завдання) ---
async def abandoned_cart_reminder():
    while True:
        await asyncio.sleep(3600) 
        now = datetime.now()
        async with aiosqlite.connect(DB_NAME) as db:
            two_hours_ago = (now - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
            async with db.execute("SELECT DISTINCT user_id FROM cart WHERE added_at < ?", (two_hours_ago,)) as c:
                users = await c.fetchall()
                for user in users:
                    try: await bot.send_message(user[0], "👋 Ви залишили товари у кошику! Не забудьте завершити замовлення. ✨")
                    except: pass
            await db.execute("DELETE FROM cart WHERE added_at < ?", (two_hours_ago,)) # Очищуємо старі записи
            await db.commit()

# --- ХЕНДЛЕРИ КЛІЄНТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    ref_id = int(command.args) if command.args and command.args.isdigit() else None
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", 
                         (message.from_user.id, message.from_user.username, ref_id))
        await db.commit()
    kb = InlineKeyboardBuilder().button(text="🇺🇦 UA", callback_data="setlang_ua").button(text="🇷🇺 RU", callback_data="setlang_ru")
    await message.answer("<b>Liberty Style</b>\n\nОберіть мову / Выберите язык:", reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang_cb(call: CallbackQuery):
    lang = call.data.split("_")[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, call.from_user.id))
        await db.commit()
    await call.message.answer(f"✅ Вітаємо! Оберіть пункт меню:", reply_markup=main_kb(lang))
    await call.answer()

@dp.message(F.text.contains("Каталог"))
async def catalog(message: types.Message):
    lang = await get_lang(message.from_user.id)
    for k, v in PRODUCTS.items():
        cap = f"🌟 <b>{v[lang]}</b>\n\n{v['desc']}\n\n💰 Ціна: <b>{v['price']} грн</b>"
        kb = InlineKeyboardBuilder().button(text="🛒 Додати в кошик", callback_data=f"add_{k}")
        await message.answer_photo(v['photo'], caption=cap, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: CallbackQuery):
    code = call.data.split("_")[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO cart (user_id, item_code, added_at) VALUES (?, ?, ?)", 
                         (call.from_user.id, code, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        await db.commit()
    await call.answer("✅ Додано!")

@dp.message(F.text.contains("Кошик") | F.text.contains("Корзина"))
async def view_cart(message: types.Message):
    lang = await get_lang(message.from_user.id)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_code FROM cart WHERE user_id = ?", (message.from_user.id,)) as c:
            items = await c.fetchall()
    if not items: return await message.answer("🛒 Кошик порожній.")
    total = sum(PRODUCTS[i[0]]['price'] for i in items)
    res = f"🛒 <b>Ваш кошик:</b>\n\n" + "\n".join([f"• {PRODUCTS[i[0]][lang]}" for i in items]) + f"\n\n💰 <b>Разом: {total} грн</b>"
    kb = InlineKeyboardBuilder().button(text="💳 Оформити", callback_data="checkout").button(text="🗑️ Очистити", callback_data="clear").adjust(1)
    await message.answer(res, reply_markup=kb.as_markup(), parse_mode="HTML")

# --- 2. ОФОРМЛЕННЯ (НОВА ПОШТА + ПРОМОКОД) ---
@dp.callback_query(F.data == "checkout")
async def start_checkout(call: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_city)
    await call.message.answer("🏙️ Вкажіть ваше місто:")
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
    
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_code FROM cart WHERE user_id = ?", (event.from_user.id,)) as c:
            items = await c.fetchall()
            
    total = sum(PRODUCTS[i[0]]['price'] for i in items)
    if discount > 0: total = int(total * (1 - discount/100))

    await state.update_data(total=total, items_str=", ".join([i[0] for i in items]))
    await state.set_state(OrderState.waiting_receipt)
    
    pay_msg = f"💳 <b>До сплати: {total} грн</b>\n\nКарта: <code>{CARD_NUMBER}</code>\n\nНадішліть скріншот оплати 👇"
    if isinstance(event, CallbackQuery): await event.message.answer(pay_msg, parse_mode="HTML")
    else: await event.answer(pay_msg, parse_mode="HTML")

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

# --- 3. ПРОФІЛЬ ТА РЕФЕРАЛКА ---
@dp.message(F.text.contains("Профіль") | F.text.contains("Профиль"))
async def profile(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)) as c:
            balance = (await c.fetchone())[0]
        async with db.execute("SELECT id, status FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 3", (message.from_user.id,)) as c:
            orders = await c.fetchall()
    
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={message.from_user.id}"
    res = f"👤 <b>Ваш профіль</b>\n\n💰 Бонуси: {balance} грн\n🔗 Рефералка (+{REF_BONUS} грн): <code>{ref_link}</code>\n\n"
    if orders:
        res += "<b>Останні замовлення:</b>\n" + "\n".join([f"#{o[0]} — {o[1]}" for o in orders])
    else: res += "У вас ще немає замовлень."
    await message.answer(res, parse_mode="HTML")

@dp.message(F.text.contains("Менеджер"))
async def support(message: types.Message):
    await message.answer(f"👨‍💼 Ви можете зв'язатися з нами тут: {MANAGER_LINK}")

# --- 4. РОЗШИРЕНА АДМІНКА ТА СТАТИСТИКА ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_menu(message: types.Message):
    kb = InlineKeyboardBuilder().button(text="📊 Статистика", callback_data="adm_stats").button(text="📦 Замовлення", callback_data="adm_orders")
    await message.answer("🛠️ Адмін-панель:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "adm_stats")
async def admin_stats(call: CallbackQuery):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*), SUM(total_price) FROM orders WHERE status = '✅ Доставлено'") as c:
            row = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM users") as u:
            u_count = (await u.fetchone())[0]
    res = f"📊 <b>Статистика Liberty Style:</b>\n\n👥 Клієнтів: {u_count}\n📦 Продано: {row[0] or 0}\n💰 Прибуток: {row[1] or 0} грн"
    await call.message.edit_text(res, reply_markup=InlineKeyboardBuilder().button(text="🔙 Назад", callback_data="adm_back").as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_orders")
async def admin_orders(call: CallbackQuery):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, status FROM orders WHERE status != '✅ Доставлено' LIMIT 5") as c:
            orders = await c.fetchall()
    kb = InlineKeyboardBuilder()
    for o in orders: kb.button(text=f"Замовлення #{o[0]} ({o[1]})", callback_data=f"st_{o[0]}")
    kb.adjust(1)
    await call.message.edit_text("📦 Керування статусами:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("st_"))
async def set_status(call: CallbackQuery):
    oid = call.data.split("_")[1]
    kb = InlineKeyboardBuilder()
    for s in ["💳 Оплачено", "✅ Доставлено"]: kb.button(text=s, callback_data=f"upd_{oid}_{s}")
    await call.message.edit_text(f"Змінити статус #{oid}:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("upd_"))
async def update_status(call: CallbackQuery):
    _, oid, status = call.data.split("_")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, oid))
        if status == "✅ Доставлено":
            async with db.execute("SELECT user_id FROM orders WHERE id = ?", (oid,)) as c: uid = (await c.fetchone())[0]
            async with db.execute("SELECT referred_by FROM users WHERE user_id = ?", (uid,)) as c: rid = (await c.fetchone())[0]
            if rid: await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, rid))
        await db.commit()
    await call.answer("Статус оновлено!")
    await admin_orders(call)

async def main():
    await init_db()
    asyncio.create_task(abandoned_cart_reminder()) # Запуск нагадувань
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
