import os
import requests
import time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue
)

# ✅ Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
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

### --- FETCH PRICE DATA FROM DEXSCREENER --- ###
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

### --- FETCH ON-CHAIN DATA FROM SOLSCAN --- ###
def fetch_solscan_data(token_address):
    url = f"https://pro-api.solscan.io/v1/token/{token_address}"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        return data.get("data", {})
    except Exception:
        return {}

### --- GENERATE PRICE MESSAGE --- ###
def generate_price_message(pair, solscan_data):
    token_name = pair.get("baseToken", {}).get("name", "Unknown Token")
    symbol = pair.get("baseToken", {}).get("symbol", "???")
    price_usd = pair["priceUsd"]
    volume_24h = pair["volume"]["h24"]
    liquidity = pair["liquidity"]["usd"]
    market_cap = solscan_data.get("marketCap", "N/A")
    holders = solscan_data.get("holders", "N/A")
    dex_url = pair["url"]

    return escape_md(
        f"💰 *{token_name} ({symbol}) Price Data*\n"
        f"🔹 *Price:* ${price_usd:.4f}\n"
        f"📊 *24h Volume:* ${volume_24h:,}\n"
        f"💧 *Liquidity:* ${liquidity:,}\n"
        f"🏦 *Market Cap:* ${market_cap:,}\n"
        f"👥 *Holders:* {holders}\n"
        f"🔗 [View on DexScreener]({dex_url})"
    )

### --- GENERATE ALERT MESSAGE --- ###
def generate_alert_message(pair, solscan_data):
    token_name = pair.get("baseToken", {}).get("name", "Unknown Token")
    symbol = pair.get("baseToken", {}).get("symbol", "???")
    price_usd = float(pair["priceUsd"])
    liquidity = float(pair["liquidity"]["usd"])
    volume_24h = float(pair["volume"]["h24"])

    price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
    price_change_24h = float(pair.get("priceChange", {}).get("h24", 0))
    
    holders = solscan_data.get("holders", "N/A")

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

    if not alert_message:
        return None

    return escape_md(
        f"🚨 *{token_name} ({symbol}) ALERT!* 🚨\n\n"
        f"💰 *Current Price:* ${price_usd:.4f}\n"
        f"📉 *Price Change:*\n"
        f"   • ⏳ 5 min: {price_change_5m:.2f}%\n"
        f"   • ⏲️ 1 hour: {price_change_1h:.2f}%\n"
        f"   • 📅 24 hours: {price_change_24h:.2f}%\n"
        f"👥 *Holders:* {holders}\n"
        f"⚠️ {alert_message}"
    )

### --- CHECK ALERTS EVERY 2 MINUTES --- ###
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Check alerts every 2 minutes for subscribed users."""
    for user_id in subscribed_users.keys():
        token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
        pair = fetch_token_data(token_address)
        solscan_data = fetch_solscan_data(token_address)

        if pair:
            alert_message = generate_alert_message(pair, solscan_data)
            if alert_message:
                await context.bot.send_message(chat_id=user_id, text=escape_md(alert_message), parse_mode="MarkdownV2")

### --- TELEGRAM COMMAND HANDLERS --- ###
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I will notify you about token activity.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = escape_md(
        "📌 *Available Commands:*\n"
        "/start - Greet the user\n"
        "/help - Show this help message\n"
        "/ping - Check if the bot is alive\n"
        "/price - Get token price\n"
        "/alert - Check for alerts manually\n"
        "/subscribe_alerts - Enable auto alerts for 24h\n"
        "/unsubscribe_alerts - Disable auto alerts"
    )
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    pair = fetch_token_data(token_address)
    solscan_data = fetch_solscan_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    message = generate_price_message(pair, solscan_data)
    await update.message.reply_text(message, parse_mode="MarkdownV2")

### --- MAIN FUNCTION --- ###
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts, interval=120, first=10)  # 2 min interval

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))

    app.run_polling()

if __name__ == "__main__":
    main()
