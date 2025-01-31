import os
import requests
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# ✅ Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

# ✅ Ensure token exists
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")

# ✅ Store user-tracked token addresses
user_addresses = {}
subscribed_users = {}  # {user_id: expiry_timestamp}

### --- MarkdownV2 Escaping Function --- ###
def escape_md(text):
    """Escape special characters for Telegram MarkdownV2 formatting."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))


### --- TELEGRAM COMMANDS --- ###
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I will notify you about token activity.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = escape_md(
        "📌 *Available Commands:*\n"
        "/start - Greet the user\n"
        "/help - Show this help message\n"
        "/ping - Check if the bot is alive\n"
        "/price - Get token price\n"
        "/change <TOKEN_ADDRESS> - Change token address\n"
        "/alert - Check for alerts manually\n"
        "/subscribe_alerts - Enable auto alerts for 24h\n"
        "/unsubscribe_alerts - Disable auto alerts"
    )
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

### --- PRICE FETCHING --- ###
def fetch_token_data(token_address):
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        response = requests.get(url)
        data = response.json()
        if "pairs" not in data or len(data["pairs"]) == 0:
            return None
        return data["pairs"][0]
    except Exception:
        return None

### --- ALERT FUNCTION --- ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    pair = fetch_token_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    price_usd = float(pair["priceUsd"])
    volume_24h = float(pair["volume"]["h24"])
    liquidity = float(pair["liquidity"]["usd"])
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))

    alert_message = None
    if price_usd > 1.2 * price_change_1h:
        alert_message = "📈 *Pump Alert!* 🚀\nRapid price increase detected!"
    elif pair["txns"]["h1"]["buys"] > 500 and volume_24h < 1000000:
        alert_message = "🛍 *Retail Arrival Detected!*"
    elif liquidity > 2000000 and volume_24h > 5000000:
        alert_message = "🔄 *Market Maker Transfer!* 📊"
    elif price_usd < 0.8 * price_change_1h:
        alert_message = "⚠️ *Dump Alert!* 💥"
    elif pair["txns"]["h1"]["sells"] > 1000 and volume_24h < 500000:
        alert_message = "💀 *Retail Capitulation!* 🏳️"

    if alert_message:
        await update.message.reply_text(escape_md(alert_message), parse_mode="MarkdownV2")
    else:
        await update.message.reply_text("🔍 No significant alerts detected.")

### --- SUBSCRIBE TO AUTOMATIC ALERTS --- ###
async def subscribe_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    expiry_time = time.time() + 86400  # 24 hours from now
    subscribed_users[user_id] = expiry_time
    await update.message.reply_text("✅ You have subscribed to alerts for 24 hours!")

async def unsubscribe_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    if user_id in subscribed_users:
        del subscribed_users[user_id]
        await update.message.reply_text("❌ You have unsubscribed from alerts.")
    else:
        await update.message.reply_text("⚠️ You are not subscribed to alerts.")

### --- AUTOMATIC ALERT JOB --- ###
def check_alerts():
    """Check alerts every 15 minutes for subscribed users."""
    current_time = time.time()
    for user_id, expiry_time in list(subscribed_users.items()):
        if current_time > expiry_time:
            del subscribed_users[user_id]  # Unsubscribe expired users
            continue

        token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
        pair = fetch_token_data(token_address)

        if not pair:
            continue

        price_usd = float(pair["priceUsd"])
        volume_24h = float(pair["volume"]["h24"])
        liquidity = float(pair["liquidity"]["usd"])
        price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))

        alert_message = None
        if price_usd > 1.2 * price_change_1h:
            alert_message = "📈 *Pump Alert!* 🚀\nRapid price increase detected!"
        elif pair["txns"]["h1"]["buys"] > 500 and volume_24h < 1000000:
            alert_message = "🛍 *Retail Arrival Detected!*"
        elif liquidity > 2000000 and volume_24h > 5000000:
            alert_message = "🔄 *Market Maker Transfer!* 📊"
        elif price_usd < 0.8 * price_change_1h:
            alert_message = "⚠️ *Dump Alert!* 💥"
        elif pair["txns"]["h1"]["sells"] > 1000 and volume_24h < 500000:
            alert_message = "💀 *Retail Capitulation!* 🏳️"

        if alert_message:
            app.bot.send_message(chat_id=user_id, text=escape_md(alert_message), parse_mode="MarkdownV2")

### --- SETUP BOT & JOBS --- ###
def main():
    global app
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("change", change_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("subscribe_alerts", subscribe_alerts_command))
    app.add_handler(CommandHandler("unsubscribe_alerts", unsubscribe_alerts_command))

    # ✅ Schedule job for automatic alerts every 15 minutes
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_alerts, "interval", minutes=15)
    scheduler.start()

    app.run_polling()

if __name__ == "__main__":
    main()
