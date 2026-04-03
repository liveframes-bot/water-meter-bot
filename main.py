import asyncio
import os
import httpx

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiohttp import web

print("=== RENDER V3 STARTED ===")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

ALLOWED_USER_ID = 380718700

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzzFf3uHEFQ0vqTJq5WR6ASVeI72Q9Rt-s49LzaWbRBRHgC6P2eEHZUkfcRNweyljf7/exec"
APPS_SCRIPT_TOKEN = "water_2026_secret"

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


def is_allowed(message: Message) -> bool:
    return message.from_user.id == ALLOWED_USER_ID


async def get_readings_from_script() -> str:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        params = {"action": "get", "token": APPS_SCRIPT_TOKEN}
        try:
            resp = await client.get(APPS_SCRIPT_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                return f"Ошибка Apps Script: {data['error']}"

            cold = data.get("cold", "—")
            hot = data.get("hot", "—")
            date = data.get("date", "—")
            return f"Холодная: {cold}\nГорячая: {hot}\nДата: {date}"
        except Exception as e:
            return f"Ошибка: {type(e).__name__}: {e}"


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed(message):
        return
    await message.answer(
        "V3 OK\n"
        "Команды:\n"
        "/start\n"
        "/id\n"
        "/status"
    )


@dp.message(Command("id"))
async def cmd_id(message: Message):
    if not is_allowed(message):
        return
    await message.answer(
        f"V3 ID = {message.from_user.id}\n"
        f"CHAT = {message.chat.id}\n"
        f"USER = {message.from_user.username or 'none'}"
    )


@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not is_allowed(message):
        return
    await message.answer("Загружаю показания...")
    readings = await get_readings_from_script()
    await message.answer(
        f"Показания счётчиков\n\n{readings}"
    )


async def health_check(request):
    return web.Response(text="OK")


async def main():
    # снимаем webhook, чтобы точно работал polling
    await bot.delete_webhook(drop_pending_updates=False)

    # простой health-check сервер для Render
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    # запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
