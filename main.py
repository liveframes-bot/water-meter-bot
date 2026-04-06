import asyncio
import os
import httpx

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    BotCommand,
)
from aiohttp import web

print("=== WATER BOT V6 STARTED ===")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

APPS_SCRIPT_TOKEN = os.getenv("APPS_SCRIPT_TOKEN")
if not APPS_SCRIPT_TOKEN:
    raise RuntimeError("APPS_SCRIPT_TOKEN is not set")

ALLOWED_USER_ID = 380718700

APPS_SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzzFf3uHEFQ0vqTJq5WR6ASVeI72Q9Rt-s49LzaWbRBRHgC6P2eEHZUkfcRNweyljf7/exec"
)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


def is_allowed(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == ALLOWED_USER_ID)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Показания"),
                KeyboardButton(text="🔄 Обновить"),
            ],
            [
                KeyboardButton(text="ℹ️ Помощь"),
                KeyboardButton(text="🆔 ID"),
            ],
            [
                KeyboardButton(text="📋 Меню"),
                KeyboardButton(text="❌ Скрыть"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Нажмите кнопку"
    )


async def setup_bot_commands() -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Запуск"),
        BotCommand(command="menu", description="Показать клавиатуру"),
        BotCommand(command="status", description="Показать показания"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="id", description="Мой ID и chat ID"),
    ])


async def get_readings_from_script() -> str:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        params = {
            "action": "get",
            "token": APPS_SCRIPT_TOKEN,
        }

        try:
            resp = await client.get(APPS_SCRIPT_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                return f"❗ Ошибка Apps Script: <code>{data['error']}</code>"

            cold = data.get("cold", "—")
            hot = data.get("hot", "—")
            date = data.get("date", "—")

            return (
                "📊 <b>Текущие показания</b>\n\n"
                f"🚿 Холодная: <b>{cold}</b>\n"
                f"♨️ Горячая: <b>{hot}</b>\n"
                f"📅 Дата: <b>{date}</b>"
            )

        except Exception as e:
            return f"❗ Ошибка: <code>{type(e).__name__}: {e}</code>"


async def send_menu(message: Message, text: str = "📋 Главное меню") -> None:
    await message.answer(text, reply_markup=main_keyboard())


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed(message):
        return

    await message.answer(
        "Привет.\n"
        "Я показываю показания счётчиков из Google Таблицы.\n\n"
        "Используйте кнопки снизу.",
        reply_markup=main_keyboard()
    )


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    if not is_allowed(message):
        return

    await send_menu(message)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_allowed(message):
        return

    await message.answer(
        "ℹ️ <b>Что умеет бот</b>\n\n"
        "📊 Показания — запросить данные из Google Таблицы\n"
        "🔄 Обновить — повторить запрос\n"
        "🆔 ID — показать техническую информацию\n"
        "📋 Меню — снова показать кнопки\n"
        "❌ Скрыть — убрать нижнюю клавиатуру\n\n"
        "Команды:\n"
        "/start\n"
        "/menu\n"
        "/status\n"
        "/help\n"
        "/id",
        reply_markup=main_keyboard()
    )


@dp.message(Command("id"))
async def cmd_id(message: Message):
    if not is_allowed(message):
        return

    username = message.from_user.username or "none"

    await message.answer(
        "🆔 <b>Техническая информация</b>\n\n"
        f"USER ID: <code>{message.from_user.id}</code>\n"
        f"CHAT ID: <code>{message.chat.id}</code>\n"
        f"USERNAME: <code>{username}</code>",
        reply_markup=main_keyboard()
    )


@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not is_allowed(message):
        return

    progress = await message.answer(
        "⏳ Загружаю показания...",
        reply_markup=main_keyboard()
    )

    readings = await get_readings_from_script()

    try:
        await progress.edit_text(readings)
    except Exception:
        await message.answer(readings, reply_markup=main_keyboard())


@dp.message()
async def on_buttons(message: Message):
    if not is_allowed(message):
        return

    text = (message.text or "").strip()

    if text in ("📊 Показания", "🔄 Обновить"):
        await cmd_status(message)
    elif text == "ℹ️ Помощь":
        await cmd_help(message)
    elif text == "🆔 ID":
        await cmd_id(message)
    elif text == "📋 Меню":
        await cmd_menu(message)
    elif text == "❌ Скрыть":
        await message.answer(
            "Клавиатура скрыта.\nЧтобы вернуть её, отправьте /menu",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "Не понял запрос.\nНажмите кнопку ниже или отправьте /menu",
            reply_markup=main_keyboard()
        )


async def health_check(request):
    return web.Response(text="OK")


async def main():
    await bot.delete_webhook(drop_pending_updates=False)
    await setup_bot_commands()

    app = web.Application()
    app.router.add_get("/", health_check)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
