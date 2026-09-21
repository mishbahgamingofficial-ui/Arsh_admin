import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ChatJoinRequest
from flask import Flask
import threading

# ==========================================
# 1. BOT & ADMIN SETUP
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') 

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# User ki step yaad rakhne ke liye
user_states = {}

# ==========================================
# 2. CHANNEL JOIN REQUEST HANDLER
# ==========================================
# Jab koi join request bhejega toh direct ye chalega
@bot.chat_join_request_handler()
def handle_join_request(request: ChatJoinRequest):
    user_id = request.from_user.id
    user_states[user_id] = 'step1'
    
    text = "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅"
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("🎁 Claim Gift Code"))
    
    try:
        # User ko DM me message bhejega
        bot.send_message(user_id, text, reply_markup=markup)
        # Automatic channel me approve bhi kar dega
        bot.approve_chat_join_request(request.chat.id, user_id)
    except Exception as e:
        print(f"Join Request Error: {e}")

# ==========================================
# 3. START COMMAND (Pehla Message)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    user_states[user_id] = 'step1'
    
    text = "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅"
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("🎁 Claim Gift Code"))
    
    bot.reply_to(message, text, reply_markup=markup)

# ==========================================
# 4. CLAIM CODE BUTTON (Dusra Message)
# ==========================================
@bot.message_handler(func=lambda msg: msg.text == "🎁 Claim Gift Code")
def step2_links(message):
    user_id = message.chat.id
    user_states[user_id] = 'step2'
    
    text = """Join Channel And Make Account With This Link ✅

Channel 🚀
https://t.me/+8CcPYcK-7_JlZDk1

Gift code Link ✅ 🚀
http://www.tashanwin.co/#/register?invitationCode=885886606870"""
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("Submit Uid For Checking 👇"))
    
    bot.reply_to(message, text, reply_markup=markup, disable_web_page_preview=True)

# ==========================================
# 5. SUBMIT UID BUTTON (Teesra Message)
# ==========================================
@bot.message_handler(func=lambda msg: msg.text == "Submit Uid For Checking 👇")
def step3_ask_uid(message):
    user_id = message.chat.id
    user_states[user_id] = 'waiting_for_uid'
    
    text = "👇 <b>Please type and send your UID here:</b>"
    
    # Keyboard hata do taaki UID likh sake
    markup = ReplyKeyboardRemove()
    
    bot.reply_to(message, text, reply_markup=markup)

# ==========================================
# 6. RECEIVE UID / SCREENSHOT & FORWARD TO ADMIN
# ==========================================
@bot.message_handler(content_types=['text', 'photo'])
def handle_final_submission(message):
    # Commands aur purane buttons ko ignore karo
    if message.text and (message.text.startswith('/') or message.text in ["🎁 Claim Gift Code", "Submit Uid For Checking 👇"]):
        return

    # Admin ko user ki detail dene ka format
    user_info = f"👤 User: {message.from_user.first_name}\n🆔 User ID: <code>{message.from_user.id}</code>"
    
    # Agar Text (UID) bheja hai
    if message.text:
        bot.reply_to(message, "Done Wait Your Uid Checking ✅\n\nMinimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀")
        
        # Admin ko direct UID bhej do
        if ADMIN_ID:
            try:
                bot.send_message(ADMIN_ID, f"🆕 <b>NEW UID SUBMITTED</b>\n\n{user_info}\n📝 UID: <code>{message.text}</code>")
            except Exception as e:
                print("Admin UID Error:", e)
                
    # Agar Photo (Screenshot) bheja hai
    elif message.photo:
        bot.reply_to(message, "✅ <b>Screenshot Received!</b>\nPlease wait while we verify.")
        
        # Admin ko Photo bhej do
        if ADMIN_ID:
            try:
                bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"📸 <b>NEW PAYMENT PROOF</b>\n\n{user_info}")
            except Exception as e:
                print("Admin Photo Error:", e)

# ==========================================
# 7. WEB SERVER (Render pe bot zinda rakhne ke liye)
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is Live and Running smoothly!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    print("Bot is Started...")
    
    # Ye line sabse zaroori hai (Join request allow karne ke liye)
    bot.infinity_polling(allowed_updates=['message', 'chat_join_request'])
