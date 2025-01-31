import os
import requests
import time
import asyncio  # ✅ Added for async handling
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue
)

# ✅ Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SOLSCAN_API_KEY = os.getenv("SOLSCAN_API_KEY") 
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

# ✅ Ensure token exists
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")
if not SOLSCAN_API_KEY:
    raise ValueError("🚨 SOLSCAN_API_KEY is missing! Set it in your environment variables.")

# ✅ Store user-tracked token addresses
user_addresses = {}
subscribed_users = {}  # {user_id: expiry_timestamp}

### --- MarkdownV2 Escaping Function --- ###
def escape_md(text):
    """Escape special characters for Telegram MarkdownV2 formatting."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))

### --- SOLSCAN FETCH FUNCTION --- ###
def fetch_solscan_data(token_address):
    """Fetch latest transactions & transfers for the token from Solscan API"""
    url = f"https://pro-api.solscan.io/v2.0/account/transactions?account={token_address}&limit=3"
    headers = {"accept": "application/json", "token": SOLSCAN_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data.get("data"):
            return None
        return data["data"]
    except requests.exceptions.RequestException as e:
        print(f"Solscan API Error: {e}")
        return None

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

    # 🔹 Fetch both DexScreener and Solscan data
    pair = fetch_token_data(token_address)
    solscan_data = fetch_solscan_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    # 🔹 Generate the alert message
    alert_message = generate_alert_message(pair, solscan_data)
    if alert_message:
        await update.message.reply_text(escape_md(alert_message), parse_mode="MarkdownV2")
    else:
        await update.message.reply_text("🔍 No significant alerts detected.")

### --- PRICE COMMAND --- ###
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    pair = fetch_token_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    price_usd = pair["priceUsd"]
    volume_24h = pair["volume"]["h24"]
    liquidity = pair["liquidity"]["usd"]
    market_cap = pair.get("marketCap", "N/A")
    dex_url = pair["url"]

    message = escape_md(
        f"💰 *Token Price (USD)*: ${price_usd}\n"
        f"📊 *24h Volume*: ${volume_24h:,}\n"
        f"💧 *Liquidity*: ${liquidity:,}\n"
        f"🏦 *Market Cap (MC)*: ${market_cap:,}\n"
        f"🔗 [View on DexScreener]({dex_url})"
    )

    await update.message.reply_text(message, parse_mode="MarkdownV2")

### --- AUTOMATIC ALERT FUNCTION (Scheduled Using JobQueue) --- ###
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Check alerts every 2 minutes for subscribed users."""
    current_time = time.time()
    expired_users = [user_id for user_id, expiry in subscribed_users.items() if current_time > expiry]

    # Remove expired subscriptions
    for user_id in expired_users:
        del subscribed_users[user_id]

    # Process active subscriptions
    for user_id in subscribed_users.keys():
        token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
        pair = fetch_token_data(token_address)
        solscan_data = fetch_solscan_data(token_address)

        if pair:
            alert_message = generate_alert_message(pair, solscan_data)
            if alert_message:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=escape_md(alert_message),
                    parse_mode="MarkdownV2"
                )

### --- BOT MAIN FUNCTION --- ###
def main():
    # ✅ Create Telegram Bot Application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # ✅ Set Up JobQueue for Automatic Alerts
    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts, interval=120, first=10)  # 2 min interval

    # ✅ Register Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("subscribe_alerts", subscribe_alerts_command))
    app.add_handler(CommandHandler("unsubscribe_alerts", unsubscribe_alerts_command))

    app.run_polling()

# ✅ **CORRECT EXECUTION (NO asyncio.run(main()))**
if __name__ == "__main__":
    main()
