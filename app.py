import os
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import telebot
from telebot.types import Update

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не задан!")
    raise RuntimeError("BOT_TOKEN не задан!")
logger.info("BOT_TOKEN загружен")

# Flask приложение
app = Flask(__name__)

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)
logger.info("TeleBot инициализирован")

# Путь для веб-хука
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
logger.info(f"Webhook path: {WEBHOOK_PATH}")

# --- Работа с базой данных ---
DB_NAME = 'water_meters.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            registered_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            water_type TEXT,
            value REAL,
            reading_date TEXT,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

def register_user(user_id, username, full_name):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        INSERT OR IGNORE INTO users (user_id, username, full_name, registered_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, full_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def save_reading(user_id, water_type, value):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    today = datetime.now().date().isoformat()
    cur.execute('''
        SELECT * FROM readings 
        WHERE user_id = ? AND water_type = ? AND reading_date = ?
    ''', (user_id, water_type, today))
    if cur.fetchone():
        conn.close()
        return False
    cur.execute('''
        INSERT INTO readings (user_id, water_type, value, reading_date, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, water_type, value, today, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_last_readings(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        SELECT water_type, value, reading_date 
        FROM readings 
        WHERE user_id = ? 
        ORDER BY reading_date DESC, created_at DESC
    ''', (user_id,))
    readings = cur.fetchall()
    conn.close()
    cold = None
    hot = None
    for r in readings:
        if r[0] == 'cold' and cold is None:
            cold = r
        if r[0] == 'hot' and hot is None:
            hot = r
    return cold, hot

def get_history(user_id, water_type, limit=5):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        SELECT value, reading_date 
        FROM readings 
        WHERE user_id = ? AND water_type = ?
        ORDER BY reading_date DESC, created_at DESC
        LIMIT ?
    ''', (user_id, water_type, limit))
    history = cur.fetchall()
    conn.close()
    return history

# --- Обработчики команд бота ---
user_state = {}

@bot.message_handler(commands=['start'])
def start(message):
    logger.info(f"Обработчик /start вызван от {message.from_user.id}")
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    register_user(user_id, username, full_name)
    
    from telebot import types
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("📊 Мои показания")
    btn2 = types.KeyboardButton("➕ Добавить показания")
    btn3 = types.KeyboardButton("📜 История")
    markup.add(btn1, btn2, btn3)
    
    bot.send_message(
        message.chat.id,
        f"Привет, {full_name}! 👋\n\nЯ помогу тебе вести учёт показаний счётчиков воды.\nИспользуй кнопки для навигации.",
        reply_markup=markup
    )
    logger.info(f"Ответ на /start отправлен пользователю {user_id}")

@bot.message_handler(func=lambda message: message.text == "📊 Мои показания")
def show_readings(message):
    logger.info(f"Показания запрошены от {message.from_user.id}")
    user_id = message.from_user.id
    cold, hot = get_last_readings(user_id)
    response = "📊 *Последние показания:*\n\n"
    if cold:
        response += f"❄️ Холодная вода: *{cold[1]}* м³\n📅 {cold[2]}\n"
    else:
        response += "❄️ Холодная вода: *нет данных*\n"
    if hot:
        response += f"🔥 Горячая вода: *{hot[1]}* м³\n📅 {hot[2]}\n"
    else:
        response += "🔥 Горячая вода: *нет данных*\n"
    bot.send_message(message.chat.id, response, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "➕ Добавить показания")
def add_reading_start(message):
    logger.info(f"Начало добавления показаний от {message.from_user.id}")
    from telebot import types
    markup = types.InlineKeyboardMarkup()
    btn_cold = types.InlineKeyboardButton("❄️ Холодная вода", callback_data="cold")
    btn_hot = types.InlineKeyboardButton("🔥 Горячая вода", callback_data="hot")
    markup.add(btn_cold, btn_hot)
    bot.send_message(message.chat.id, "Выберите тип счётчика:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["cold", "hot"])
def ask_for_value(call):
    water_type = call.data
    user_state[call.from_user.id] = {"water_type": water_type}
    type_name = "❄️ ХОЛОДНОЙ" if water_type == "cold" else "🔥 ГОРЯЧЕЙ"
    bot.edit_message_text(
        f"Введите показания для {type_name} воды (в м³):\n\nПример: 123.45 или 123",
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(call.message, save_reading_value)

def save_reading_value(message):
    user_id = message.from_user.id
    logger.info(f"Сохранение показаний от {user_id}: {message.text}")
    if user_id not in user_state or "water_type" not in user_state[user_id]:
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте снова.")
        return
    water_type = user_state[user_id]["water_type"]
    try:
        value = float(message.text.replace(',', '.'))
        if value < 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат. Введите число, например 123.45 или 123.\nПопробуйте снова.")
        del user_state[user_id]
        return
    success = save_reading(user_id, water_type, value)
    type_name = "холодной" if water_type == "cold" else "горячей"
    if success:
        bot.send_message(message.chat.id, f"✅ Показания для {type_name} воды ({value} м³) сохранены!")
    else:
        bot.send_message(message.chat.id, f"⚠️ Вы уже отправляли показания для {type_name} воды сегодня.\nМожно отправлять не чаще 1 раза в день.")
    del user_state[user_id]

@bot.message_handler(func=lambda message: message.text == "📜 История")
def show_history_menu(message):
    logger.info(f"История запрошена от {message.from_user.id}")
    from telebot import types
    markup = types.InlineKeyboardMarkup()
    btn_cold = types.InlineKeyboardButton("❄️ Холодная вода", callback_data="hist_cold")
    btn_hot = types.InlineKeyboardButton("🔥 Горячая вода", callback_data="hist_hot")
    markup.add(btn_cold, btn_hot)
    bot.send_message(message.chat.id, "Выберите счётчик для просмотра истории:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["hist_cold", "hist_hot"])
def show_history(call):
    user_id = call.from_user.id
    water_type = "cold" if call.data == "hist_cold" else "hot"
    type_name = "Холодная вода" if water_type == "cold" else "Горячая вода"
    emoji = "❄️" if water_type == "cold" else "🔥"
    history = get_history(user_id, water_type, limit=10)
    if not history:
        text = f"{emoji} {type_name}\n\nНет сохранённых показаний."
    else:
        text = f"{emoji} {type_name} - последние 10 показаний:\n\n"
        for value, date in history:
            text += f"📅 {date}: *{value}* м³\n"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    logger.info(f"Неизвестное сообщение от {message.from_user.id}: {message.text}")
    bot.send_message(message.chat.id, "Используйте кнопки меню для работы с ботом.")

# --- Flask маршруты ---
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    logger.info("Webhook запрос получен")
    if request.headers.get("content-type") != "application/json":
        logger.warning("Неверный content-type: %s", request.headers.get("content-type"))
        return "Unsupported Media Type", 415
    
    try:
        json_str = request.get_data().decode("utf-8")
        logger.info(f"Тело запроса: {json_str[:200]}")  # Логируем первые 200 символов
        update = Update.de_json(json_str)
        logger.info("Update объект создан, передаю в бота")
        bot.process_new_updates([update])
        logger.info("Обработка завершена")
    except Exception as e:
        logger.exception("Ошибка при обработке webhook")
        return "Internal Server Error", 500
    
    return "", 200

def set_webhook():
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        logger.warning("RENDER_EXTERNAL_URL не задан, пропускаем установку webhook")
        return
    
    webhook_url = f"{render_url.rstrip('/')}{WEBHOOK_PATH}"
    logger.info(f"Попытка установить webhook: {webhook_url}")
    bot.remove_webhook()
    result = bot.set_webhook(url=webhook_url)
    if result:
        logger.info(f"Webhook установлен: {webhook_url}")
    else:
        logger.error("Ошибка установки webhook")

# --- Инициализация при старте ---
logger.info("Инициализация приложения...")
init_db()
set_webhook()
logger.info("Приложение готово к работе")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
