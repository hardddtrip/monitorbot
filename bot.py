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

### --- Fetch Solscan Whale Transactions --- ###
def fetch_whale_transactions(token_address):
    """Fetch the largest recent transactions for the token using Solscan API."""
    url = f"https://public-api.solscan.io/token/txs?tokenAddress={token_address}&limit=10"
    
    try:
        response = requests.get(url)
        data = response.json()
        if "data" not in data:
            return None

        # ✅ Extract large transactions (greater than $50,000 in SOL)
        large_txns = [
            txn for txn in data["data"]
            if txn.get("lamport", 0) > 50_000 * 1_000_000_000  # Convert SOL to lamports
        ]

        return large_txns

    except Exception as e:
        print(f"❌ Error fetching whale transactions: {e}")
        return None

### --- Fetch Solscan Wallet Activity --- ###
def fetch_wallet_activity(token_address):
    """Fetch recent wallet activity for the token using Solscan API."""
    url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&limit=10"
    
    try:
        response = requests.get(url)
        data = response.json()
        if "data" not in data:
            return None

        # ✅ Extract top wallets (who are the biggest buyers/sellers?)
        top_wallets = data["data"][:5]  # Top 5 wallets

        return top_wallets

    except Exception as e:
        print(f"❌ Error fetching wallet activity: {e}")
        return None

### --- Fetch Token Data --- ###
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

### --- Generate Alert Message --- ###
def generate_alert_message(pair, token_address):
    """Generate alert messages based on token metrics & on-chain data."""
    
    # 🔹 Extract DEX price data
    token_name = pair.get("baseToken", {}).get("name", "Unknown Token")
    symbol = pair.get("baseToken", {}).get("symbol", "???")
    price_usd = float(pair["priceUsd"])
    liquidity = float(pair["liquidity"]["usd"])
    volume_24h = float(pair["volume"]["h24"])
    price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
    price_change_24h = float(pair.get("priceChange", {}).get("h24", 0))

    # 🔹 Fetch Whale Transactions 🐋
    whales = fetch_whale_transactions(token_address)
    whale_alert = "🐋 *No whale transactions detected.*"
    if whales:
        whale_alert = f"🐋 *{len(whales)} large whale transactions detected!*"
    
    # 🔹 Fetch Wallet Activity 📊
    wallets = fetch_wallet_activity(token_address)
    wallet_alert = "📊 *No significant wallet changes.*"
    if wallets:
        wallet_alert = f"👛 *New wallet activity detected!*"

    # 🔹 Alert conditions
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

    # 🔹 Create enhanced alert message
    message = escape_md(
        f"🚨 *{token_name} ({symbol}) ALERT!* 🚨\n\n"
        f"💰 *Current Price:* ${price_usd:.4f}\n"
        f"📉 *Price Change:*\n"
        f"   • ⏳ 5 min: {price_change_5m:.2f}%\n"
        f"   • ⏲️ 1 hour: {price_change_1h:.2f}%\n"
        f"   • 📅 24 hours: {price_change_24h:.2f}%\n"
        f"📊 *Liquidity:* ${liquidity:,.0f}\n"
        f"📈 *24h Volume:* ${volume_24h:,.0f}\n\n"
        f"{whale_alert}\n"
        f"{wallet_alert}\n\n"
        f"⚠️ {alert_message}"
    )

    return message

### --- Alert Command --- ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    pair = fetch_token_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    alert_message = generate_alert_message(pair, token_address)
    if alert_message:
        await update.message.reply_text(escape_md(alert_message), parse_mode="MarkdownV2")
    else:
        await update.message.reply_text("🔍 No significant alerts detected.")

### --- Automatic Alerts --- ###
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Check alerts every 5 minutes for subscribed users."""
    current_time = time.time()
    expired_users = [user_id for user_id, expiry in subscribed_users.items() if current_time > expiry]

    for user_id in expired_users:
        del subscribed_users[user_id]

    for user_id in subscribed_users.keys():
        token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
        pair = fetch_token_data(token_address)

        if pair:
            alert_message = generate_alert_message(pair, token_address)
            if alert_message:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=escape_md(alert_message),
                    parse_mode="MarkdownV2"
                )

### --- Start Bot --- ###
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts, interval=300, first=10)  # 5 min interval

    app.add_handler(CommandHandler("alert", alert_command))
    app.run_polling()

if __name__ == "__main__":
    main()
