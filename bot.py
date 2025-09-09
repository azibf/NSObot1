import telebot
from telebot import types
import psycopg2
from datetime import datetime, timedelta
import time
from config import *

# list of super administrators should be defined in config as SUPER_ADMINS
try:
    SUPER_ADMINS
except NameError:
    SUPER_ADMINS = []

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

# Create tables if they don't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        type VARCHAR(255),
        title VARCHAR(255),
        date TIMESTAMP,
        url VARCHAR(255)
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id BIGINT PRIMARY KEY
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_proposals (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        type VARCHAR(255),
        title VARCHAR(255),
        date TIMESTAMP,
        url VARCHAR(255),
        status VARCHAR(50) DEFAULT 'pending'
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        text TEXT,
        response TEXT
    )
""")
conn.commit()


def is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS


def is_admin(user_id: int) -> bool:
    if is_super_admin(user_id):
        return True
    cursor.execute("SELECT 1 FROM admins WHERE user_id=%s", (user_id,))
    return cursor.fetchone() is not None


def get_admin_ids():
    cursor.execute("SELECT user_id FROM admins")
    ids = [row[0] for row in cursor.fetchall()]
    return list(set(ids + SUPER_ADMINS))


def kb(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("/start"))
    markup.add(types.KeyboardButton("/help"))
    markup.add(types.KeyboardButton("/list_events"))
    markup.add(types.KeyboardButton("/contact_admin"))
    markup.add(types.KeyboardButton("/propose_event"))
    if is_admin(user_id):
        markup.add(types.KeyboardButton("/add_event"))
        markup.add(types.KeyboardButton("/view_proposals"))
    if is_super_admin(user_id):
        markup.add(types.KeyboardButton("/add_admin"))
        markup.add(types.KeyboardButton("/remove_admin"))
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


# Functions for proposals and messages
def add_proposal(user_id, event_type, title, event_date, url):
    cursor.execute(
        """
        INSERT INTO event_proposals (user_id, type, title, date, url)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
        """,
        (user_id, event_type, title, event_date, url),
    )
    proposal_id = cursor.fetchone()[0]
    conn.commit()
    return proposal_id


def get_pending_proposals():
    cursor.execute(
        "SELECT id, type, title, date, url FROM event_proposals WHERE status='pending'"
    )
    return cursor.fetchall()


def update_proposal_status(proposal_id, status):
    cursor.execute(
        "UPDATE event_proposals SET status=%s WHERE id=%s", (status, proposal_id)
    )
    conn.commit()


def save_message(user_id, text):
    cursor.execute(
        "INSERT INTO messages (user_id, text) VALUES (%s,%s) RETURNING id",
        (user_id, text),
    )
    msg_id = cursor.fetchone()[0]
    conn.commit()
    return msg_id


def get_unanswered_messages():
    cursor.execute("SELECT id, user_id, text FROM messages WHERE response IS NULL")
    return cursor.fetchall()


def answer_message(msg_id, response):
    cursor.execute(
        "UPDATE messages SET response=%s WHERE id=%s RETURNING user_id",
        (response, msg_id),
    )
    row = cursor.fetchone()
    conn.commit()
    return row[0] if row else None

# Function to delete expired events
def delete_expired_events():
    current_date = datetime.now()
    cursor.execute("DELETE FROM events WHERE date < %s", (current_date,))
    conn.commit()

# Command handler for adding an event
@bot.message_handler(commands=['add_event'])
def handle_add_event(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(chat_id=user_id, text="Недостаточно прав", reply_markup=kb(user_id))
        return
    data = message.text.split('\n')
    if len(data) < 5:
        bot.send_message(chat_id=user_id, text="Формат:\n/add_event\n#CTF/#Olymp\nНазвание\nдд.мм.гггг\nurl", reply_markup=kb(user_id))
        return
    event_type = data[1][1:]
    if event_type not in ["CTF", "Olymp"]:
        bot.send_message(chat_id=user_id, text="Тип события не соотвествует #CTF или #Olymp!", reply_markup=kb(user_id))
    else:
        title = data[2]
        event_date = datetime.strptime(data[3], '%d.%m.%Y')
        url = data[4]
        add_event(event_type, title, event_date, url)
        bot.send_message(chat_id=user_id, text="Событие добавлено успешно!", reply_markup=kb(user_id))


@bot.message_handler(commands=['start'])
def start_message(message):
  uid = message.from_user.id
  bot.send_message(uid,
'''Привет ✌️
Я помогаю планировать расписание мероприятий для НСО
''', reply_markup=kb(uid))

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
        bot.send_message(chat_id=user_id, text=response, reply_markup=kb(user_id))
    else:
        bot.send_message(chat_id=user_id, text="Нет предстоящих CTF.", reply_markup=kb(user_id))

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
        bot.send_message(chat_id=user_id, text=response, reply_markup=kb(user_id))
    else:
        bot.send_message(chat_id=user_id, text="Нет предстоящих олимпиад.", reply_markup=kb(user_id))


@bot.message_handler(commands=['list_events'])
def handle_list_events(message):
    user_id = message.from_user.id
    events = get_events()
    if events:
        response = "Предстоящие мероприятия:\n"
        for event in events:
            num, event_type, title, event_date, url = event
            response += f"{title} ({event_type}) - {event_date.strftime('%d.%m.%Y')} - {url}\n"
        bot.send_message(chat_id=user_id, text=response, reply_markup=kb(user_id))
    else:
        bot.send_message(chat_id=user_id, text="Нет предстоящих мероприятий.", reply_markup=kb(user_id))


@bot.message_handler(commands=['propose_event'])
def handle_propose_event(message):
    user_id = message.from_user.id
    data = message.text.split('\n')
    if len(data) < 5:
        bot.send_message(chat_id=user_id, text="Формат:\n/propose_event\n#CTF/#Olymp\nНазвание\nдд.мм.гггг\nurl", reply_markup=kb(user_id))
        return
    event_type = data[1][1:]
    title = data[2]
    event_date = datetime.strptime(data[3], '%d.%m.%Y')
    url = data[4]
    proposal_id = add_proposal(user_id, event_type, title, event_date, url)
    for admin_id in get_admin_ids():
        bot.send_message(chat_id=admin_id, text=f"Новое предложение #{proposal_id} от {user_id}: {title} {event_date.strftime('%d.%m.%Y')} {url}")
    bot.send_message(chat_id=user_id, text="Предложение отправлено администраторам.", reply_markup=kb(user_id))


@bot.message_handler(commands=['view_proposals'])
def handle_view_proposals(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(chat_id=user_id, text="Недостаточно прав", reply_markup=kb(user_id))
        return
    proposals = get_pending_proposals()
    if proposals:
        response = "Предложения:\n"
        for prop in proposals:
            pid, etype, title, edate, url = prop
            response += f"{pid}: {title} ({etype}) - {edate.strftime('%d.%m.%Y')} - {url}\n"
        bot.send_message(chat_id=user_id, text=response, reply_markup=kb(user_id))
    else:
        bot.send_message(chat_id=user_id, text="Нет предложений.", reply_markup=kb(user_id))


@bot.message_handler(commands=['accept_event'])
def handle_accept_event(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(chat_id=user_id, text="Недостаточно прав", reply_markup=kb(user_id))
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(chat_id=user_id, text="Использование: /accept_event <id>", reply_markup=kb(user_id))
        return
    pid = parts[1]
    cursor.execute("SELECT user_id, type, title, date, url FROM event_proposals WHERE id=%s", (pid,))
    row = cursor.fetchone()
    if not row:
        bot.send_message(chat_id=user_id, text="Предложение не найдено", reply_markup=kb(user_id))
        return
    p_user, etype, title, edate, url = row
    add_event(etype, title, edate, url)
    update_proposal_status(pid, 'accepted')
    bot.send_message(chat_id=user_id, text="Событие добавлено.", reply_markup=kb(user_id))
    bot.send_message(chat_id=p_user, text=f"Ваше предложение '{title}' принято!", reply_markup=kb(p_user))


@bot.message_handler(commands=['reject_event'])
def handle_reject_event(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(chat_id=user_id, text="Недостаточно прав", reply_markup=kb(user_id))
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(chat_id=user_id, text="Использование: /reject_event <id>", reply_markup=kb(user_id))
        return
    pid = parts[1]
    cursor.execute("SELECT user_id, title FROM event_proposals WHERE id=%s", (pid,))
    row = cursor.fetchone()
    if not row:
        bot.send_message(chat_id=user_id, text="Предложение не найдено", reply_markup=kb(user_id))
        return
    p_user, title = row
    update_proposal_status(pid, 'rejected')
    bot.send_message(chat_id=user_id, text="Предложение отклонено.", reply_markup=kb(user_id))
    bot.send_message(chat_id=p_user, text=f"Ваше предложение '{title}' отклонено.", reply_markup=kb(p_user))


@bot.message_handler(commands=['contact_admin'])
def handle_contact_admin(message):
    user_id = message.from_user.id
    text = message.text.partition(' ')[2].strip()
    if not text:
        bot.send_message(chat_id=user_id, text="Использование: /contact_admin <сообщение>", reply_markup=kb(user_id))
        return
    msg_id = save_message(user_id, text)
    for admin_id in get_admin_ids():
        bot.send_message(chat_id=admin_id, text=f"Сообщение #{msg_id} от {user_id}: {text}")
    bot.send_message(chat_id=user_id, text="Сообщение отправлено администраторам.", reply_markup=kb(user_id))


@bot.message_handler(commands=['reply'])
def handle_reply(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(chat_id=user_id, text="Недостаточно прав", reply_markup=kb(user_id))
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.send_message(chat_id=user_id, text="Использование: /reply <id> <текст>", reply_markup=kb(user_id))
        return
    msg_id = parts[1]
    response = parts[2]
    target_user = answer_message(msg_id, response)
    if target_user:
        bot.send_message(chat_id=target_user, text=response, reply_markup=kb(target_user))
        bot.send_message(chat_id=user_id, text="Ответ отправлен.", reply_markup=kb(user_id))
    else:
        bot.send_message(chat_id=user_id, text="Сообщение не найдено.", reply_markup=kb(user_id))


@bot.message_handler(commands=['add_admin'])
def handle_add_admin(message):
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        bot.send_message(chat_id=user_id, text="Недостаточно прав", reply_markup=kb(user_id))
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(chat_id=user_id, text="Использование: /add_admin <user_id>", reply_markup=kb(user_id))
        return
    target = int(parts[1])
    cursor.execute("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (target,))
    conn.commit()
    bot.send_message(chat_id=user_id, text="Администратор добавлен.", reply_markup=kb(user_id))
    try:
        bot.send_message(chat_id=target, text="Вы назначены администратором.", reply_markup=kb(target))
    except Exception:
        pass


@bot.message_handler(commands=['remove_admin'])
def handle_remove_admin(message):
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        bot.send_message(chat_id=user_id, text="Недостаточно прав", reply_markup=kb(user_id))
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(chat_id=user_id, text="Использование: /remove_admin <user_id>", reply_markup=kb(user_id))
        return
    target = int(parts[1])
    cursor.execute("DELETE FROM admins WHERE user_id=%s", (target,))
    conn.commit()
    bot.send_message(chat_id=user_id, text="Администратор удалён.", reply_markup=kb(user_id))
    try:
        bot.send_message(chat_id=target, text="Вы больше не администратор.", reply_markup=kb(target))
    except Exception:
        pass

# Command handler for help
@bot.message_handler(commands=['help'])
def handle_help(message):
    user_id = message.from_user.id
    help_lines = [
        "Доступные команды:",
        "/list_events - список мероприятий",
        "/get_ctf - список CTF",
        "/get_olymp - список олимпиад",
        "/propose_event - предложить мероприятие",
        "/contact_admin - написать админу",
    ]
    if is_admin(user_id):
        help_lines.extend([
            "/add_event - добавить событие",
            "/view_proposals - предложения пользователей",
            "/accept_event <id> - принять предложение",
            "/reject_event <id> - отклонить предложение",
            "/reply <id> <текст> - ответить пользователю",
        ])
    if is_super_admin(user_id):
        help_lines.extend([
            "/add_admin <id> - назначить администратора",
            "/remove_admin <id> - удалить администратора",
        ])
    help_lines.append("/help - показать это сообщение")
    bot.send_message(chat_id=user_id, text="\n".join(help_lines), reply_markup=kb(user_id))

# Start the bot
bot.polling()
