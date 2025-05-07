import asyncio
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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

# Прогресс пользователей по постам (user_id: index)
user_progress = {}
user_tasks = {}

# Авторизация в Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Основной лист с содержимым постов
main_ws = client.open(SPREADSHEET_NAME).sheet1

# Инициализация листов
try:
    report_ws = client.open(SPREADSHEET_NAME).worksheet("report")
except Exception:
    sh = client.open(SPREADSHEET_NAME)
    report_ws = sh.add_worksheet(title="report", rows="1000", cols="5")
    report_ws.append_row(["DateTime Moscow", "UserID", "Start", "Paid", "Status"])

try:
    greeting_ws = client.open(SPREADSHEET_NAME).worksheet("greeting")
except Exception:
    greeting_ws = client.open(SPREADSHEET_NAME).add_worksheet(title="greeting", rows="10", cols="3")
    greeting_ws.update("A1", [["Welcome Message", "media_type", "file_url"], ["🚀 Отлично! Чтобы получать материалы, нажимай кнопку 'Далее'.", "", ""]])

try:
    broadcast_ws = client.open(SPREADSHEET_NAME).worksheet("broadcast")
except Exception:
    broadcast_ws = client.open(SPREADSHEET_NAME).add_worksheet(title="broadcast", rows="10", cols="3")
    broadcast_ws.update("A1", [["content", "media_type", "file_url"]])

def load_posts():
    return main_ws.get_all_records()

def get_greeting():
    try:
        message = greeting_ws.cell(2, 1).value
        media_type = greeting_ws.cell(2, 2).value.strip().lower()
        file_url = greeting_ws.cell(2, 3).value.strip()
        return message, media_type, file_url
    except Exception:
        logging.exception("Failed to load greeting message")
        return "Привет!", "text", ""

def get_broadcast():
    try:
        data = broadcast_ws.get_all_records()
        if not data:
            return None
        return data[0]  # Берём только первую строку
    except Exception:
        logging.exception("Failed to load broadcast message")
        return None

async def send_media(user_id: int, content: str, media_type: str, file_url: str):
    try:
        if media_type == "text":
            await bot.send_message(user_id, content)
        elif media_type == "photo":
            await bot.send_photo(user_id, photo=file_url, caption=content)
        elif media_type == "video":
            await bot.send_video(user_id, video=file_url, caption=content)
        elif media_type == "document":
            await bot.send_document(user_id, document=file_url, caption=content)
        elif media_type == "audio":
            await bot.send_audio(user_id, audio=file_url, caption=content)
        elif media_type == "voice":
            await bot.send_voice(user_id, voice=file_url, caption=content)
        elif media_type == "video_note":
            await bot.send_video_note(user_id, video_note=file_url)
        else:
            await bot.send_message(user_id, content)
    except Exception:
        logging.exception(f"Failed to send broadcast to {user_id}")

async def handle_broadcast(message: types.Message):
    if message.from_user.id != int(os.getenv("ADMIN_ID", "0")):
        await message.answer("⛔ Нет доступа.")
        return

    broadcast = get_broadcast()
    if not broadcast:
        await message.answer("❗Нет сообщения для рассылки.")
        return

    users = report_ws.col_values(2)[1:]  # Все user_id, кроме заголовка
    content = broadcast.get("content", "")
    media_type = broadcast.get("media_type", "text").strip().lower()
    file_url = broadcast.get("file_url", "").strip()

    for user_id in users:
        try:
            await send_media(int(user_id), content, media_type, file_url)
        except Exception:
            logging.exception(f"Broadcast failed for user {user_id}")
    await message.answer("📢 Рассылка завершена.")

# Остальной код (обработка команд /start, /stop, /paid и т.д.) остаётся без изменений...

# Регистрация хендлеров
dp.message.register(handle_broadcast, Command(commands=["broadcast"]))
# ... другие команды ниже
