import asyncio
import logging
import sys
import aiofiles
import os
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
TOKEN = "8528185164:AAEqb_Yr8DYxWNzRlPPOHODf6WPY2qcnO5U" 
ADMIN_ID = 843027482  # <--- ВСТАВЬ СВОЙ ID (ЧИСЛОМ)
USERS_FILE = "users.txt" 

# Ссылки и данные
MANAGER_LINK = "https://t.me/fuckoffaz"
INSTAGRAM_LINK = "https://www.instagram.com/_liberty.style_/" 
CARD_NUMBER = "4874 0700 7049 2978"

# --- БАЗА ТОВАРОВ (КАТАЛОГ) ---
# Здесь ты можешь менять названия, цены и ссылки на фото
PRODUCTS = {
    "skirt_pleated": {
        "name": "Спідниця плісирована", 
        "price": 550, 
        "photo": "https://i.imgur.com/PZ7a2X3.jpg" # Замени на свои ссылки
    },
    "blouse_classic": {
        "name": "Блуза класична", 
        "price": 450, 
        "photo": "https://i.imgur.com/PZ7a2X3.jpg"
    },
    "trousers_school": {
        "name": "Штани шкільні", 
        "price": 600, 
        "photo": "https://i.imgur.com/PZ7a2X3.jpg"
    },
    "jacket_form": {
        "name": "Жакет шкільний", 
        "price": 850, 
        "photo": "https://i.imgur.com/PZ7a2X3.jpg"
    }
}

# Инициализация
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ТЕКСТЫ (HTML) ---
texts = {
    "ua": {
        "welcome": "Ласкаво просимо в Liberty Style! Оберіть мову:",
        "main_menu": "Головне меню 🛍️",
        "catalog": "👗 Каталог товарів",
        "payment_delivery": "💳 Оплата та Доставка",
        "support": "🆘 Підтримка / Соцмережі",
        "sizes_info": "📏 <b>Розмірна сітка:</b>\nXS: 122-128 см | S: 128-134 см\nM: 134-140 см | L: 140-146 см\nXL: 146-152 см",
        "pay_info": f"🚚 <b>Доставка:</b> Нова Пошта.\n💳 <b>Оплата:</b> Переказ на карту.\n\nРеквізити: <code>{CARD_NUMBER}</code>",
        "support_info": f"📞 <b>Контакти:</b>\nМенеджер: {MANAGER_LINK}\n\n👇 <b>Підписуйтесь на нас:</b>",
        "ask_name": "✍️ Напишіть ПІБ отримувача:",
        "ask_phone": "📱 Напишіть номер телефону:",
        "ask_city": "🏙 Напишіть Місто та номер відділення Нової Пошти:",
        "wait_payment": f"✅ Замовлення сформовано!\nДо сплати: <b>{{price}} грн</b>\n\n💳 Карта: <code>{CARD_NUMBER}</code>\n\n📎 <b>Пришліть скріншот оплати:</b>",
        "order_done": "✅ Замовлення відправлено менеджеру! Очікуйте підтвердження.",
        "send_photo_please": "Будь ласка, надішліть фото квитанції.",
        "new_order_admin": "🚨 <b>НОВЕ ЗАМОВЛЕННЯ!</b>",
        "item_select": "Оберіть товар:",
        "size_select": "Оберіть розмір:",
        "confirm_order_user": "✅ Ваше замовлення #{{id}} підтверджено! Ми готуємо його до відправки.",
        "reject_order_user": "❌ Ваше замовлення #{{id}} скасовано. Зв'яжіться з менеджером.",
        "admin_panel": "👑 <b>Адмін-панель</b>\nОберіть дію:",
        "stats": "📊 Користувачів у базі: "
    },
    "ru": {
        "welcome": "Добро пожаловать в Liberty Style! Выберите язык:",
        "main_menu": "Главное меню 🛍️",
        "catalog": "👗 Каталог товаров",
        "payment_delivery": "💳 Оплата и Доставка",
        "support": "🆘 Поддержка / Соцсети",
        "sizes_info": "📏 <b>Размерная сетка:</b>\nXS: 122-128 см | S: 128-134 см\nM: 134-140 см | L: 140-146 см\nXL: 146-152 см",
        "pay_info": f"🚚 <b>Доставка:</b> Новая Почта.\n💳 <b>Оплата:</b> Перевод на карту.\n\nРеквизиты: <code>{CARD_NUMBER}</code>",
        "support_info": f"📞 <b>Контакты:</b>\nМенеджер: {MANAGER_LINK}\n\n👇 <b>Подписывайтесь на нас:</b>",
        "ask_name": "✍️ Напишите ФИО получателя:",
        "ask_phone": "📱 Напишите номер телефона:",
        "ask_city": "🏙 Напишите Город и номер отделения Новой Почты:",
        "wait_payment": f"✅ Заказ сформирован!\nК оплате: <b>{{price}} грн</b>\n\n💳 Карта: <code>{CARD_NUMBER}</code>\n\n📎 <b>Пришлите скриншот оплаты:</b>",
        "order_done": "✅ Заказ отправлен менеджеру! Ожидайте подтверждения.",
        "send_photo_please": "Пожалуйста, отправьте фото квитанции.",
        "new_order_admin": "🚨 <b>НОВЫЙ ЗАКАЗ!</b>",
        "item_select": "Выберите товар:",
        "size_select": "Выберите размер:",
        "confirm_order_user": "✅ Ваш заказ #{{id}} подтвержден! Мы готовим его к отправке.",
        "reject_order_user": "❌ Ваш заказ #{{id}} отменен. Свяжитесь с менеджером.",
        "admin_panel": "👑 <b>Админ-панель</b>\nВыберите действие:",
        "stats": "📊 Пользователей в базе: "
    }
}

user_langs = {}

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
async def add_user(user_id):
    if not os.path.exists(USERS_FILE):
        async with aiofiles.open(USERS_FILE, "w") as f: await f.write("")
    async with aiofiles.open(USERS_FILE, "r") as f: users = await f.read()
    if str(user_id) not in users.split():
        async with aiofiles.open(USERS_FILE, "a") as f: await f.write(f"{user_id}\n")

async def get_all_users():
    if not os.path.exists(USERS_FILE): return []
    async with aiofiles.open(USERS_FILE, "r") as f: data = await f.read()
    return data.split()

# --- FSM (Машина состояний) ---
class OrderState(StatesGroup):
    choosing_item = State() # Выбор товара (техническое состояние)
    choosing_size = State() # Выбор размера
    waiting_name = State()
    waiting_phone = State()
    waiting_city = State()
    waiting_receipt = State()

class AdminState(StatesGroup):
    waiting_broadcast_text = State()

# --- КЛАВИАТУРЫ ---
def get_lang_kb():
    return ReplyKeyboardBuilder().button(text="🇺🇦 Українська").button(text="🇷🇺 Русский").as_markup(resize_keyboard=True)

def get_main_kb(lang):
    t = texts[lang]
    kb = ReplyKeyboardBuilder()
    kb.button(text=t["catalog"]) # Теперь это ведет к инлайн-меню
    kb.button(text=t["payment_delivery"])
    kb.button(text=t["support"])
    kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True)

def get_catalog_kb(lang):
    kb = InlineKeyboardBuilder()
    for code, data in PRODUCTS.items():
        # Создаем кнопку для каждого товара
        kb.button(text=f"{data['name']} - {data['price']} грн", callback_data=f"show_{code}")
    kb.adjust(1)
    return kb.as_markup()

def get_buy_kb(item_code, lang):
    kb = InlineKeyboardBuilder()
    text_buy = "Купити" if lang == "ua" else "Купить"
    text_back = "🔙 Назад"
    kb.button(text=f"🛒 {text_buy}", callback_data=f"buy_{item_code}")
    kb.button(text=text_back, callback_data="back_to_catalog")
    kb.adjust(1)
    return kb.as_markup()

def get_sizes_kb(item_code):
    kb = InlineKeyboardBuilder()
    sizes = ["XS", "S", "M", "L", "XL"]
    for s in sizes:
        kb.button(text=s, callback_data=f"size_{item_code}_{s}")
    kb.button(text="🔙", callback_data=f"show_{item_code}")
    kb.adjust(3, 2, 1)
    return kb.as_markup()

def get_admin_order_kb(user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=f"adm_ok_{user_id}")
    kb.button(text="❌ Отклонить", callback_data=f"adm_no_{user_id}")
    return kb.as_markup()

def get_admin_panel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    return kb.as_markup()

# --- ХЕНДЛЕРЫ: ОБЩИЕ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await add_user(message.from_user.id)
    await message.answer("🇺🇦 Оберіть мову / 🇷🇺 Выберите язык", reply_markup=get_lang_kb())

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        lang = user_langs.get(ADMIN_ID, "ru")
        await message.answer(texts[lang]["admin_panel"], reply_markup=get_admin_panel_kb(), parse_mode="HTML")

@dp.message(F.text.in_({"🇺🇦 Українська", "🇷🇺 Русский"}))
async def set_language(message: types.Message):
    lang = "ua" if "Українська" in message.text else "ru"
    user_langs[message.from_user.id] = lang
    await message.answer(texts[lang]["main_menu"], reply_markup=get_main_kb(lang))

def get_u_lang(user_id): return user_langs.get(user_id, "ua")

# --- ЛОГИКА КАТАЛОГА ---
@dp.message(lambda msg: any(txt in msg.text for txt in ["Каталог", "Catalog"]))
async def show_catalog_menu(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["item_select"], reply_markup=get_catalog_kb(lang))

# Показ товара
@dp.callback_query(F.data.startswith("show_"))
async def show_item(callback: CallbackQuery):
    item_code = callback.data.split("_")[1]
    item = PRODUCTS[item_code]
    lang = get_u_lang(callback.from_user.id)
    
    caption = f"<b>{item['name']}</b>\n\n💰 Цiна: {item['price']} грн\n\n{texts[lang]['sizes_info']}"
    
    # Пытаемся удалить старое сообщение или отправить новое с фото
    try:
        await callback.message.delete()
    except: pass
    
    await callback.message.answer_photo(
        photo=item['photo'],
        caption=caption,
        reply_markup=get_buy_kb(item_code, lang),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "back_to_catalog")
async def back_catalog(callback: CallbackQuery):
    lang = get_u_lang(callback.from_user.id)
    try: await callback.message.delete()
    except: pass
    await callback.message.answer(texts[lang]["item_select"], reply_markup=get_catalog_kb(lang))

# --- ЛОГИКА ЗАКАЗА (Покупка) ---
@dp.callback_query(F.data.startswith("buy_"))
async def start_buying(callback: CallbackQuery):
    item_code = callback.data.split("_")[1]
    lang = get_u_lang(callback.from_user.id)
    # Редактируем сообщение, предлагая размеры
    await callback.message.edit_reply_markup(reply_markup=get_sizes_kb(item_code))
    await callback.answer()

@dp.callback_query(F.data.startswith("size_"))
async def size_selected(callback: CallbackQuery, state: FSMContext):
    _, item_code, size = callback.data.split("_")
    lang = get_u_lang(callback.from_user.id)
    
    # Сохраняем выбор
    await state.update_data(item_code=item_code, size=size, price=PRODUCTS[item_code]['price'])
    await state.set_state(OrderState.waiting_name)
    
    await callback.message.answer(texts[lang]["ask_name"])
    await callback.answer()

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
    data = await state.get_data()
    lang = get_u_lang(message.from_user.id)
    
    await state.set_state(OrderState.waiting_receipt)
    # Форматируем текст с ценой
    text = texts[lang]["wait_payment"].replace("{{price}}", str(data['price']))
    await message.answer(text, parse_mode="HTML")

@dp.message(OrderState.waiting_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_u_lang(message.from_user.id)
    user = message.from_user
    
    item_name = PRODUCTS[data['item_code']]['name']

    admin_text = (
        f"{texts[lang]['new_order_admin']}\n\n"
        f"👤 <b>Покупець:</b> @{user.username} (ID: {user.id})\n"
        f"👗 <b>Товар:</b> {item_name}\n"
        f"📏 <b>Розмір:</b> {data['size']}\n"
        f"💰 <b>Сума:</b> {data['price']} грн\n"
        f"📛 <b>ПІБ:</b> {data['name']}\n"
        f"📱 <b>Телефон:</b> {data['phone']}\n"
        f"🏙 <b>Доставка:</b> {data['city']}\n\n"
        f"👇 <b>Підтвердіть або відхиліть замовлення:</b>"
    )

    # Отправляем админу сообщение с кнопками действий
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_admin_order_kb(user.id), parse_mode="HTML")
    await message.copy_to(ADMIN_ID)
    
    await message.answer(texts[lang]["order_done"], reply_markup=get_main_kb(lang))
    await state.clear()

# --- ОБРАБОТКА ДЕЙСТВИЙ АДМИНА ---
@dp.callback_query(F.data.startswith("adm_"))
async def admin_decision(callback: CallbackQuery):
    action, user_id = callback.data.split("_")[1], callback.data.split("_")[2]
    lang = get_u_lang(int(user_id))
    
    if action == "ok":
        msg_user = texts[lang]["confirm_order_user"].replace("{{id}}", str(callback.message.message_id))
        msg_admin = f"✅ Заказ клиента {user_id} ПОДТВЕРЖДЕН."
    else:
        msg_user = texts[lang]["reject_order_user"].replace("{{id}}", str(callback.message.message_id))
        msg_admin = f"❌ Заказ клиента {user_id} ОТКЛОНЕН."
    
    # Отправляем уведомление пользователю
    try:
        await bot.send_message(int(user_id), msg_user)
    except:
        msg_admin += " (Клиент заблокировал бота)"

    # Меняем сообщение у админа
    await callback.message.edit_text(callback.message.text + f"\n\n👉 {msg_admin}")
    await callback.answer()

# --- АДМИН ПАНЕЛЬ ---
@dp.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    users = await get_all_users()
    await callback.message.answer(f"📊 Всего пользователей: {len(users)}")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast_btn(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Введите текст/фото для рассылки:")
    await state.set_state(AdminState.waiting_broadcast_text)
    await callback.answer()

@dp.message(AdminState.waiting_broadcast_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    users = await get_all_users()
    count = 0
    await message.answer(f"📢 Рассылка на {len(users)} чел...")
    for user_id in users:
        try:
            await message.copy_to(chat_id=int(user_id))
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Успешно: {count}")
    await state.clear()

# Остальные кнопки меню
@dp.message(lambda msg: any(txt in msg.text for txt in ["Оплата", "Payment"]))
async def show_payment(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["pay_info"], parse_mode="HTML")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Підтримка", "Поддержка", "Support"]))
async def show_support(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="📸 Instagram", url=INSTAGRAM_LINK)
    kb.button(text="👨‍💻 Менеджер", url=MANAGER_LINK)
    await message.answer(texts[lang]["support_info"], reply_markup=kb.as_markup(), parse_mode="HTML")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
