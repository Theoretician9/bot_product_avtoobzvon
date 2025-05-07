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

# Инициализация листа report
try:
    report_ws = client.open(SPREADSHEET_NAME).worksheet("report")
except Exception:
    sh = client.open(SPREADSHEET_NAME)
    report_ws = sh.add_worksheet(title="report", rows="1000", cols="5")
    report_ws.append_row(["DateTime Moscow", "UserID", "Start", "Paid", "Status"])

# Инициализация листа greeting
try:
    greeting_ws = client.open(SPREADSHEET_NAME).worksheet("greeting")
except Exception:
    greeting_ws = client.open(SPREADSHEET_NAME).add_worksheet(title="greeting", rows="10", cols="1")
    greeting_ws.update("A1", [["Welcome Message"], ["🚀 Отлично! Чтобы получать материалы, нажимай кнопку 'Далее'."]])

# Загрузка всех записей из основной таблицы

def load_posts():
    return main_ws.get_all_records()

def get_greeting():
    try:
        return greeting_ws.cell(2, 1).value
    except Exception:
        logging.exception("Failed to load greeting message")
        return "Привет!"

# Функция отправки одного поста
async def send_post(user_id: int, post_index: int):
    posts = load_posts()
    if post_index >= len(posts):
        await bot.send_message(user_id, "✅ Все материалы были отправлены.")
        return

    post = posts[post_index]
    content = post.get('content', '')
    media_type = post.get('media_type', '').strip().lower()
    file_url = post.get('file_url', '').strip()
    with_button = str(post.get('pay_button', '')).strip().lower() == 'true'

    buttons = []
    if with_button and TRIBUTE_LINK:
        buttons.append([InlineKeyboardButton(text="💳 Оплатить", url=TRIBUTE_LINK)])
    buttons.append([InlineKeyboardButton(text="➡️ Далее", callback_data=f"next_{post_index+1}")])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

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
    except Exception:
        logging.exception(f"Error sending post to {user_id}")

# Обработчик команды /start
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    logging.info(f"User {user_id} started sequence")

    try:
        greeting = get_greeting()
        await message.answer(greeting)
    except Exception:
        await message.answer("🚀 Отлично! Чтобы получать материалы, нажимай кнопку 'Далее'.")

    try:
        now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
        report_ws.append_row([now, str(user_id), "Yes", "No", "Subscribed"])
    except Exception:
        logging.exception(f"Failed to log /start for {user_id}")

    user_progress[user_id] = 0
    await send_post(user_id, 0)

# Обработка кнопки "Далее"
@dp.callback_query(F.data.startswith("next_"))
async def handle_next(callback: CallbackQuery):
    user_id = callback.from_user.id
    next_index = int(callback.data.split("_")[1])
    user_progress[user_id] = next_index
    await send_post(user_id, next_index)
    await callback.answer()

# Обработчик команды /stop
async def handle_stop(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    try:
        report_ws.append_row([now, str(user_id), "No", "No", "Unsubscribed"])
    except Exception:
        logging.exception(f"Failed to log /stop for {user_id}")
    await message.answer("👋 Вы отписались. Чтобы начать заново, нажмите /start.")

# Обработчик команды /paid
async def handle_paid(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    try:
        report_ws.append_row([now, str(user_id), "", "Yes", "Subscribed"])
    except Exception:
        logging.exception(f"Failed to log /paid for {user_id}")
    await message.answer("✅ Отметил оплату. Спасибо!")

# Регистрация хендлеров команд
dp.message.register(handle_start, Command(commands=["start"]))
dp.message.register(handle_stop, Command(commands=["stop"]))
dp.message.register(handle_paid, Command(commands=["paid"]))

# Точка входа
async def main():
    logging.info("Bot is starting polling now...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
