import asyncio
import logging
import sys
import os
import html
import aiosqlite
import google.generativeai as genai
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, FSInputFile
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# --- КОНФІГУРАЦІЯ ---
# Твої дані
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY"
ADMIN_ID = 843027482
GEMINI_KEY = "AIzaSyBNTVcRS468EACwmZ5gV4tINfDGbMWWUzU"
DB_NAME = "shop.db"

# Константи
CARD_NUMBER = "4874 0700 7049 2978"
MANAGER_LINK = "https://t.me/polinakondratii"

# Налаштування AI (Стабільна версія)
AI_ENABLED = False
try:
    if GEMINI_KEY:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        AI_ENABLED = True
        print("✅ AI підключено")
except Exception as e:
    print(f"⚠️ AI помилка: {e}")

AI_PROMPT = """
Ти — консультант магазину шкільного одягу 'Liberty Style'.
Товар: Шкільна форма (Туреччина, 80% бавовна).
Доставка: Нова Пошта (1-2 дні).
Оплата: Монобанк.
Ціни: Спідниця-550, Блуза-450, Штани-600, Жакет-850 грн.
Розміри: XS (122), S (128), M (134), L (140), XL (146).
Відповідай коротко, ввічливо, мовою клієнта (Укр/Рос).
Якщо не знаєш - пиши "Зверніться до менеджера".
"""

# --- ТОВАРИ ---
# Використовуємо надійні посилання або заглушки, щоб бот не падав
PRODUCTS = {
    "skirt": {
        "name_ua": "Спідниця плісирована", "name_ru": "Юбка плиссированная",
        "price": 550,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg"
    },
    "blouse": {
        "name_ua": "Блуза класична", "name_ru": "Блуза классическая",
        "price": 450,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/White_blouse.jpg/480px-White_blouse.jpg"
    },
    "trousers": {
        "name_ua": "Штани шкільні", "name_ru": "Брюки школьные",
        "price": 600,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Trousers.jpg/480px-Trousers.jpg"
    },
    "jacket": {
        "name_ua": "Жакет шкільний", "name_ru": "Жакет школьный",
        "price": 850,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ТЕКСТИ ---
texts = {
    "ua": {
        "welcome": "🎓 Вітаємо в Liberty Style!\n\nОберіть мову:",
        "menu": "📋 Головне меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_ai": "🤖 ШІ-асистент",
        "btn_manager": "👨‍💼 Менеджер",
        "catalog_title": "🛍️ <b>Каталог товарів:</b>\nОберіть, що вас цікавить:",
        "enter_data": "✍️ <b>Введіть дані для доставки одним повідомленням:</b>\n\n(ПІБ, Телефон, Місто, Відділення НП)\n\n<i>Приклад: Іванова Марія, 0991234567, Київ, 15</i>",
        "wait_payment": "✅ Замовлення сформовано!\n\n💰 До сплати: <b>{price} грн</b>\n💳 Карта: <code>{card}</code>\n\n📎 <b>Надішліть фото/скріншот оплати сюди:</b>",
        "order_done": "✅ <b>Прийнято!</b> Менеджер перевірить оплату і зв'яжеться з вами.",
        "ai_intro": "🤖 <b>ШІ-помічник</b>\nЗапитайте про розміри, тканину, доставку.\n👇 Пишіть питання:",
        "manager_contact": "👨‍💼 Менеджер: {link}",
        "session_lost": "⚠️ <b>Увага:</b> Бот перезавантажився. Будь ласка, оберіть товар заново в Каталозі.",
        "admin_panel": "🔧 <b>АДМІН-ПАНЕЛЬ</b>",
        "stats": "📊 <b>СТАТИСТИКА</b>\n👥 Юзерів: {users}\n📦 Замовлень: {orders}",
        "cancel": "❌ Скасувати",
        "canceled": "Операцію скасовано.",
        "broadcast_ask": "✍️ Введіть текст для розсилки всім користувачам:",
        "broadcast_done": "✅ Розсилка завершена. Отримали: {count}"
    },
    "ru": {
        "welcome": "🎓 Добро пожаловать в Liberty Style!\n\nВыберите язык:",
        "menu": "📋 Главное меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_ai": "🤖 ИИ-ассистент",
        "btn_manager": "👨‍💼 Менеджер",
        "catalog_title": "🛍️ <b>Каталог товаров:</b>\nВыберите, что вас интересует:",
        "enter_data": "✍️ <b>Введите данные для доставки одним сообщением:</b>\n\n(ФИО, Телефон, Город, Отделение НП)\n\n<i>Пример: Иванова Мария, 0991234567, Киев, 15</i>",
        "wait_payment": "✅ Заказ сформирован!\n\n💰 К оплате: <b>{price} грн</b>\n💳 Карта: <code>{card}</code>\n\n📎 <b>Пришлите фото/скриншот оплаты сюда:</b>",
        "order_done": "✅ <b>Принято!</b> Менеджер проверит оплату и свяжется с вами.",
        "ai_intro": "🤖 <b>ИИ-помощник</b>\nСпросите о размерах, ткани, доставке.\n👇 Пишите вопрос:",
        "manager_contact": "👨‍💼 Менеджер: {link}",
        "session_lost": "⚠️ <b>Внимание:</b> Бот перезагрузился. Пожалуйста, выберите товар заново в Каталоге.",
        "admin_panel": "🔧 <b>АДМИН-ПАНЕЛЬ</b>",
        "stats": "📊 <b>СТАТИСТИКА</b>\n👥 Юзеров: {users}\n📦 Заказов: {orders}",
        "cancel": "❌ Отменить",
        "canceled": "Операция отменена.",
        "broadcast_ask": "✍️ Введите текст для рассылки всем пользователям:",
        "broadcast_done": "✅ Рассылка завершена. Получили: {count}"
    }
}

user_langs = {}

# --- БАЗА ДАНИХ ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, join_date TEXT)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_name TEXT,
                price INTEGER,
                info TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        await db.commit()

async def add_user(user):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
        if not await cursor.fetchone():
            await db.execute("INSERT INTO users VALUES (?, ?, ?)", (user.id, user.username, str(datetime.now())))
            await db.commit()

async def save_order_to_db(user_id, item_name, price, info):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("INSERT INTO orders (user_id, item_name, price, info) VALUES (?, ?, ?, ?)", 
                                  (user_id, item_name, price, info))
        await db.commit()
        return cursor.lastrowid

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        u = await db.execute("SELECT COUNT(*) FROM users")
        o = await db.execute("SELECT COUNT(*) FROM orders")
        return (await u.fetchone())[0], (await o.fetchone())[0]

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        return [row[0] for row in await cursor.fetchall()]

# --- СТАНИ (FSM) ---
class OrderState(StatesGroup):
    waiting_data = State()
    waiting_receipt = State()

class SupportState(StatesGroup):
    chat = State()

class AdminState(StatesGroup):
    broadcast = State()

# --- КЛАВІАТУРИ ---
def get_lang_kb():
    return ReplyKeyboardBuilder().button(text="🇺🇦 Українська").button(text="🇷🇺 Русский").as_markup(resize_keyboard=True)

def get_menu_kb(lang):
    t = texts[lang]
    kb = ReplyKeyboardBuilder()
    kb.button(text=t["btn_cat"])
    kb.button(text=t["btn_ai"])
    kb.button(text=t["btn_manager"])
    kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True)

def get_cancel_kb(lang):
    kb = ReplyKeyboardBuilder()
    kb.button(text=texts[lang]["cancel"])
    return kb.as_markup(resize_keyboard=True)

def get_catalog_kb(lang):
    kb = InlineKeyboardBuilder()
    for code, data in PRODUCTS.items():
        name_key = f"name_{lang}"
        kb.button(text=f"{data[name_key]} - {data['price']} грн", callback_data=f"item_{code}")
    kb.adjust(1)
    return kb.as_markup()

def get_buy_kb(code, lang):
    kb = InlineKeyboardBuilder()
    lbl = "Купити" if lang == "ua" else "Купить"
    kb.button(text=f"🛒 {lbl}", callback_data=f"buy_{code}")
    kb.button(text="🔙", callback_data="back_catalog")
    kb.adjust(1)
    return kb.as_markup()

def get_admin_main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="adm_stats")
    kb.button(text="📢 Розсилка", callback_data="adm_broadcast")
    kb.adjust(2)
    return kb.as_markup()

def get_admin_decision_kb(user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ OK", callback_data=f"ok_{user_id}")
    kb.button(text="❌ NO", callback_data=f"no_{user_id}")
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

# СКАСУВАННЯ
@dp.message(F.text.in_({"❌ Скасувати", "❌ Отменить"}))
async def cancel_action(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    await state.clear()
    await message.answer(texts[lang]["canceled"], reply_markup=get_menu_kb(lang))

# КАТАЛОГ
@dp.message(F.text.contains("Каталог"))
async def show_catalog(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["catalog_title"], reply_markup=get_catalog_kb(lang))

@dp.callback_query(F.data.startswith("item_"))
async def show_item(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    lang = get_ul(callback.from_user.id)
    item = PRODUCTS[code]
    name = item[f"name_{lang}"]
    
    caption = f"<b>{name}</b>\n💰 {item['price']} грн"
    
    try:
        # Видаляємо старе, шлемо нове (надійніше)
        await callback.message.delete() 
        await callback.message.answer_photo(
            item['photo'], 
            caption=caption, 
            reply_markup=get_buy_kb(code, lang), 
            parse_mode="HTML"
        )
    except:
        # Якщо фото не вантажиться
        await callback.message.answer(caption + "\n(Фото не завантажилось)", reply_markup=get_buy_kb(code, lang), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "back_catalog")
async def back(callback: CallbackQuery):
    lang = get_ul(callback.from_user.id)
    try: await callback.message.delete()
    except: pass
    await callback.message.answer(texts[lang]["catalog_title"], reply_markup=get_catalog_kb(lang))

# ПОКУПКА
@dp.callback_query(F.data.startswith("buy_"))
async def buy_start(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[1]
    lang = get_ul(callback.from_user.id)
    item = PRODUCTS[code]
    
    await state.update_data(item_code=code, price=item['price'], item_name=item[f"name_{lang}"])
    await state.set_state(OrderState.waiting_data)
    
    # Не видаляємо фото, просто шлемо повідомлення знизу
    await callback.message.answer(texts[lang]["enter_data"], reply_markup=get_cancel_kb(lang), parse_mode="HTML")
    await callback.answer()

@dp.message(OrderState.waiting_data)
async def process_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    
    # Захист від перезавантаження бота
    if 'price' not in data:
        await message.answer(texts[lang]["session_lost"], reply_markup=get_menu_kb(lang), parse_mode="HTML")
        await state.clear()
        return

    await state.update_data(info=message.text)
    await state.set_state(OrderState.waiting_receipt)
    
    msg = texts[lang]["wait_payment"].format(price=data['price'], card=CARD_NUMBER)
    await message.answer(msg, parse_mode="HTML")

@dp.message(OrderState.waiting_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    user = message.from_user
    
    if 'item_name' not in data:
        await message.answer(texts[lang]["session_lost"], reply_markup=get_menu_kb(lang), parse_mode="HTML")
        await state.clear()
        return

    # Зберігаємо в БД (опціонально, щоб отримати ID)
    order_id = await save_order_to_db(user.id, data['item_name'], data['price'], data['info'])

    # Адміну
    admin_text = (
        f"🚨 <b>НОВЕ ЗАМОВЛЕННЯ #{order_id}</b>\n"
        f"👤 @{user.username} (ID: {user.id})\n"
        f"👗 {data['item_name']}\n"
        f"💰 {data['price']} грн\n"
        f"📝 {html.escape(data['info'])}"
    )
    
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_admin_decision_kb(user.id), parse_mode="HTML")
        await message.copy_to(ADMIN_ID)
    except: pass

    await message.answer(texts[lang]["order_done"], reply_markup=get_menu_kb(lang), parse_mode="HTML")
    await state.clear()

# ЛОВЕЦЬ ПОМИЛОК ФОТО
@dp.message(OrderState.waiting_receipt)
async def not_photo(message: types.Message):
    await message.answer("📸 Будь ласка, надішліть фото або скріншот.")

# МЕНЕДЖЕР
@dp.message(F.text.contains("Менеджер"))
async def manager(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["manager_contact"].format(link=MANAGER_LINK))

# AI
@dp.message(F.text.contains("асистент") | F.text.contains("ассистент"))
async def ai_start(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    if not AI_ENABLED:
        await message.answer("AI вимкнено.")
        return
    await state.set_state(SupportState.chat)
    await message.answer(texts[lang]["ai_intro"], reply_markup=get_cancel_kb(lang), parse_mode="HTML")

@dp.message(SupportState.chat)
async def ai_chat(message: types.Message, state: FSMContext):
    wait = await message.answer("⏳ ...")
    try:
        response = await asyncio.to_thread(
            model.generate_content, 
            f"{AI_PROMPT}\nПитання клієнта: {message.text}"
        )
        await bot.edit_message_text(response.text, message.chat.id, wait.message_id)
    except Exception as e:
        print(e)
        await bot.edit_message_text("Менеджер відповість пізніше.", message.chat.id, wait.message_id)

# АДМІНКА
@dp.message(Command("admin"))
async def admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Адмін-панель:", reply_markup=get_admin_main_kb())

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    u, o = await get_stats()
    lang = get_ul(call.from_user.id)
    await call.message.edit_text(texts[lang]["stats"].format(users=u, orders=o), reply_markup=get_admin_main_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("ok_"))
async def order_ok(call: CallbackQuery):
    uid = int(call.data.split("_")[1])
    try: await bot.send_message(uid, "✅ Ваше замовлення підтверджено! Очікуйте ТТН.")
    except: pass
    await call.message.edit_text(call.message.text + "\n\n✅ ПРИЙНЯТО")

@dp.callback_query(F.data.startswith("no_"))
async def order_no(call: CallbackQuery):
    uid = int(call.data.split("_")[1])
    try: await bot.send_message(uid, "❌ Замовлення скасовано.")
    except: pass
    await call.message.edit_text(call.message.text + "\n\n❌ СКАСОВАНО")

# РОЗСИЛКА
@dp.callback_query(F.data == "adm_broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    lang = get_ul(call.from_user.id)
    await call.message.answer(texts[lang]["broadcast_ask"], reply_markup=get_cancel_kb(lang))
    await state.set_state(AdminState.broadcast)
    await call.answer()

@dp.message(AdminState.broadcast)
async def broadcast_run(message: types.Message, state: FSMContext):
    users = await get_all_users()
    count = 0
    await message.answer("🚀 Розсилка почалась...")
    for uid in users:
        try:
            await message.copy_to(uid)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["broadcast_done"].format(count=count), reply_markup=get_menu_kb(lang))
    await state.clear()

async def main():
    await init_db()
    try: await bot.send_message(ADMIN_ID, "✅ BOT STARTED")
    except: pass
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
