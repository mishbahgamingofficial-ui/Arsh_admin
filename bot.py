import os
import json
import logging
import threading
from datetime import datetime
from functools import wraps

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from flask import Flask

# ==========================================
# 1. ADVANCED CONFIGURATION & LOGGING
# ==========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0)) # Apna Telegram ID zaroor dalna!

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==========================================
# 2. DATABASE MANAGEMENT (With Image Support)
# ==========================================
class DatabaseManager:
    def __init__(self, filename='bot_database.json'):
        self.db_file = filename
        self.lock = threading.Lock()
        self.default_data = {
            "config": {
                "welcome_message": "<b>Welcome to the Elite Gift Code Portal!</b> 🎁\n\nClaim your reward safely and securely. ✅",
                "welcome_photo": None, # Image file_id save karne ke liye
                "require_join_approval": True
            },
            "buttons": {
                "🎁 Claim Gift Code": "Follow these steps to claim:\n\n1. Join Channel 🚀: https://t.me/+8CcPYcK-7_JlZDk1\n2. Register ✅: http://www.tashanwin.co/#/register?invitationCode=885886606870"
            },
            "users": {},
            "admin_logs": []
        }
        self.init_db()

    def init_db(self):
        if not os.path.exists(self.db_file):
            self.save_db(self.default_data)

    def load_db(self):
        with self.lock:
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception: return self.default_data

    def save_db(self, data):
        with self.lock:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

db_manager = DatabaseManager()

# ==========================================
# 3. UTILITY FUNCTIONS
# ==========================================
def admin_only(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if message.from_user.id != ADMIN_ID: return
        return func(message, *args, **kwargs)
    return wrapper

def generate_user_keyboard():
    db = db_manager.load_db()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=False)
    if db.get("buttons"):
        for btn_name in db["buttons"].keys():
            markup.add(KeyboardButton(btn_name))
    return markup

def log_user_activity(user_id, username, action):
    db = db_manager.load_db()
    user_str = str(user_id)
    if user_str not in db["users"]:
        db["users"][user_str] = {"username": username, "history": []}
    db["users"][user_str]["history"].append({"time": str(datetime.now()), "action": action})
    db_manager.save_db(db)

def send_welcome_content(chat_id):
    """Smart function jo decide karega ki sirf text bhejna hai ya photo ke sath"""
    db = db_manager.load_db()
    text = db['config']['welcome_message']
    photo = db['config'].get('welcome_photo')
    markup = generate_user_keyboard()
    
    try:
        if photo: # Agar admin ne photo set ki hai toh Image + Caption jayega
            bot.send_photo(chat_id, photo, caption=text, reply_markup=markup, parse_mode='HTML')
        else: # Warna normal text
            bot.send_message(chat_id, text, reply_markup=markup, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error sending welcome: {e}")

# ==========================================
# 4. CHANNEL JOIN REQUEST HANDLER
# ==========================================
@bot.chat_join_request_handler()
def handle_advanced_join_request(request: ChatJoinRequest):
    user_id = request.from_user.id
    chat_id = request.chat.id
    log_user_activity(user_id, request.from_user.username, "Channel Join Request")
    
    send_welcome_content(user_id)
    
    db = db_manager.load_db()
    if db['config'].get('require_join_approval', True):
        bot.approve_chat_join_request(chat_id, user_id)

# ==========================================
# 5. USER COMMANDS
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    log_user_activity(message.from_user.id, message.from_user.username, "/start command")
    send_welcome_content(message.chat.id)

# ==========================================
# 6. SECURE ADMIN CONTROL PANEL (With Image Support)
# ==========================================
admin_sessions = {}

@bot.message_handler(commands=['admin'])
@admin_only
def show_admin_dashboard(message):
    db = db_manager.load_db()
    dashboard_text = "🔐 <b>SECURE ADMIN DASHBOARD</b> 🔐\n\nSelect an action below:"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📝 Edit Text", callback_data="admin_welcome"),
        InlineKeyboardButton("🖼️ Set Welcome Photo", callback_data="admin_photo"),
        InlineKeyboardButton("❌ Remove Photo", callback_data="admin_rem_photo"),
        InlineKeyboardButton("➕ Add Button", callback_data="admin_add_btn"),
        InlineKeyboardButton("🗑️ Delete Button", callback_data="admin_del_btn")
    )
    bot.reply_to(message, dashboard_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_queries(call):
    if call.from_user.id != ADMIN_ID: return
    action = call.data
    chat_id = call.message.chat.id
    db = db_manager.load_db()

    if action == "admin_welcome":
        msg = bot.send_message(chat_id, "Send new Welcome Message (HTML supported):")
        admin_sessions[ADMIN_ID] = {'action': 'edit_welcome'}
        bot.register_next_step_handler(msg, process_admin_input)
        
    elif action == "admin_photo":
        msg = bot.send_message(chat_id, "📸 <b>Send me a Photo</b> that you want to set as the Welcome Banner:")
        admin_sessions[ADMIN_ID] = {'action': 'set_welcome_photo'}
        bot.register_next_step_handler(msg, process_admin_input)
        
    elif action == "admin_rem_photo":
        db['config']['welcome_photo'] = None
        db_manager.save_db(db)
        bot.answer_callback_query(call.id, "Welcome Photo Removed!", show_alert=True)
        
    elif action == "admin_add_btn":
        msg = bot.send_message(chat_id, "Enter the <b>name</b> for the new Keyboard Button:")
        admin_sessions[ADMIN_ID] = {'action': 'add_btn_name'}
        bot.register_next_step_handler(msg, process_admin_input)
        
    elif action == "admin_del_btn":
        markup = InlineKeyboardMarkup(row_width=1)
        for btn in db.get("buttons", {}).keys():
            markup.add(InlineKeyboardButton(f"🗑️ {btn}", callback_data=f"del_{btn}"))
        bot.send_message(chat_id, "Select a button to delete:", reply_markup=markup)

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def perform_button_deletion(call):
    if call.from_user.id != ADMIN_ID: return
    btn_to_delete = call.data.replace('del_', '')
    db = db_manager.load_db()
    if btn_to_delete in db.get("buttons", {}):
        del db["buttons"][btn_to_delete]
        db_manager.save_db(db)
        bot.edit_message_text(f"✅ Button '{btn_to_delete}' deleted.", chat_id=call.message.chat.id, message_id=call.message.message_id)

# Handler that accepts text AND photos from Admin
@bot.message_handler(content_types=['text', 'photo'], func=lambda message: message.from_user.id == ADMIN_ID and ADMIN_ID in admin_sessions)
def process_admin_input(message):
    session = admin_sessions[ADMIN_ID]
    action = session.get('action')
    db = db_manager.load_db()

    if action == 'edit_welcome' and message.text:
        db['config']['welcome_message'] = message.text
        bot.reply_to(message, "✅ Welcome Message updated.")
        
    elif action == 'set_welcome_photo' and message.photo:
        db['config']['welcome_photo'] = message.photo[-1].file_id # Save highest resolution image
        bot.reply_to(message, "✅ Welcome Photo successfully set!")
        
    elif action == 'add_btn_name' and message.text:
        session['btn_name'] = message.text
        session['action'] = 'add_btn_reply'
        msg = bot.reply_to(message, f"Button: <b>{message.text}</b>\nNow send the REPLY TEXT (Or Photo) for this button:")
        bot.register_next_step_handler(msg, process_admin_input)
        return # return to keep session active
        
    elif action == 'add_btn_reply':
        btn_name = session.get('btn_name')
        db["buttons"][btn_name] = message.text if message.text else "Photo reply saved."
        bot.reply_to(message, f"✅ Button <b>{btn_name}</b> added!")

    db_manager.save_db(db)
    del admin_sessions[ADMIN_ID]

# ==========================================
# 7. UNIVERSAL MESSAGE/IMAGE ROUTING (For Users)
# ==========================================
# Ab user text, photo, document kuch bhi bheje, bot handle karega
@bot.message_handler(content_types=['text', 'photo', 'document', 'video', 'audio'])
def route_user_message(message):
    if message.text and message.text.startswith('/'): return

    user_id = message.from_user.id
    username = message.from_user.username or "No Username"
    db = db_manager.load_db()
    
    # 1. Custom Button Press Check
    if message.text and message.text in db.get("buttons", {}):
        bot.reply_to(message, db["buttons"][message.text], disable_web_page_preview=True)
        return

    # 2. Payment/UID Submission Processing
    user_identity = f"👤 User: {message.from_user.first_name}\n🔗 User: @{username}\n🆔 ID: <code>{user_id}</code>"
    
    if message.text:
        bot.reply_to(message, "⏳ <b>Processing Details...</b>\n\nWait Your Uid Checking ✅\nMinimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀")
        if ADMIN_ID: bot.send_message(ADMIN_ID, f"🔔 <b>NEW SUBMISSION</b> 🔔\n\n{user_identity}\n\n📝 <b>UID:</b> <code>{message.text}</code>")
            
    elif message.photo or message.document:
        bot.reply_to(message, "✅ <b>Media Received Successfully!</b>\n\nOur team is verifying your deposit.")
        if ADMIN_ID:
            if message.photo:
                bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"📸 <b>NEW PAYMENT PROOF</b> 📸\n\n{user_identity}")
            elif message.document:
                bot.send_document(ADMIN_ID, message.document.file_id, caption=f"📄 <b>NEW DOCUMENT PROOF</b> 📄\n\n{user_identity}")

# ==========================================
# 8. WEB SERVER (Render/Heroku Support)
# ==========================================
app = Flask(__name__)
@app.route('/')
def health_check(): return {"status": "online"}

def start_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=start_web_server).start()
    logger.info("Bot Engine Started with Image Support...")
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'chat_join_request'])
