import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ChatJoinRequest
from flask import Flask
import threading

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') 

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# State tracking & Selective Auto-Delete
user_states = {}
last_bot_msg = {} # Sirf bot ke purane message track karne ke liye

def delete_previous_bot_msg(chat_id):
    """Ye sirf bot ka pichla message delete karega, user ka nahi!"""
    if chat_id in last_bot_msg:
        try:
            bot.delete_message(chat_id, last_bot_msg[chat_id])
        except:
            pass

# ==========================================
# 🔥 MAIN FEATURE: CHANNEL JOIN REQUEST
# ==========================================
# Jaise hi koi channel join karne ki request bhejega, ye chalega
@bot.chat_join_request_handler()
def handle_join_request(request: ChatJoinRequest):
    chat_id = request.from_user.id
    user_states[chat_id] = 'step1'
    
    text = "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅"
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("🎁 Claim Gift Code"))
    
    try:
        # User ko DM me welcome bhejenge
        msg = bot.send_message(chat_id, text, reply_markup=markup)
        last_bot_msg[chat_id] = msg.message_id
        
        # (Optional) Request automatically approve karna:
        bot.approve_chat_join_request(request.chat.id, chat_id)
    except Exception as e:
        print(f"Error sending DM to {chat_id}:", e)


# ==========================================
# STEP 1: WELCOME MESSAGE (Agar koi direct bot me aaye)
# ==========================================
@bot.message_handler(commands=['start'])
def step1_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'step1'
    
    text = "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅"
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("🎁 Claim Gift Code"))
    
    msg = bot.reply_to(message, text, reply_markup=markup)
    last_bot_msg[chat_id] = msg.message_id


# ==========================================
# STEP 2: REGISTER LINKS
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🎁 Claim Gift Code")
def step2_register(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'step2'
    
    # Pichla 'Welcome' message delete kar dega
    delete_previous_bot_msg(chat_id)
    
    text = """Join Channel And Make Account With This Link ✅

Channel 🚀
https://t.me/+8CcPYcK-7_JlZDk1

Gift code Link ✅ 🚀
http://www.tashanwin.co/#/register?invitationCode=885886606870"""
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("Submit Uid For Checking 👇"))
    
    msg = bot.reply_to(message, text, reply_markup=markup, disable_web_page_preview=True)
    last_bot_msg[chat_id] = msg.message_id


# ==========================================
# STEP 3: ASK FOR UID
# ==========================================
@bot.message_handler(func=lambda message: message.text == "Submit Uid For Checking 👇")
def step3_ask_uid(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'waiting_for_uid'
    
    # Pichla 'Links' wala message delete kar dega
    delete_previous_bot_msg(chat_id)
    
    text = "👇 <b>Please type and send your UID here:</b>"
    
    markup = ReplyKeyboardRemove() # Keyboard hata do
    
    msg = bot.reply_to(message, text, reply_markup=markup)
    last_bot_msg[chat_id] = msg.message_id


# ==========================================
# FINAL STEP: ALL SET & ADMIN FORWARD
# ==========================================
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_for_uid' and not message.text.startswith('/'))
def final_step_receive(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'completed'
    
    # Sirf "Please type UID" wala question delete karega. 
    # User ne jo UID type ki hai, wo CHAT ME RUKHI RAHEGI!
    delete_previous_bot_msg(chat_id) 
    
    reply_text = "Done Wait Your Uid Checking ✅\n\nMinimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀"
    
    # Final message bhej diya, ise hum delete nahi karenge
    bot.reply_to(message, reply_text, reply_markup=ReplyKeyboardRemove())
    
    # Admin ko chup-chap details forward
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
    bot.reply_to(message, "✅ <b>Screenshot Received!</b>\nPlease wait while we verify.")
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
    return "Bot is running perfectly!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    bot.infinity_polling(allowed_updates=['message', 'chat_join_request'])
