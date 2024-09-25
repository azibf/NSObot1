import telebot
from telebot import types
import psycopg2
from datetime import datetime, timedelta
import time
from config import *

bot = telebot.TeleBot(BOT_TOKEN)

# Connect to the database
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        type VARCHAR(255),
        title VARCHAR(255),
        date TIMESTAMP,
        url VARCHAR(255)
    )
""")
conn.commit()

def kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("/start")
    item2 = types.KeyboardButton("/help")
    item3 = types.KeyboardButton("/get_ctf")
    item4 = types.KeyboardButton("/get_olymp")
    item5 = types.KeyboardButton("/add_event")
    markup.add(item1, item2, item3, item4, item5)
    return markup

# Function to add an event
def add_event(event_type, title, event_date, url):
    cursor.execute("""
        INSERT INTO events (type, title, date, url)
        VALUES (%s, %s, %s, %s)
    """, (event_type, title, event_date, url))
    conn.commit()

# Function to get events
def get_events():
    cursor.execute("SELECT * FROM events")
    return cursor.fetchall()

# Function to get CTF events
def get_ctf():
    cursor.execute("SELECT * FROM events WHERE type = 'CTF' ORDER BY date ASC")
    return cursor.fetchall()

# Function to get Olympic events
def get_olymp():
    cursor.execute("SELECT * FROM events WHERE type = 'Olymp' ORDER BY date ASC")
    return cursor.fetchall()

# Function to delete expired events
def delete_expired_events():
    current_date = datetime.now()
    cursor.execute("DELETE FROM events WHERE date < %s", (current_date,))
    conn.commit()

# Function to send reminders
def send_reminders():
    events = get_events()
    for event in events:
        num, event_type, title, event_date, url = event
        current_date = datetime.now()
        three_days_before = event_date - timedelta(days=3)
        one_day_before = event_date - timedelta(days=1)

        if current_date >= three_days_before and current_date < event_date:
            bot.send_message(chat_id=user_id, text=f"НАПОМИНАНИЕ: {title} - {url} случится через 3 дня!", reply_markup=kb())
        elif current_date >= one_day_before and current_date < three_days_before:
            bot.send_message(chat_id=user_id, text=f"НАПОМИНАНИЕ: {title} - {url} случится через 1 день!", reply_markup=kb())

# Command handler for adding an event
@bot.message_handler(commands=['add_event'])
def handle_add_event(message):
    user_id = message.from_user.id
    data = message.text.split('\n')
    event_type = data[1][1:]
    if event_type not in ["CTF", "Olymp"]:
        bot.send_message(chat_id=user_id, text="Тип события не соотвествует #CTF или #Olymp!", reply_markup=kb())
    else:
        title = data[2]
        event_date = datetime.strptime(data[3], '%d.%m.%Y')
        url = data[4]
        add_event(event_type, title, event_date, url)
        bot.send_message(chat_id=user_id, text="Событие добавлено успешно!", reply_markup=kb())


@bot.message_handler(commands=['start'])
def start_message(message):
  bot.send_message(message.chat.id,
'''Привет ✌️ 
Я помогаю планировать расписание мероприятий для НСО
''', reply_markup=kb())

# Command handler for getting CTF events
@bot.message_handler(commands=['get_ctf'])
def handle_get_ctf(message):
    user_id = message.from_user.id
    ctf_events = get_ctf()
    if ctf_events:
        response = "Предстоящие CTF:\n"
        for event in ctf_events:
            num, event_type, title, event_date, url = event
            response += f"{title} - {event_date.strftime('%d.%m.%Y')} - {url}\n"
        bot.send_message(chat_id=user_id, text=response, reply_markup=kb())
    else:
        bot.send_message(chat_id=user_id, text="Нет предстоящих CTF.", reply_markup=kb())

# Command handler for getting Olympic events
@bot.message_handler(commands=['get_olymp'])
def handle_get_olymp(message):
    user_id = message.from_user.id
    olymp_events = get_olymp()
    if olymp_events:
        response = "Предстоящие олимпиады:\n"
        for event in olymp_events:
            num, event_type, title, event_date, url = event
            response += f"{title} - {event_date.strftime('%d.%m.%Y')} - {url}\n"
        bot.send_message(chat_id=user_id, text=response, reply_markup=kb())
    else:
        bot.send_message(chat_id=user_id, text="Нет предстоящих олимпиад.", reply_markup=kb())

# Command handler for help
@bot.message_handler(commands=['help'])
def handle_help(message):
    user_id = message.from_user.id
    help_text = """
Доступные команды:
- /add_event - Добавить новое событие
<тип события #CTF/#Olymp>
<название>
<дата дд.мм.гггг>
<url>

- /get_ctf - Получить список CTF
- /get_olymp - Получить список олимпиад
- /help - Показать это сообщение
"""
    bot.send_message(chat_id=user_id, text=help_text, reply_markup=kb())

# Start the bot
bot.polling()

# Run the reminder check every minute
while True:
    send_reminders()
    time.sleep(60)