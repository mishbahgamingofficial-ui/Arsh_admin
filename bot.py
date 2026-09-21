import os
import telebot
from flask import Flask
import threading

# Tokens Render ke environment variables se aayenge
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') # Tumhara Telegram ID

bot = telebot.TeleBot(BOT_TOKEN)

# Start Command Handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
Hello Welcome To Our Gift Code bot !! 🎁

Get Upto 200 Rs Gift Code 💸

⚠️ Free Gift Code Upto 200Rs Sabhi Condition Ho Proper Follow Krna Vrna Aapko Code nhi Milega !! 

Click /ClaimCode to proceed.
    """
    bot.reply_to(message, welcome_text)

# Claim Code Command Handler
@bot.message_handler(commands=['ClaimCode', 'claimcode'])
def claim_code(message):
    claim_text = """
Join Channel And Make Account With This Link 👇

📢 Channel - https://t.me/+8CcPYcK-7_JlZDk1

🔗 Gift code Link - http://www.tashanwin.co/#/register?invitationCode=885886606870

Next Button Submit Uid For Checking !! 
(Minimum 200+ Deposit And Also Send Screenshot And Get 500Rs gift Code)

Send your UID and Screenshot here 👇
    """
    bot.reply_to(message, claim_text)

# UID and Screenshot Receiver + ADMIN FORWARDING
@bot.message_handler(content_types=['photo', 'text'])
def handle_verification(message):
    # Commands ko ignore karo
    if message.text and message.text.startswith('/'):
        return

    # User ki details nikalna
    username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    user_info = f"👤 *User:* {message.from_user.first_name}\n🔗 *Username:* {username}\n🆔 *User ID:* `{message.from_user.id}`"

    if message.text:
        # User ko confirmation
        bot.reply_to(message, "✅ UID Received! Please make sure to send the deposit screenshot if you haven't yet.")
        
        # Admin ko UID forward karna
        if ADMIN_ID:
            admin_msg = f"🆕 *New UID Submission*\n\n{user_info}\n\n📝 *UID Submitted:* `{message.text}`"
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")

    elif message.photo:
        # User ko confirmation
        bot.reply_to(message, "✅ Screenshot Received! Please wait while we verify your UID and deposit. Gift code will be sent upon successful checking.")
        
        # Admin ko Screenshot forward karna
        if ADMIN_ID:
            photo_id = message.photo[-1].file_id # Get highest quality photo
            admin_caption = f"🆕 *New Payment Screenshot*\n\n{user_info}"
            bot.send_photo(ADMIN_ID, photo_id, caption=admin_caption, parse_mode="Markdown")

# --- Dummy Flask Server for Render ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is Running Live with Admin Features!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    print("Bot Started...")
    bot.infinity_polling()
