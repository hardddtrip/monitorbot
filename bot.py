import os
import requests
import time
import asyncio  # ✅ Fixed: Now properly imported
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


### --- SOLSCAN PUBLIC API FETCH --- ###
def fetch_solscan_data(token_address):
    """Fetch token metadata and top holders from Solscan Public API."""
    try:
        # Fetch token metadata
        meta_url = f"https://public-api.solscan.io/token/meta/{token_address}"
        meta_response = requests.get(meta_url)
        meta_response.raise_for_status()
        meta_data = meta_response.json()

        # Fetch top holders (first 5 holders)
        holders_url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&limit=5"
        holders_response = requests.get(holders_url)
        holders_response.raise_for_status()
        holders_data = holders_response.json()

        # Extract token info
        token_name = meta_data.get("name", "Unknown Token")
        token_symbol = meta_data.get("symbol", "???")
        total_supply = meta_data.get("supply", {}).get("total", "N/A")
        
        # Extract top holders
        top_holders = []
        for holder in holders_data.get("data", []):
            address = holder["owner"]
            balance = float(holder["amount"])
            top_holders.append(f"🔹 {address[:6]}...{address[-4:]}: {balance:,.0f}")

        return {
            "name": token_name,
            "symbol": token_symbol,
            "supply": total_supply,
            "top_holders": top_holders
        }
    
    except requests.exceptions.RequestException as e:
        print(f"Solscan API Error: {e}")
        return None



### --- ALERT GENERATION FUNCTION (FIXED) --- ###
def generate_alert_message(pair, solscan_data):
    """Generate alert messages based on token metrics and Solscan data."""
    
    # 🔹 Extract DexScreener Data
    token_name = pair.get("baseToken", {}).get("name", "Unknown Token")
    symbol = pair.get("baseToken", {}).get("symbol", "???")
    price_usd = float(pair["priceUsd"])
    liquidity = float(pair["liquidity"]["usd"])
    volume_24h = float(pair["volume"]["h24"])
    price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
    price_change_24h = float(pair.get("priceChange", {}).get("h24", 0))

    # 🔹 Extract Solscan Data
    token_name = solscan_data.get("name", "Unknown Token")
    symbol = solscan_data.get("symbol", "???")
    total_supply = solscan_data.get("supply", "N/A")
    top_holders = "\n".join(solscan_data.get("top_holders", ["🚫 No holders found"]))

    # 🔹 Alert Conditions
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

    # 🔹 If no alert, return None
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
        f"📈 *24h Volume:* ${volume_24h:,.0f}\n"
        f"🏦 *Total Supply:* {total_supply}\n\n"
        f"⚠️ {alert_message}\n\n"
        f"🔎 *Top Holders:*\n{top_holders}"
    )
    
    return message

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

    # 🔹 Fetch DexScreener and Solscan data
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

### --- FIXED SUBSCRIPTION FUNCTIONS --- ###
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

### --- AUTOMATIC ALERT FUNCTION --- ###
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
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(60)  # ✅ Increased timeout
        .connect_timeout(30)
        .build()
    )

    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts, interval=120, first=10)  # 2 min interval

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("subscribe_alerts", subscribe_alerts_command))  # ✅ Fixed
    app.add_handler(CommandHandler("unsubscribe_alerts", unsubscribe_alerts_command))  # ✅ Fixed

    app.run_polling()
    
# ✅ **CORRECT EXECUTION (NO asyncio.run(main()))**
if __name__ == "__main__":
    main()
