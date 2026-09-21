import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading

# Tokens Render ke environment variables se aayenge
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') # Tumhara Telegram ID

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==========================================
# 1. START COMMAND
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
<b>Hello Welcome To Our Gift Code bot !!</b> 🎁

Get Upto 200 Rs Gift Code 💸

⚠️ Free Gift Code Upto 200Rs Sabhi Condition Ho Proper Follow Krna Vrna Aapko Code nhi Milega !! 

👇 <b>Click below to claim your code:</b>
    """
    
    markup = InlineKeyboardMarkup()
    claim_btn = InlineKeyboardButton("🎁 Claim Gift Code", callback_data="claim_code")
    markup.add(claim_btn)

    bot.reply_to(message, welcome_text, reply_markup=markup)


# ==========================================
# 2. CLAIM CODE CLICK (Exact Client Format)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == 'claim_code')
def handle_claim_button(call):
    # Client ka exact text aur emojis
    claim_text = """
Join Channel And Make Account With This Link ✅

Channel 🚀
https://t.me/+8CcPYcK-7_JlZDk1

Gift code Link ✅ 🚀
http://www.tashanwin.co/#/register?invitationCode=885886606870
    """
    
    markup = InlineKeyboardMarkup(row_width=1)
    # Client ki demand wala button
    uid_btn = InlineKeyboardButton("Submit Uid For Checking 👇", callback_data="ask_uid")
    markup.add(uid_btn)
    
    try:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                              text=claim_text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass 
        
    bot.answer_callback_query(call.id)


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
    if message.text and message.text.startswith('/'):
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    user_info = f"👤 <b>User:</b> {message.from_user.first_name}\n🔗 <b>Username:</b> {username}\n🆔 <b>User ID:</b> <code>{message.from_user.id}</code>"

    # Agar user Text (UID) bhejta hai
    if message.text:
        # Client ka exact reply message
        uid_reply = """
Done Wait Your Uid Checking ✅

Minimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code !! 🚀
        """
        bot.reply_to(message, uid_reply)
        
        # Admin ko UID forward
        if ADMIN_ID:
            admin_msg = f"🆕 <b>New UID Submission</b>\n\n{user_info}\n\n📝 <b>UID Submitted:</b> <code>{message.text}</code>"
            try:
                bot.send_message(ADMIN_ID, admin_msg)
            except Exception as e:
                print("Admin Error:", e)

    # Agar user Photo (Screenshot) bhejta hai
    elif message.photo:
        bot.reply_to(message, "✅ <b>Screenshot Received!</b>\nPlease wait while we verify your UID and deposit.")
        
        # Admin ko Screenshot forward
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
