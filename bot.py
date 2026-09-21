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
# 1. ADVANCED CONFIGURATION & LOGGING SETUP
# ==========================================
# Setup professional logging taaki koi error aaye toh pata chal jaye
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Security: Environment variables for sensitive data
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0)) # Ensure it's an integer

if not BOT_TOKEN:
    raise ValueError("CRITICAL ERROR: BOT_TOKEN is missing in environment variables!")
if ADMIN_ID == 0:
    logger.warning("WARNING: ADMIN_ID is not set. Admin features will be disabled.")

# Initialize the Bot with HTML parse mode for premium styling
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==========================================
# 2. DATABASE MANAGEMENT (Robust JSON Handling)
# ==========================================
class DatabaseManager:
    """Class to handle all database operations securely."""
    def __init__(self, filename='bot_database.json'):
        self.db_file = filename
        self.lock = threading.Lock() # Thread-safety ke liye
        self.default_data = {
            "config": {
                "welcome_message": "<b>Welcome to the Elite Gift Code Portal!</b> 🎁\n\nClaim your reward safely and securely. ✅",
                "require_join_approval": True # Admin can toggle this
            },
            "buttons": {
                "🎁 Claim Gift Code": "Follow these steps to claim:\n\n1. Join Channel 🚀: https://t.me/+8CcPYcK-7_JlZDk1\n2. Register ✅: http://www.tashanwin.co/#/register?invitationCode=885886606870"
            },
            "users": {}, # Store user interaction logs
            "admin_logs": [] # Store admin actions
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
            except Exception as e:
                logger.error(f"Database Load Error: {e}")
                return self.default_data

    def save_db(self, data):
        with self.lock:
            try:
                with open(self.db_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4) # Pretty print for readability
            except Exception as e:
                logger.error(f"Database Save Error: {e}")

db_manager = DatabaseManager()

# ==========================================
# 3. UTILITY FUNCTIONS & SECURITY DECORATORS
# ==========================================
def admin_only(func):
    """Decorator to strictly enforce admin-only access."""
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"Unauthorized access attempt by {message.from_user.id}")
            bot.reply_to(message, "⛔ <b>Access Denied:</b> You do not have administrator privileges.")
            return
        return func(message, *args, **kwargs)
    return wrapper

def generate_user_keyboard():
    """Generates a dynamic reply keyboard based on DB state."""
    db = db_manager.load_db()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=False)
    if db.get("buttons"):
        for btn_name in db["buttons"].keys():
            markup.add(KeyboardButton(btn_name))
    return markup

def log_user_activity(user_id, username, action):
    """Logs user activity for admin review."""
    db = db_manager.load_db()
    user_str = str(user_id)
    if user_str not in db["users"]:
        db["users"][user_str] = {"username": username, "history": []}
    
    # Keep only last 10 actions to save space
    db["users"][user_str]["history"].append({"time": str(datetime.now()), "action": action})
    if len(db["users"][user_str]["history"]) > 10:
        db["users"][user_str]["history"].pop(0)
    db_manager.save_db(db)

# ==========================================
# 4. CHANNEL JOIN REQUEST HANDLER (Automated)
# ==========================================
@bot.chat_join_request_handler()
def handle_advanced_join_request(request: ChatJoinRequest):
    user_id = request.from_user.id
    chat_id = request.chat.id
    username = request.from_user.username or "No Username"
    
    logger.info(f"Join request received from user {user_id} ({username}) for chat {chat_id}")
    log_user_activity(user_id, username, "Channel Join Request")
    
    db = db_manager.load_db()
    try:
        # Send Welcome Message privately
        bot.send_message(
            user_id, 
            db['config']['welcome_message'], 
            reply_markup=generate_user_keyboard(),
            disable_web_page_preview=True
        )
        
        # Approve request if configured
        if db['config'].get('require_join_approval', True):
            bot.approve_chat_join_request(chat_id, user_id)
            logger.info(f"Automatically approved user {user_id}")
            
    except Exception as e:
        logger.error(f"Failed to process join request for {user_id}: {e}")

# ==========================================
# 5. USER INTERFACE HANDLERS
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    log_user_activity(user_id, username, f"Sent command: {message.text}")
    
    db = db_manager.load_db()
    try:
        bot.reply_to(message, db['config']['welcome_message'], reply_markup=generate_user_keyboard())
    except Exception as e:
        logger.error(f"Start command error: {e}")
        bot.reply_to(message, "An error occurred. Please try again later.")

# ==========================================
# 6. SECURE ADMIN CONTROL PANEL
# ==========================================
admin_sessions = {} # Track what admin is currently editing

@bot.message_handler(commands=['admin'])
@admin_only
def show_admin_dashboard(message):
    db = db_manager.load_db()
    dashboard_text = (
        "🔐 <b>SECURE ADMIN DASHBOARD</b> 🔐\n\n"
        f"👥 Total Users Tracked: <b>{len(db.get('users', {}))}</b>\n"
        f"🔘 Active Custom Buttons: <b>{len(db.get('buttons', {}))}</b>\n\n"
        "Select an action below:"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📝 Edit Welcome", callback_data="admin_welcome"),
        InlineKeyboardButton("➕ Add Button", callback_data="admin_add_btn"),
        InlineKeyboardButton("🗑️ Delete Button", callback_data="admin_del_btn"),
        InlineKeyboardButton("📊 View Stats", callback_data="admin_stats"),
        InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel")
    )
    bot.reply_to(message, dashboard_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_queries(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized access!", show_alert=True)
        return

    action = call.data
    chat_id = call.message.chat.id
    db = db_manager.load_db()

    if action == "admin_cancel":
        if ADMIN_ID in admin_sessions:
            del admin_sessions[ADMIN_ID]
        bot.edit_message_text("✅ Admin action cancelled.", chat_id=chat_id, message_id=call.message.message_id)
        
    elif action == "admin_welcome":
        msg = bot.send_message(chat_id, f"Current Message:\n<pre>{db['config']['welcome_message']}</pre>\n\nSend new Welcome Message (HTML supported):")
        admin_sessions[ADMIN_ID] = {'action': 'edit_welcome'}
        bot.register_next_step_handler(msg, process_admin_input)
        
    elif action == "admin_add_btn":
        msg = bot.send_message(chat_id, "Enter the <b>name</b> for the new Keyboard Button:")
        admin_sessions[ADMIN_ID] = {'action': 'add_btn_name'}
        bot.register_next_step_handler(msg, process_admin_input)
        
    elif action == "admin_del_btn":
        buttons = db.get("buttons", {})
        if not buttons:
            bot.send_message(chat_id, "No custom buttons to delete.")
            return
        
        markup = InlineKeyboardMarkup(row_width=1)
        for btn in buttons.keys():
            markup.add(InlineKeyboardButton(f"🗑️ {btn}", callback_data=f"del_{btn}"))
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel"))
        bot.send_message(chat_id, "Select a button to permanently delete:", reply_markup=markup)
        
    elif action == "admin_stats":
        user_count = len(db.get('users', {}))
        bot.answer_callback_query(call.id, f"Total unique users interacted: {user_count}", show_alert=True)

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def perform_button_deletion(call):
    if call.from_user.id != ADMIN_ID: return
    
    btn_to_delete = call.data.replace('del_', '')
    db = db_manager.load_db()
    
    if btn_to_delete in db.get("buttons", {}):
        del db["buttons"][btn_to_delete]
        db_manager.save_db(db)
        bot.edit_message_text(f"✅ Button '{btn_to_delete}' deleted successfully.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Button not found.")

def process_admin_input(message):
    """Centralized handler for all multi-step admin processes."""
    if message.from_user.id != ADMIN_ID or ADMIN_ID not in admin_sessions:
        return

    session = admin_sessions[ADMIN_ID]
    action = session.get('action')
    db = db_manager.load_db()

    try:
        if action == 'edit_welcome':
            db['config']['welcome_message'] = message.text
            db_manager.save_db(db)
            bot.reply_to(message, "✅ Welcome Message updated successfully.")
            del admin_sessions[ADMIN_ID]

        elif action == 'add_btn_name':
            btn_name = message.text
            session['btn_name'] = btn_name
            session['action'] = 'add_btn_reply'
            msg = bot.reply_to(message, f"Button Name: <b>{btn_name}</b>\n\nNow send the REPLY TEXT for this button:")
            bot.register_next_step_handler(msg, process_admin_input)

        elif action == 'add_btn_reply':
            btn_name = session.get('btn_name')
            reply_text = message.text
            db["buttons"][btn_name] = reply_text
            db_manager.save_db(db)
            bot.reply_to(message, f"✅ Button <b>{btn_name}</b> added successfully!")
            del admin_sessions[ADMIN_ID]
            
    except Exception as e:
        logger.error(f"Admin process error: {e}")
        bot.reply_to(message, "❌ An error occurred while saving. Please try again.")

# ==========================================
# 7. INTELLIGENT MESSAGE ROUTING (Catch-all)
# ==========================================
@bot.message_handler(content_types=['text', 'photo', 'document'])
def route_user_message(message):
    if message.text and message.text.startswith('/'):
        return # Let command handlers deal with it

    user_id = message.from_user.id
    username = message.from_user.username or "No Username"
    db = db_manager.load_db()
    
    # 1. Check if it matches a custom button
    if message.text and message.text in db.get("buttons", {}):
        log_user_activity(user_id, username, f"Clicked button: {message.text}")
        bot.reply_to(message, db["buttons"][message.text], disable_web_page_preview=True)
        return

    # 2. Process as UID or Payment Screenshot (Business Logic)
    user_identity = f"👤 User: {message.from_user.first_name}\n🔗 User: @{username}\n🆔 ID: <code>{user_id}</code>"
    
    if message.text:
        log_user_activity(user_id, username, "Submitted Text/UID")
        bot.reply_to(message, "⏳ <b>Processing Details...</b>\n\nWait Your Uid Checking ✅\nMinimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀")
        
        if ADMIN_ID:
            bot.send_message(ADMIN_ID, f"🔔 <b>NEW SUBMISSION ALERT</b> 🔔\n\n{user_identity}\n\n📝 <b>Payload:</b> <code>{message.text}</code>")
            
    elif message.photo:
        log_user_activity(user_id, username, "Submitted Photo")
        bot.reply_to(message, "✅ <b>Media Received Successfully!</b>\n\nOur team is verifying your deposit.")
        
        if ADMIN_ID:
            # Send the highest resolution photo
            bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"📸 <b>NEW PAYMENT PROOF</b> 📸\n\n{user_identity}")

# ==========================================
# 8. WEB SERVER FOR DEPLOYMENT (Render/Heroku)
# ==========================================
app = Flask(__name__)

@app.route('/')
def health_check():
    """Health check endpoint for cloud platforms to keep bot awake."""
    return {
        "status": "online",
        "service": "Advanced Telegram Bot",
        "timestamp": datetime.now().isoformat()
    }

def start_web_server():
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == "__main__":
    # Start web server in background thread
    server_thread = threading.Thread(target=start_web_server)
    server_thread.daemon = True # Allows thread to exit when main program exits
    server_thread.start()
    
    logger.info("Bot Engine Starting...")
    try:
        # Start bot polling with specific allowed updates for optimization
        bot.infinity_polling(allowed_updates=['message', 'callback_query', 'chat_join_request'])
    except Exception as e:
        logger.critical(f"Bot execution failed: {e}")
