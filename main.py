import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

print("=== RENDER VERSION V3 STARTED ===")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "V3 OK\n"
        "Команды:\n"
        "/start\n"
        "/id"
    )

@dp.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(
        f"V3 ID = <code>{message.from_user.id}</code>\n"
        f"CHAT = <code>{message.chat.id}</code>\n"
        f"USER = <code>{message.from_user.username or 'none'}</code>"
    )

async def main():
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())