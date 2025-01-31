import os
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ✅ Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

# ✅ Ensure token exists
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")

# ✅ User-tracked token addresses
user_addresses = {}

### --- MarkdownV2 Escaping Function --- ###
def escape_md(text):
    """Escape special characters for Telegram MarkdownV2 formatting."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))

### --- CORE COMMANDS --- ###
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Use /alert to check for token alerts.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = escape_md(
        "📌 *Available Commands:*\n"
        "/start - Greet the user\n"
        "/help - Show this help message\n"
        "/ping - Check if the bot is alive\n"
        "/alert - Get real-time token alerts"
    )
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

### --- PRICE FETCHING & ALERT SYSTEM --- ###
async def fetch_token_data(token_address):
    """Fetch token data from DexScreener API."""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        response = requests.get(url)
        data = response.json()
        if "pairs" not in data or len(data["pairs"]) == 0:
            return None
        return data["pairs"][0]
    except Exception:
        return None

async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch real-time alerts when the user runs /alert"""
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    pair = await fetch_token_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    price_usd = float(pair["priceUsd"])
    volume_24h = float(pair["volume"]["h24"])
    liquidity = float(pair["liquidity"]["usd"])
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))

    alert_message = "📢 *Current Token Status:*\n"
    
    if price_usd > 1.2 * price_change_1h:
        alert_message += "🚀 *Pump Alert!* Rapid price increase detected!\n"
    if pair["txns"]["h1"]["buys"] > 500 and volume_24h < 1000000:
        alert_message += "🛍 *Retail Arrival Detected!*\n"
    if liquidity > 2000000 and volume_24h > 5000000:
        alert_message += "🔄 *Market Maker Transfer!* 📊\n"
    if price_usd < 0.8 * price_change_1h:
        alert_message += "💥 *Dump Alert!* Price drop detected!\n"
    if pair["txns"]["h1"]["sells"] > 1000 and volume_24h < 500000:
        alert_message += "💀 *Retail Capitulation!* 🏳️\n"

    if alert_message == "📢 *Current Token Status:*\n":
        alert_message += "✅ No significant market events detected."

    await update.message.reply_text(escape_md(alert_message), parse_mode="MarkdownV2")

### --- BOT SETUP --- ###
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

async def main():
    """Start the bot and register command handlers."""
    await app.initialize()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("alert", alert_command))  # ✅ New command

    print("⚡ Bot is running...")
    await app.run_polling()

# ✅ Start the bot
if __name__ == "__main__":
    asyncio.run(main())
