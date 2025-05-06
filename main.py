import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

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

# Настройка доступа к Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
gs = gspread.authorize(credentials)
worksheet = gs.open(SPREADSHEET_NAME).sheet1

# Загрузка всех записей из таблицы
def load_posts():
    return worksheet.get_all_records()

# Отправка одного поста
async def send_post(user_id, post):
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

# Обработка всех входящих сообщений
@dp.message()
async def handle_all_messages(message: types.Message):
    user_id = message.from_user.id
    if message.text == "/start":
        logging.info(f"User {user_id} started sequence")
        await message.answer("🚀 Отлично! Сейчас начну присылать тебе материалы.")
        posts = load_posts()
        for post in posts:
            delay = int(post.get('delay_minutes', 0))
            await asyncio.sleep(delay * 60)
            await send_post(user_id, post)
    else:
        await message.answer("👋 Добро пожаловать! Нажми /start, чтобы начать.")

# Инициализация report sheet
try:
    report_ws = gs.open(SPREADSHEET_NAME).worksheet("report")
except Exception:
    # Если листа нет, создаём
    sh = gs.open(SPREADSHEET_NAME)
    report_ws = sh.add_worksheet(title="report", rows="1000", cols="5")
    # Устанавливаем заголовки
    report_ws.append_row(["DateTime Moscow","UserID","Start","Paid","Status"])

# Функция обновления отчёта
def update_report(user_id, start=None, paid=None, status=None):
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    # Ищем пользователя
    try:
        cell = report_ws.find(str(user_id), in_column=2)
        row = cell.row
        if start is not None:
            report_ws.update_cell(row, 3, "Yes" if start else "No")
            report_ws.update_cell(row, 1, now)
        if paid is not None:
            report_ws.update_cell(row, 4, "Yes" if paid else "No")
        if status is not None:
            report_ws.update_cell(row, 5, status)
    except Exception:
        # Если не найден — добавляем новую строку
        report_ws.append_row([
            now,
            str(user_id),
            "Yes" if start else "No" if start is not None else "",
            "Yes" if paid else "No" if paid is not None else "",
            status or ""
        ])

# Обработка всех входящих сообщений
@dp.message()
async def handle_all_messages(message: types.Message):
    user_id = message.from_user.id
    if message.text == "/start":
        logging.info(f"User {user_id} started sequence")
        update_report(user_id, start=True, status="Subscribed")
        await message.answer("🚀 Отлично! Сейчас начну присылать тебе материалы.")
        posts = load_posts()
        for post in posts:
            delay = int(post.get('delay_minutes', 0))
            await asyncio.sleep(delay * 60)
            await send_post(user_id, post)
        # после рассылки остаём статус подписан, paid по команде
    elif message.text == "/stop":
        update_report(user_id, status="Unsubscribed")
        await message.answer("👋 Вы отписались. Чтобы начать заново, нажмите /start.")
    elif message.text == "/paid":
        update_report(user_id, paid=True)
        await message.answer("✅ Отметил оплату. Спасибо!")
    else:
        await message.answer("👋 Добро пожаловать! Нажми /start, чтобы начать или /paid после оплаты.")

# Запуск бота
async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
