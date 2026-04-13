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
    CallbackQuery
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY" # Краще ховати в .env
ADMIN_ID = 843027482
GEMINI_KEY = "AIzaSyBNTVcRS468EACwmZ5gV4tINfDGbMWWUzU"
DB_NAME = "shop.db"

CARD_NUMBER = "4874 0700 7049 2978"
MANAGER_LINK = "https://t.me/polinakondratii"

AI_ENABLED = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        AI_ENABLED = True
    except Exception as e:
        logging.error(f"AI Error: {e}")

AI_PROMPT = """
Ти — консультант магазину 'Liberty Style'.
Товар: Футболка вільного крою.
Доставка: Нова Пошта. Оплата: Монобанк.
Відповідай коротко. Якщо не знаєш - "Зверніться до менеджера".
"""

# --- ТОВАРИ ---
PRODUCTS = {
    "tshirt": {
        "name_ua": "Футболка вільного крою", 
        "name_ru": "Футболка свободного кроя",
        "price": 500,
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/White_blouse.jpg/480px-White_blouse.jpg" # Заміни на своє посилання або file_id
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
        "btn_cat": "🛍️ Каталог", "btn_ai": "🤖 ШІ-асистент", "btn_manager": "👨‍💼 Менеджер",
        "catalog_title": "🛍️ <b>Каталог:</b>",
        "enter_data": "✍️ <b>Введіть дані (ПІБ, Телефон, Місто, НП):</b>",
        "wait_payment": "✅ Замовлення сформовано!\n💰 До сплати: <b>{price} грн</b>\n💳 Карта: <code>{card}</code>\n📎 <b>Надішліть скріншот сюди:</b>",
        "order_done": "✅ Прийнято! Менеджер перевірить оплату.",
        "ai_intro": "🤖 <b>ШІ-помічник</b>\nПишіть питання:",
        "manager_contact": "👨‍💼 Менеджер: {link}",
        "session_lost": "⚠️ Перезавантажте вибір в Каталозі.",
        "admin_panel": "🔧 <b>АДМІН-ПАНЕЛЬ</b>",
        "stats": "📊 Юзерів: {users}\n📦 Замовлень: {orders}",
        "cancel": "❌ Скасувати", "canceled": "Скасовано.",
        "broadcast_ask": "✍️ Введіть текст розсилки:",
        "broadcast_done": "✅ Розіслано: {count}"
    },
    "ru": {
        "welcome": "🎓 Добро пожаловать!\n\nВыберите язык:",
        "menu": "📋 Главное меню:",
        "btn_cat": "🛍️ Каталог", "btn_ai": "🤖 ИИ-ассистент", "btn_manager": "👨‍💼 Менеджер",
        "catalog_title": "🛍️ <b>Каталог:</b>",
        "enter_data": "✍️ <b>Введите данные (ФИО, Телефон, Город, НП):</b>",
        "wait_payment": "✅ Заказ сформирован!\n💰 К оплате: <b>{price} грн</b>\n💳 Карта: <code>{card}</code>\n📎 <b>Пришлите скриншот сюда:</b>",
        "order_done": "✅ Принято! Менеджер проверит оплату.",
        "ai_intro": "🤖 <b>ИИ-помощник</b>\nПишите вопрос:",
        "manager_contact": "👨‍💼 Менеджер: {link}",
        "session_lost": "⚠️ Перезагрузите выбор в Каталоге.",
        "admin_panel": "🔧 <b>АДМИН-ПАНЕЛЬ</b>",
        "stats": "📊 Юзеров: {users}\n📦 Заказов: {orders}",
        "cancel": "❌ Отменить", "canceled": "Отменено.",
        "broadcast_ask": "✍️ Введите текст рассылки:",
        "broadcast_done": "✅ Разослано: {count}"
    }
}

# --- БАЗА ДАНИХ ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ua')")
        await db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, price INTEGER, info TEXT, status TEXT DEFAULT 'pending')""")
        await db.commit()

async def add_user(user):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username))
        await db.commit()

async def set_lang_db(user_id, lang):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
        await db.commit()

async def get_lang_db(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "ua"

async def save_order(user_id, item_name, price, info):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("INSERT INTO orders (user_id, item_name, price, info) VALUES (?, ?, ?, ?)", (user_id, item_name, price, info))
        await db.commit()
        return cursor.lastrowid

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        u = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
        o = await (await db.execute("SELECT COUNT(*) FROM orders")).fetchone()
        return u[0], o[0]

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        return [row[0] for row in await (await db.execute("SELECT user_id FROM users")).fetchall()]

# --- СТАНИ ---
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
    kb = ReplyKeyboardBuilder()
    for btn in [texts[lang]["btn_cat"], texts[lang]["btn_ai"], texts[lang]["btn_manager"]]: 
        kb.button(text=btn)
    kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True)

def get_cancel_kb(lang): 
    return ReplyKeyboardBuilder().button(text=texts[lang]["cancel"]).as_markup(resize_keyboard=True)

def get_catalog_kb(lang):
    kb = InlineKeyboardBuilder()
    for code, data in PRODUCTS.items(): 
        kb.button(text=f"{data[f'name_{lang}']} - {data['price']} грн", callback_data=f"item_{code}")
    kb.adjust(1)
    return kb.as_markup()

def get_buy_kb(code, lang):
    kb = InlineKeyboardBuilder()
    lbl = "Купити" if lang == "ua" else "Купить"
    kb.button(text=f"🛒 {lbl}", callback_data=f"buy_{code}").button(text="🔙", callback_data="back_catalog")
    kb.adjust(1)
    return kb.as_markup()

def get_admin_main_kb():
    kb = InlineKeyboardBuilder().button(text="📊 Статистика", callback_data="adm_stats").button(text="📢 Розсилка", callback_data="adm_broadcast")
    kb.adjust(2)
    return kb.as_markup()

def get_admin_decision_kb(user_id):
    return InlineKeyboardBuilder().button(text="✅ OK", callback_data=f"ok_{user_id}").button(text="❌ NO", callback_data=f"no_{user_id}").as_markup()

# --- ХЕНДЛЕРИ ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await add_user(message.from_user)
    await message.answer(texts["ua"]["welcome"], reply_markup=get_lang_kb())

@dp.message(F.text.in_({"🇺🇦 Українська", "🇷🇺 Русский"}))
async def set_lang(message: types.Message):
    lang = "ua" if "🇺🇦" in message.text else "ru"
    await set_lang_db(message.from_user.id, lang)
    await message.answer(texts[lang]["menu"], reply_markup=get_menu_kb(lang))

@dp.message(F.text.in_({"❌ Скасувати", "❌ Отменить"}))
async def cancel_action(message: types.Message, state: FSMContext):
    lang = await get_lang_db(message.from_user.id)
    await state.clear()
    await message.answer(texts[lang]["canceled"], reply_markup=get_menu_kb(lang))

@dp.message(F.text.contains("Каталог"))
async def show_catalog(message: types.Message):
    lang = await get_lang_db(message.from_user.id)
    await message.answer(texts[lang]["catalog_title"], reply_markup=get_catalog_kb(lang), parse_mode="HTML")

@dp.callback_query(F.data.startswith("item_"))
async def show_item(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    lang = await get_lang_db(callback.from_user.id)
    item = PRODUCTS[code]
    caption = f"<b>{item[f'name_{lang}']}</b>\n💰 {item['price']} грн"
    try: await callback.message.delete()
    except Exception as e: logging.error(f"Del msg: {e}")
    try: 
        await callback.message.answer_photo(item['photo'], caption=caption, reply_markup=get_buy_kb(code, lang), parse_mode="HTML")
    except Exception as e: 
        logging.error(f"Photo error: {e}")
        await callback.message.answer(caption + "\n(Без фото)", reply_markup=get_buy_kb(code, lang), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "back_catalog")
async def back(callback: CallbackQuery):
    lang = await get_lang_db(callback.from_user.id)
    try: await callback.message.delete()
    except Exception as e: logging.error(e)
    await callback.message.answer(texts[lang]["catalog_title"], reply_markup=get_catalog_kb(lang), parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def buy_start(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[1]
    lang = await get_lang_db(callback.from_user.id)
    item = PRODUCTS[code]
    await state.update_data(item_code=code, price=item['price'], item_name=item[f"name_{lang}"])
    await state.set_state(OrderState.waiting_data)
    await callback.message.answer(texts[lang]["enter_data"], reply_markup=get_cancel_kb(lang), parse_mode="HTML")
    await callback.answer()

@dp.message(OrderState.waiting_data)
async def process_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = await get_lang_db(message.from_user.id)
    if 'price' not in data: 
        return await message.answer(texts[lang]["session_lost"], reply_markup=get_menu_kb(lang))
    await state.update_data(info=message.text)
    await state.set_state(OrderState.waiting_receipt)
    await message.answer(texts[lang]["wait_payment"].format(price=data['price'], card=CARD_NUMBER), parse_mode="HTML")

@dp.message(OrderState.waiting_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = await get_lang_db(message.from_user.id)
    user = message.from_user
    if 'item_name' not in data: 
        return await message.answer(texts[lang]["session_lost"], reply_markup=get_menu_kb(lang))
    
    order_id = await save_order(user.id, data['item_name'], data['price'], data['info'])
    adm_text = f"🚨 <b>ЗАМОВЛЕННЯ #{order_id}</b>\n👤 @{user.username} ({user.id})\n👗 {data['item_name']}\n💰 {data['price']} грн\n📝 {html.escape(data['info'])}"
    try:
        await bot.send_message(ADMIN_ID, adm_text, reply_markup=get_admin_decision_kb(user.id), parse_mode="HTML")
        await message.copy_to(ADMIN_ID)
    except Exception as e: 
        logging.error(f"Admin send error: {e}")
        
    await message.answer(texts[lang]["order_done"], reply_markup=get_menu_kb(lang), parse_mode="HTML")
    await state.clear()

@dp.message(OrderState.waiting_receipt)
async def not_photo(message: types.Message): 
    await message.answer("📸 Будь ласка, надішліть фото або скріншот.")

@dp.message(F.text.contains("Менеджер"))
async def manager(message: types.Message):
    lang = await get_lang_db(message.from_user.id)
    await message.answer(texts[lang]["manager_contact"].format(link=MANAGER_LINK))

@dp.message(F.text.contains("асистент") | F.text.contains("ассистент"))
async def ai_start(message: types.Message, state: FSMContext):
    lang = await get_lang_db(message.from_user.id)
    if not AI_ENABLED: 
        return await message.answer("AI тимчасово вимкнено.")
    await state.set_state(SupportState.chat)
    await message.answer(texts[lang]["ai_intro"], reply_markup=get_cancel_kb(lang), parse_mode="HTML")

@dp.message(SupportState.chat)
async def ai_chat(message: types.Message):
    wait = await message.answer("⏳ ...")
    try:
        resp = await asyncio.to_thread(model.generate_content, f"{AI_PROMPT}\nПитання: {message.text}")
        await bot.edit_message_text(resp.text, message.chat.id, wait.message_id)
    except Exception as e: 
        logging.error(e)
        await bot.edit_message_text("Помилка AI, зверніться до менеджера.", message.chat.id, wait.message_id)

@dp.message(Command("admin"))
async def admin(message: types.Message):
    if message.from_user.id == ADMIN_ID: 
        await message.answer("Адмінка:", reply_markup=get_admin_main_kb())

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    u, o = await get_stats()
    lang = await get_lang_db(call.from_user.id)
    await call.message.edit_text(texts[lang]["stats"].format(users=u, orders=o), reply_markup=get_admin_main_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("ok_"))
async def order_ok(call: CallbackQuery):
    uid = int(call.data.split("_")[1])
    try: await bot.send_message(uid, "✅ Ваше замовлення підтверджено!")
    except Exception as e: logging.error(e)
    await call.message.edit_text(call.message.text + "\n\n✅ ПРИЙНЯТО")

@dp.callback_query(F.data.startswith("no_"))
async def order_no(call: CallbackQuery):
    uid = int(call.data.split("_")[1])
    try: await bot.send_message(uid, "❌ Замовлення скасовано.")
    except Exception as e: logging.error(e)
    await call.message.edit_text(call.message.text + "\n\n❌ СКАСОВАНО")

@dp.callback_query(F.data == "adm_broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    lang = await get_lang_db(call.from_user.id)
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
        except Exception as e: 
            logging.error(e)
            
    lang = await get_lang_db(message.from_user.id)
    await message.answer(texts[lang]["broadcast_done"].format(count=count), reply_markup=get_menu_kb(lang))
    await state.clear()

async def main():
    await init_db()
    try: await bot.send_message(ADMIN_ID, "✅ BOT STARTED")
    except Exception as e: logging.error(e)
    await dp.start_polling(bot)

if __name__ == "__main__": 
    asyncio.run(main())
