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

# Настройка ИИ (Используем модель 1.5-flash, она работает стабильнее)
try:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"AI INIT ERROR: {e}")

# --- МОЗГИ БОТА ---
AI_PROMPT = """
Ты — консультант магазина 'Liberty Style'. 
Твоя задача - отвечать на вопросы клиентов про одежду.
Товар: Школьная форма (Турция, 80% хлопок, 20% эластан).
Доставка: Новая Почта (1-2 дня). Отправка в 18:00.
Оплата: Монобанк.
Цены: Спідниця-550, Блуза-450, Штани-600, Жакет-850 грн.
Размеры: XS, S, M, L, XL.
Если не знаешь ответ - пиши "Напишите менеджеру".
Отвечай кратко и вежливо.
"""

# Данные
MANAGER_LINK = "https://t.me/fuckoffaz"
CARD_NUMBER = "4874 0700 7049 2978"

PRODUCTS = {
    "skirt_pleated": {"name": "Спідниця плісирована", "price": 550, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg"},
    "blouse_classic": {"name": "Блуза класична", "price": 450, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/White_blouse.jpg/480px-White_blouse.jpg"},
    "trousers_school": {"name": "Штани шкільні", "price": 600, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Trousers.jpg/480px-Trousers.jpg"},
    "jacket_form": {"name": "Жакет шкільний", "price": 850, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg"}
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ТЕКСТЫ ---
texts = {
    "ua": {
        "welcome": "Вітаємо в Liberty Style! Оберіть мову:",
        "menu": "Головне меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_sup": "🆘 Підтримка / ШІ",
        "btn_man": "👨‍💻 Менеджер",
        "wait_payment": f"✅ Замовлення створено!\nДо сплати: <b>%price% грн</b>\nКарта: <code>{CARD_NUMBER}</code>\n\n📎 <b>Пришліть чек сюди:</b>",
        "order_done": "✅ Замовлення прийнято! Менеджер скоро зв'яжеться.",
        "ai_intro": "🤖 <b>ШІ-Помічник Liberty Style</b>\nЗапитайте мене про тканину, доставку або розміри.\n\n👇 Напишіть питання нижче:",
        "session_lost": "⚠️ <b>Увага:</b> Бот був перезавантажений.\nНатисніть 'Каталог' і оберіть товар заново.",
        "send_photo": "📷 Будь ласка, надішліть фото або скріншот чеку."
    },
    "ru": {
        "welcome": "Добро пожаловать в Liberty Style! Выберите язык:",
        "menu": "Главное меню:",
        "btn_cat": "🛍️ Каталог",
        "btn_sup": "🆘 Поддержка / ИИ",
        "btn_man": "👨‍💻 Менеджер",
        "wait_payment": f"✅ Заказ создан!\nК оплате: <b>%price% грн</b>\nКарта: <code>{CARD_NUMBER}</code>\n\n📎 <b>Пришлите чек сюда:</b>",
        "order_done": "✅ Заказ принят! Менеджер скоро свяжется.",
        "ai_intro": "🤖 <b>ИИ-Помощник Liberty Style</b>\nСпросите меня про ткань, доставку или размеры.\n\n👇 Напишите вопрос ниже:",
        "session_lost": "⚠️ <b>Внимание:</b> Бот был перезагружен.\nНажмите 'Каталог' и выберите товар заново.",
        "send_photo": "📷 Пожалуйста, отправьте фото или скриншот чека."
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

# --- FSM ---
class OrderState(StatesGroup):
    waiting_data = State()
    waiting_receipt = State()

class SupportState(StatesGroup):
    chat = State()

# --- KB ---
def get_lang_kb():
    return ReplyKeyboardBuilder().button(text="🇺🇦 UA").button(text="🇷🇺 RU").as_markup(resize_keyboard=True)

def get_menu_kb(lang):
    t = texts[lang]
    kb = ReplyKeyboardBuilder()
    kb.button(text=t["btn_cat"])
    kb.button(text=t["btn_sup"])
    kb.button(text=t["btn_man"]) # Добавил кнопку менеджера
    kb.adjust(2, 1)
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
    return kb.as_markup()

def get_admin_kb(user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ OK + ТТН", callback_data=f"ok_{user_id}")
    kb.button(text="❌ NO", callback_data=f"no_{user_id}")
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

def get_ul(uid): return user_langs.get(uid, "ua")

# МЕНЕДЖЕР
@dp.message(F.text.contains("Менеджер"))
async def call_manager(message: types.Message):
    await message.answer(f"👨‍💻 Контакт: {MANAGER_LINK}")

# CATALOG
@dp.message(F.text.contains("Каталог") | F.text.contains("Catalog"))
async def show_catalog(message: types.Message):
    await message.answer("👗 Оберіть товар:", reply_markup=get_catalog_kb())

@dp.callback_query(F.data.startswith("show_"))
async def show_item(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    item = PRODUCTS[code]
    try:
        await callback.message.answer_photo(
            item['photo'], 
            caption=f"{item['name']}\n💰 {item['price']} грн", 
            reply_markup=get_buy_kb(code)
        )
        await callback.answer()
    except:
        await callback.message.answer("Фото не грузится, но товар есть!", reply_markup=get_buy_kb(code))
        await callback.answer()

# BUY
@dp.callback_query(F.data.startswith("buy_"))
async def buy_item(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[1]
    await state.update_data(item=code, price=PRODUCTS[code]['price'])
    await state.set_state(OrderState.waiting_data)
    await callback.message.answer("✍️ Напишіть ПІБ, Телефон і Місто одним повідомленням:\n(Приклад: Іванов Іван, 0991234567, Київ НП 1)")
    await callback.answer()

@dp.message(OrderState.waiting_data)
async def process_data(message: types.Message, state: FSMContext):
    await state.update_data(info=message.text)
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    await state.set_state(OrderState.waiting_receipt)
    msg = texts[lang]["wait_payment"].replace("%price%", str(data['price']))
    await message.answer(msg, parse_mode="HTML")

# RECEIPT
@dp.message(OrderState.waiting_receipt, F.photo)
async def get_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_ul(message.from_user.id)
    user = message.from_user
    
    # Отправка админу
    try:
        txt = f"🚨 <b>НОВЕ ЗАМОВЛЕННЯ!</b>\n👤 @{user.username}\n📦 Товар: {PRODUCTS[data['item']]['name']}\n📝 Інфо: {data['info']}"
        await bot.send_message(ADMIN_ID, txt, reply_markup=get_admin_kb(user.id), parse_mode="HTML")
        await message.copy_to(ADMIN_ID)
    except: pass
    
    await message.answer(texts[lang]["order_done"], reply_markup=get_menu_kb(lang))
    await state.clear()

@dp.message(OrderState.waiting_receipt)
async def receipt_error(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["send_photo"])

# АДМИНКА
@dp.callback_query(F.data.startswith("ok_"))
async def approve_order(callback: CallbackQuery):
    user_id = callback.data.split("_")[1]
    await callback.message.answer(f"🚚 Введіть ТТН для користувача {user_id}:")
    # Тут можно добавить состояние для ТТН, но для простоты просто покажем сообщение админу

@dp.callback_query(F.data.startswith("no_"))
async def reject_order(callback: CallbackQuery):
    user_id = callback.data.split("_")[1]
    try:
        await bot.send_message(user_id, "❌ Ваше замовлення скасовано.")
        await callback.message.edit_text("❌ Замовлення відхилено.")
    except:
        await callback.message.edit_text("❌ Відхилено (Користувач заблокував бота).")

# ЛОВУШКА ДЛЯ ФОТО (Если бот забыл состояние)
@dp.message(F.photo)
async def unexpected_receipt(message: types.Message):
    lang = get_ul(message.from_user.id)
    await message.answer(texts[lang]["session_lost"], reply_markup=get_menu_kb(lang), parse_mode="HTML")

# SUPPORT / AI (ИСПРАВЛЕНО ЗАВИСАНИЕ)
@dp.message(F.text.contains("Підтримка") | F.text.contains("Поддержка"))
async def support(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    await state.set_state(SupportState.chat)
    await message.answer(texts[lang]["ai_intro"], reply_markup=get_back_kb(), parse_mode="HTML")

@dp.message(SupportState.chat)
async def ai_chat(message: types.Message, state: FSMContext):
    lang = get_ul(message.from_user.id)
    
    # Выход из чата
    if "menu" in message.text.lower() or "меню" in message.text.lower() or "back" in message.text.lower():
        await state.clear()
        await message.answer("Menu", reply_markup=get_menu_kb(lang))
        return
        
    wait = await message.answer("⏳ ...")
    try:
        # Используем to_thread чтобы не блокировать бота
        response = await asyncio.to_thread(model.generate_content, AI_PROMPT + f"\nВопрос: {message.text}")
        await bot.edit_message_text(response.text, message.chat.id, wait.message_id)
    except Exception as e:
        # Если ИИ сломался, бот не зависнет, а напишет это:
        print(f"AI Error: {e}")
        await bot.edit_message_text("😵‍💫 ШІ зараз перевантажений. Напишіть менеджеру @fuckoffaz", message.chat.id, wait.message_id)

async def main():
    await init_db()
    try: await bot.send_message(ADMIN_ID, "✅ БОТ ПЕРЕЗАПУЩЕН!")
    except: pass
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
