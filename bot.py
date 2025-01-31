import os

from telegram.ext import ApplicationBuilder, CommandHandler
from telegram import Update
from telegram.ext import ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


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


import requests

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# DexScreener API URL for the token
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Fetch data from DexScreener API
        response = requests.get(DEXSCREENER_URL)
        data = response.json()

        # Extract relevant information from the first pair
        pair = data["pairs"][0]
        price_usd = pair["priceUsd"]
        volume_24h = pair["volume"]["h24"]
        liquidity = pair["liquidity"]["usd"]
        market_cap = pair["marketCap"]  # Market Cap (MC)
        dex_url = pair["url"]

        # Format the response message
        message = (
            f"💰 *Token Price (USD)*: ${price_usd}\n"
            f"📊 *24h Volume*: ${volume_24h:,.2f}\n"
            f"💧 *Liquidity*: ${liquidity:,.2f}\n"
            f"🏦 *Market Cap (MC)*: ${market_cap:,.2f}\n"
            f"🔗 [View on DexScreener]({dex_url})"
        )

        # Send the formatted response to the user
        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        # Handle errors gracefully
        await update.message.reply_text(f"⚠️ Error fetching price data: {e}")



def main():
    # Initialize the bot
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))  # or your existing start_command
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))

    app.run_polling()




if __name__ == "__main__":
    main()
