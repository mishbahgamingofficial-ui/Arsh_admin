import os
import json
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0)) # Yahan apna ID zaroor dalna!

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==========================================
# DATABASE (JSON) SETUP
# ==========================================
SETTINGS_FILE = 'settings.json'

# Default settings agar file na ho
default_settings = {
    "welcome_msg": "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅",
    "button_name": "🎁 Claim Gift Code"
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(default_settings, f)
        return default_settings
    with open(SETTINGS_FILE, 'r') as f:
        return json.load(f)

def save_settings(new_settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(new_settings, f)

# State tracking for Admin (kya change kar raha hai)
admin_states = {}

# ==========================================
# 1. ADMIN PANEL (Only for Admin)
# ==========================================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    settings = load_settings()
    panel_text = f"""
🛠️ <b>ADMIN CONTROL PANEL</b> 🛠️

<b>Current Message:</b>
{settings['welcome_msg']}

<b>Current Button Name:</b>
{settings['button_name']}

👇 What do you want to change?
    """
    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("📝 Edit Welcome Message", callback_data="edit_msg")
    btn2 = InlineKeyboardButton("🔠 Edit Button Name", callback_data="edit_btn")
    markup.add(btn1, btn2)
    
    bot.reply_to(message, panel_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['edit_msg', 'edit_btn'])
def handle_admin_action(call):
    if call.from_user.id != ADMIN_ID:
        return
        
    if call.data == 'edit_msg':
        admin_states[ADMIN_ID] = 'waiting_for_msg'
        bot.send_message(call.message.chat.id, "✏️ <b>Send the new Welcome Message now:</b>\n<i>(You can use HTML tags like &lt;b&gt;bold&lt;/b&gt;)</i>")
    
    elif call.data == 'edit_btn':
        admin_states[ADMIN_ID] = 'waiting_for_btn'
        bot.send_message(call.message.chat.id, "✏️ <b>Send the new Button Name now:</b>")
        
    bot.answer_callback_query(call.id)

# Handle Admin's new input
@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and admin_states.get(ADMIN_ID) in ['waiting_for_msg', 'waiting_for_btn'])
def save_admin_changes(message):
    settings = load_settings()
    state = admin_states[ADMIN_ID]
    
    if state == 'waiting_for_msg':
        settings['welcome_msg'] = message.text
        bot.reply_to(message, "✅ <b>Welcome Message updated successfully!</b>")
    
    elif state == 'waiting_for_btn':
        settings['button_name'] = message.text
        bot.reply_to(message, "✅ <b>Button Name updated successfully!</b>")
        
    save_settings(settings)
    admin_states[ADMIN_ID] = None # Reset state


# ==========================================
# 2. START COMMAND (User side)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    settings = load_settings()
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    claim_btn = KeyboardButton(settings['button_name'])
    markup.add(claim_btn)

    try:
        bot.reply_to(message, settings['welcome_msg'], reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, "Error loading text. Admin, check formatting.")


# ==========================================
# 3. DYNAMIC BUTTON CLICK HANDLER
# ==========================================
# Kyunki button ka naam change ho sakta hai, hum check karenge ki message settings wale button se match karta hai ya nahi
@bot.message_handler(func=lambda message: message.text == load_settings()['button_name'])
def handle_claim_button(message):
    claim_text = """
Join Channel And Make Account With This Link ✅

Channel 🚀
https://t.me/+8CcPYcK-7_JlZDk1

Gift code Link ✅ 🚀
http://www.tashanwin.co/#/register?invitationCode=885886606870
    """
    
    markup = InlineKeyboardMarkup(row_width=1)
    uid_btn = InlineKeyboardButton("Submit Uid For Checking 👇", callback_data="ask_uid")
    markup.add(uid_btn)
    
    bot.send_message(message.chat.id, claim_text, reply_markup=markup, disable_web_page_preview=True)


# ==========================================
# 4. SUBMIT UID BUTTON CLICK
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == 'ask_uid')
def handle_ask_uid(call):
    bot.send_message(call.message.chat.id, "Please type and send your UID here: 👇")
    bot.answer_callback_query(call.id)


# ==========================================
# 5. UID & SCREENSHOT HANDLER + ADMIN FORWARD
# ==========================================
@bot.message_handler(content_types=['photo', 'text'])
def handle_verification(message):
    settings = load_settings()
    
    if message.text and (message.text.startswith('/') or message.text == settings['button_name']):
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    user_info = f"👤 <b>User:</b> {message.from_user.first_name}\n🔗 <b>Username:</b> {username}\n🆔 <b>User ID:</b> <code>{message.from_user.id}</code>"

    if message.text:
        uid_reply = "Done Wait Your Uid Checking ✅\n\nMinimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀"
        bot.reply_to(message, uid_reply)
        
        if ADMIN_ID:
            admin_msg = f"🆕 <b>New UID Submission</b>\n\n{user_info}\n\n📝 <b>UID Submitted:</b> <code>{message.text}</code>"
            try:
                bot.send_message(ADMIN_ID, admin_msg)
            except Exception: pass

    elif message.photo:
        bot.reply_to(message, "✅ <b>Screenshot Received!</b>\nPlease wait while we verify your UID and deposit.")
        
        if ADMIN_ID:
            photo_id = message.photo[-1].file_id 
            admin_caption = f"🆕 <b>New Payment Screenshot</b>\n\n{user_info}"
            try:
                bot.send_photo(ADMIN_ID, photo_id, caption=admin_caption)
            except Exception: pass


# ==========================================
# 6. RENDER FLASK SERVER
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is Running Live with In-App Admin Panel!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    print("Bot Started...")
    bot.infinity_polling()
