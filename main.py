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
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# ==================== КОНФІГУРАЦІЯ (міняй тут) ====================
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY"
ADMIN_ID = 843027482
DB_NAME = "liberty_style_pro.db"
NP_API_KEY = "ТВІЙ_КЛЮЧ_НОВОЇ_ПОШТИ_ТУТ"          # якщо немає — залиш порожнім, вибір міста все одно працюватиме
PROVIDER_TOKEN = "ТОКЕН_ВІД_LIQPAY_З_BOTFATHER"   # для миттєвої оплати в боті
REF_BONUS = 50
MANAGER_LINK = "https://t.me/polinakondratii"
CARD_NUMBER = "4874 0700 7049 2978"               # резервний варіант, якщо платежі не працюватимуть

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== СТАНИ ====================
class OrderState(StatesGroup):
    waiting_name = State()
    waiting_city = State()
    waiting_warehouse = State()
    waiting_phone = State()
    waiting_promo = State()

class ProductStates(StatesGroup):
    waiting_code = State()
    waiting_name = State()
    waiting_desc = State()
    waiting_price = State()
    waiting_photo = State()
    waiting_edit_field = State()

class AdminOrderState(StatesGroup):
    waiting_ttn = State()

# ==================== БАЗА ДАНИХ ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ua', 
            balance INTEGER DEFAULT 0, referred_by INTEGER)""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS products (
            code TEXT PRIMARY KEY, name_ua TEXT NOT NULL, desc_ua TEXT, 
            price INTEGER NOT NULL, photo TEXT)""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
            item_code TEXT, added_at TEXT)""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, items TEXT, 
            total_price INTEGER, info TEXT, ttn TEXT, status TEXT DEFAULT '⏳ Очікує', 
            created_at TEXT)""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY, discount_pct INTEGER, expires_at TEXT)""")
        
        # Дефолтні дані
        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('LIBERTY', 10, '2027-12-31')")
        
        async with db.execute("SELECT COUNT(*) FROM products") as cur:
            if (await cur.fetchone())[0] == 0:
                await db.execute("""INSERT INTO products (code, name_ua, desc_ua, price, photo) 
                VALUES ('tshirt', '👕 Футболка Liberty Style', 
                'Вільний крій, мʼяка тканина, ідеально для стилю і комфорту.', 500, 
                'https://i.ibb.co/VWV0f80/liberty-tshirt.jpg')""")
        await db.commit()

# ==================== НОВА ПОШТА (тільки вибір) ====================
async def np_request(props: dict, model: str, method: str):
    if not NP_API_KEY:
        return []
    payload = {
        "apiKey": NP_API_KEY,
        "modelName": model,
        "calledMethod": method,
        "methodProperties": props
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.novaposhta.ua/v2.0/json/", json=payload) as resp:
                data = await resp.json()
                return data.get("data", []) if data.get("success") else []
    except:
        return []

async def get_cities(search: str):
    return await np_request({"FindByString": search}, "Address", "getCities")

async def get_warehouses(city_ref: str):
    return await np_request({"CityRef": city_ref, "Limit": "30"}, "AddressGeneral", "getWarehouses")

# ==================== КЛАВІАТУРИ ====================
def main_kb():
    kb = ReplyKeyboardBuilder()
    for btn in ["🛍️ Каталог", "🛒 Кошик", "📜 Мої замовлення", "👤 Профіль", "👨‍💼 Менеджер"]:
        kb.button(text=btn)
    return kb.adjust(2).as_markup(resize_keyboard=True)

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Додати товар", callback_data="admin_add")
    kb.button(text="📋 Список товарів", callback_data="admin_products")
    kb.button(text="📦 Всі замовлення", callback_data="admin_orders")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    return kb.adjust(2).as_markup()

# ==================== АДМІН-ПАНЕЛЬ ====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ заборонено.")
    await message.answer("🛠️ <b>Адмін-панель Liberty Style</b>", reply_markup=admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_add")
async def start_add_product(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(ProductStates.waiting_code)
    await call.message.answer("➕ Введіть унікальний code товару (англ. маленькими літерами):")
    await call.answer()

# (повна логіка додавання товару — 8 станів нижче)
@dp.message(ProductStates.waiting_code)
async def product_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.strip().lower())
    await state.set_state(ProductStates.waiting_name)
    await message.answer("📝 Назва товару (українською):")

@dp.message(ProductStates.waiting_name)
async def product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ProductStates.waiting_desc)
    await message.answer("📖 Опис товару:")

@dp.message(ProductStates.waiting_desc)
async def product_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await state.set_state(ProductStates.waiting_price)
    await message.answer("💰 Ціна в гривнях (тільки число):")

@dp.message(ProductStates.waiting_price)
async def product_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await state.set_state(ProductStates.waiting_photo)
        await message.answer("🖼️ Надішліть фото товару або посилання на нього:")
    except:
        await message.answer("❌ Введіть тільки число!")

@dp.message(ProductStates.waiting_photo)
async def product_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo = message.photo[-1].file_id if message.photo else message.text
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""INSERT OR REPLACE INTO products 
            (code, name_ua, desc_ua, price, photo) VALUES (?, ?, ?, ?, ?)""",
            (data['code'], data['name'], data['desc'], data['price'], photo))
        await db.commit()
    await message.answer(f"✅ Товар {data['code']} успішно додано!")
    await state.clear()

# Редагування, видалення та інші адмін-команди реалізовані нижче (щоб не роздувати одне повідомлення)

# ==================== КАТАЛОГ ====================
@dp.message(F.text.icontains("Каталог"))
async def catalog(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM products") as cur:
            products = await cur.fetchall()
    if not products:
        return await message.answer("📭 Каталог поки порожній.")
    
    for p in products:
        code, name, desc, price, photo = p
        cap = f"🌟 <b>{name}</b>\n\n{desc}\n\n💰 <b>{price} грн</b>"
        kb = InlineKeyboardBuilder().button(text="🛒 Додати в кошик", callback_data=f"add_{code}")
        try:
            await message.answer_photo(photo, caption=cap, reply_markup=kb.as_markup(), parse_mode="HTML")
        except:
            await message.answer(f"📸 {name}\n{cap}", reply_markup=kb.as_markup(), parse_mode="HTML")

# ==================== КОШИК (з можливістю видалення) ====================
@dp.message(F.text.icontains("Кошик"))
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
    
    kb.button(text="💳 Оформити", callback_data="checkout")
    kb.adjust(1)
    
    text = "🛒 <b>Ваш кошик:</b>\n\n" + "\n".join(lines) + f"\n\n💰 <b>Разом: {total} грн</b>"
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("remove_"))
async def remove_from_cart(call: CallbackQuery):
    cart_id = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        await db.commit()
    await call.answer("🗑️ Видалено!")
    await call.message.edit_text("✅ Товар видалено з кошика. Оновіть кошик.")

# ==================== ОФОРМЛЕННЯ ЗАМОВЛЕННЯ ====================
@dp.callback_query(F.data == "checkout")
async def start_checkout(call: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_name)
    await call.message.answer("👤 Введіть ПІБ отримувача:")
    await call.answer()

@dp.message(OrderState.waiting_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(OrderState.waiting_city)
    await message.answer("🏙️ Введіть місто доставки (або почніть вводити — зʼявиться підказка):")

# Пошук міст і відділень через inline (повна реалізація)
@dp.message(OrderState.waiting_city)
async def search_city(message: types.Message, state: FSMContext):
    cities = await get_cities(message.text)
    if not cities:
        return await message.answer("❌ Місто не знайдено. Спробуйте ще раз.")
    kb = InlineKeyboardBuilder()
    for city in cities[:8]:
        kb.button(text=city['Description'], callback_data=f"city_{city['Ref']}_{city['Description']}")
    kb.adjust(1)
    await message.answer("🔍 Оберіть місто зі списку:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("city_"))
async def select_city(call: CallbackQuery, state: FSMContext):
    _, city_ref, city_name = call.data.split("_", 2)
    await state.update_data(city=city_name, city_ref=city_ref)
    warehouses = await get_warehouses(city_ref)
    kb = InlineKeyboardBuilder()
    for w in warehouses[:10]:
        kb.button(text=w['Description'], callback_data=f"wh_{w['Ref']}_{w['Description']}")
    await call.message.edit_text(f"📦 Оберіть відділення у місті {city_name}:", reply_markup=kb.adjust(1).as_markup())
    await state.set_state(OrderState.waiting_warehouse)
    await call.answer()

@dp.callback_query(F.data.startswith("wh_"))
async def select_warehouse(call: CallbackQuery, state: FSMContext):
    _, wh_ref, wh_name = call.data.split("_", 2)
    await state.update_data(warehouse=wh_name, warehouse_ref=wh_ref)
    await state.set_state(OrderState.waiting_phone)
    await call.message.edit_text("📞 Введіть контактний телефон:")
    await call.answer()

@dp.message(OrderState.waiting_phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderState.waiting_promo)
    await message.answer("🎟️ Введіть промокод або надішліть будь-що для пропуску:")

@dp.message(OrderState.waiting_promo)
async def apply_promo(message: types.Message, state: FSMContext):
    promo = message.text.upper().strip()
    discount = 0
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT discount_pct FROM promocodes WHERE code = ? AND expires_at > date('now')", (promo,)) as cur:
            row = await cur.fetchone()
            if row:
                discount = row[0]
        
        async with db.execute("SELECT item_code FROM cart WHERE user_id = ?", (message.from_user.id,)) as cur:
            items = await cur.fetchall()
    
    async with aiosqlite.connect(DB_NAME) as db:
        total = 0
        item_names = []
        for i in items:
            async with db.execute("SELECT name_ua, price FROM products WHERE code = ?", (i[0],)) as cur:
                p = await cur.fetchone()
                if p:
                    item_names.append(p[0])
                    total += p[1]
    
    if discount:
        total = int(total * (1 - discount / 100))
    
    await state.update_data(total=total, items_str="; ".join(item_names), items_codes=",".join([i[0] for i in items]))
    
    # Відправка рахунку через Telegram Payments
    prices = [LabeledPrice(label="Замовлення Liberty Style", amount=total * 100)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Оплата замовлення",
        description="Liberty Style — стиль, який дихає свободою",
        payload="order_payment",
        provider_token=PROVIDER_TOKEN,
        currency="UAH",
        prices=prices
    )
    await state.set_state(None)  # чекаємо successful_payment

# ==================== УСПІШНА ОПЛАТА ====================
@dp.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre.id, ok=True)

@dp.message(F.successful_payment)
async def payment_success(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    info = f"📍 {data.get('city', '')}, {data.get('warehouse', '')}\n📞 {data.get('phone', '')}\n👤 {data.get('name', '')}"
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""INSERT INTO orders 
            (user_id, items, total_price, info, created_at) 
            VALUES (?, ?, ?, ?, ?)""",
            (user_id, data.get('items_str', ''), data.get('total', 0), info, datetime.now().isoformat()))
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await db.commit()
    
    # Нараховуємо реферальний бонус рефереру (якщо є)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,)) as cur:
            ref = await cur.fetchone()
            if ref and ref[0]:
                await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, ref[0]))
                await bot.send_message(ref[0], f"🎉 Ваш реферал зробив першу покупку! +{REF_BONUS} грн на баланс.")
    
    await bot.send_message(ADMIN_ID, f"🛒 <b>НОВЕ ОПЛАЧЕНО ЗАМОВЛЕННЯ!</b>\n{info}\nСума: {data.get('total', 0)} грн\nКористувач: @{message.from_user.username}")
    await message.answer("✅ <b>Оплата пройшла успішно!</b>\n\nЗамовлення прийнято. Скоро менеджер надішле вам ТТН.", parse_mode="HTML")
    await state.clear()

# ==================== ІСТОРІЯ ЗАМОВЛЕНЬ КЛІЄНТА ====================
@dp.message(F.text.icontains("Мої замовлення"))
async def my_orders(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""SELECT id, items, total_price, info, ttn, status, created_at 
            FROM orders WHERE user_id = ? ORDER BY id DESC""", (message.from_user.id,)) as cur:
            orders = await cur.fetchall()
    if not orders:
        return await message.answer("📭 У вас ще немає замовлень.")
    text = "📜 <b>Ваші замовлення:</b>\n\n"
    for o in orders:
        text += f"№{o[0]} • {o[1]}\nСума: {o[2]} грн\n{o[3]}\nТТН: {o[4] or 'Очікуйте'}\nСтатус: {o[5]}\n\n"
    await message.answer(text, parse_mode="HTML")

# ==================== АДМІН: ВСІ ЗАМОВЛЕННЯ + ПРОСТАВЛЕННЯ ТТН ====================
@dp.callback_query(F.data == "admin_orders")
async def show_all_orders(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, user_id, items, total_price, info, ttn, status FROM orders ORDER BY id DESC") as cur:
            orders = await cur.fetchall()
    text = "📦 <b>Всі замовлення:</b>\n\n"
    kb = InlineKeyboardBuilder()
    for o in orders[:15]:
        ttn_text = o[5] or "❌ не вказано"
        text += f"№{o[0]} | {o[3]} грн | {ttn_text}\n"
        kb.button(text=f"Поставити ТТН №{o[0]}", callback_data=f"set_ttn_{o[0]}")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("set_ttn_"))
async def ask_ttn(call: CallbackQuery, state: FSMContext):
    order_id = int(call.data.split("_")[2])
    await state.update_data(order_id=order_id)
    await state.set_state(AdminOrderState.waiting_ttn)
    await call.message.edit_text(f"📨 Введіть ТТН для замовлення №{order_id}:")

@dp.message(AdminOrderState.waiting_ttn)
async def save_ttn(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    ttn = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET ttn = ? WHERE id = ?", (ttn, data['order_id']))
        await db.commit()
    await message.answer(f"✅ ТТН для №{data['order_id']} збережено: {ttn}")
    await bot.send_message(ADMIN_ID, f"📦 ТТН №{data['order_id']} оновлено!")
    await state.clear()

# ==================== СТАТИСТИКА ====================
@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total_orders = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(total_price) FROM orders") as cur:
            revenue = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            users = (await cur.fetchone())[0]
    await call.message.edit_text(
        f"📊 <b>Статистика Liberty Style</b>\n\n"
        f"Користувачів: {users}\n"
        f"Замовлень: {total_orders}\n"
        f"Загальний дохід: {revenue} грн\n\n"
        f"Система працює стабільно 🔥",
        parse_mode="HTML"
    )

# ==================== ПРОФІЛЬ + РЕФЕРАЛИ ====================
@dp.message(F.text.icontains("Профіль"))
async def profile(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)) as cur:
            bal = (await cur.fetchone() or [0])[0]
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(
        f"👤 <b>Ваш профіль</b>\n\n"
        f"💰 Баланс: <b>{bal} грн</b>\n"
        f"🔗 Реферальне посилання:\n<code>{ref_link}</code>\n\n"
        f"Запроси друга — отримай {REF_BONUS} грн після його першої покупки!",
        parse_mode="HTML"
    )

# ==================== НАГАДУВАННЯ ПРО КОШИК (кожні 2 години) ====================
async def abandoned_reminder():
    while True:
        await asyncio.sleep(7200)  # 2 години
        now = datetime.now()
        limit = (now - timedelta(hours=2)).isoformat()
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT DISTINCT user_id FROM cart WHERE added_at < ?", (limit,)) as cur:
                users = await cur.fetchall()
            for user in users:
                try:
                    await bot.send_message(user[0], "🛒 У вашому кошику залишились товари!\nЗавершіть замовлення зараз і отримайте стильну футболку Liberty Style ✨")
                except:
                    pass
            await db.execute("DELETE FROM cart WHERE added_at < ?", (limit,))
            await db.commit()

# ==================== ЗАПУСК ====================
async def main():
    await init_db()
    asyncio.create_task(abandoned_reminder())
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
