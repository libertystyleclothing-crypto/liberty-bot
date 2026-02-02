import asyncio
import logging
import sys  # <--- Добавили библиотеку для исправления логов
import aiofiles
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8528185164:AAEqb_Yr8DYxWNzRlPPOHODf6WPY2qcnO5U" 
ADMIN_ID = 843027482  # <--- ВСТАВЬ СВОЙ ID
USERS_FILE = "users.txt" 

# Ссылки и данные
MANAGER_LINK = "https://t.me/fuckoffaz"
INSTAGRAM_LINK = "https://www.instagram.com/_liberty.style_/" # Замени на свою
CARD_NUMBER = "4874 0700 7049 2978"

# Инициализация
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- ИСПРАВЛЕНИЕ ЛОГОВ ---
# Теперь логи летят в sys.stdout, и Railway не будет показывать их красным
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ТЕКСТЫ (HTML) ---
texts = {
    "ua": {
        "welcome": "Ласкаво просимо в Liberty Style! Оберіть мову:",
        "main_menu": "Головне меню 🛍️",
        "catalog": "👗 Каталог / Розміри",
        "payment_delivery": "💳 Оплата та Доставка",
        "support": "🆘 Підтримка / Соцмережі",
        "make_order": "🛒 Зробити замовлення",
        "sizes_info": "📏 <b>Розмірна сітка Liberty Style:</b>\n\nXS: 122-128 см\nS: 128-134 см\nM: 134-140 см\nL: 140-146 см\nXL: 146-152 см\n\nМи допоможемо підібрати ідеальний розмір!",
        "pay_info": f"🚚 <b>Доставка:</b> Нова Пошта.\n💳 <b>Оплата:</b> Переказ на карту.\n\nРеквізити: <code>{CARD_NUMBER}</code>\n(Натисніть на номер, щоб скопіювати).\nПри замовленні бот попросить скріншот оплати.",
        "support_info": f"📞 <b>Контакти:</b>\nМенеджер: {MANAGER_LINK}\n\n👇 <b>Підписуйтесь на нас:</b>",
        "ask_item": "Напишіть назву товару, розмір та кількість:",
        "ask_name": "Напишіть ПІБ отримувача:",
        "ask_phone": "Напишіть номер телефону:",
        "ask_city": "Напишіть Місто та номер відділення Нової Пошти:",
        "wait_payment": f"Супер! Ваше замовлення сформовано.\n\nБудь ласка, переведіть кошти на карту:\n<code>{CARD_NUMBER}</code>\n\n📎 <b>Пришліть сюди квитанцію (скріншот) про оплату.</b>",
        "order_done": "✅ Дякуємо! Ваше замовлення та чек відправлені менеджеру. Ми скоро зв'яжемося з вами!",
        "send_photo_please": "Будь ласка, надішліть саме фото/скріншот квитанції.",
        "new_order_admin": "🚨 <b>НОВЕ ЗАМОВЛЕННЯ!</b>"
    },
    "ru": {
        "welcome": "Добро пожаловать в Liberty Style! Выберите язык:",
        "main_menu": "Главное меню 🛍️",
        "catalog": "👗 Каталог / Размеры",
        "payment_delivery": "💳 Оплата и Доставка",
        "support": "🆘 Поддержка / Соцсети",
        "make_order": "🛒 Сделать заказ",
        "sizes_info": "📏 <b>Размерная сетка Liberty Style:</b>\n\nXS: 122-128 см\nS: 128-134 см\nM: 134-140 см\nL: 140-146 см\nXL: 146-152 см\n\nМы поможем подобрать идеальный размер!",
        "pay_info": f"🚚 <b>Доставка:</b> Новая Почта.\n💳 <b>Оплата:</b> Перевод на карту.\n\nРеквизиты: <code>{CARD_NUMBER}</code>\n(Нажмите на номер, чтобы скопировать).\nПри заказе бот попросит скриншот оплаты.",
        "support_info": f"📞 <b>Контакты:</b>\nМенеджер: {MANAGER_LINK}\n\n👇 <b>Подписывайтесь на нас:</b>",
        "ask_item": "Напишите название товара, размер и количество:",
        "ask_name": "Напишите ФИО получателя:",
        "ask_phone": "Напишите номер телефона:",
        "ask_city": "Напишите Город и номер отделения Новой Почты:",
        "wait_payment": f"Супер! Ваш заказ сформирован.\n\nПожалуйста, переведите средства на карту:\n<code>{CARD_NUMBER}</code>\n\n📎 <b>Пришлите сюда квитанцию (скриншот) об оплате.</b>",
        "order_done": "✅ Спасибо! Ваш заказ и чек отправлены менеджеру. Мы скоро свяжемся с вами!",
        "send_photo_please": "Пожалуйста, отправьте именно фото/скриншот квитанции.",
        "new_order_admin": "🚨 <b>НОВЫЙ ЗАКАЗ!</b>"
    }
}

user_langs = {}

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
async def add_user(user_id):
    if not os.path.exists(USERS_FILE):
        async with aiofiles.open(USERS_FILE, "w") as f:
            await f.write("")
    async with aiofiles.open(USERS_FILE, "r") as f:
        users = await f.read()
        users_list = users.split()
    if str(user_id) not in users_list:
        async with aiofiles.open(USERS_FILE, "a") as f:
            await f.write(f"{user_id}\n")

async def get_all_users():
    if not os.path.exists(USERS_FILE):
        return []
    async with aiofiles.open(USERS_FILE, "r") as f:
        data = await f.read()
        return data.split()

# --- FSM ---
class OrderState(StatesGroup):
    waiting_item = State()
    waiting_name = State()
    waiting_phone = State()
    waiting_city = State()
    waiting_receipt = State()

class AdminState(StatesGroup):
    waiting_broadcast_text = State()

# --- КЛАВИАТУРЫ ---
def get_lang_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🇺🇦 Українська")
    kb.button(text="🇷🇺 Русский")
    return kb.as_markup(resize_keyboard=True)

def get_main_kb(lang):
    t = texts[lang]
    kb = ReplyKeyboardBuilder()
    kb.button(text=t["catalog"])
    kb.button(text=t["make_order"])
    kb.button(text=t["payment_delivery"])
    kb.button(text=t["support"])
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)

def get_social_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📸 Instagram", url=INSTAGRAM_LINK)
    kb.button(text="👨‍💻 Менеджер", url=MANAGER_LINK)
    return kb.as_markup()

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await add_user(message.from_user.id)
    await message.answer("🇺🇦 Оберіть мову / 🇷🇺 Выберите язык", reply_markup=get_lang_kb())

@dp.message(F.text.in_({"🇺🇦 Українська", "🇷🇺 Русский"}))
async def set_language(message: types.Message):
    lang = "ua" if "Українська" in message.text else "ru"
    user_langs[message.from_user.id] = lang
    await message.answer(texts[lang]["main_menu"], reply_markup=get_main_kb(lang))

def get_u_lang(user_id):
    return user_langs.get(user_id, "ua")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Каталог", "Catalog"]))
async def show_catalog(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    # Если хочешь фото вместо текста, используй:
    # await message.answer_photo(photo="ССЫЛКА", caption=texts[lang]["sizes_info"], parse_mode="HTML")
    await message.answer(texts[lang]["sizes_info"], parse_mode="HTML")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Оплата", "Payment"]))
async def show_payment(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["pay_info"], parse_mode="HTML")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Підтримка", "Поддержка", "Support"]))
async def show_support(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["support_info"], reply_markup=get_social_kb(), parse_mode="HTML")

# --- ЗАКАЗ ---
@dp.message(lambda msg: any(txt in msg.text for txt in ["Зробити замовлення", "Сделать заказ"]))
async def start_order(message: types.Message, state: FSMContext):
    lang = get_u_lang(message.from_user.id)
    await state.set_state(OrderState.waiting_item)
    await message.answer(texts[lang]["ask_item"], reply_markup=types.ReplyKeyboardRemove())

@dp.message(OrderState.waiting_item)
async def process_item(message: types.Message, state: FSMContext):
    await state.update_data(item=message.text)
    lang = get_u_lang(message.from_user.id)
    await state.set_state(OrderState.waiting_name)
    await message.answer(texts[lang]["ask_name"])

@dp.message(OrderState.waiting_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    lang = get_u_lang(message.from_user.id)
    await state.set_state(OrderState.waiting_phone)
    await message.answer(texts[lang]["ask_phone"])

@dp.message(OrderState.waiting_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    lang = get_u_lang(message.from_user.id)
    await state.set_state(OrderState.waiting_city)
    await message.answer(texts[lang]["ask_city"])

@dp.message(OrderState.waiting_city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    lang = get_u_lang(message.from_user.id)
    await state.set_state(OrderState.waiting_receipt)
    await message.answer(texts[lang]["wait_payment"], parse_mode="HTML")

@dp.message(OrderState.waiting_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_u_lang(message.from_user.id)
    user = message.from_user

    admin_text = (
        f"{texts[lang]['new_order_admin']}\n\n"
        f"👤 <b>Покупець:</b> @{user.username} (ID: {user.id})\n"
        f"👗 <b>Товар:</b> {data['item']}\n"
        f"📛 <b>ПІБ:</b> {data['name']}\n"
        f"📱 <b>Телефон:</b> {data['phone']}\n"
        f"🏙 <b>Доставка:</b> {data['city']}\n\n"
        f"👇 <b>Скріншот оплати нижче:</b>"
    )

    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    await message.copy_to(ADMIN_ID)
    
    await message.answer(texts[lang]["order_done"], reply_markup=get_main_kb(lang))
    await state.clear()

@dp.message(OrderState.waiting_receipt)
async def process_receipt_invalid(message: types.Message, state: FSMContext):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["send_photo_please"])

# --- РАССЫЛКА ---
@dp.message(Command("sendall"))
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📝 Введите текст (или фото с текстом) для рассылки:")
    await state.set_state(AdminState.waiting_broadcast_text)

@dp.message(AdminState.waiting_broadcast_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    users = await get_all_users()
    count = 0
    await message.answer(f"📢 Рассылка на {len(users)} чел...")
    for user_id in users:
        try:
            await message.copy_to(chat_id=int(user_id))
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"✅ Успешно отправлено: {count}")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
