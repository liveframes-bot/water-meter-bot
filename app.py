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

# URL вашего Google Apps Script
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyUnjNzY1-JrTSSfPpP3UjJLpQ06Gyr_EmgmWgViRGf2_hvIxevRrIcFqMRLKCYJqVW/exec"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

def get_last_reading():
    """Запрашивает последние показания через Apps Script"""
    try:
        resp = requests.get(SCRIPT_URL, params={"action": "get"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Получены данные: {data}")
        return data
    except Exception as e:
        logger.exception("Ошибка при запросе к скрипту")
        return None

def start(message):
    """Обработчик /start"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Последние показания")
    bot.send_message(
        message.chat.id,
        "Привет! Я покажу последние показания воды из вашей таблицы.",
        reply_markup=markup
    )

def show_last(message):
    """Показывает последние показания"""
    data = get_last_reading()
    if data is None:
        bot.send_message(message.chat.id, "❌ Не удалось получить данные. Попробуйте позже.")
        return

    # Преобразование даты
    dt_str = data.get("date", "")
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        dt_local = dt.astimezone()  # в локальное время
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

def unknown(message):
    """Ответ на неизвестные сообщения"""
    bot.send_message(message.chat.id, "Используйте кнопку «Последние показания».")

# --- Flask маршруты ---
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") != "application/json":
        return "Unsupported Media Type", 415
    try:
        json_str = request.get_data().decode("utf-8")
        update = Update.de_json(json_str)
        if update.message:
            msg = update.message
            if msg.text == '/start':
                start(msg)
            elif msg.text == "📊 Последние показания":
                show_last(msg)
            else:
                unknown(msg)
    except Exception as e:
        logger.exception("Ошибка в webhook")
        return "Internal Server Error", 500
    return "", 200

def set_webhook():
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        logger.warning("RENDER_EXTERNAL_URL не задан")
        return
    webhook_url = f"{render_url.rstrip('/')}{WEBHOOK_PATH}"
    bot.remove_webhook()
    result = bot.set_webhook(url=webhook_url)
    if result:
        logger.info(f"Webhook установлен: {webhook_url}")
    else:
        logger.error("Ошибка установки webhook")

set_webhook()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
