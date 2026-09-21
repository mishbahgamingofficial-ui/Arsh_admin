import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading

# Tokens Render ke environment variables se aayenge
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') # Tera Telegram ID

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==========================================
# 1. START COMMAND (Keyboard ki jagah par Button)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Tune jaisa text manga tha bilkul waisa hi
    welcome_text = """
<b>Hello Welcome To Our Gift Code bot !!</b> ✅ 

Get Upto 200 Rs Gift Code ✅
    """
    
    # Typing keyboard ki jagah bada button laane ke liye ReplyKeyboardMarkup
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    claim_btn = KeyboardButton("🎁 Claim Gift Code")
    markup.add(claim_btn)

    # Message ke sath keyboard wala button bhej diya
    bot.reply_to(message, welcome_text, reply_markup=markup)


# ==========================================
# 2. CLAIM CODE BUTTON CLICK HANDLER
# ==========================================
# Jab user keyboard ki jagah wale "🎁 Claim Gift Code" par touch karega
@bot.message_handler(func=lambda message: message.text == "🎁 Claim Gift Code")
def handle_claim_button(message):
    claim_text = """
Join Channel And Make Account With This Link ✅

Channel 🚀
https://t.me/+8CcPYcK-7_JlZDk1

Gift code Link ✅ 🚀
http://www.tashanwin.co/#/register?invitationCode=885886606870
    """
    
    # Ab iske aage ke process ke liye wapas Inline Button (message ke niche wala)
    markup = InlineKeyboardMarkup(row_width=1)
    uid_btn = InlineKeyboardButton("Submit Uid For Checking 👇", callback_data="ask_uid")
    markup.add(uid_btn)
    
    bot.send_message(message.chat.id, claim_text, reply_markup=markup, disable_web_page_preview=True)


# ==========================================
# 3. SUBMIT UID BUTTON CLICK
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == 'ask_uid')
def handle_ask_uid(call):
    bot.send_message(call.message.chat.id, "Please type and send your UID here: 👇")
    bot.answer_callback_query(call.id)


# ==========================================
# 4. UID & SCREENSHOT HANDLER + ADMIN FORWARD
# ==========================================
@bot.message_handler(content_types=['photo', 'text'])
def handle_verification(message):
    # Commands aur us Claim button ke text ko ignore karne ke liye
    if message.text and (message.text.startswith('/') or message.text == "🎁 Claim Gift Code"):
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    user_info = f"👤 <b>User:</b> {message.from_user.first_name}\n🔗 <b>Username:</b> {username}\n🆔 <b>User ID:</b> <code>{message.from_user.id}</code>"

    # Agar user Text (UID) bhejta hai
    if message.text:
        uid_reply = """
Done Wait Your Uid Checking ✅

Minimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀
        """
        bot.reply_to(message, uid_reply)
        
        # Admin ko UID forward hogi
        if ADMIN_ID:
            admin_msg = f"🆕 <b>New UID Submission</b>\n\n{user_info}\n\n📝 <b>UID Submitted:</b> <code>{message.text}</code>"
            try:
                bot.send_message(ADMIN_ID, admin_msg)
            except Exception as e:
                print("Admin Error:", e)

    # Agar user Photo (Screenshot) bhejta hai
    elif message.photo:
        bot.reply_to(message, "✅ <b>Screenshot Received!</b>\nPlease wait while we verify your UID and deposit.")
        
        # Admin ko Screenshot forward hogi
        if ADMIN_ID:
            photo_id = message.photo[-1].file_id 
            admin_caption = f"🆕 <b>New Payment Screenshot</b>\n\n{user_info}"
            try:
                bot.send_photo(ADMIN_ID, photo_id, caption=admin_caption)
            except Exception as e:
                print("Admin Error:", e)


# ==========================================
# 5. RENDER FLASK SERVER
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is Running Live!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    print("Bot Started...")
    bot.infinity_polling()
