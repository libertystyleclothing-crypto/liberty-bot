import asyncio
import logging
import sys
import os
import aiosqlite # Библиотека для базы данных
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
TOKEN = "8528185164:AAEqb_Yr8DYxWNzRlPPOHODf6WPY2qcnO5U" 
ADMIN_ID = 843027482  # ТВОЙ ID
DB_NAME = "shop.db"   # Имя файла базы данных

# Ссылки и данные
MANAGER_LINK = "https://t.me/fuckoffaz"
INSTAGRAM_LINK = "https://www.instagram.com/_liberty.style_/" 
CARD_NUMBER = "4874 0700 7049 2978"

# --- БАЗА ТОВАРОВ ---
PRODUCTS = {
    "skirt_pleated": {
        "name": "Спідниця плісирована", 
        "price": 550, 
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg"
    },
    "blouse_classic": {
        "name": "Блуза класична", 
        "price": 450, 
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/White_blouse.jpg/480px-White_blouse.jpg"
    },
    "trousers_school": {
        "name": "Штани шкільні", 
        "price": 600, 
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Trousers.jpg/480px-Trousers.jpg"
    },
    "jacket_form": {
        "name": "Жакет шкільний", 
        "price": 850, 
        "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Girl_in_a_jacket_and_pleated_skirt.jpg/480px-Girl_in_a_jacket_and_pleated_skirt.jpg"
    }
}

# Инициализация
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ТЕКСТЫ (HTML) ---
texts = {
    "ua": {
        "welcome": "Вітаємо в Liberty Style! Оберіть мову:",
        "main_menu_text": "Оберіть розділ:",
        "btn_sizes": "📏 Розміри",
        "btn_pay": "💳 Оплата",
        "btn_delivery": "🚚 Доставка",
        "btn_support": "🆘 Підтримка / Чат",
        "btn_status": "🔎 Статус/ТТН",
        "btn_catalog": "🛍️ Замовлення / Каталог",
        "btn_return": "♻️ Обмін і повернення",
        "btn_problems": "❗️ Проблеми з замовленням",
        
        "info_sizes": "📏 <b>Розмірна сітка Liberty Style:</b>\n\nXS: 122-128 см\nS: 128-134 см\nM: 134-140 см\nL: 140-146 см\nXL: 146-152 см",
        "info_pay": f"💳 <b>Оплата:</b>\nПереказ на карту Monobank.\n\nРеквізити: <code>{CARD_NUMBER}</code>\n\n(При оформленні замовлення бот попросить скріншот оплати).",
        "info_delivery": "🚚 <b>Доставка:</b>\nВідправляємо Новою Поштою щодня о 18:00.\nТермін доставки: 1-2 дні.",
        "info_return": "♻️ <b>Обмін та Повернення:</b>\nМожливий протягом 14 днів, якщо товар не був у використанні.\nДоставку при обміні оплачує покупець.",
        "info_status": "🔎 <b>Статус замовлення:</b>\nМи надішлемо ТТН у цей чат.\n\nЯкщо у вас є питання — просто напишіть їх сюди, менеджер відповість.",
        "support_header": "👨‍💻 <b>Підтримка</b>\n\nВи можете написати своє питання прямо сюди в чат, і ми відповімо!",

        "ask_name": "✍️ Напишіть ПІБ отримувача:",
        "ask_phone": "📱 Напишіть номер телефону:",
        "ask_city": "🏙 Напишіть Місто та номер відділення Нової Пошти:",
        "wait_payment": f"✅ Замовлення сформовано!\nДо сплати: <b>%price% грн</b>\n\n💳 Карта: <code>{CARD_NUMBER}</code>\n\n📎 <b>Пришліть сюди фото/скріншот квитанції:</b>",
        "order_done": "✅ <b>Дякуємо! Ваше замовлення прийнято.</b>\nМенеджер перевірить оплату і підтвердить замовлення.",
        "send_photo_please": "📷 Будь ласка, надішліть саме фото/скріншот квитанції.",
        
        "new_order_admin": "🚨 <b>НОВЕ ЗАМОВЛЕННЯ!</b>",
        "item_select": "Оберіть категорію/товар:",
        "confirm_order_user": "✅ <b>Ваше замовлення #%id% підтверджено!</b>\n📦 ТТН: <code>%ttn%</code>\n\nДякуємо, що ви з нами!",
        "reject_order_user": "❌ Ваше замовлення #%id% скасовано. Зв'яжіться з менеджером.",
        "admin_panel": "👑 <b>Адмін-панель</b>",
        "ask_ttn": "🚚 Введіть номер ТТН для клієнта:"
    },
    "ru": {
        "welcome": "Добро пожаловать в Liberty Style! Выберите язык:",
        "main_menu_text": "Выберите раздел:",
        "btn_sizes": "📏 Размеры",
        "btn_pay": "💳 Оплата",
        "btn_delivery": "🚚 Доставка",
        "btn_support": "🆘 Поддержка / Чат",
        "btn_status": "🔎 Статус/ТТН",
        "btn_catalog": "🛍️ Заказ / Каталог",
        "btn_return": "♻️ Обмен и возврат",
        "btn_problems": "❗️ Проблемы с заказом",
        
        "info_sizes": "📏 <b>Размерная сетка Liberty Style:</b>\n\nXS: 122-128 см\nS: 128-134 см\nM: 134-140 см\nL: 140-146 см\nXL: 146-152 см",
        "info_pay": f"💳 <b>Оплата:</b>\nПеревод на карту Monobank.\n\nРеквизиты: <code>{CARD_NUMBER}</code>\n\n(При оформлении заказа бот попросит скриншот оплаты).",
        "info_delivery": "🚚 <b>Доставка:</b>\nОтправляем Новой Почтой каждый день в 18:00.\nСрок доставки: 1-2 дня.",
        "info_return": "♻️ <b>Обмен и Возврат:</b>\nВозможен в течение 14 дней, если товар не был в использовании.",
        "info_status": "🔎 <b>Статус заказа:</b>\nМы пришлем ТТН в этот чат.\n\nЕсли есть вопросы — просто напишите их сюда, менеджер ответит.",
        "support_header": "👨‍💻 <b>Поддержка</b>\n\nВы можете написать свой вопрос прямо сюда в чат, и мы ответим!",
        
        "ask_name": "✍️ Напишите ФИО получателя:",
        "ask_phone": "📱 Напишите номер телефона:",
        "ask_city": "🏙 Напишите Город и номер отделения Новой Почты:",
        "wait_payment": f"✅ Заказ сформирован!\nК оплате: <b>%price% грн</b>\n\n💳 Карта: <code>{CARD_NUMBER}</code>\n\n📎 <b>Пришлите сюда фото/скриншот квитанции:</b>",
        "order_done": "✅ <b>Спасибо! Ваш заказ принят.</b>\nМенеджер проверит оплату и подтвердит заказ.",
        "send_photo_please": "📷 Пожалуйста, отправьте именно фото/скриншот квитанции.",
        
        "new_order_admin": "🚨 <b>НОВЫЙ ЗАКАЗ!</b>",
        "item_select": "Выберите товар:",
        "confirm_order_user": "✅ <b>Ваш заказ #%id% подтвержден!</b>\n📦 ТТН: <code>%ttn%</code>\n\nСпасибо, что вы с нами!",
        "reject_order_user": "❌ Ваш заказ #%id% отменен. Свяжитесь с менеджером.",
        "admin_panel": "👑 <b>Админ-панель</b>",
        "ask_ttn": "🚚 Введите номер ТТН для клиента:"
    }
}

user_langs = {}

# --- БАЗА ДАННЫХ (SQLITE) ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                join_date TEXT
            )
        """)
        await db.commit()

async def add_user_db(user: types.User):
    async with aiosqlite.connect(DB_NAME) as db:
        # Проверяем, есть ли уже такой пользователь
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
        data = await cursor.fetchone()
        if not data:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute(
                "INSERT INTO users (user_id, username, full_name, join_date) VALUES (?, ?, ?, ?)",
                (user.id, user.username, user.full_name, now)
            )
            await db.commit()

async def get_all_users_db():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows] # Возвращаем список ID

async def get_stats_text():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        count = await cursor.fetchone()
        return f"📊 <b>Статистика:</b>\nВсего пользователей: {count[0]}"

# --- FSM ---
class OrderState(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_city = State()
    waiting_receipt = State()

class AdminState(StatesGroup):
    waiting_broadcast_text = State()
    waiting_ttn = State()

# --- КЛАВИАТУРЫ ---
def get_lang_kb():
    return ReplyKeyboardBuilder().button(text="🇺🇦 Українська").button(text="🇷🇺 Русский").as_markup(resize_keyboard=True)

def get_main_kb(lang):
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

def get_catalog_kb(lang):
    kb = InlineKeyboardBuilder()
    for code, data in PRODUCTS.items():
        kb.button(text=f"{data['name']} - {data['price']} грн", callback_data=f"show_{code}")
    kb.adjust(1)
    return kb.as_markup()

def get_buy_kb(item_code, lang):
    kb = InlineKeyboardBuilder()
    text_buy = "Купити" if lang == "ua" else "Купить"
    kb.button(text=f"🛒 {text_buy}", callback_data=f"buy_{item_code}")
    kb.button(text="🔙", callback_data="back_to_catalog")
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

def get_admin_order_kb(user_id, order_msg_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить + ТТН", callback_data=f"adm_ok_{user_id}_{order_msg_id}")
    kb.button(text="❌ Отклонить", callback_data=f"adm_no_{user_id}_{order_msg_id}")
    return kb.as_markup()

def get_admin_panel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    return kb.as_markup()

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await add_user_db(message.from_user) # Пишем в БД
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
    await message.answer(texts[lang]["main_menu_text"], reply_markup=get_main_kb(lang))

def get_u_lang(user_id): return user_langs.get(user_id, "ua")

# --- МЕНЮ ---
@dp.message(lambda msg: any(txt in msg.text for txt in ["Замовлення", "Заказ", "Catalog"]))
async def show_catalog_menu(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["item_select"], reply_markup=get_catalog_kb(lang))

@dp.message(lambda msg: any(txt in msg.text for txt in ["Розміри", "Размеры"]))
async def menu_sizes(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["info_sizes"], parse_mode="HTML")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Оплата", "Payment"]))
async def menu_payment(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["info_pay"], parse_mode="HTML")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Доставка", "Delivery"]))
async def menu_delivery(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["info_delivery"], parse_mode="HTML")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Підтримка", "Поддержка", "Проблеми", "Проблемы"]))
async def menu_support(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    # Предлагаем написать прямо в чат
    await message.answer(texts[lang]["support_header"], parse_mode="HTML")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Обмін", "Обмен"]))
async def menu_return(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["info_return"], parse_mode="HTML")

@dp.message(lambda msg: any(txt in msg.text for txt in ["Статус", "ТТН"]))
async def menu_status(message: types.Message):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["info_status"], parse_mode="HTML")

# --- ПОКУПКА ---
@dp.callback_query(F.data.startswith("show_"))
async def show_item(callback: CallbackQuery):
    item_code = callback.data.replace("show_", "")
    if item_code not in PRODUCTS:
        await callback.answer("Error", show_alert=True)
        return
    item = PRODUCTS[item_code]
    lang = get_u_lang(callback.from_user.id)
    caption = f"<b>{item['name']}</b>\n\n💰 Цiна: {item['price']} грн"
    try: await callback.message.delete()
    except: pass
    await callback.message.answer_photo(photo=item['photo'], caption=caption, reply_markup=get_buy_kb(item_code, lang), parse_mode="HTML")

@dp.callback_query(F.data == "back_to_catalog")
async def back_catalog(callback: CallbackQuery):
    lang = get_u_lang(callback.from_user.id)
    try: await callback.message.delete()
    except: pass
    await callback.message.answer(texts[lang]["item_select"], reply_markup=get_catalog_kb(lang))

@dp.callback_query(F.data.startswith("buy_"))
async def start_buying(callback: CallbackQuery):
    item_code = callback.data.replace("buy_", "")
    await callback.message.edit_reply_markup(reply_markup=get_sizes_kb(item_code))
    await callback.answer()

@dp.callback_query(F.data.startswith("size_"))
async def size_selected(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    size = parts[-1]
    item_code = "_".join(parts[1:-1]) 
    lang = get_u_lang(callback.from_user.id)
    await state.update_data(item_code=item_code, size=size, price=PRODUCTS[item_code]['price'])
    await state.set_state(OrderState.waiting_name)
    await callback.message.answer(texts[lang]["ask_name"])
    await callback.answer()

# --- АНКЕТА ---
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
    text = texts[lang]["wait_payment"].replace("%price%", str(data['price']))
    await message.answer(text, parse_mode="HTML")

@dp.message(OrderState.waiting_receipt, F.photo | F.document)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = get_u_lang(message.from_user.id)
    user = message.from_user
    try: item_name = PRODUCTS[data['item_code']]['name']
    except: item_name = "Товар"

    admin_text = (
        f"{texts[lang]['new_order_admin']}\n\n"
        f"👤 <b>Клієнт:</b> @{user.username} (ID: {user.id})\n"
        f"👗 <b>Товар:</b> {item_name}\n"
        f"📏 <b>Розмір:</b> {data['size']}\n"
        f"💰 <b>Сума:</b> {data['price']} грн\n"
        f"📛 <b>ПІБ:</b> {data['name']}\n"
        f"📱 <b>Телефон:</b> {data['phone']}\n"
        f"🏙 <b>Доставка:</b> {data['city']}\n\n"
        f"👇 <b>Дії:</b>"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_admin_order_kb(user.id, message.message_id), parse_mode="HTML")
        await message.copy_to(ADMIN_ID)
    except: pass
    await message.answer(texts[lang]["order_done"], reply_markup=get_main_kb(lang))
    await state.clear()

@dp.message(OrderState.waiting_receipt)
async def process_receipt_invalid(message: types.Message, state: FSMContext):
    lang = get_u_lang(message.from_user.id)
    await message.answer(texts[lang]["send_photo_please"])

# --- ЧАТ ПОДДЕРЖКИ (ОТВЕТЫ) ---
@dp.message(F.reply_to_message)
async def admin_reply(message: types.Message):
    # Если Админ отвечает на пересланное сообщение
    if message.from_user.id == ADMIN_ID:
        # Пробуем достать ID пользователя из пересланного сообщения
        original_msg = message.reply_to_message
        if original_msg.forward_from:
            user_id = original_msg.forward_from.id
        else:
            # Если пользователь скрыл профиль, айди не будет (это ограничение Телеграма)
            await message.answer("⚠️ Не могу ответить: пользователь скрыл свой профиль.")
            return

        try:
            await message.copy_to(user_id) # Копируем ответ админа пользователю
            await message.react([types.ReactionTypeEmoji(emoji="👍")])
        except:
            await message.answer("⚠️ Не удалось отправить сообщение (юзер заблокировал бота).")

@dp.message(F.text & ~F.text.startswith("/"))
async def chat_with_admin(message: types.Message):
    # Если это обычное сообщение (не команда и не кнопка меню)
    if message.from_user.id == ADMIN_ID:
        return # Админ сам себе не пишет

    # Проверяем, что это не текст кнопки (чтобы не спамить)
    # Простая проверка, можно улучшить
    if len(message.text) < 50 and ("Доставка" in message.text or "Оплата" in message.text):
        return

    # Пересылаем сообщение Админу
    try:
        await message.forward(ADMIN_ID)
    except: pass

# --- АДМИНКА ---
@dp.callback_query(F.data.startswith("adm_"))
async def admin_decision(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    action, user_id = parts[1], parts[2]
    await state.update_data(target_user_id=user_id)

    if action == "ok":
        lang = user_langs.get(ADMIN_ID, "ru")
        await callback.message.answer(texts[lang]["ask_ttn"])
        await state.set_state(AdminState.waiting_ttn)
        await callback.answer()
    else:
        lang = get_u_lang(int(user_id))
        try:
            msg_user = texts[lang]["reject_order_user"].replace("%id%", "New")
            await bot.send_message(int(user_id), msg_user)
            await callback.message.edit_text(callback.message.text + "\n\n❌ ОТКЛОНЕНО")
        except:
            await callback.message.edit_text(callback.message.text + "\n\n❌ Ошибка (Юзер заблочил бота)")
        await callback.answer()

@dp.message(AdminState.waiting_ttn)
async def process_ttn_input(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    ttn = message.text
    data = await state.get_data()
    target_user_id = data['target_user_id']
    lang = get_u_lang(int(target_user_id))
    try:
        msg_user = texts[lang]["confirm_order_user"].replace("%id%", "New").replace("%ttn%", ttn)
        await bot.send_message(int(target_user_id), msg_user, parse_mode="HTML")
        await message.answer(f"✅ ТТН {ttn} отправлен!")
    except:
        await message.answer("⚠️ Не удалось отправить.")
    await state.clear()

@dp.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    stats_text = await get_stats_text()
    await callback.message.answer(stats_text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast_btn(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Введите текст для рассылки:")
    await state.set_state(AdminState.waiting_broadcast_text)
    await callback.answer()

@dp.message(AdminState.waiting_broadcast_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    users = await get_all_users_db()
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

async def main():
    await init_db() # Создаем базу данных при запуске
    try:
        await bot.send_message(ADMIN_ID, "✅ <b>Бот обновлен!</b>\nБаза данных подключена.\nЧат работает (отвечай Replay-ем).", parse_mode="HTML")
    except: pass
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
