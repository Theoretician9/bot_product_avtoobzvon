import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TRIBUTE_LINK = os.getenv("TRIBUTE_LINK") or "https://tribute.tg/ВАША_ССЫЛКА_НА_ОПЛАТУ"
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME") or "bot_posts"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
user_start_times = {}

# Авторизация в Google Sheets
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Чтение постов из таблицы
def load_posts():
    sheet = client.open(SPREADSHEET_NAME).sheet1
    data = sheet.get_all_records()
    return data

# Отправка поста с нужным типом
async def send_post(user_id, post, with_button):
    content = post['content']
    media_type = post['media_type'].strip().lower()
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

# Хендлер для /start
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    user_start_times[user_id] = datetime.now()
    await message.answer("🚀 Отлично! Сейчас начну присылать тебе материалы.")
    posts = load_posts()

    for post in posts:
        delay = int(post['delay_minutes'])
        await asyncio.sleep(delay * 60)
        with_button = str(post.get('pay_button', '')).lower() == 'true'
        await send_post(user_id, post, with_button)

# Сообщение до /start
@dp.message_handler()
async def welcome(message: types.Message):
    await message.answer("👋 Добро пожаловать! Нажми /start, чтобы начать.")

# Запуск
if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
