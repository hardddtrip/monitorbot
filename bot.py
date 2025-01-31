import os

from telegram.ext import ApplicationBuilder, CommandHandler
from telegram import Update
from telegram.ext import ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv.get("TELEGRAM_BOT_TOKEN")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a list of commands or usage instructions."""
    help_text = (
        "Available commands:\n"
        "/start - Greet the user\n"
        "/help - Show this help message\n"
        "/ping - Check if the bot is alive"
    )
    await update.message.reply_text(help_text)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello from the new v20-style bot!")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply with 'Pong!' for connectivity testing."""
    await update.message.reply_text("Pong!")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", help_command))  # or your existing start_command
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))

    app.run_polling()

if __name__ == "__main__":
    main()
