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
from aiogram.exceptions import TelegramForbiddenError
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

# Инициализация листа report
try:
    report_ws = client.open(SPREADSHEET_NAME).worksheet("report")
except Exception:
    sh = client.open(SPREADSHEET_NAME)
    report_ws = sh.add_worksheet(title="report", rows="1000", cols="5")
    report_ws.append_row(["DateTime Moscow", "UserID", "Start", "Paid", "Status"])

# Загрузка всех записей из основной таблицы
def load_posts():
    return main_ws.get_all_records()

# Поиск строки пользователя в report
def find_user_row(user_id):
    records = report_ws.get_all_records()
    for idx, row in enumerate(records, start=2):
        if str(row.get("UserID")) == str(user_id):
            return idx
    return None

# Обновление или добавление строки в report
def update_or_append_report(user_id, start=None, paid=None, status=None):
    now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    row_idx = find_user_row(user_id)
    if row_idx:
        if start is not None:
            report_ws.update_cell(row_idx, 3, start)
        if paid is not None:
            report_ws.update_cell(row_idx, 4, paid)
        if status is not None:
            report_ws.update_cell(row_idx, 5, status)
        report_ws.update_cell(row_idx, 1, now)
    else:
        report_ws.append_row([now, str(user_id), start or "", paid or "", status or ""])

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
    file_path = file_url if file_url.startswith("http") else os.path.join("/home/admin/telegram_bot", file_url)
    with_pay_button = str(post.get('pay_button', '')).strip().lower() == 'true'
    with_next_button = str(post.get('button', '')).strip().lower() == 'true'
    delay = int(post.get('delay_minutes', 0))

    buttons = []
    if with_pay_button:
        buttons.append([
            InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{post_index}")
        ])
    if with_next_button:
        buttons.append([InlineKeyboardButton(text="➡️ Далее", callback_data=f"next_{post_index+1}")])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    try:
        if media_type == "text":
            await bot.send_message(user_id, content, reply_markup=markup)
        elif media_type == "photo":
            await bot.send_photo(user_id, photo=file_path, caption=content, reply_markup=markup)
        elif media_type == "video":
            await bot.send_video(user_id, video=file_path, caption=content, reply_markup=markup)
        elif media_type == "document":
            await bot.send_document(user_id, document=file_path, caption=content, reply_markup=markup)
        elif media_type == "audio":
            await bot.send_audio(user_id, audio=file_path, caption=content, reply_markup=markup)
        elif media_type == "voice":
            await bot.send_voice(user_id, voice=file_path, caption=content, reply_markup=markup)
        elif media_type == "video_note":
            from aiogram.types import FSInputFile

            if file_url.startswith("http"):
                # Скачивание в temp файл
                import aiohttp
                import tempfile
                async with aiohttp.ClientSession() as session:
                    async with session.get(file_url) as resp:
                        if resp.status == 200:
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                            tmp.write(await resp.read())
                            tmp.close()
                            import subprocess
                            try:
                                result = subprocess.run(
                                    ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                     "stream=width,height,duration", "-of", "csv=p=0", tmp.name],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT
                                )
                                width, height, duration = result.stdout.decode().strip().split(',')
                                if width != height:
                                    logging.warning(f"Video is not square: {width}x{height}")
                                if float(duration) > 60:
                                    logging.warning(f"Video duration too long: {duration}s")
                            except Exception:
                                logging.exception("Failed to verify video format")
                            await bot.send_video_note(user_id, video_note=FSInputFile(tmp.name))
                        else:
                            logging.warning(f"Couldn't download video_note from URL: {file_url}")
            else:
                await bot.send_video_note(user_id, video_note=FSInputFile(file_path))
        else:
            logging.warning(f"Unknown media type '{media_type}' for user {user_id}")
    except TelegramForbiddenError:
        logging.warning(f"User {user_id} blocked the bot. Marking as Unsubscribed.")
        update_or_append_report(user_id, start="No", status="Unsubscribed")
    except Exception:
        logging.exception(f"Error sending post to {user_id}")

    if post_index + 1 < len(posts):
        if user_id in user_tasks and user_tasks[user_id]:
            user_tasks[user_id].cancel()
        user_tasks[user_id] = asyncio.create_task(schedule_next_post(user_id, post_index + 1, delay))

# Планирование следующего поста по таймеру
async def schedule_next_post(user_id: int, post_index: int, delay: int):
    try:
        await asyncio.sleep(delay * 60)
        user_progress[user_id] = post_index
        await send_post(user_id, post_index)
    except asyncio.CancelledError:
        logging.info(f"Auto-sending to {user_id} cancelled manually.")

# Обработчик команды /start
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    logging.info(f"User {user_id} started sequence")

    try:
        update_or_append_report(user_id, start="Yes", status="Subscribed")
    except Exception:
        logging.exception(f"Failed to log /start for {user_id}")

    user_progress[user_id] = 0
    await send_post(user_id, 0)

# Обработка кнопки "Оплатить"
@dp.callback_query(F.data.startswith("pay_"))
async def handle_payment(callback: CallbackQuery):
    index = int(callback.data.split("_")[1])
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌟 Оплатить звёздочками Telegram", url=os.getenv("TRIBUTE_LINK")),
            InlineKeyboardButton(text="💳 Оплатить картой", url=os.getenv("YOOMONEY_LINK"))
        ]
    ])
    await callback.message.answer("Выберите способ оплаты:", reply_markup=markup)
    await callback.answer()


# Обработка кнопки "Далее"
@dp.callback_query(F.data.startswith("next_"))
async def handle_next(callback: CallbackQuery):
    user_id = callback.from_user.id
    next_index = int(callback.data.split("_")[1])
    user_progress[user_id] = next_index

    if user_id in user_tasks and user_tasks[user_id]:
        user_tasks[user_id].cancel()

    await send_post(user_id, next_index)
    await callback.answer()

# Обработчик команды /stop
async def handle_stop(message: types.Message):
    user_id = message.from_user.id
    try:
        update_or_append_report(user_id, start="No", paid="No", status="Unsubscribed")
    except Exception:
        logging.exception(f"Failed to log /stop for {user_id}")
    await message.answer("👋 Вы отписались. Чтобы начать заново, нажмите /start.")

# Обработчик команды /paid
async def handle_paid(message: types.Message):
    user_id = message.from_user.id
    try:
        update_or_append_report(user_id, paid="Yes", status="Subscribed")
    except Exception:
        logging.exception(f"Failed to log /paid for {user_id}")
    await message.answer("✅ Отметил оплату. Спасибо!")

# Обработчик команды /broadcast
async def handle_broadcast(message: types.Message):
    admin_id = os.getenv("ADMIN_ID")
    if str(message.from_user.id) != str(admin_id):
        await message.answer("⛔️ У вас нет прав на выполнение этой команды.")
        return

    try:
        records = report_ws.get_all_records()
        user_ids = list({str(row['UserID']) for row in records if row.get('Status') == 'Subscribed'})

        try:
            broadcast_ws = client.open(SPREADSHEET_NAME).worksheet("broadcast")
            row = broadcast_ws.get_all_records()[0]
            content = row.get('content', '')
            media_type = str(row.get('media_type', '')).strip().lower()
            file_url = str(row.get('file_url', '')).strip()
        except Exception:
            await message.answer("❌ Не удалось прочитать вкладку broadcast.")
            return

        success, fail = 0, 0
        for uid in user_ids:
            try:
                uid = int(uid)
                if media_type == "text" or not media_type:
                    await bot.send_message(uid, content)
                elif media_type == "photo":
                    await bot.send_photo(uid, photo=file_url, caption=content)
                elif media_type == "video":
                    await bot.send_video(uid, video=file_url, caption=content)
                elif media_type == "document":
                    await bot.send_document(uid, document=file_url, caption=content)
                elif media_type == "audio":
                    await bot.send_audio(uid, audio=file_url, caption=content)
                elif media_type == "voice":
                    await bot.send_voice(uid, voice=file_url, caption=content)
                elif media_type == "video_note":
                    from aiogram.types import FSInputFile
                    import aiohttp, tempfile
                    if file_url.startswith("http"):
                        async with aiohttp.ClientSession() as session:
                            async with session.get(file_url) as resp:
                                if resp.status == 200:
                                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                                    tmp.write(await resp.read())
                                    tmp.close()
                                    await bot.send_video_note(uid, video_note=FSInputFile(tmp.name))
                                else:
                                    logging.warning(f"Couldn't download video_note from URL: {file_url}")
                    else:
                        await bot.send_video_note(uid, video_note=FSInputFile(file_url))
                else:
                    await bot.send_message(uid, content)
                success += 1
            except Exception:
                fail += 1
                logging.exception(f"Failed to send broadcast to {uid}")

        await message.answer(f"📢 Broadcast завершён. Успешно: {success}, ошибок: {fail}")

    except Exception:
        logging.exception("Broadcast failed")
        await message.answer("❌ Произошла ошибка при рассылке.")

# Регистрация хендлеров команд
dp.message.register(handle_start, Command(commands=["start"]))
dp.message.register(handle_stop, Command(commands=["stop"]))
dp.message.register(handle_paid, Command(commands=["paid"]))
dp.message.register(handle_broadcast, Command(commands=["broadcast"]))

# Точка входа
async def main():
    logging.info("Bot is starting polling now...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
