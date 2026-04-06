import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

print("=== WATER BOT FINAL STARTED ===")

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
        ],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
        input_field_placeholder="Нажмите кнопку"
    )


def format_moscow_time(iso_string: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        dt_msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
        return dt_msk.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return iso_string


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
            raw_date = data.get("date", "—")
            pretty_date = format_moscow_time(raw_date) if raw_date != "—" else "—"

            return (
                "📊 <b>Текущие показания</b>\n\n"
                f"🚿 Холодная: <b>{cold}</b>\n"
                f"♨️ Горячая: <b>{hot}</b>\n"
                f"🗓 <b>{pretty_date}</b>"
            )

        except Exception as e:
            return f"❗ Ошибка: <code>{type(e).__name__}: {e}</code>"


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
        await progress.edit_text(readings, reply_markup=main_keyboard())
    except Exception:
        await message.answer(readings, reply_markup=main_keyboard())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_allowed(message):
        return

    await message.answer(
        "ℹ️ <b>Помощь</b>\n\n"
        "📊 Показания — получить текущие данные\n"
        "🔄 Обновить — обновить показания\n"
        "🆔 ID — показать техническую информацию",
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
    else:
        await message.answer(
            "Нажмите кнопку ниже.",
            reply_markup=main_keyboard()
        )


async def health_check(request):
    return web.Response(text="OK")


async def main():
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.delete_my_commands()

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