import asyncio
import logging
import sys
import os
import html
import aiosqlite
import aiofiles
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

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8528185164:AAEqb_Yr8DYxWNzRlPPOHODf6WPY2qcnO5U" 
ADMIN_ID = 843027482 
GEMINI_KEY = "AIzaSyBDEXCPh7-Ryo6gjK5e-8SjA4Gl9Ga4BLQ"
DB_NAME = "shop.db"

# Настройка ИИ (Gemini 1.5 Flash - самая быстрая и стабильная)
try:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"AI ERROR: {e}")

# --- МОЗГИ БОТА ---
AI_PROMPT = """
Ты — консультант магазина школьной одежды 'Liberty Style'.
Отвечай коротко, вежливо, используй смайлики.
Товар: Школьная форма (Турция, 80% хлопок). Не кашлатится.
Доставка: Новая Почта (1-2 дня). Отправка в 18:00.
Оплата: Монобанк.
Цены: Спідниця-550, Блуза-450, Штани-600, Жакет-850 грн.
Размеры: XS (122), S (128), M (134), L (140), XL (146).
Если не знаешь ответ — пиши "Напишіть менеджеру: @fuckoffaz".
"""

# Данные
MANAGER_LINK = "https://t.me/fuckoffaz"
CARD_NUMBER = "4874 0700 7049 2978"

# Используем надежные ссылки на фото (Википедия), чтобы не было ошибки "Content not viewable"
PRODUCTS = {
    "skirt_pleated": {"name": "Спідниця плісирована", "price": 550, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Fashion_School_Girl.jpg/320px-Fashion_School_Girl.jpg"},
    "blouse_classic": {"name": "Блуза класична", "price": 450, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/White_blouse.jpg/320px-White_blouse.jpg"},
    "trousers_school": {"name": "Штани шкільні", "price": 600, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Trousers.jpg/320px-Trousers.jpg"},
    "jacket_form": {"name": "Жакет шкільний", "price": 850, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/320px-Girl_in_a_jacket_and_pleated_skirt.jpg"}
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ТЕКСТЫ ---
texts = {
    "ua": {
        "welcome": "Вітаємо в Liberty Style! Оберіть мову:",
        "menu": "Головне меню:",
        "btn_sizes": "📏 Розміри",
        "btn_pay": "💳 Оплата",
        "btn_delivery": "🚚 Доставка",
        "btn_support": "🤖 ШІ-Помічник / Чат",
        "btn_status": "🔎 Статус/ТТН",
        "btn_catalog": "🛍️ Замовлення / Каталог",
        "btn_return": "♻️ Обмін і повернення",
        "btn_problems": "❗️ Проблеми з замовленням",
        
        "info_sizes": "📏 <b>Розмірна сітка:</b>\nXS: 122-128 | S: 128-134\nM: 134-140 | L: 140-146\nXL: 146-152 см",
        "info_pay": f"💳 <b>Оплата:</b>\nМонобанк: <code>{CARD_NUMBER}</code>",
        "info_delivery": "🚚 <b>Доставка:</b>\nНова Пошта (1-2 дні). Відправка о 18:00.",
        "info_return": "♻️ <b>Обмін:</b> 14 днів (якщо є бірки).",
        "info_status": "🔎 ТТН надішлемо сюди. Якщо довго немає — пишіть менеджеру.",
        
        "wait_payment": f"✅ Замовлення створено!\nДо сплати: <b>%price% грн</b>\nКарта: <code>{CARD_NUMBER}</code>\n\n📎 <b>Пришліть чек сюди (фото або файл):</b>",
        "order_done": "✅ <b>Дякуємо!</b> Замовлення прийнято. Менеджер скоро напише.",
        "ai_intro": "🤖 <b>Я — ШІ-Помічник.</b>\nЗапитайте про тканину, розміри чи доставку.\n👇 Пишіть питання:",
        "session_lost": "⚠️ <b>Сесія оновилась.</b>\nНатисніть 'Каталог' і оберіть товар знову.",
        "send_photo": "📷 Будь ласка, надішліть фото або скріншот чеку.",
        "new_order_admin": "🚨 <b>НОВЕ ЗАМОВЛЕННЯ!</b>",
        "item_select": "Оберіть товар:",
        "ask_name": "✍️ Напишіть ПІБ, Телефон і Місто одним повідомленням:"
    },
    "ru": {
        "welcome": "Добро пожаловать в Liberty Style! Выберите язык:",
        "menu": "Главное меню:",
        "btn_sizes": "📏 Размеры",
        "btn_pay": "💳 Оплата",
        "btn_delivery": "🚚 Доставка",
        "btn_support": "🤖 ИИ-Помощник / Чат",
        "btn_status": "🔎 Статус/ТТН",
        "btn_catalog": "🛍️ Заказ / Каталог",
        "btn_return": "♻️ Обмен и возврат",
        "btn_problems": "❗️ Проблемы с заказом",
        
        "info_sizes": "📏 <b>Размеры:</b>\nXS: 122-128 | S: 128-134\nM: 134-140 | L: 140-146\nXL: 146-152 см",
        "info_pay": f"💳 <b>Оплата:</b>\nМонобанк: <code>{CARD_NUMBER}</code>",
        "info_delivery": "🚚 <b>Доставка:</b>\nНовая Почта (1-2 дня). Отправка в 18:00.",
        "info_return": "♻️ <b>Обмен:</b> 14 дней (если есть бирки).",
        "info_status": "🔎 ТТН пришлем сюда. Если долго нет — пишите менеджеру.",
        
        "wait_payment": f"✅ Заказ создан!\nК оплате: <b>%price% грн</b>\nКарта: <code>{CARD_NUMBER}</code>\n\n📎 <b>Пришлите чек сюда (фото или файл):</b>",
        "order_done": "✅ <b>Спасибо!</b> Заказ принят. Менеджер скоро напишет.",
        "ai_intro": "🤖 <b>Я — ИИ-Помощник.</b>\nСпросите про ткань, размеры или доставку.\n👇 Пишите вопрос:",
        "session_lost": "⚠️ <b>Сессия обновилась.</b>\nНажмите 'Каталог' и выберите товар снова.",
        "send_photo": "📷 Пожалуйста, отправьте фото или скриншот чека.",
        "new_order_admin": "🚨 <b>НОВЫЙ ЗАКАЗ!</b>",
        "item_select": "Выберите товар:",
        "ask_name": "✍️ Напишите ФИО, Телефон и Город одним сообщением:"
    }
}

user_langs = {}

# --- DB ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)")
        await db.commit()

async def add_user(user):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username))
        await db.commit()

async def get_all_users_db():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_stats_text():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        count = await cursor.fetchone()
        return f"📊 Всего пользователей: {count[0]}"

# --- FSM ---
class OrderState(StatesGroup):
    waiting_data = State() 
    waiting_receipt = State()

class SupportState(StatesGroup):
    chat = State()
    
class AdminState(StatesGroup):
    broadcast = State()
    ttn = State()

# --- KB ---
def get_lang_kb():
    return ReplyKeyboardBuilder().button(text="🇺🇦 UA").button(text="🇷🇺 RU").as_markup(resize_keyboard=True)

def get_menu_kb(lang):
    t = texts[lang]
    kb = ReplyKeyboardBuilder()
    kb.button(text=t["btn_sizes"])
    kb.button(text=t["btn_pay"])
    kb.button(text=t["btn_delivery"])
    kb.button(text=t["btn_support"])
    kb.button(text=t["btn_status"])
    kb.button(text=t["btn_catalog"])
    kb.button(text=t["btn_return"])
    kb.button(text=t["btn_problems"])
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup(resize_keyboard=True)

def get_catalog_kb():
    kb = InlineKeyboardBuilder()
    for code, data in PRODUCTS.items():
        kb.button(text=f"{data['name']} - {data['price']} грн", callback_data=f"show_{code}")
    kb.adjust(1)
    return kb.as_markup()

def get_buy_kb(item_code):
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Купити / Купить", callback_data=f"buy_{item_code}")
    kb.button(text="🔙", callback_data="back_to_catalog")
    kb.adjust(1)
    return kb.as_markup()

def get_admin_kb(user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ OK + ТТН", callback_data=f"ok_{user_id}")
    kb.button(text="❌ NO", callback_data=f"no_{user_id}")
    return kb.as_markup()

def get_admin_panel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    return kb.as_markup()

def get_back_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🔙 Menu")
    return kb.as_markup(resize_keyboard=True)

# --- HANDLERS ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await add_user(message.from_user)
    await message.answer("🇺🇦 Оберіть мову / 🇷🇺 Выберите язык", reply_markup=get_lang_kb())

@dp.message(F.text.in_({"🇺🇦 UA", "🇷🇺 RU"}))
async def set_lang(message: types.Message):
    lang = "ua" if "UA" in message.text else "ru"
    user_langs[message.from_user.id] = lang
    await message.answer(texts[lang]["menu"], reply_markup=get_menu_kb(lang))

@dp.message(Command("admin"))
async def admin_menu(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Адмінка:", reply_markup=get_admin_panel_kb())

def get_ul(uid): return user_langs.get(uid, "ua")

# --- МЕНЮ (Все кнопки) ---
@dp.message(F.text, lambda msg: any(txt in msg.text for txt in ["Розміри", "Размеры"]))
async def m_sizes(msg: types.Message): await msg.answer(texts[get_ul(msg.from_user.id)]["info_sizes"], parse_mode="HTML")

@dp.message(F.text, lambda msg: any(txt in msg.text for txt in ["Оплата", "Payment"]))
async def m_pay(msg: types.Message): await msg.answer(texts[get_ul(msg.from_user.id)]["info_pay"], parse_mode="HTML")

@dp.message(F.text, lambda msg: any(txt in msg.text for txt in ["Доставка", "Delivery"]))
async def m_del(msg: types.Message): await msg.answer(texts[get_ul(msg.from_user.id)]["info_delivery"], parse_mode="HTML")

@dp.message(F.text, lambda msg: any(txt in msg.text for txt in ["Обмін", "Обмен"]))
async def m_ret(msg: types.Message): await msg.answer(texts[get_ul(msg.from_user.id)]["info_return"], parse_mode="HTML")

@dp.message(F.text, lambda msg: any(txt in msg.text for txt in ["Статус", "ТТН"]))
async def m_stat(msg: types.Message): await msg.answer(texts[get_ul(msg.from_user.id)]["info_status"], parse_mode="HTML")

@dp.message(F.text, lambda msg: any(txt in msg.text for txt in ["Проблеми", "Проблемы"]))
async def m_prob(msg: types.Message): 
    kb = InlineKeyboardBuilder().button(text="👨‍💻 Менеджер", url=MANAGER_LINK).as_markup()
    await msg.answer(f"Напишіть менеджеру: {MANAGER_LINK}", reply_markup=kb)

# --- КАТАЛОГ И ЗАКАЗ ---
@dp.message(F.text, lambda msg: any(txt in msg.text for txt in ["Замовлення", "Заказ", "Catalog"]))
async def show_catalog(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["item_select"], reply_markup=get_catalog_kb())

@dp.callback_query(F.data.startswith("show_"))
async def show_item(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    item = PRODUCTS[code]
    try:
        await callback.message.answer_photo(
            item['photo'], 
            caption=f"<b>{item['name']}</b>\n💰 {item['price']} грн", 
            reply_markup=get_buy_kb(code),
            parse_mode="HTML"
        )
    except:
        await callback.message.answer(f"{item['name']}\n💰 {item['price']} грн", reply_markup=get_buy_kb(code))
    await callback.answer()

@dp.callback_query(F.data == "back_to_catalog")
async def back_cat(callback: CallbackQuery):
    await callback.message.answer("Каталог:", reply_markup=get_catalog_kb())
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_item(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[1]
    lang = get_ul(callback.from_user.id)
    await state.update_data(item=code, price=PRODUCTS[code]['price'])
    await state.set_state(OrderState.waiting_data)
    await callback.message.answer(texts[lang]["ask_name"])
    await callback.answer()

@dp.message(OrderState.waiting_data)
async def process_data(message: types.Message, state: FSMContext):
    await state.update_data(info=message.text)
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    await state.set_state(OrderState.waiting_receipt)
    msg = texts[lang]["wait_payment"].replace("%price%", str(data['price']))
    await message.answer(msg, parse_mode="HTML")

# --- ЧЕК ---
@dp.message(OrderState.waiting_receipt)
async def get_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    
    if not data or 'item' not in data:
        await message.answer(texts[lang]["session_lost"], reply_markup=get_menu_kb(lang), parse_mode="HTML")
        await state.clear()
        return

    # Принимаем ФОТО или ДОКУМЕНТ. Если текст - просим фото.
    if not message.photo and not message.document:
        await message.answer(texts[lang]["send_photo"])
        return

    user = message.from_user
    safe_info = html.escape(data['info'])
    item_name = PRODUCTS[data['item']]['name']
    
    txt = (
        f"{texts[lang]['new_order_admin']}\n\n"
        f"👤 @{user.username} (ID: {user.id})\n"
        f"👗 Товар: {item_name}\n"
        f"💰 {data['price']} грн\n"
        f"📝 Інфо: {safe_info}"
    )
    
    try:
        await bot.send_message(ADMIN_ID, txt, reply_markup=get_admin_kb(user.id), parse_mode="HTML")
        await message.copy_to(ADMIN_ID)
    except: pass
    
    await message.answer(texts[lang]["order_done"], reply_markup=get_menu_kb(lang), parse_mode="HTML")
    await state.clear()

# --- ИИ ---
@dp.message(F.text, lambda msg: any(txt in msg.text for txt in ["Підтримка", "Поддержка", "ШІ", "ИИ"]))
async def support(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    await state.set_state(SupportState.chat)
    await message.answer(texts[lang]["ai_intro"], reply_markup=get_back_kb(), parse_mode="HTML")

@dp.message(SupportState.chat)
async def ai_chat(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    if "menu" in message.text.lower() or "меню" in message.text.lower() or "back" in message.text.lower():
        await state.clear()
        await message.answer(texts[lang]["menu"], reply_markup=get_menu_kb(lang))
        return
        
    wait = await message.answer("⏳ ...")
    try:
        response = await asyncio.to_thread(model.generate_content, AI_PROMPT + f"\nВопрос: {message.text}")
        await bot.edit_message_text(response.text, message.chat.id, wait.message_id)
    except Exception as e:
        print(f"AI ERR: {e}")
        await bot.edit_message_text("😵‍💫 ШІ зараз зайнятий. Напишіть менеджеру @fuckoffaz", message.chat.id, wait.message_id)

# --- АДМИНКА ---
@dp.callback_query(F.data.startswith("ok_"))
async def approve_order(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]
    await state.update_data(target_id=user_id)
    await callback.message.answer(f"🚚 Введіть ТТН для {user_id}:")
    await state.set_state(AdminState.ttn)
    await callback.answer()

@dp.message(AdminState.ttn)
async def send_ttn(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    try:
        await bot.send_message(data['target_id'], f"✅ Ваше замовлення відправлено!\n📦 ТТН: <code>{message.text}</code>", parse_mode="HTML")
        await message.answer("ТТН відправлено!")
    except:
        await message.answer("Не вдалось відправити (юзер заблокував бота).")
