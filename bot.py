import os
from telegram.ext import ApplicationBuilder, CommandHandler
from telegram import Update
from telegram.ext import ContextTypes

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "dummy_token")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello from the new v20-style bot!")

def main():
    # Create the application/bot
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Add your command handler
    app.add_handler(CommandHandler("start", start_command))

    # Start polling
    app.run_polling()

if __name__ == "__main__":
    main()
