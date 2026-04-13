import asyncio
import logging
import sys
import os
import html
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardBuilder, CallbackQuery

TOKEN = "ТВОЙ_ТОКЕН"
ADMIN_ID = 843027482
DB_NAME = "shop.db"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# --- ТОВАРЫ ---
PRODUCTS = {
    "tshirt": {
        "name_ua": "Футболка Liberty Style",
        "price": 300,
        "photos": [
            "https://via.placeholder.com/500x500?text=Tshirt1",
            "https://via.placeholder.com/500x500?text=Tshirt2"
        ],
        "desc_ua": "М’яка тканина, вільний крій, стильний вигляд.",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "reviews": [
            "🔥 Дуже зручна!",
            "👍 Якість топ за свої гроші",
            "💯 Рекомендую"
        ],
        "related": ["blouse"]
    },

    "blouse": {
        "name_ua": "Блуза",
        "price": 450,
        "photos": ["https://via.placeholder.com/500x500?text=Blouse"],
        "desc_ua": "Класична шкільна блуза.",
        "sizes": ["XS", "S", "M", "L"],
        "reviews": ["👍 Гарна тканина"],
        "related": ["tshirt"]
    }
}

# --- FSM ---
class OrderState(StatesGroup):
    waiting_data = State()
    waiting_receipt = State()

# --- КНОПКИ ---
def get_catalog_kb():
    kb = InlineKeyboardBuilder()
    for code, item in PRODUCTS.items():
        kb.button(text=f"{item['name_ua']} - {item['price']} грн", callback_data=f"item_{code}")
    kb.adjust(1)
    return kb.as_markup()

def get_item_kb(code):
    kb = InlineKeyboardBuilder()

    for size in PRODUCTS[code]["sizes"]:
        kb.button(text=f"📏 {size}", callback_data=f"size_{code}_{size}")

    kb.button(text="⭐ Відгуки", callback_data=f"reviews_{code}")
    kb.button(text="🤖 Рекомендуємо", callback_data=f"rel_{code}")
    kb.button(text="🛒 Купити", callback_data=f"buy_{code}")
    kb.button(text="🔙 Назад", callback_data="back")

    kb.adjust(2, 2, 1)
    return kb.as_markup()

# --- СТАРТ ---
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🛍 Каталог:", reply_markup=get_catalog_kb())

# --- КАТАЛОГ ---
@dp.callback_query(F.data.startswith("item_"))
async def show_item(call: CallbackQuery):
    code = call.data.split("_")[1]
    item = PRODUCTS[code]

    caption = (
        f"🛍 <b>{item['name_ua']}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"{item['desc_ua']}\n\n"
        f"💰 <b>{item['price']} грн</b>\n"
        f"📦 В наявності"
    )

    await call.message.delete()

    # отправляем галерею
    for i, photo in enumerate(item["photos"]):
        if i == 0:
            await call.message.answer_photo(photo, caption=caption, parse_mode="HTML", reply_markup=get_item_kb(code))
        else:
            await call.message.answer_photo(photo)

    await call.answer()

# --- ВЫБОР РАЗМЕРА ---
@dp.callback_query(F.data.startswith("size_"))
async def choose_size(call: CallbackQuery, state: FSMContext):
    _, code, size = call.data.split("_")
    await state.update_data(size=size)
    await call.answer(f"Обрано: {size}")

# --- ОТЗЫВЫ ---
@dp.callback_query(F.data.startswith("reviews_"))
async def reviews(call: CallbackQuery):
    code = call.data.split("_")[1]
    text = "\n".join(PRODUCTS[code]["reviews"])
    await call.message.answer(f"⭐ Відгуки:\n\n{text}")
    await call.answer()

# --- РЕКОМЕНДАЦИИ ---
@dp.callback_query(F.data.startswith("rel_"))
async def related(call: CallbackQuery):
    code = call.data.split("_")[1]
    rel = PRODUCTS[code]["related"]

    text = "🤖 З цим беруть:\n"
    for r in rel:
        text += f"\n• {PRODUCTS[r]['name_ua']}"

    await call.message.answer(text)
    await call.answer()

# --- ПОКУПКА ---
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery, state: FSMContext):
    code = call.data.split("_")[1]
    data = await state.get_data()
    size = data.get("size", "Не вибрано")

    item = PRODUCTS[code]

    await state.update_data(
        item=item["name_ua"],
        price=item["price"],
        size=size
    )

    await state.set_state(OrderState.waiting_data)

    await call.message.answer(
        f"📦 Введіть дані:\n\nПІБ, Телефон, Місто, НП\n\nОбраний розмір: {size}"
    )

    await call.answer()

# --- ДАННЫЕ ---
@dp.message(OrderState.waiting_data)
async def data(msg: types.Message, state: FSMContext):
    await state.update_data(info=msg.text)
    await state.set_state(OrderState.waiting_receipt)

    await msg.answer("💳 Оплатіть і надішліть скрін")

# --- ЧЕК ---
@dp.message(OrderState.waiting_receipt, F.photo)
async def receipt(msg: types.Message, state: FSMContext):
    data = await state.get_data()

    text = (
        f"🆕 Замовлення\n"
        f"{data['item']}\n"
        f"📏 {data['size']}\n"
        f"{data['price']} грн\n"
        f"{data['info']}"
    )

    await bot.send_message(ADMIN_ID, text)
    await msg.copy_to(ADMIN_ID)

    await msg.answer("✅ Замовлення прийнято!")
    await state.clear()

# --- НАЗАД ---
@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.answer("🛍 Каталог:", reply_markup=get_catalog_kb())
    await call.answer()

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
