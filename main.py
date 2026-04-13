import asyncio
import logging
from datetime import datetime
from typing import List

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ==================== НАСТРОЙКИ (ВШИТЫ) ====================
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY"
ADMIN_ID = 843027482
PROVIDER_TOKEN = ""                 # для LiqPay (если нужна оплата)
REF_BONUS = 50
MANAGER_LINK = "https://t.me/polinakondratii"
DB_NAME = "liberty_style.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== СОСТОЯНИЯ ====================
class OrderState(StatesGroup):
    waiting_name = State()
    waiting_city = State()
    waiting_warehouse = State()
    waiting_phone = State()
    waiting_promo = State()
    waiting_payment = State()

class AddProductState(StatesGroup):
    waiting_code = State()
    waiting_name_ua = State()
    waiting_desc_ua = State()
    waiting_price = State()
    waiting_photo = State()

# ==================== БАЗА ДАННЫХ ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                referred_by INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                code TEXT PRIMARY KEY,
                name_ua TEXT,
                desc_ua TEXT,
                price INTEGER,
                photo TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_code TEXT,
                quantity INTEGER DEFAULT 1,
                added_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                items TEXT,
                total_price INTEGER,
                info TEXT,
                ttn TEXT,
                status TEXT DEFAULT '⏳ Очікує',
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0
            )
        """)

        # Дефолтный товар
        await db.execute(
            "INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?)",
            ("tshirt", "👕 Футболка Liberty Style", "Вільний крій, м'яка тканина, комфорт", 500,
             "https://i.ibb.co/VWV0f80/liberty-tshirt.jpg")
        )
        await db.commit()
    logger.info("База данных инициализирована")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def get_user_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def update_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_cart_items(user_id: int) -> List[tuple]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT c.id, c.item_code, p.name_ua, p.price, c.quantity
            FROM cart c JOIN products p ON c.item_code = p.code
            WHERE c.user_id = ?
        """, (user_id,))
        return await cursor.fetchall()

async def clear_cart(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await db.commit()

# ==================== КЛАВИАТУРЫ ====================
def main_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🛍️ Каталог"), KeyboardButton(text="🛒 Кошик"))
    builder.row(KeyboardButton(text="📜 Мої замовлення"), KeyboardButton(text="👤 Профіль"))
    builder.row(KeyboardButton(text="👨‍💼 Менеджер"))
    return builder.as_markup(resize_keyboard=True)

def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardBuilder().button(text="❌ Скасувати", callback_data="cancel_order").as_markup()

# ==================== КОМАНДЫ ====================
@dp.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    args = command.args
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                         (user_id, message.from_user.username))
        await db.commit()
        if args and args.isdigit():
            referrer_id = int(args)
            if referrer_id != user_id:
                cursor = await db.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                if row and row[0] is None:
                    await db.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, user_id))
                    await update_balance(referrer_id, REF_BONUS)
                    await db.commit()
                    try:
                        await bot.send_message(referrer_id,
                            f"🎉 По вашому реферальному посиланню зареєструвався новий користувач! +{REF_BONUS} грн.")
                    except:
                        pass
    await message.answer(
        "✨ <b>Вітаємо у Liberty Style!</b>\n\nМи створюємо стиль, який дихає свободою.\n\nОберіть дію 👇",
        reply_markup=main_keyboard(), parse_mode="HTML"
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Немає доступу.")
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Додати товар", callback_data="admin_add_product")
    builder.button(text="📦 Замовлення", callback_data="admin_orders")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.adjust(1)
    await message.answer("🔧 Адмін-панель:", reply_markup=builder.as_markup())

# ==================== ОСНОВНЫЕ КНОПКИ ====================
@dp.message(F.text == "🛍️ Каталог")
async def show_catalog(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM products")
        products = await cursor.fetchall()
    if not products:
        return await message.answer("😔 Каталог порожній.")
    for p in products:
        code, name, desc, price, photo = p
        cap = f"🌟 <b>{name}</b>\n\n{desc}\n\n💰 <b>{price} грн</b>"
        kb = InlineKeyboardBuilder()
        kb.button(text="🛒 Додати в кошик", callback_data=f"add_{code}")
        kb.button(text="📦 Швидке замовлення", callback_data=f"fast_{code}")
        kb.adjust(1)
        try:
            await message.answer_photo(photo, caption=cap, reply_markup=kb.as_markup(), parse_mode="HTML")
        except:
            await message.answer(cap, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.message(F.text == "🛒 Кошик")
async def show_cart(message: Message):
    user_id = message.from_user.id
    items = await get_cart_items(user_id)
    if not items:
        return await message.answer("🛒 Кошик порожній.")
    total = 0
    lines = []
    kb = InlineKeyboardBuilder()
    for cart_id, code, name, price, qty in items:
        item_total = price * qty
        total += item_total
        lines.append(f"• {name} x{qty} — {item_total} грн")
        kb.row(
            InlineKeyboardButton(text="➖", callback_data=f"qty_{cart_id}_dec"),
            InlineKeyboardButton(text=f"{qty} шт", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"qty_{cart_id}_inc"),
        )
        kb.button(text=f"🗑️ Видалити {name}", callback_data=f"remove_{cart_id}")
    kb.button(text="🧹 Очистити кошик", callback_data="clear_cart")
    kb.button(text="💳 Оформити замовлення", callback_data="checkout")
    kb.adjust(2, 1, 1)
    text = "🛒 <b>Ваш кошик:</b>\n\n" + "\n".join(lines) + f"\n\n💰 <b>Разом: {total} грн</b>"
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.message(F.text == "📜 Мої замовлення")
async def show_orders(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, total_price, status, ttn, created_at FROM orders WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        )
        orders = await cursor.fetchall()
    if not orders:
        return await message.answer("📜 У вас ще немає замовлень.")
    for order in orders:
        oid, total, status, ttn, created = order
        text = f"📦 <b>Замовлення #{oid}</b>\n💰 Сума: {total} грн\n📅 Дата: {created[:10]}\n🚚 Статус: {status}\n"
        if ttn:
            text += f"📮 ТТН: <code>{ttn}</code>"
        kb = InlineKeyboardBuilder().button(text="🔍 Детальніше", callback_data=f"order_{oid}")
        await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.message(F.text == "👤 Профіль")
async def show_profile(message: Message):
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={user_id}"
    text = f"👤 <b>Ваш профіль</b>\n\n💰 Баланс: {balance} грн\n🔗 Реферальне посилання:\n<code>{ref_link}</code>\n\nЗапрошуйте друзів — отримуйте {REF_BONUS} грн!"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "👨‍💼 Менеджер")
async def contact_manager(message: Message):
    await message.answer(f"👨‍💼 Зв'яжіться з менеджером: {MANAGER_LINK}")

# ==================== CALLBACKS ====================
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: CallbackQuery):
    code = call.data.split("_")[1]
    user_id = call.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, quantity FROM cart WHERE user_id = ? AND item_code = ?", (user_id, code))
        existing = await cursor.fetchone()
        if existing:
            await db.execute("UPDATE cart SET quantity = quantity + 1 WHERE id = ?", (existing[0],))
        else:
            await db.execute("INSERT INTO cart (user_id, item_code, added_at) VALUES (?, ?, ?)",
                             (user_id, code, datetime.now().isoformat()))
        await db.commit()
    await call.answer("✅ Додано в кошик!")

@dp.callback_query(F.data.startswith("fast_"))
async def fast_order(call: CallbackQuery, state: FSMContext):
    code = call.data.split("_")[1]
    user_id = call.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO cart (user_id, item_code, added_at) VALUES (?, ?, ?)",
                         (user_id, code, datetime.now().isoformat()))
        await db.commit()
    await call.message.answer("⚡ Швидке оформлення. Давайте заповнимо дані.")
    await start_checkout(call, state)

@dp.callback_query(F.data.startswith("qty_"))
async def change_quantity(call: CallbackQuery):
    _, cart_id, action = call.data.split("_")
    cart_id = int(cart_id)
    async with aiosqlite.connect(DB_NAME) as db:
        if action == "inc":
            await db.execute("UPDATE cart SET quantity = quantity + 1 WHERE id = ?", (cart_id,))
        elif action == "dec":
            cursor = await db.execute("SELECT quantity FROM cart WHERE id = ?", (cart_id,))
            row = await cursor.fetchone()
            if row and row[0] > 1:
                await db.execute("UPDATE cart SET quantity = quantity - 1 WHERE id = ?", (cart_id,))
            else:
                await db.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        await db.commit()
    await call.answer("✅ Оновлено")
    await show_cart(call.message)
    try:
        await call.message.delete()
    except:
        pass

@dp.callback_query(F.data.startswith("remove_"))
async def remove_item(call: CallbackQuery):
    cart_id = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        await db.commit()
    await call.answer("🗑️ Видалено")
    await show_cart(call.message)
    try:
        await call.message.delete()
    except:
        pass

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_cb(call: CallbackQuery):
    await clear_cart(call.from_user.id)
    await call.answer("🧹 Кошик очищено")
    await call.message.edit_text("🛒 Кошик порожній.")

@dp.callback_query(F.data == "checkout")
async def start_checkout(call: CallbackQuery, state: FSMContext):
    if not await get_cart_items(call.from_user.id):
        await call.answer("Кошик порожній!", show_alert=True)
        return
    await state.set_state(OrderState.waiting_name)
    await call.message.answer("👤 Введіть ПІБ отримувача:", reply_markup=cancel_keyboard())
    await call.answer()

@dp.callback_query(F.data == "cancel_order")
async def cancel_order(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Оформлення скасовано.")
    await call.answer()

# ==================== ЦЕПОЧКА ОФОРМЛЕННЯ (БЕЗ API НОВОЙ ПОЧТЫ) ====================
@dp.message(OrderState.waiting_name)
async def process_name(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 3:
        return await message.answer("❌ Введіть коректне ім'я (не менше 3 символів).")
    await state.update_data(name=message.text.strip())
    await state.set_state(OrderState.waiting_city)
    await message.answer("🏙️ Введіть назву міста для доставки Новою Поштою:", reply_markup=cancel_keyboard())

@dp.message(OrderState.waiting_city)
async def process_city(message: Message, state: FSMContext):
    city = message.text.strip()
    if not city:
        return await message.answer("❌ Введіть назву міста.")
    await state.update_data(city_search=city)
    await state.set_state(OrderState.waiting_warehouse)
    await message.answer("🏢 Введіть номер або адресу відділення Нової Пошти:", reply_markup=cancel_keyboard())

@dp.message(OrderState.waiting_warehouse)
async def process_warehouse_manual(message: Message, state: FSMContext):
    warehouse = message.text.strip()
    if not warehouse:
        return await message.answer("❌ Введіть відділення.")
    await state.update_data(warehouse_desc=warehouse)
    await state.set_state(OrderState.waiting_phone)
    await message.answer("📞 Введіть номер телефону у форматі +380XXXXXXXXX:", reply_markup=cancel_keyboard())

@dp.message(OrderState.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+380") or not phone[1:].isdigit() or len(phone) != 13:
        return await message.answer("❌ Невірний формат. Введіть номер у форматі +380XXXXXXXXX.")
    await state.update_data(phone=phone)
    await state.set_state(OrderState.waiting_promo)
    kb = InlineKeyboardBuilder()
    kb.button(text="Пропустити", callback_data="skip_promo")
    kb.button(text="❌ Скасувати", callback_data="cancel_order")
    await message.answer("🎁 Введіть промокод (якщо є) або натисніть 'Пропустити':", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "skip_promo", OrderState.waiting_promo)
async def skip_promo(call: CallbackQuery, state: FSMContext):
    await state.update_data(promo_discount=0)
    await show_order_summary(call.message, state)
    await call.answer()

@dp.message(OrderState.waiting_promo)
async def process_promo(message: Message, state: FSMContext):
    promo = message.text.strip().upper()
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT discount_percent, max_uses, used_count FROM promocodes WHERE code = ?", (promo,))
        promo_data = await cursor.fetchone()
    if not promo_data:
        await message.answer("❌ Промокод не знайдено.")
        return
    discount, max_uses, used = promo_data
    if used >= max_uses:
        await message.answer("❌ Промокод вичерпано.")
        return
    await state.update_data(promo_code=promo, promo_discount=discount)
    await message.answer(f"✅ Промокод застосовано! Знижка {discount}%.")
    await show_order_summary(message, state)

async def show_order_summary(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    items = await get_cart_items(user_id)
    subtotal = sum(item[3] * item[4] for item in items)
    discount_percent = data.get("promo_discount", 0)
    discount_amount = subtotal * discount_percent // 100
    total = subtotal - discount_amount
    balance = await get_user_balance(user_id)
    if balance > 0:
        if balance >= total:
            total_after_balance = 0
            balance_used = total
        else:
            total_after_balance = total - balance
            balance_used = balance
    else:
        total_after_balance = total
        balance_used = 0

    await state.update_data(
        subtotal=subtotal, discount=discount_amount, total=total,
        balance_used=balance_used, final_payment=total_after_balance
    )

    text = (f"📋 <b>Підтвердження замовлення</b>\n\n"
            f"👤 Отримувач: {data['name']}\n"
            f"🏙️ Місто: {data.get('city_search')}\n"
            f"🏢 Відділення: {data['warehouse_desc']}\n"
            f"📞 Телефон: {data['phone']}\n\n"
            f"💰 Сума товарів: {subtotal} грн\n")
    if discount_amount:
        text += f"🎁 Знижка: -{discount_amount} грн ({discount_percent}%)\n"
    if balance_used:
        text += f"💳 Використано бонусів: {balance_used} грн\n"
    text += f"💵 <b>До сплати: {total_after_balance} грн</b>"

    kb = InlineKeyboardBuilder()
    if total_after_balance > 0:
        kb.button(text="💳 Оплатити", callback_data="pay_order")
    else:
        kb.button(text="✅ Підтвердити замовлення", callback_data="confirm_free_order")
    kb.button(text="✏️ Редагувати", callback_data="edit_order")
    kb.button(text="❌ Скасувати", callback_data="cancel_order")
    kb.adjust(1)

    await state.set_state(OrderState.waiting_payment)
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "pay_order", OrderState.waiting_payment)
async def pay_order(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    final_payment = data["final_payment"]
    if PROVIDER_TOKEN:
        prices = [LabeledPrice(label="Замовлення Liberty Style", amount=final_payment * 100)]
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title="Оплата замовлення",
            description=f"Замовлення в Liberty Style на суму {final_payment} грн",
            payload="order_payment",
            provider_token=PROVIDER_TOKEN,
            currency="UAH",
            prices=prices,
            start_parameter="liberty_order",
        )
        await call.message.edit_reply_markup()
        await call.answer("Виставлено рахунок на оплату.")
    else:
        await call.answer("Оплата тимчасово недоступна. Зв'яжіться з менеджером.", show_alert=True)

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message, state: FSMContext):
    await finalize_order(message.from_user.id, state, payment_success=True)
    await message.answer("✅ Дякуємо за оплату! Замовлення оформлено.")

@dp.callback_query(F.data == "confirm_free_order", OrderState.waiting_payment)
async def confirm_free_order(call: CallbackQuery, state: FSMContext):
    await finalize_order(call.from_user.id, state, payment_success=True)
    await call.message.edit_text("✅ Замовлення підтверджено! Очікуйте на відправку.")
    await call.answer()

async def finalize_order(user_id: int, state: FSMContext, payment_success: bool):
    data = await state.get_data()
    items = await get_cart_items(user_id)
    if not items:
        return
    items_text = "; ".join([f"{name} x{qty}" for _, _, name, _, qty in items])
    info = (f"ПІБ: {data['name']}\nМісто: {data.get('city_search')}\n"
            f"Відділення: {data['warehouse_desc']}\nТелефон: {data['phone']}")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO orders (user_id, items, total_price, info, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, items_text, data['total'], info,
             "⏳ Очікує підтвердження" if payment_success else "⏳ Очікує оплату",
             datetime.now().isoformat())
        )
        if data.get("balance_used", 0):
            await update_balance(user_id, -data["balance_used"])
        if promo := data.get("promo_code"):
            await db.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (promo,))
        await db.commit()
    await clear_cart(user_id)
    await state.clear()
    await bot.send_message(ADMIN_ID, f"🆕 Нове замовлення!\nКористувач: {user_id}\nСума: {data['total']} грн")

# ==================== АДМИН-ПАНЕЛЬ ====================
@dp.callback_query(F.data == "admin_add_product")
async def admin_add_product(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("⛔ Немає доступу.", show_alert=True)
    await state.set_state(AddProductState.waiting_code)
    await call.message.answer("🔤 Введіть унікальний код товару (латиницею, без пробілів):")
    await call.answer()

@dp.message(AddProductState.waiting_code)
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip()
    if not code.isalnum():
        return await message.answer("❌ Код має містити лише літери та цифри.")
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT code FROM products WHERE code = ?", (code,))
        if await cursor.fetchone():
            return await message.answer("❌ Такий код вже існує.")
    await state.update_data(code=code)
    await state.set_state(AddProductState.waiting_name_ua)
    await message.answer("📝 Введіть назву товару українською:")

@dp.message(AddProductState.waiting_name_ua)
async def process_name_ua(message: Message, state: FSMContext):
    await state.update_data(name_ua=message.text.strip())
    await state.set_state(AddProductState.waiting_desc_ua)
    await message.answer("📄 Введіть опис товару:")

@dp.message(AddProductState.waiting_desc_ua)
async def process_desc_ua(message: Message, state: FSMContext):
    await state.update_data(desc_ua=message.text.strip())
    await state.set_state(AddProductState.waiting_price)
    await message.answer("💰 Введіть ціну (ціле число, грн):")

@dp.message(AddProductState.waiting_price)
async def process_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Введіть число.")
    await state.update_data(price=int(message.text))
    await state.set_state(AddProductState.waiting_photo)
    await message.answer("🖼️ Надішліть фото товару або посилання на зображення:")

@dp.message(AddProductState.waiting_photo)
async def process_photo(message: Message, state: FSMContext):
    photo = None
    if message.photo:
        photo = message.photo[-1].file_id
    elif message.text:
        photo = message.text.strip()
    if not photo:
        return await message.answer("❌ Потрібно фото або посилання.")
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO products (code, name_ua, desc_ua, price, photo) VALUES (?, ?, ?, ?, ?)",
            (data["code"], data["name_ua"], data["desc_ua"], data["price"], photo)
        )
        await db.commit()
    await state.clear()
    await message.answer("✅ Товар додано!")

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("⛔ Немає доступу.", show_alert=True)
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, user_id, total_price, status FROM orders ORDER BY id DESC LIMIT 10")
        orders = await cursor.fetchall()
    if not orders:
        return await call.message.answer("Замовлень немає.")
    text = "📋 Останні замовлення:\n\n"
    for oid, uid, total, status in orders:
        text += f"#{oid} | user {uid} | {total} грн | {status}\n"
    await call.message.answer(text)
    await call.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("⛔ Немає доступу.", show_alert=True)
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        users = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*), SUM(total_price) FROM orders")
        orders_count, total_sum = await cursor.fetchone()
    text = f"👥 Користувачів: {users}\n📦 Замовлень: {orders_count or 0}\n💰 Загальна сума: {total_sum or 0} грн"
    await call.message.answer(text)
    await call.answer()

@dp.callback_query(F.data.startswith("order_"))
async def order_detail(call: CallbackQuery):
    oid = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT items, total_price, info, ttn, status, created_at FROM orders WHERE id = ?", (oid,))
        order = await cursor.fetchone()
    if not order:
        return await call.answer("Не знайдено.")
    items, total, info, ttn, status, created = order
    text = f"📦 Замовлення #{oid}\n📅 {created}\n🛒 {items}\n💰 {total} грн\n🚚 {status}\n"
    if ttn:
        text += f"📮 ТТН: {ttn}\n"
    text += f"\n📋 {info}"
    await call.message.answer(text)
    await call.answer()

# ==================== ЗАПУСК ====================
async def main():
    await init_db()
    logger.info("Бот Liberty Style запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
