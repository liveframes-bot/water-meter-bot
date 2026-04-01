import os
import logging
import requests
from flask import Flask, request, jsonify
import telebot
from telebot.types import Update
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан!")

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyUnjNzY1-JrTSSfPpP3UjJLpQ06Gyr_EmgmWgViRGf2_hvIxevRrIcFqMRLKCYJqVW/exec"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

def get_last_reading():
    try:
        resp = requests.get(SCRIPT_URL, params={"action": "get"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Данные из скрипта: {data}")
        return data
    except Exception as e:
        logger.exception("Ошибка при запросе к скрипту")
        return None

def start(message):
    logger.info(f"Вызван обработчик /start для {message.from_user.id}")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Последние показания")
    bot.send_message(
        message.chat.id,
        "Привет! Я покажу последние показания воды из вашей таблицы.",
        reply_markup=markup
    )
    logger.info("Ответ отправлен")

def show_last(message):
    logger.info(f"Вызван обработчик показаний для {message.from_user.id}")
    data = get_last_reading()
    if data is None:
        bot.send_message(message.chat.id, "❌ Не удалось получить данные. Попробуйте позже.")
        return
    dt_str = data.get("date", "")
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        dt_local = dt.astimezone()
        dt_formatted = dt_local.strftime("%d.%m.%Y %H:%M:%S")
    except:
        dt_formatted = dt_str
    cold = data.get("cold", 0)
    hot = data.get("hot", 0)
    text = f"📊 *Последние показания:*\n\n" \
           f"📅 {dt_formatted}\n" \
           f"❄️ Холодная вода: *{cold:.2f}* м³\n" \
           f"🔥 Горячая вода: *{hot:.2f}* м³"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")
    logger.info("Показания отправлены
