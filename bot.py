import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from flask import Flask
import threading

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') 

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# State tracking & Message tracking for Auto-Delete
user_states = {}
last_bot_msg = {} # Bot ke purane message yaad rakhne ke liye

# ==========================================
# AUTO-DELETE HELPER FUNCTIONS
# ==========================================
def clean_previous_and_send(chat_id, text, markup=None):
    """Ye function purana message delete karke naya bhejega"""
    # 1. Purana bot ka message delete karo
    if chat_id in last_bot_msg:
        try:
            bot.delete_message(chat_id, last_bot_msg[chat_id])
        except:
            pass # Agar message pehle hi delete ho chuka ho toh error na aaye

    # 2. Naya message bhejo aur uska ID save kar lo
    try:
        msg = bot.send_message(chat_id, text, reply_markup=markup, disable_web_page_preview=True)
        last_bot_msg[chat_id] = msg.message_id
    except Exception as e:
        print("Send error:", e)

def delete_user_msg(message):
    """Ye function user ka bheja hua text/command delete karega"""
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass


# ==========================================
# STEP 1: WELCOME MESSAGE
# ==========================================
@bot.message_handler(commands=['start'])
def step1_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'step1'
    delete_user_msg(message) # User ka '/start' delete kar do
    
    text = "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅"
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("🎁 Claim Gift Code"))
    
    clean_previous_and_send(chat_id, text, markup)


# ==========================================
# STEP 2: REGISTER LINKS
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🎁 Claim Gift Code")
def step2_register(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'step2'
    delete_user_msg(message) # User ne jo button dabaya wo delete kar do
    
    text = """Join Channel And Make Account With This Link ✅

Channel 🚀
https://t.me/+8CcPYcK-7_JlZDk1

Gift code Link ✅ 🚀
http://www.tashanwin.co/#/register?invitationCode=885886606870"""
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("Submit Uid For Checking 👇"))
    
    clean_previous_and_send(chat_id, text, markup)


# ==========================================
# STEP 3: ASK FOR UID
# ==========================================
@bot.message_handler(func=lambda message: message.text == "Submit Uid For Checking 👇")
def step3_ask_uid(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'waiting_for_uid'
    delete_user_msg(message) # Button delete kar do
    
    text = "👇 <b>Please type and send your UID here:</b>"
    
    markup = ReplyKeyboardRemove() # Keyboard hata do UID type karne ke liye
    clean_previous_and_send(chat_id, text, markup)


# ==========================================
# FINAL STEP: ALL SET & ADMIN FORWARD
# ==========================================
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_for_uid' and not message.text.startswith('/'))
def final_step_receive(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'completed'
    delete_user_msg(message) # User ki type ki hui UID chat se delete kar do (Security/Clean chat)
    
    reply_text = "Done Wait Your Uid Checking ✅\n\nMinimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀"
    clean_previous_and_send(chat_id, reply_text, ReplyKeyboardRemove())
    
    if ADMIN_ID:
        try:
            admin_text = f"🆕 <b>NEW UID SUBMITTED</b>\n\n👤 User: {message.from_user.first_name}\n🆔 UID: <code>{message.text}</code>"
            bot.send_message(ADMIN_ID, admin_text)
        except:
            pass

# ==========================================
# SCREENSHOT HANDLER
# ==========================================
@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    chat_id = message.chat.id
    delete_user_msg(message) # User ki photo chat se delete kardo
    
    clean_previous_and_send(chat_id, "✅ <b>Screenshot Received!</b>\nPlease wait while we verify.")
    
    if ADMIN_ID:
        try:
            bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"📸 <b>NEW PAYMENT PROOF</b>\n👤 User: {message.from_user.first_name}")
        except:
            pass


# ==========================================
# RENDER SERVER
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Auto-Delete Bot is running flawlessly!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    bot.infinity_polling()
