
# main.py
# Упрощённый шаблон бота с отложенной отправкой постов
# Настройки и логика задаются в отдельном файле
# Поддерживает кнопку оплаты и чтение контента из CSV

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
import csv
from datetime import datetime, timedelta

BOT_TOKEN = "ВАШ_ТОКЕН_БОТА"
TRIBUTE_LINK = "https://tribute.tg/ВАША_ССЫЛКА_НА_ОПЛАТУ"
POSTS_FILE = "post_template.csv"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
user_start_times = {}

def load_posts():
    with open(POSTS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        posts = [row for row in reader]
    return posts

async def send_post(user_id, post, with_button):
    content = post['content']
    media_type = post['media_type']
    file_url = post.get('file_url')

    markup = None
    if with_button:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("💳 Оплатить", url=TRIBUTE_LINK)
        )

    if media_type == "text":
        await bot.send_message(user_id, content, reply_markup=markup)
    elif media_type == "photo":
        await bot.send_photo(user_id, photo=file_url, caption=content, reply_markup=markup)
    elif media_type == "video":
        await bot.send_video(user_id, video=file_url, caption=content, reply_markup=markup)
    elif media_type == "document":
        await bot.send_document(user_id, document=file_url, caption=content, reply_markup=markup)

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    user_start_times[user_id] = datetime.now()
    await message.answer("🚀 Отлично! Сейчас начну присылать тебе материалы.")
    posts = load_posts()
    for post in posts:
        delay = int(post['delay_minutes'])
        await asyncio.sleep(delay * 60)
        with_button = post.get('pay_button', '').lower() == 'true'
        await send_post(user_id, post, with_button)

@dp.message_handler()
async def welcome(message: types.Message):
    await message.answer("👋 Добро пожаловать! Нажми /start, чтобы начать.")
