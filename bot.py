import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonCommands
import config
import database
from datetime import datetime

bot = telebot.TeleBot(config.TOKEN)

# Словарь для хранения временного состояния пользователя
user_state = {}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    database.register_user(user_id, username, full_name)
    
    # Клавиатура в чате (под полем ввода)
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = KeyboardButton("📊 Мои показания")
    btn2 = KeyboardButton("➕ Добавить показания")
    btn3 = KeyboardButton("📜 История")
    markup.add(btn1, btn2, btn3)
    
    # Приветственное сообщение
    bot.send_message(
        message.chat.id,
        f"Привет, {full_name}! 👋\n\n"
        "Я помогу тебе вести учёт показаний счётчиков воды.\n"
        "Используй кнопки для навигации.",
        reply_markup=markup
    )
    
    # НАСТРОЙКА КНОПКИ МЕНЮ (в интерфейсе Telegram, справа от поля ввода)
    # Эта кнопка будет показывать список команд при нажатии
    bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonCommands("commands")
    )

@bot.message_handler(func=lambda message: message.text == "📊 Мои показания")
def show_readings(message):
    user_id = message.from_user.id
    cold, hot = database.get_last_readings(user_id)
    
    response = "📊 *Последние показания:*\n\n"
    
    if cold:
        response += f"❄️ Холодная вода: *{cold[1]}* м³\n"
        response += f"   📅 {cold[2]}\n"
    else:
        response += "❄️ Холодная вода: *нет данных*\n"
    
    if hot:
        response += f"🔥 Горячая вода: *{hot[1]}* м³\n"
        response += f"   📅 {hot[2]}\n"
    else:
        response += "🔥 Горячая вода: *нет данных*\n"
    
    bot.send_message(message.chat.id, response, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "➕ Добавить показания")
def add_reading_start(message):
    markup = InlineKeyboardMarkup()
    btn_cold = InlineKeyboardButton("❄️ Холодная вода", callback_data="cold")
    btn_hot = InlineKeyboardButton("🔥 Горячая вода", callback_data="hot")
    markup.add(btn_cold, btn_hot)
    
    bot.send_message(
        message.chat.id,
        "Выберите тип счётчика:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ["cold", "hot"])
def ask_for_value(call):
    water_type = call.data
    user_state[call.from_user.id] = {"water_type": water_type}
    
    type_name = "❄️ ХОЛОДНОЙ" if water_type == "cold" else "🔥 ГОРЯЧЕЙ"
    
    bot.edit_message_text(
        f"Введите показания для {type_name} воды (в м³):\n\n"
        f"Пример: 123.45 или 123",
        call.message.chat.id,
        call.message.message_id
    )
    
    # Регистрируем следующий шаг
    bot.register_next_step_handler(call.message, save_reading_value)

def save_reading_value(message):
    user_id = message.from_user.id
    
    if user_id not in user_state or "water_type" not in user_state[user_id]:
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте снова.")
        return
    
    water_type = user_state[user_id]["water_type"]
    
    try:
        value = float(message.text.replace(',', '.'))
        if value < 0:
            raise ValueError("Отрицательное значение")
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Неверный формат. Введите число, например 123.45 или 123.\n"
            "Попробуйте снова через кнопку '➕ Добавить показания'."
        )
        del user_state[user_id]
        return
    
    success = database.save_reading(user_id, water_type, value)
    
    type_name = "холодной" if water_type == "cold" else "горячей"
    
    if success:
        bot.send_message(
            message.chat.id,
            f"✅ Показания для {type_name} воды ({value} м³) сохранены!"
        )
    else:
        bot.send_message(
            message.chat.id,
            f"⚠️ Вы уже отправляли показания для {type_name} воды сегодня.\n"
            f"Можно отправлять не чаще 1 раза в день."
        )
    
    del user_state[user_id]

@bot.message_handler(func=lambda message: message.text == "📜 История")
def show_history_menu(message):
    markup = InlineKeyboardMarkup()
    btn_cold = InlineKeyboardButton("❄️ Холодная вода", callback_data="hist_cold")
    btn_hot = InlineKeyboardButton("🔥 Горячая вода", callback_data="hist_hot")
    markup.add(btn_cold, btn_hot)
    
    bot.send_message(
        message.chat.id,
        "Выберите счётчик для просмотра истории:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ["hist_cold", "hist_hot"])
def show_history(call):
    user_id = call.from_user.id
    water_type = "cold" if call.data == "hist_cold" else "hot"
    type_name = "Холодная вода" if water_type == "cold" else "Горячая вода"
    emoji = "❄️" if water_type == "cold" else "🔥"
    
    history = database.get_history(user_id, water_type, limit=10)
    
    if not history:
        text = f"{emoji} {type_name}\n\nНет сохранённых показаний."
    else:
        text = f"{emoji} {type_name} - последние 10 показаний:\n\n"
        for value, date in history:
            text += f"📅 {date}: *{value}* м³\n"
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.send_message(
        message.chat.id,
        "Используйте кнопки меню для работы с ботом."
    )

if __name__ == "__main__":
    database.init_db()
    print("Бот запущен...")
    bot.infinity_polling()
