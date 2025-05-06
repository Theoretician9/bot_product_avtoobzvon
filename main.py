import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")
TRIBUTE_LINK = os.getenv("TRIBUTE_LINK") or "https://tribute.tg/ВАША_ССЫЛКА_НА_ОПЛАТУ"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# Словарь для хранения времени начала взаимодействия с ботом
user_start_times = {}

# Получение доступа к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
gs = gspread.authorize(credentials)
worksheet = gs.open(SPREADSHEET_NAME).sheet1


def load_posts():
    rows = worksheet.get_all_records()
    return rows


async def send_post(user_id, post, with_button):
    content = post['content']
    media_type = post['media_type'].strip().lower()
    file_url = post.get('file_url', '').strip()

    markup = None
    if with_button:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("💳 Оплатить", url=TRIBUTE_LINK)
        )

    try:
        if media_type == "text":
            await bot.send_message(user_id, content, reply_markup=markup)
        elif media_type == "photo":
            await bot.send_photo(user_id, photo=file_url, caption=content, reply_markup=markup)
        elif media_type == "video":
            await bot.send_video(user_id, video=file_url, caption=content, reply_markup=markup)
        elif media_type == "document":
            await bot.send_document(user_id, document=file_url, caption=content, reply_markup=markup)
    except Exception as e:
        print(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")


@dp.message()
async def handle_all_messages(message: types.Message):
    user_id = message.from_user.id
    if message.text == "/start":
        user_start_times[user_id] = datetime.now()
        await message.answer("🚀 Отлично! Сейчас начну присылать тебе материалы.")
        posts = load_posts()
        for post in posts:
            delay = int(post.get('delay_minutes', 0))
            await asyncio.sleep(delay * 60)
            with_button = str(post.get('pay_button', '')).lower() == 'true'
            await send_post(user_id, post, with_button)
    else:
        await message.answer("👋 Добро пожаловать! Нажми /start, чтобы начать.")


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
