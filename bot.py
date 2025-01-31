import os
from telegram.ext import Updater, CommandHandler

# We'll store our bot token in an environment variable
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "dummy_token")

def start_command(update, context):
    update.message.reply_text("Hello from your brand-new Heroku bot!")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command))

    # Start the bot in 'polling' mode
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
