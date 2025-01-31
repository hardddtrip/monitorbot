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

### --- PRICE FETCHING (DexScreener) --- ###
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

### --- FETCH SOLSCAN WALLET & TRANSACTION DATA --- ###
def fetch_whale_transactions(token_address):
    """Fetch recent large transactions from Solscan."""
    url = f"https://public-api.solscan.io/token/txs?tokenAddress={token_address}&limit=10"
    try:
        response = requests.get(url)
        data = response.json()
        whale_txns = [tx for tx in data.get("data", []) if float(tx.get("amount", 0)) > 50000]  # Adjust threshold
        return len(whale_txns)
    except Exception:
        return 0

def fetch_wallet_activity(token_address):
    """Check how many new wallets are holding the token."""
    url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&limit=20"
    try:
        response = requests.get(url)
        data = response.json()
        new_wallets = [holder for holder in data.get("data", []) if int(holder.get("amount", 0)) > 100]  # Adjust threshold
        return len(new_wallets)
    except Exception:
        return 0

### --- ALERT FUNCTION --- ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    pair = fetch_token_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    alert_message = generate_alert_message(token_address, pair)
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

    message = generate_price_message(pair)
    await update.message.reply_text(message, parse_mode="MarkdownV2")

### --- AUTOMATIC ALERT FUNCTION --- ###
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Check alerts every 1 minute for testing."""
    for user_id in subscribed_users.keys():
        token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
        pair = fetch_token_data(token_address)

        if pair:
            alert_message = generate_alert_message(token_address, pair)
            if alert_message:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=escape_md(alert_message),
                    parse_mode="MarkdownV2"
                )

### --- ALERT GENERATION FUNCTION --- ###
def generate_alert_message(token_address, pair):
    """Generate alert messages based on token metrics and Solscan data."""
    
    # 🔹 Extract DexScreener Data
    token_name = pair.get("baseToken", {}).get("name", "Unknown Token")
    symbol = pair.get("baseToken", {}).get("symbol", "???")
    price_usd = float(pair["priceUsd"])
    liquidity = float(pair["liquidity"]["usd"])
    volume_24h = float(pair["volume"]["h24"])
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))

    # 🔹 Solscan Whale & Wallet Data
    whale_transactions = fetch_whale_transactions(token_address)
    new_wallets = fetch_wallet_activity(token_address)

    # 🔹 Alert Conditions
    alert_message = None
    if whale_transactions > 5:
        alert_message = f"🐋 *{whale_transactions} large whale transactions detected!*"
    elif new_wallets > 10:
        alert_message = f"👛 *{new_wallets} new wallets holding this token!*"
    elif price_usd > 1.2 * price_change_1h:
        alert_message = "📈 *Pump Alert!* 🚀"
    elif price_usd < 0.8 * price_change_1h:
        alert_message = "⚠️ *Dump Alert!* 💥"

    if not alert_message:
        return None

    return escape_md(
        f"🚨 *{token_name} ({symbol}) ALERT!* 🚨\n\n"
        f"💰 *Current Price:* ${price_usd:.4f}\n"
        f"📊 *Liquidity:* ${liquidity:,.0f}\n"
        f"📈 *24h Volume:* ${volume_24h:,.0f}\n"
        f"⚠️ {alert_message}"
    )

### --- BOT MAIN FUNCTION --- ###
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # ✅ **ENSURE `JobQueue` is setup inside `Application`**
    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts, interval=120, first=10)  # 1 min interval

    # ✅ **Register command handlers**
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("alert", alert_command))

    app.run_polling()

if __name__ == "__main__":
    main()
