import asyncio
import logging
import sys
import os
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) if os.getenv("ADMIN_ID") else 0
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
CARD_NUMBER = os.getenv("CARD_NUMBER", "1234 5678 1234 5678")
MANAGER_LINK = os.getenv("MANAGER_LINK", "https://t.me/polinakondratii")

# Якщо хочете токени прямо у коді, розкоментуйте:
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY"
ADMIN_ID = 843027482
GEMINI_KEY = "AIzaSyBNTVcRS468EACwmZ5gV4tINfDGbMWWUzU"

DB_NAME = "shop.db"

if not TOKEN:
    print("❌ TELEGRAM_TOKEN не вказаний!")
    sys.exit(1)

# Google AI
AI_ENABLED = False
try:
    from google import genai
    if GEMINI_KEY:
        client = genai.Client(api_key=GEMINI_KEY)
        AI_ENABLED = True
        print("✅ AI підключено")
except:
    print("⚠️ AI недоступний")

AI_PROMPT = """
Ти — консультант магазина 'Liberty Style'.
Товар: Школьная форма (Турция, 80% хлопок).
Доставка: Новая Почта (1-2 дня).
Оплата: Монобанк.
Цены: Юбка-550, Блуза-450, Брюки-600, Жакет-850 грн.
Размеры: XS-XL (34-46).
Отвечай кратко, вежливо, на языке клиента.
"""

PRODUCTS = {
    "skirt": {
        "name_ua": "Спідниця плісирована",
        "name_ru": "Юбка плиссированная",
        "price": 550,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg",
        "desc_ua": "Класична шкільна спідниця, 80% бавовна",
        "desc_ru": "Классическая школьная юбка, 80% хлопок"
    },
    "blouse": {
        "name_ua": "Блуза класична",
        "name_ru": "Блуза классическая",
        "price": 450,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/White_blouse.jpg/480px-White_blouse.jpg",
        "desc_ua": "Біла шкільна блуза, дихаюча тканина",
        "desc_ru": "Белая школьная блуза, дышащая ткань"
    },
    "trousers": {
        "name_ua": "Штани шкільні",
        "name_ru": "Брюки школьные",
        "price": 600,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Trousers.jpg/480px-Trousers.jpg",
        "desc_ua": "Класичні шкільні штани",
        "desc_ru": "Классические школьные брюки"
    },
    "jacket": {
        "name_ua": "Жакет шкільний",
        "name_ru": "Жакет школьный",
        "price": 850,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg",
        "desc_ua": "Елегантний жакет",
        "desc_ru": "Элегантный жакет"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

texts = {
    "ua": {
        "welcome": "🎓 Вітаємо в Liberty Style!\n\nОберіть мову:",
        "menu": "📋 Головне меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_ai": "🤖 ШІ-асистент",
        "btn_manager": "👨‍💼 Менеджер",
        "catalog_title": "🛍️ Наш асортимент:\n\nОберіть товар:",
        "enter_data": "✍️ <b>Введіть дані:</b>\n\n📝 ПІБ\n📱 Телефон\n📍 Місто, НП\n\n<i>Приклад:\nІванова Марія\n+380991234567\nКиїв, НП №15</i>",
        "wait_payment": "✅ Замовлення #{order_id}\n\n💰 До сплати: <b>{price} грн</b>\n💳 <code>{card}</code>\n\n📎 Надішліть чек:",
        "order_done": "✅ Прийнято! Менеджер зв'яжеться.",
        "ai_intro": "🤖 ШІ-помічник\n\nЗапитайте про розміри, тканину, доставку.",
        "manager_contact": "👨‍💼 Менеджер:\n{link}",
        "no_ai": "⚠️ AI недоступний\n{link}",
        "session_lost": "⚠️ Сеанс втрачено. Почніть заново.",
        "admin_panel": "🔧 <b>АДМІН-ПАНЕЛЬ</b>\n\nВиберіть дію:",
        "stats": "📊 <b>СТАТИСТИКА</b>\n\n👥 Користувачів: {users}\n📦 Замовлень: {orders}\n💰 Виконано: {completed}",
        "no_orders": "Немає замовлень"
    },
    "ru": {
        "welcome": "🎓 Добро пожаловать в Liberty Style!\n\nВыберите язык:",
        "menu": "📋 Главное меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_ai": "🤖 ИИ-ассистент",
        "btn_manager": "👨‍💼 Менеджер",
        "catalog_title": "🛍️ Наш ассортимент:\n\nВыберите товар:",
        "enter_data": "✍️ <b>Введите данные:</b>\n\n📝 ФИО\n📱 Телефон\n📍 Город, НП\n\n<i>Пример:\nИванова Мария\n+380991234567\nКиев, НП №15</i>",
        "wait_payment": "✅ Заказ #{order_id}\n\n💰 К оплате: <b>{price} грн</b>\n💳 <code>{card}</code>\n\n📎 Пришлите чек:",
        "order_done": "✅ Принят! Менеджер свяжется.",
        "ai_intro": "🤖 ИИ-помощник\n\nСпросите о размерах, ткани, доставке.",
        "manager_contact": "👨‍💼 Менеджер:\n{link}",
        "no_ai": "⚠️ AI недоступен\n{link}",
        "session_lost": "⚠️ Сеанс потерян. Начните заново.",
        "admin_panel": "🔧 <b>АДМИН-ПАНЕЛЬ</b>\n\nВыберите действие:",
        "stats": "📊 <b>СТАТИСТИКА</b>\n\n👥 Пользователей: {users}\n📦 Заказов: {orders}\n💰 Выполнено: {completed}",
        "no_orders": "Нет заказов"
    }
}

user_langs = {}

# --- DATABASE ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, 
                username TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_code TEXT,
                item_name TEXT,
                user_info TEXT,
                price INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)
        await db.commit()

async def add_user(user):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", 
                        (user.id, user.username, datetime.now()))
        await db.commit()

async def save_order(user_id, item_code, item_name, user_info, price):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, item_code, item_name, user_info, price) VALUES (?, ?, ?, ?, ?)",
            (user_id, item_code, item_name, user_info, price)
        )
        await db.commit()
        return cursor.lastrowid

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        users = await db.execute("SELECT COUNT(*) FROM users")
        users_count = (await users.fetchone())[0]
        
        orders = await db.execute("SELECT COUNT(*) FROM orders")
        orders_count = (await orders.fetchone())[0]
        
        completed = await db.execute("SELECT COUNT(*) FROM orders WHERE status='completed'")
        completed_count = (await completed.fetchone())[0]
        
        return users_count, orders_count, completed_count

async def get_pending_orders():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, user_id, item_name, price, user_info, created_at FROM orders WHERE status='pending' ORDER BY created_at DESC LIMIT 10"
        )
        return await cursor.fetchall()

# --- FSM ---
class OrderState(StatesGroup):
    waiting_data = State()
    waiting_receipt = State()

class SupportState(StatesGroup):
    chat = State()

# --- KEYBOARDS ---
def get_lang_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🇺🇦 Українська")
    kb.button(text="🇷🇺 Русский")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def get_menu_kb(lang):
    t = texts[lang]
    kb = ReplyKeyboardBuilder()
    kb.button(text=t["btn_cat"])
    kb.button(text=t["btn_ai"])
    kb.button(text=t["btn_manager"])
    kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True)

def get_catalog_kb(lang):
    kb = InlineKeyboardBuilder()
    for code, data in PRODUCTS.items():
        name_key = f"name_{lang}"
        kb.button(text=f"{data[name_key]} - {data['price']} грн", callback_data=f"item_{code}")
    kb.adjust(1)
    return kb.as_markup()

def get_item_kb(code, lang):
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Купити / Купить", callback_data=f"buy_{code}")
    kb.button(text="◀️ Назад / Назад", callback_data="back_catalog")
    kb.adjust(1)
    return kb.as_markup()

def get_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.button(text="📦 Замовлення", callback_data="admin_orders")
    kb.button(text="✅ Підтвердити всі", callback_data="admin_approve_all")
    kb.adjust(2, 1)
    return kb.as_markup()

def get_order_kb(order_id, user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ OK", callback_data=f"ok_{order_id}_{user_id}")
    kb.button(text="❌ NO", callback_data=f"no_{order_id}_{user_id}")
    kb.adjust(2)
    return kb.as_markup()

def get_ul(uid):
    return user_langs.get(uid, "ua")

# --- HANDLERS ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await add_user(message.from_user)
    await message.answer(texts["ua"]["welcome"], reply_markup=get_lang_kb())

@dp.message(F.text.in_({"🇺🇦 Українська", "🇷🇺 Русский"}))
async def set_lang(message: types.Message):
    lang = "ua" if "🇺🇦" in message.text else "ru"
    user_langs[message.from_user.id] = lang
    await message.answer(texts[lang]["menu"], reply_markup=get_menu_kb(lang))

# CATALOG
@dp.message(F.text.contains("Каталог"))
async def show_catalog(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["catalog_title"], reply_markup=get_catalog_kb(lang))

@dp.callback_query(F.data.startswith("item_"))
async def show_item(callback: CallbackQuery):
    code = callback.data.replace("item_", "")
    lang = get_ul(callback.from_user.id)
    
    item = PRODUCTS.get(code)
    if not item:
        await callback.answer("❌ Помилка")
        return
    
    name = item[f"name_{lang}"]
    desc = item[f"desc_{lang}"]
    caption = f"<b>{name}</b>\n\n{desc}\n\n💰 <b>{item['price']} грн</b>"
    
    try:
        await callback.message.delete()
        await callback.message.answer_photo(
            item['photo'], 
            caption=caption,
            reply_markup=get_item_kb(code, lang),
            parse_mode="HTML"
        )
    except:
        await callback.message.edit_text(caption, reply_markup=get_item_kb(code, lang), parse_mode="HTML")
    
    await callback.answer()

@dp.callback_query(F.data == "back_catalog")
async def back_catalog(callback: CallbackQuery):
    lang = get_ul(callback.from_user.id)
    await callback.message.delete()
    await callback.message.answer(texts[lang]["catalog_title"], reply_markup=get_catalog_kb(lang))
    await callback.answer()

# BUY
@dp.callback_query(F.data.startswith("buy_"))
async def buy_item(callback: CallbackQuery, state: FSMContext):
    code = callback.data.replace("buy_", "")
    lang = get_ul(callback.from_user.id)
    item = PRODUCTS[code]
    
    await state.update_data(
        item_code=code, 
        item_name=item[f"name_{lang}"],
        price=item['price']
    )
    await state.set_state(OrderState.waiting_data)
    
    await callback.message.delete()
    await callback.message.answer(texts[lang]["enter_data"], parse_mode="HTML")
    await callback.answer()

@dp.message(OrderState.waiting_data)
async def process_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    
    # Зберігаємо у БД
    order_id = await save_order(
        message.from_user.id,
        data['item_code'],
        data['item_name'],
        message.text,
        data['price']
    )
    
    await state.update_data(info=message.text, order_id=order_id)
    await state.set_state(OrderState.waiting_receipt)
    
    msg = texts[lang]["wait_payment"].format(
        order_id=order_id,
        price=data['price'],
        card=CARD_NUMBER
    )
    await message.answer(msg, parse_mode="HTML")

# RECEIPT
@dp.message(OrderState.waiting_receipt, F.photo)
async def get_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    user = message.from_user
    
    # Відправка адміну
    if ADMIN_ID:
        try:
            txt = (
                f"🚨 <b>ЗАМОВЛЕННЯ #{data['order_id']}</b>\n\n"
                f"👤 @{user.username or user.first_name} (ID: {user.id})\n"
                f"📦 {data['item_name']}\n"
                f"💰 {data['price']} грн\n\n"
                f"📝 {data['info']}\n\n"
                f"⏰ {datetime.now().strftime('%d.%m %H:%M')}"
            )
            await bot.send_message(ADMIN_ID, txt, reply_markup=get_order_kb(data['order_id'], user.id), parse_mode="HTML")
            await message.copy_to(ADMIN_ID)
        except Exception as e:
            logging.error(f"Admin error: {e}")
    
    await message.answer(texts[lang]["order_done"], reply_markup=get_menu_kb(lang))
    await state.clear()

@dp.message(F.photo)
async def unexpected_photo(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["session_lost"])

# MANAGER
@dp.message(F.text.contains("Менеджер"))
async def contact_manager(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["manager_contact"].format(link=MANAGER_LINK), parse_mode="HTML")

# AI
@dp.message(F.text.contains("асистент") | F.text.contains("ассистент"))
async def support(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    
    if not AI_ENABLED:
        await message.answer(texts[lang]["no_ai"].format(link=MANAGER_LINK))
        return
    
    await state.set_state(SupportState.chat)
    await message.answer(texts[lang]["ai_intro"])

@dp.message(SupportState.chat)
async def ai_chat(message: types.Message, state: FSMContext):
    if "меню" in message.text.lower() or "menu" in message.text.lower():
        await state.clear()
        lang = get_ul(message.from_user.id)
        await message.answer(texts[lang]["menu"], reply_markup=get_menu_kb(lang))
        return
    
    wait = await message.answer("⏳...")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=f"{AI_PROMPT}\n\n{message.text}"
        )
        await bot.edit_message_text(response.text, message.chat.id, wait.message_id)
    except:
        await bot.edit_message_text(f"⚠️ Помилка. {MANAGER_LINK}", message.chat.id, wait.message_id)

# ADMIN PANEL
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ Доступ заборонено")
        return
    
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["admin_panel"], reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔️")
        return
    
    lang = get_ul(callback.from_user.id)
    users, orders, completed = await get_stats()
    
    msg = texts[lang]["stats"].format(users=users, orders=orders, completed=completed)
    await callback.message.edit_text(msg, reply_markup=get_admin_kb(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔️")
        return
    
    orders = await get_pending_orders()
    
    if not orders:
        await callback.answer("Немає замовлень")
        return
    
    msg = "📦 <b>АКТИВНІ ЗАМОВЛЕННЯ:</b>\n\n"
    for order in orders:
        msg += f"#{order[0]} | {order[2]} | {order[3]}грн\n{order[4]}\n\n"
    
    await callback.message.edit_text(msg, reply_markup=get_admin_kb(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("ok_"))
async def approve_order(callback: CallbackQuery):
    parts = callback.data.split("_")
    order_id, user_id = int(parts[1]), int(parts[2])
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
        await db.commit()
    
    await callback.message.edit_text(callback.message.text + "\n\n✅ ПІДТВЕРДЖЕНО", parse_mode="HTML")
    
    try:
        await bot.send_message(user_id, "✅ Замовлення підтверджено! Очікуйте ТТН.")
    except:
        pass
    
    await callback.answer("✅")

@dp.callback_query(F.data.startswith("no_"))
async def reject_order(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    
    await callback.message.edit_text(callback.message.text + "\n\n❌ ВІДХИЛЕНО", parse_mode="HTML")
    
    try:
        await bot.send_message(user_id, f"❌ Проблема з оплатою. {MANAGER_LINK}")
    except:
        pass
    
    await callback.answer("❌")

@dp.errors()
async def error_handler(event, exception):
    logging.error(f"Error: {exception}", exc_info=True)
    return True

async def main():
    await init_db()
    
    print("🤖 Liberty Style Bot")
    print("=" * 50)
    print(f"Token: {'✅' if TOKEN else '❌'}")
    print(f"Admin: {ADMIN_ID if ADMIN_ID else '❌'}")
    print(f"AI: {'✅' if AI_ENABLED else '⚠️'}")
    print("=" * 50)
    
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, "✅ БОТ ЗАПУЩЕНО!")
        except:
            pass
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
