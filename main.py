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
# Варіант 1: Читати з Railway Variables (РЕКОМЕНДОВАНО)
# TOKEN = os.getenv("TELEGRAM_TOKEN", "")
# ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) if os.getenv("ADMIN_ID") else 0
# GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
# CARD_NUMBER = os.getenv("CARD_NUMBER", "1234 5678 1234 5678")
# MANAGER_LINK = os.getenv("MANAGER_LINK", "https://t.me/polinakondratii")

# Варіант 2: Якщо хочете прямо у коді (розкоментуйте рядки нижче)
TOKEN = "8528185164:AAEStuXrXQ6aSeiYRSxYXHSVLP5nZJSkqBY"
ADMIN_ID = 843027482
GEMINI_KEY = "AIzaSyBNTVcRS468EACwmZ5gV4tINfDGbMWWUzU"
CARD_NUMBER = "1234 5678 1234 5678"
MANAGER_LINK = "https://t.me/polinakondratii"

DB_NAME = "shop.db"

# Перевірка наявності токена
if not TOKEN:
    print("❌ КРИТИЧНА ПОМИЛКА: Не вказаний TELEGRAM_TOKEN!")
    print("\nДодайте у Railway Variables або розкоментуйте рядок у коді")
    sys.exit(1)

if not ADMIN_ID:
    print("⚠️ УВАГА: Не вказаний ADMIN_ID, адмін-функції не працюватимуть")

# Настройка Google AI
AI_ENABLED = False
try:
    from google import genai
    from google.genai import types as genai_types
    
    if GEMINI_KEY:
        client = genai.Client(api_key=GEMINI_KEY)
        AI_ENABLED = True
        print("✅ Google AI підключено")
    else:
        print("⚠️ GEMINI_API_KEY не вказаний, AI вимкнено")
except ImportError:
    print("⚠️ Бібліотека google-genai не встановлена")
    print("   Встановіть: pip install google-genai")
except Exception as e:
    print(f"⚠️ AI недоступний: {e}")

# --- ПРОМПТ ДЛЯ AI ---
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
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# --- ТЕКСТЫ ---
texts = {
    "ua": {
        "welcome": "🎓 Вітаємо в Liberty Style!\n\nОберіть мову для продовження:",
        "menu": "📋 Головне меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_ai": "🤖 ШІ-асистент",
        "btn_manager": "👨‍💼 Менеджер",
        "wait_payment": "✅ Замовлення створено!\n\n💰 До сплати: <b>{price} грн</b>\n💳 Карта Monobank:\n<code>{card}</code>\n\n📎 <b>Надішліть скріншот оплати:</b>",
        "order_done": "✅ Замовлення прийнято!\n\n📞 Менеджер зв'яжеться протягом години.\nОчікуйте дзвінок або повідомлення.",
        "ai_intro": "🤖 Привіт! Я ШІ-помічник Liberty Style.\n\n❓ Запитайте мене про:\n• Розміри та таблиці розмірів\n• Склад тканини\n• Умови доставки\n• Способи оплати\n\n💬 Або напишіть 'меню' для виходу",
        "session_lost": "⚠️ <b>Сеанс втрачено</b>\n\nБот був перезавантажений.\nБудь ласка, почніть замовлення заново через Каталог.",
        "catalog_title": "🛍️ Наш асортимент:\n\nОберіть товар для перегляду:",
        "enter_data": "✍️ <b>Введіть дані для замовлення:</b>\n\n📝 ПІБ (повністю)\n📱 Номер телефону\n📍 Місто та відділення Нової Пошти\n\n<i>Приклад:\nІванова Марія Петрівна\n+380991234567\nКиїв, відділення №15</i>",
        "manager_contact": "👨‍💼 <b>Зв'язок з менеджером:</b>\n\n{link}\n\nМенеджер онлайн та готовий відповісти на всі питання!",
        "no_ai": "⚠️ ШІ-асистент тимчасово недоступний.\n\n👨‍💼 Зверніться до менеджера:\n{link}"
    },
    "ru": {
        "welcome": "🎓 Добро пожаловать в Liberty Style!\n\nВыберите язык для продолжения:",
        "menu": "📋 Главное меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_ai": "🤖 ИИ-ассистент",
        "btn_manager": "👨‍💼 Менеджер",
        "wait_payment": "✅ Заказ создан!\n\n💰 К оплате: <b>{price} грн</b>\n💳 Карта Monobank:\n<code>{card}</code>\n\n📎 <b>Пришлите скриншот оплаты:</b>",
        "order_done": "✅ Заказ принят!\n\n📞 Менеджер свяжется в течение часа.\nОжидайте звонок или сообщение.",
        "ai_intro": "🤖 Привет! Я ИИ-помощник Liberty Style.\n\n❓ Спросите меня о:\n• Размерах и таблицах размеров\n• Составе ткани\n• Условиях доставки\n• Способах оплаты\n\n💬 Или напишите 'меню' для выхода",
        "session_lost": "⚠️ <b>Сеанс потерян</b>\n\nБот был перезагружен.\nПожалуйста, начните заказ заново через Каталог.",
        "catalog_title": "🛍️ Наш ассортимент:\n\nВыберите товар для просмотра:",
        "enter_data": "✍️ <b>Введите данные для заказа:</b>\n\n📝 ФИО (полностью)\n📱 Номер телефона\n📍 Город и отделение Новой Почты\n\n<i>Пример:\nИванова Мария Петровна\n+380991234567\nКиев, отделение №15</i>",
        "manager_contact": "👨‍💼 <b>Связь с менеджером:</b>\n\n{link}\n\nМенеджер онлайн и готов ответить на все вопросы!",
        "no_ai": "⚠️ ИИ-ассистент временно недоступен.\n\n👨‍💼 Обратитесь к менеджеру:\n{link}"
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
        cursor = await db.execute(
            "INSERT INTO orders (user_id, item_code, user_info, price) VALUES (?, ?, ?, ?)",
            (user_id, item_code, user_info, price)
        )
        await db.commit()
        return cursor.lastrowid

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
    
    logging.info(f"User {message.from_user.id} (@{message.from_user.username}) started bot")
    
    await message.answer(
        texts["ua"]["welcome"], 
        reply_markup=get_lang_kb()
    )

@dp.message(F.text.in_({"🇺🇦 Українська", "🇷🇺 Русский"}))
async def set_lang(message: types.Message):
    lang = "ua" if "🇺🇦" in message.text else "ru"
    user_langs[message.from_user.id] = lang
    
    logging.info(f"User {message.from_user.id} selected language: {lang}")
    
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
    item = PRODUCTS.get(code)
    
    if not item:
        await callback.answer("Товар не знайдено")
        return
    
    caption = f"<b>{item['name']}</b>\n\n{item.get('desc', '')}\n\n💰 Ціна: <b>{item['price']} грн</b>"
    
    try:
        await callback.message.answer_photo(
            item['photo'], 
            caption=caption,
            reply_markup=get_buy_kb(code),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Photo error for {code}: {e}")
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
    
    # Зберігаємо у БД
    try:
        order_id = await save_order(user.id, data['item'], data['info'], data['price'])
    except Exception as e:
        logging.error(f"DB save error: {e}")
        order_id = int(datetime.now().timestamp())
    
    # Надсилаємо адміну
    if ADMIN_ID:
        try:
            txt = (
                f"🚨 <b>НОВЕ ЗАМОВЛЕННЯ #{order_id}</b>\n\n"
                f"👤 @{user.username or 'без_username'} (ID: {user.id})\n"
                f"📦 {PRODUCTS[data['item']]['name']}\n"
                f"💰 {data['price']} грн\n\n"
                f"📝 <b>Дані клієнта:</b>\n{data['info']}\n\n"
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

@dp.message(F.photo)
async def unexpected_receipt(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(
        texts[lang]["session_lost"], 
        reply_markup=get_menu_kb(lang),
        parse_mode="HTML"
    )

# MANAGER
@dp.message(F.text.contains("Менеджер"))
async def contact_manager(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(
        texts[lang]["manager_contact"].format(link=MANAGER_LINK),
        parse_mode="HTML"
    )

# AI
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
    # Вихід
    if any(word in message.text.lower() for word in ["каталог", "меню", "menu", "назад", "вихід", "выход"]):
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
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=f"{AI_PROMPT}\n\nПитання: {message.text}"
        )
        
        answer_text = response.text if hasattr(response, 'text') else "Вибачте, не зміг обробити запит"
        
        await bot.edit_message_text(
            answer_text, 
            message.chat.id, 
            wait.message_id
        )
    except Exception as e:
        logging.error(f"AI error: {e}")
        await bot.edit_message_text(
            f"⚠️ Помилка ШІ.\n\n👨‍💼 Зверніться до менеджера:\n{MANAGER_LINK}",
            message.chat.id, 
            wait.message_id
        )

# ADMIN CALLBACKS
@dp.callback_query(F.data.startswith("ok_"))
async def admin_approve(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[1])
    
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>ПІДТВЕРДЖЕНО</b>",
        reply_markup=None,
        parse_mode="HTML"
    )
    
    try:
        await bot.send_message(
            user_id,
            "✅ Ваше замовлення підтверджено!\n\n📦 Менеджер надішле номер ТТН протягом години."
        )
    except:
        pass
    
    await callback.answer("✅ Підтверджено")

@dp.callback_query(F.data.startswith("no_"))
async def admin_reject(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[1])
    
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ВІДХИЛЕНО</b>",
        reply_markup=None,
        parse_mode="HTML"
    )
    
    try:
        await bot.send_message(
            user_id,
            f"❌ Виникла проблема з оплатою.\n\n👨‍💼 Зверніться до менеджера:\n{MANAGER_LINK}"
        )
    except:
        pass
    
    await callback.answer("❌ Відхилено")

# ERROR HANDLER
@dp.errors()
async def error_handler(event, exception):
    logging.error(f"Update error: {exception}", exc_info=True)
    return True

async def main():
    await init_db()
    
    print("🤖 Liberty Style Bot")
    print("=" * 50)
    print(f"✅ Token: {'Встановлено' if TOKEN else '❌ НЕМАЄ'}")
    print(f"✅ Admin ID: {ADMIN_ID if ADMIN_ID else '❌ НЕ ВКАЗАНО'}")
    print(f"✅ AI: {'Активовано' if AI_ENABLED else '⚠️ Вимкнено'}")
    print("=" * 50)
    
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, "✅ БОТ ЗАПУЩЕНО!")
        except Exception as e:
            logging.error(f"Cannot notify admin: {e}")
    
    logging.info("🚀 Bot started and polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
