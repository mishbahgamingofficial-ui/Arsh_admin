import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') 

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# User kis step par hai, ye yaad rakhne ke liye Dictionary
user_states = {}

# ==========================================
# STEP 1: WELCOME MESSAGE (Pehla Padhao)
# ==========================================
@bot.message_handler(commands=['start'])
def step1_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'step1' # User abhi step 1 par hai
    
    text = "<b>Hello Welcome To Our Gift Code bot !!</b> ✅\n\nGet Upto 200 Rs Gift Code ✅"
    
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton("🎁 Claim Gift Code", callback_data="goto_step2")
    markup.add(btn)
    
    bot.reply_to(message, text, reply_markup=markup)


# ==========================================
# STEP 2: REGISTER LINKS (Dusra Padhao)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == 'goto_step2')
def step2_register(call):
    chat_id = call.message.chat.id
    user_states[chat_id] = 'step2' # User ab step 2 par aa gaya
    
    text = """Join Channel And Make Account With This Link ✅

Channel 🚀
https://t.me/+8CcPYcK-7_JlZDk1

Gift code Link ✅ 🚀
http://www.tashanwin.co/#/register?invitationCode=885886606870"""
    
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton("Submit Uid For Checking 👇", callback_data="goto_step3")
    markup.add(btn)
    
    # MAGIC YAHAN HAI: Purana message badal jayega taaki chat me kachra na ho
    bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                          text=text, reply_markup=markup, disable_web_page_preview=True)


# ==========================================
# STEP 3: ASK FOR UID (Teesra Padhao)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == 'goto_step3')
def step3_ask_uid(call):
    chat_id = call.message.chat.id
    user_states[chat_id] = 'waiting_for_uid' # Bot ab user ke reply ka wait karega
    
    text = "👇 <b>Please type and send your UID here:</b>"
    
    # Message badal kar UID mangega
    bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text)


# ==========================================
# FINAL STEP: ALL SET & ADMIN FORWARD
# ==========================================
# Ye function tabhi chalega jab user "waiting_for_uid" state me hoga
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_for_uid')
def final_step_receive(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'completed' # Flow khatam
    
    # Client ko final confirmation
    reply_text = "Done Wait Your Uid Checking ✅\n\nMinimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀"
    bot.reply_to(message, reply_text)
    
    # Admin ko chup-chap details forward kar do
    if ADMIN_ID:
        try:
            admin_text = f"🆕 <b>NEW UID SUBMITTED</b>\n\n👤 User: {message.from_user.first_name}\n🆔 UID: <code>{message.text}</code>"
            bot.send_message(ADMIN_ID, admin_text)
        except:
            pass

# ==========================================
# SCREENSHOT HANDLER (Agar photo bhejta hai)
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
# RENDER SERVER (Zinda rakhne ke liye)
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running perfectly step-by-step!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    bot.infinity_polling()
