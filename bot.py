import os
import sqlite3
import threading
import time
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from flask import Flask

# ==========================================
# 1. BOT & MULTI-ADMIN SETUP
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS_STR = os.environ.get('ADMIN_IDS', '12345678') # Comma separated admin IDs
ADMIN_IDS = [int(aid.strip()) for aid in ADMIN_IDS_STR.split(',') if aid.strip().isdigit()]

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
user_states = {}

# ==========================================
# 2. SQLITE DATABASE SETUP
# ==========================================
DB_FILE = 'bot_database.db'
db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                          (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT)''')
        conn.commit()
        conn.close()

def add_user(user_id, username, first_name):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
                           (user_id, username, first_name))
            conn.commit()
            conn.close()
        except: pass

def get_all_users():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users

init_db()

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def notify_all_admins(text=None, photo_id=None, caption=None, document=None):
    for admin_id in ADMIN_IDS:
        try:
            if photo_id: bot.send_photo(admin_id, photo_id, caption=caption)
            elif document: bot.send_document(admin_id, document, caption=caption)
            elif text: bot.send_message(admin_id, text)
        except: pass

def get_user_link(user):
    """
    Agar username hai toh @username dega.
    Agar username NAHI hai, toh First Name ko Direct Profile Link bana dega!
    """
    if user.username:
        return f"@{user.username}"
    else:
        # Direct Telegram Profile Link
        return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"


# ==========================================
# 4. AUTO BACKUP SYSTEM (Every 8 Hours)
# ==========================================
def auto_backup_scheduler():
    while True:
        # 8 Hours = 8 * 60 * 60 seconds = 28800 seconds
        time.sleep(28800) 
        try:
            with open(DB_FILE, 'rb') as f:
                caption = f"💾 <b>AUTO BACKUP (8 HRS)</b> 💾\n\n🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n👥 Total Users: {len(get_all_users())}"
                notify_all_admins(document=f, caption=caption)
            print("Auto Backup sent successfully!")
        except Exception as e:
            print(f"Auto Backup Error: {e}")

# Backup thread start karo
threading.Thread(target=auto_backup_scheduler, daemon=True).start()


# ==========================================
# 5. DYNAMIC KEYBOARDS
# ==========================================
def get_main_keyboard(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("🎁 Claim Gift Code"))
    if user_id in ADMIN_IDS:
        markup.add(KeyboardButton("⚙️ Admin Panel"))
    return markup

def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📢 Broadcast"), KeyboardButton("👥 Users"), KeyboardButton("💾 Backup DB"))
    markup.add(KeyboardButton("🔙 Main Menu"))
    return markup


# ==========================================
# 6. CHANNEL JOIN REQUEST HANDLER
# ==========================================
@bot.chat_join_request_handler()
def handle_join_request(request):
    user = request.from_user
    add_user(user.id, user.username or "", user.first_name)
    
    # Username ya Direct Link logic yahan use hua hai
    user_identity = get_user_link(user)
    
    alert_text = f"🚨 <b>NEW CHANNEL JOIN REQUEST</b> 🚨\n\n👤 User: {user_identity}\n🆔 ID: <code>{user.id}</code>"
    notify_all_admins(text=alert_text)
    
    try:
        bot.send_message(user.id, "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅", 
                         reply_markup=get_main_keyboard(user.id))
        bot.approve_chat_join_request(request.chat.id, user.id)
    except: pass


# ==========================================
# 7. ADMIN PANEL CONTROLS
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name)
    user_states[user.id] = 'home'
    
    bot.reply_to(message, "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅", 
                 reply_markup=get_main_keyboard(user.id))

@bot.message_handler(func=lambda msg: msg.text == "⚙️ Admin Panel" and msg.from_user.id in ADMIN_IDS)
def open_admin_panel(message):
    user_states[message.from_user.id] = 'admin_panel'
    bot.reply_to(message, "🛠️ <b>Admin Panel</b>", reply_markup=get_admin_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "🔙 Main Menu" and msg.from_user.id in ADMIN_IDS)
def back_to_main(message):
    user_states[message.from_user.id] = 'home'
    bot.reply_to(message, "🏠 Main Menu", reply_markup=get_main_keyboard(message.from_user.id))

@bot.message_handler(func=lambda msg: msg.text == "👥 Users" and msg.from_user.id in ADMIN_IDS)
def show_total_users(message):
    bot.reply_to(message, f"👥 <b>Total Users:</b> {len(get_all_users())}")

# Admin can request MANUAL backup anytime
@bot.message_handler(func=lambda msg: msg.text == "💾 Backup DB" and msg.from_user.id in ADMIN_IDS)
def send_manual_backup(message):
    try:
        with open(DB_FILE, 'rb') as f:
            bot.send_document(message.chat.id, f, caption=f"💾 <b>MANUAL DB BACKUP</b>\nTotal Users: {len(get_all_users())}")
    except:
        bot.reply_to(message, "Error creating backup.")

@bot.message_handler(func=lambda msg: msg.text == "📢 Broadcast" and msg.from_user.id in ADMIN_IDS)
def ask_broadcast_msg(message):
    user_states[message.from_user.id] = 'waiting_for_broadcast'
    bot.reply_to(message, "👇 <b>Send Broadcast Message:</b>\n<i>(Type 'Cancel' to stop)</i>", reply_markup=ReplyKeyboardRemove())

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'waiting_for_broadcast')
def process_broadcast(message):
    if message.text and message.text.lower() == 'cancel':
        user_states[message.from_user.id] = 'admin_panel'
        return bot.reply_to(message, "❌ Cancelled.", reply_markup=get_admin_keyboard())

    users = get_all_users()
    bot.reply_to(message, f"🚀 Broadcast started for {len(users)} users.", reply_markup=get_admin_keyboard())
    user_states[message.from_user.id] = 'admin_panel'
    
    def run_broadcast(msg_text, u_list):
        success = 0
        for uid in u_list:
            try: bot.send_message(uid, msg_text); success += 1; time.sleep(0.05)
            except: pass
        bot.send_message(message.chat.id, f"📊 <b>Broadcast Complete:</b> {success} users got the message.")

    threading.Thread(target=run_broadcast, args=(message.text, users)).start()


# ==========================================
# 8. USER FLOW (3-Step Sequence)
# ==========================================
@bot.message_handler(func=lambda msg: msg.text == "🎁 Claim Gift Code")
def step2_links(message):
    user_states[message.from_user.id] = 'step2'
    text = """Join Channel And Make Account With This Link ✅\n\nChannel 🚀\nhttps://t.me/+8CcPYcK-7_JlZDk1\n\nGift code Link ✅ 🚀\nhttp://www.tashanwin.co/#/register?invitationCode=885886606870"""
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("Submit Uid For Checking 👇"))
    if message.from_user.id in ADMIN_IDS: markup.add(KeyboardButton("⚙️ Admin Panel"))
    
    bot.reply_to(message, text, reply_markup=markup, disable_web_page_preview=True)

@bot.message_handler(func=lambda msg: msg.text == "Submit Uid For Checking 👇")
def step3_ask_uid(message):
    user_states[message.from_user.id] = 'waiting_for_uid'
    bot.reply_to(message, "👇 <b>Please type and send your UID here:</b>", reply_markup=ReplyKeyboardRemove())

# ==========================================
# 9. FINAL RECEIVER (UID / Photo)
# ==========================================
@bot.message_handler(content_types=['text', 'photo'])
def handle_final_submission(message):
    if message.text and (message.text.startswith('/') or message.text in ["🎁 Claim Gift Code", "Submit Uid For Checking 👇", "⚙️ Admin Panel", "🔙 Main Menu", "👥 Users", "📢 Broadcast", "💾 Backup DB"]):
        return

    if user_states.get(message.from_user.id) != 'waiting_for_uid':
        return 

    # SMART USERNAME / DIRECT LINK LOGIC
    user_identity = get_user_link(message.from_user)
    
    user_info = f"👤 User: {user_identity}\n🆔 ID: <code>{message.from_user.id}</code>"
    
    if message.text:
        bot.reply_to(message, "Done Wait Your Uid Checking ✅\n\nMinimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀", reply_markup=get_main_keyboard(message.from_user.id))
        notify_all_admins(text=f"🆕 <b>NEW UID SUBMITTED</b>\n\n{user_info}\n📝 UID: <code>{message.text}</code>")
        user_states[message.from_user.id] = 'home'
                
    elif message.photo:
        bot.reply_to(message, "✅ <b>Screenshot Received!</b>\nPlease wait while we verify.", reply_markup=get_main_keyboard(message.from_user.id))
        notify_all_admins(photo_id=message.photo[-1].file_id, caption=f"📸 <b>NEW PAYMENT PROOF</b>\n\n{user_info}")
        user_states[message.from_user.id] = 'home'

# ==========================================
# 10. WEB SERVER
# ==========================================
app = Flask(__name__)
@app.route('/')
def index(): return "Advanced Bot with Auto-Backup is Live!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    bot.remove_webhook()
    bot.infinity_polling(allowed_updates=['message', 'chat_join_request'])
