import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8528185164:AAEqb_Yr8DYxWNzRlPPOHODf6WPY2qcnO5U" 
ADMIN_ID = 843027482 # <--- ЗАМЕНИ НА СВОЙ ID (узнай у @userinfobot)

# Ссылки и данные
MANAGER_LINK = "https://t.me/fuckoffaz"
CARD_NUMBER = "4874 0700 7049 2978"

# Инициализация
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# --- ТЕКСТЫ И ПЕРЕВОДЫ ---
texts = {
    "ua": {
        "welcome": "Ласкаво просимо в Liberty Style! Оберіть мову:",
        "main_menu": "Головне меню 🛍️",
        "catalog": "👗 Каталог / Розміри",
        "payment_delivery": "💳 Оплата та Доставка",
        "support": "🆘 Підтримка / Обмін",
        "make_order": "🛒 Зробити замовлення",
        "back": "🔙 Назад",
        "sizes_info": "📏 **Розмірна сітка Liberty Style:**\n\nXS: 122-128 см\nS: 128-134 см\nM: 134-140 см\nL: 140-146 см\nXL: 146-152 см\n\nМи допоможемо підібрати ідеальний розмір!",
        "pay_info": f"🚚 **Доставка:** Нова Пошта.\n💳 **Оплата:** Переказ на карту.\n\nРеквізити: `{CARD_NUMBER}`\n(При замовленні бот попросить скріншот оплати).",
        "support_info": f"📞 **Контакти:**\nМенеджер: {MANAGER_LINK}\n\n♻️ **Обмін та повернення:**\nМожливий протягом 14 днів за умови збереження бірок.",
        "ask_item": "Напишіть назву товару, розмір та кількість:",
        "ask_name": "Напишіть ПІБ отримувача:",
        "ask_phone": "Напишіть номер телефону:",
        "ask_city": "Напишіть Місто та номер відділення Нової Пошти:",
        "wait_payment": f"Супер! Ваше замовлення сформовано.\n\nБудь ласка, переведіть кошти на карту:\n`{CARD_NUMBER}`\n\n📎 **Пришліть сюди квитанцію (скріншот) про оплату.**",
        "order_done": "✅ Дякуємо! Ваше замовлення та чек відправлені менеджеру. Ми скоро зв'яжемося з вами!",
        "send_photo_please": "Будь ласка, надішліть саме фото/скріншот квитанції.",
        "new_order_admin": "🚨 **НОВЕ ЗАМОВЛЕННЯ!**"
    },
    "ru": {
        "welcome": "Добро пожаловать в Liberty Style! Выберите язык:",
        "main_menu": "Главное меню 🛍️",
        "catalog": "👗 Каталог / Размеры",
        "payment_delivery": "💳 Оплата и Доставка",
        "support": "🆘 Поддержка / Обмен",
        "make_order": "🛒 Сделать заказ",
        "back": "🔙 Назад",
        "sizes_info": "📏 **Размерная сетка Liberty Style:**\n\nXS: 122-128 см\nS: 128-134 см\nM: 134-140 см\nL: 140-146 см\nXL: 146-152 см\n\nМы поможем подобрать идеальный размер!",
        "pay_info": f"🚚 **Доставка:** Новая Почта.\n💳 **Оплата:** Перевод на карту.\n\nРеквизиты: `{CARD_NUMBER}`\n(При заказе бот попросит скриншот оплаты).",
        "support_info": f"📞 **Контакты:**\nМенеджер: {MANAGER_LINK}\n\n♻️ **Обмен и возврат:**\nВозможен в течение 14 дней при сохранении бирок.",
        "ask_item": "Напишите название товара, размер и количество:",
        "ask_name": "Напишите ФИО получателя:",
        "ask_phone": "Напишите номер телефона:",
        "ask_city": "Напишите Город и номер отделения Новой Почты:",
        "wait_payment": f"Супер! Ваш заказ сформирован.\n\nПожалуйста, переведите средства на карту:\n`{CARD_NUMBER}`\n\n📎 **Пришлите сюда квитанцию (скриншот) об оплате.**",
        "order_done": "✅ Спасибо! Ваш заказ и чек отправлены менеджеру. Мы скоро свяжемся с вами!",
        "send_photo_please": "Пожалуйста, отправьте именно фото/скриншот квитанции.",
        "new_order_admin": "🚨 **НОВЫЙ ЗАКАЗ!**"
    }
}

# Пользователи выбирают язык (храним в памяти)
user_langs = {}

# --- МАШИНА СОСТОЯНИЙ (FSM) ДЛЯ ЗАКАЗА ---
class OrderState(StatesGroup):
    waiting_item = State()
    waiting_name = State()
    waiting_phone = State()
    waiting_city = State()
    waiting_receipt = State()

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

# --- ХЕНДЛЕРЫ (ОБРАБОТЧИКИ) ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🇺🇦 Оберіть мову / 🇷🇺 Выберите язык", reply_markup=get_lang_kb())

@dp.message(F.text.in_({"🇺🇦 Українська", "🇷🇺 Русский"}))
async def set_language(message: types.Message):
    lang = "ua" if "Українська" in message.text else "ru"
    user_langs[message.from_user.id] = lang
    await message.answer(texts[lang]["main_menu"], reply_markup=get_main_kb(lang))

# Универсальная функция получения языка
def get_u_lang(user_id):
    return user_langs.get(user_id, "ua")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Каталог", "Catalog"]))
async def show_catalog(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["sizes_info"])

@dp.message(lambda msg: any(txt in msg.text for txt in ["Оплата", "Payment"]))
async def show_payment(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["pay_info"], parse_mode="Markdown")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Підтримка", "Поддержка", "Support"]))
async def show_support(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["support_info"])

# --- ЛОГИКА ЗАКАЗА ---

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
    # Показываем карту и просим чек
    await message.answer(texts[lang]["wait_payment"], parse_mode="Markdown")

@dp.message(OrderState.waiting_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_u_lang(message.from_user.id)
    user = message.from_user

    # Формируем отчет админу
    admin_text = (
        f"{texts[lang]['new_order_admin']}\n\n"
        f"👤 **Покупець:** @{user.username} (ID: {user.id})\n"
        f"👗 **Товар:** {data['item']}\n"
        f"📛 **ПІБ:** {data['name']}\n"
        f"📱 **Телефон:** {data['phone']}\n"
        f"🏙 **Доставка:** {data['city']}\n\n"
        f"👇 **Скріншот оплати нижче:**"
    )

    # Отправляем админу (тебе)
    await bot.send_message(ADMIN_ID, admin_text)
    # Пересылаем фото чека
    await message.copy_to(ADMIN_ID)
    
    # Отвечаем пользователю
    await message.answer(texts[lang]["order_done"], reply_markup=get_main_kb(lang))
    await state.clear()

@dp.message(OrderState.waiting_receipt)
async def process_receipt_invalid(message: types.Message, state: FSMContext):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["send_photo_please"])

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())