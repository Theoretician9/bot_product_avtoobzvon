import asyncio
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")
TRIBUTE_LINK = os.getenv("TRIBUTE_LINK")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# Авторизация в Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
worksheet = client.open(SPREADSHEET_NAME).sheet1

# Инициализация листа report
try:
    report_ws = client.open(SPREADSHEET_NAME).worksheet("report")
except gspread.WorksheetNotFound:
    sh = client.open(SPREADSHEET_NAME)
    report_ws = sh.add_worksheet(title="report", rows="1000", cols="5")
    report_ws.append_row(["DateTime Moscow", "UserID", "Start", "Paid", "Status"])

# Загрузка всех записей из таблицы

def load_posts():
    return worksheet.get_all_records()

# Отправка одного поста
async def send_post(user_id: int, post: dict):
    content = post.get('content', '')
    media_type = post.get('media_type', '').strip().lower()
    file_url = post.get('file_url', '').strip()
    with_button = str(post.get('pay_button', '')).strip().lower() == 'true'

    markup = None
    if with_button and TRIBUTE_LINK:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=TRIBUTE_LINK)]
        ])

    try:
        if media_type == "text":
            await bot.send_message(user_id, content, reply_markup=markup)
        elif media_type == "photo":
            await bot.send_photo(user_id, photo=file_url, caption=content, reply_markup=markup)
        elif media_type == "video":
            await bot.send_video(user_id, video=file_url, caption=content, reply_markup=markup)
        elif media_type == "document":
            await bot.send_document(user_id, document=file_url, caption=content, reply_markup=markup)
        elif media_type == "audio":
            await bot.send_audio(user_id, audio=file_url, caption=content, reply_markup=markup)
        elif media_type == "voice":
            await bot.send_voice(user_id, voice=file_url, caption=content, reply_markup=markup)
        elif media_type == "video_note":
            await bot.send_video_note(user_id, video_note=file_url)
        else:
            logging.warning(f"Unknown media type '{media_type}' for user {user_id}")
    except Exception as e:
        logging.error(f"Error sending post to {user_id}: {e}")

# Обработчики команд
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    logging.info(f"User {user_id} started sequence")
    await message.answer("🚀 Отлично! Сейчас начну присылать тебе материалы.")

    # === Тестовая вставка в report ===
    try:
        now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
        report_ws.append_row([
            now,
            str(user_id),
            "Yes",
            "No",
            "Subscribed"
        ])
        logging.info("Report: added test row")
    except Exception as e:
        logging.error(f"Report test failed: {e}")
    # === Конец теста ===

    # Рассылка постов
    posts = load_posts()
    for post in posts:
        delay = int(post.get('delay_minutes', 0))
        await asyncio.sleep(delay * 60)
        await send_post(user_id, post)

async def handle_stop(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    report_ws.append_row([now, str(user_id), "No", "No", "Unsubscribed"])
    await message.answer("👋 Вы отписались. Чтобы начать заново, нажмите /start.")

async def handle_paid(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    report_ws.append_row([now, str(user_id), "", "Yes", "Subscribed"])
    await message.answer("✅ Отметил оплату. Спасибо!")

# Регистрация хендлеров
from aiogram.filters import Command

dp.message.register(handle_start, Command(commands=["start"]))
dp.message.register(handle_stop, Command(commands=["stop"]))
dp.message.register(handle_paid, Command(commands=["paid"]))

# Запуск бот-поллинга
async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
