import asyncio
import logging
import sys
import os
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

# --- КОНФИГУРАЦИЯ (БЕЗПЕЧНА) ---
TOKEN = os.getenv("8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY", "")
ADMIN_ID = int(os.getenv("843027482", "0"))
GEMINI_KEY = os.getenv("AIzaSyBDEXCPh7-Ryo6gjK5e-8SjA4Gl9Ga4BLQ", "")
CARD_NUMBER = os.getenv("4874 0700 7049 2978", "")
MANAGER_LINK = os.getenv("MANAGER_LINK", "https://t.me/fuckoffaz")
DB_NAME = "shop.db"

# Перевірка наявності токенів
if not TOKEN or not ADMIN_ID or not GEMINI_KEY:
    print("❌ ПОМИЛКА: Не вказані змінні оточення!")
    print("Потрібні: TELEGRAM_TOKEN, ADMIN_ID, GEMINI_API_KEY")
    sys.exit(1)

# Настройка ИИ
try:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-pro')
    AI_ENABLED = True
except Exception as e:
    print(f"⚠️ AI недоступний: {e}")
    AI_ENABLED = False

# --- МОЗГИ БОТА ---
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
    "skirt_pleated": {
        "name": "Спідниця плісирована", 
        "price": 550, 
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg",
        "desc": "Класична шкільна спідниця, 80% бавовна"
    },
    "blouse_classic": {
        "name": "Блуза класична", 
        "price": 450, 
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/White_blouse.jpg/480px-White_blouse.jpg",
        "desc": "Біла шкільна блуза, дихаюча тканина"
    },
    "trousers_school": {
        "name": "Штани шкільні", 
        "price": 600, 
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Trousers.jpg/480px-Trousers.jpg",
        "desc": "Класичні шкільні штани"
    },
    "jacket_form": {
        "name": "Жакет шкільний", 
        "price": 850, 
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg",
        "desc": "Елегантний жакет для урочистих подій"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ТЕКСТЫ ---
texts = {
    "ua": {
        "welcome": "Вітаємо в Liberty Style! 🎓\n\nОберіть мову:",
        "menu": "📋 Головне меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_sup": "🆘 Підтримка",
        "btn_ai": "🤖 ШІ-асистент",
        "btn_manager": "👨‍💼 Менеджер",
        "wait_payment": "✅ Замовлення створено!\n\n💰 До сплати: <b>{price} грн</b>\n💳 Карта: <code>{card}</code>\n\n📎 <b>Надішліть скріншот оплати:</b>",
        "order_done": "✅ Замовлення прийнято!\n\nМенеджер зв'яжеться протягом години.",
        "ai_intro": "🤖 Привіт! Я ШІ-помічник Liberty Style.\n\nЗапитайте мене про:\n• Розміри\n• Тканину\n• Доставку\n• Оплату",
        "session_lost": "⚠️ <b>Увага:</b> Бот був перезавантажений.\n\nБудь ласка, оберіть товар заново через Каталог.",
        "catalog_title": "🛍️ Наш асортимент:",
        "enter_data": "✍️ Введіть дані для замовлення:\n\n📝 ПІБ\n📱 Телефон\n📍 Місто та відділення НП\n\n<i>Приклад: Іванова Марія, 0991234567, Київ НП №15</i>",
        "manager_contact": "👨‍💼 Зв'язок з менеджером:\n{link}",
        "no_ai": "⚠️ ШІ-асистент тимчасово недоступний.\nЗверніться до менеджера: {link}"
    },
    "ru": {
        "welcome": "Добро пожаловать в Liberty Style! 🎓\n\nВыберите язык:",
        "menu": "📋 Главное меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_sup": "🆘 Поддержка",
        "btn_ai": "🤖 ИИ-ассистент",
        "btn_manager": "👨‍💼 Менеджер",
        "wait_payment": "✅ Заказ создан!\n\n💰 К оплате: <b>{price} грн</b>\n💳 Карта: <code>{card}</code>\n\n📎 <b>Пришлите скриншот оплаты:</b>",
        "order_done": "✅ Заказ принят!\n\nМенеджер свяжется в течение часа.",
        "ai_intro": "🤖 Привет! Я ИИ-помощник Liberty Style.\n\nСпросите меня о:\n• Размерах\n• Ткани\n• Доставке\n• Оплате",
        "session_lost": "⚠️ <b>Внимание:</b> Бот был перезагружен.\n\nПожалуйста, выберите товар заново через Каталог.",
        "catalog_title": "🛍️ Наш ассортимент:",
        "enter_data": "✍️ Введите данные для заказа:\n\n📝 ФИО\n📱 Телефон\n📍 Город и отделение НП\n\n<i>Пример: Иванова Мария, 0991234567, Киев НП №15</i>",
        "manager_contact": "👨‍💼 Связь с менеджером:\n{link}",
        "no_ai": "⚠️ ИИ-ассистент временно недоступен.\nОбратитесь к менеджеру: {link}"
    }
}

user_langs = {}

# --- DB ---
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
                user_info TEXT,
                price INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)
        await db.commit()

async def add_user(user):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", 
            (user.id, user.username)
        )
        await db.commit()

async def save_order(user_id, item_code, user_info, price):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO orders (user_id, item_code, user_info, price) VALUES (?, ?, ?, ?)",
            (user_id, item_code, user_info, price)
        )
        await db.commit()

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
        kb.button(
            text=f"{data['name']} - {data['price']} грн", 
            callback_data=f"show_{code}"
        )
    kb.adjust(1)
    return kb.as_markup()

def get_buy_kb(item_code):
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Купити / Купить", callback_data=f"buy_{item_code}")
    kb.adjust(1)
    return kb.as_markup()

def get_admin_kb(user_id, order_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Підтвердити", callback_data=f"ok_{user_id}_{order_id}")
    kb.button(text="❌ Відхилити", callback_data=f"no_{user_id}_{order_id}")
    kb.adjust(2)
    return kb.as_markup()

def get_ul(uid):
    return user_langs.get(uid, "ua")

# --- HANDLERS ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await add_user(message.from_user)
    await message.answer(
        texts["ua"]["welcome"], 
        reply_markup=get_lang_kb()
    )

@dp.message(F.text.in_({"🇺🇦 Українська", "🇷🇺 Русский"}))
async def set_lang(message: types.Message):
    lang = "ua" if "🇺🇦" in message.text else "ru"
    user_langs[message.from_user.id] = lang
    await message.answer(
        texts[lang]["menu"], 
        reply_markup=get_menu_kb(lang)
    )

# CATALOG
@dp.message(F.text.contains("Каталог"))
async def show_catalog(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(
        texts[lang]["catalog_title"], 
        reply_markup=get_catalog_kb(lang)
    )

@dp.callback_query(F.data.startswith("show_"))
async def show_item(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    item = PRODUCTS[code]
    
    caption = f"<b>{item['name']}</b>\n\n{item.get('desc', '')}\n\n💰 Ціна: <b>{item['price']} грн</b>"
    
    try:
        await callback.message.answer_photo(
            item['photo'], 
            caption=caption,
            reply_markup=get_buy_kb(code),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Photo error: {e}")
        await callback.message.answer(
            caption, 
            reply_markup=get_buy_kb(code),
            parse_mode="HTML"
        )
    
    await callback.answer()

# BUY
@dp.callback_query(F.data.startswith("buy_"))
async def buy_item(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[1]
    lang = get_ul(callback.from_user.id)
    
    await state.update_data(item=code, price=PRODUCTS[code]['price'])
    await state.set_state(OrderState.waiting_data)
    
    await callback.message.answer(
        texts[lang]["enter_data"],
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(OrderState.waiting_data)
async def process_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    
    await state.update_data(info=message.text)
    await state.set_state(OrderState.waiting_receipt)
    
    msg = texts[lang]["wait_payment"].format(
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
    
    # Сохраняем заказ в БД
    try:
        await save_order(user.id, data['item'], data['info'], data['price'])
    except Exception as e:
        logging.error(f"DB save error: {e}")
    
    # Отправка админу
    try:
        order_id = int(datetime.now().timestamp())
        txt = (
            f"🚨 <b>НОВЕ ЗАМОВЛЕННЯ #{order_id}</b>\n\n"
            f"👤 Користувач: @{user.username or 'без_username'} (ID: {user.id})\n"
            f"📦 Товар: {PRODUCTS[data['item']]['name']}\n"
            f"💰 Сума: {data['price']} грн\n"
            f"📝 Дані:\n{data['info']}\n\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await bot.send_message(
            ADMIN_ID, 
            txt, 
            reply_markup=get_admin_kb(user.id, order_id),
            parse_mode="HTML"
        )
        await message.copy_to(ADMIN_ID)
    except Exception as e:
        logging.error(f"Admin notify error: {e}")
    
    await message.answer(
        texts[lang]["order_done"], 
        reply_markup=get_menu_kb(lang)
    )
    await state.clear()

# Ловушка для фото без состояния
@dp.message(F.photo)
async def unexpected_receipt(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(
        texts[lang]["session_lost"], 
        reply_markup=get_menu_kb(lang),
        parse_mode="HTML"
    )

# MANAGER CONTACT
@dp.message(F.text.contains("Менеджер"))
async def contact_manager(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(
        texts[lang]["manager_contact"].format(link=MANAGER_LINK),
        parse_mode="HTML"
    )

# AI SUPPORT
@dp.message(F.text.contains("ШІ-асистент") | F.text.contains("ИИ-ассистент"))
async def support(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    
    if not AI_ENABLED:
        await message.answer(
            texts[lang]["no_ai"].format(link=MANAGER_LINK),
            parse_mode="HTML"
        )
        return
    
    await state.set_state(SupportState.chat)
    await message.answer(texts[lang]["ai_intro"])

@dp.message(SupportState.chat)
async def ai_chat(message: types.Message, state: FSMContext):
    # Выход из чата
    if any(word in message.text.lower() for word in ["каталог", "меню", "menu", "вихід", "выход"]):
        await state.clear()
        lang = get_ul(message.from_user.id)
        await message.answer(
            texts[lang]["menu"], 
            reply_markup=get_menu_kb(lang)
        )
        return
    
    if not AI_ENABLED:
        lang = get_ul(message.from_user.id)
        await message.answer(texts[lang]["no_ai"].format(link=MANAGER_LINK))
        return
    
    wait = await message.answer("⏳ Думаю...")
    
    try:
        response = await asyncio.to_thread(
            model.generate_content, 
            AI_PROMPT + f"\n\nПитання клієнта: {message.text}"
        )
        await bot.edit_message_text(
            response.text, 
            message.chat.id, 
            wait.message_id
        )
    except Exception as e:
        logging.error(f"AI error: {e}")
        await bot.edit_message_text(
            f"⚠️ Помилка ШІ. Зверніться до менеджера:\n{MANAGER_LINK}",
            message.chat.id, 
            wait.message_id
        )

# ADMIN CALLBACKS
@dp.callback_query(F.data.startswith("ok_"))
async def admin_approve(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[1])
    
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ ПІДТВЕРДЖЕНО",
        reply_markup=None
    )
    
    try:
        await bot.send_message(
            user_id,
            "✅ Ваше замовлення підтверджено!\nМенеджер надішле ТТН протягом години."
        )
    except:
        pass
    
    await callback.answer("✅ Підтверджено")

@dp.callback_query(F.data.startswith("no_"))
async def admin_reject(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[1])
    
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ ВІДХИЛЕНО",
        reply_markup=None
    )
    
    try:
        await bot.send_message(
            user_id,
            f"❌ Виникла проблема з оплатою.\nЗверніться до менеджера: {MANAGER_LINK}"
        )
    except:
        pass
    
    await callback.answer("❌ Відхилено")

# ERROR HANDLER
@dp.errors()
async def error_handler(event, exception):
    logging.error(f"Error: {exception}", exc_info=True)
    return True

async def main():
    await init_db()
    
    try:
        await bot.send_message(ADMIN_ID, "✅ БОТ ЗАПУЩЕНО!")
    except Exception as e:
        logging.error(f"Cannot notify admin: {e}")
    
    logging.info("🚀 Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
