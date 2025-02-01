import os
import json
import time
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue,
    CallbackContext
)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")  # Helius API Key
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # Add environment variable
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"
DEFAULT_WALLET = "DzfNo1qoGx4rYXbwS273tmPaxZMibr8iSrdw4Mvnhtv4" 
WALLET_ADDRESS = "DzfNo1qoGx4rYXbwS273tmPaxZMibr8iSrdw4Mvnhtv4"

# Ensure tokens exist
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")
if not HELIUS_API_KEY:
    raise ValueError("HELIUS_API_KEY is missing! Set it in your environment variables.")

# Store user-tracked token addresses
user_addresses = {}
subscribed_users = {}  # {user_id: expiry_timestamp}

### --- MarkdownV2 Escaping Function --- ###
def escape_md(text):
    """Escape special characters for Telegram MarkdownV2 formatting."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))


### Fetch Recent Solana Transactions (Helius API) ###
def fetch_solana_transactions(wallet_address, limit=5):
    """Fetch recent transactions for a wallet using Helius RPC."""
    url = "https://mainnet.helius-rpc.com/?api-key=" + HELIUS_API_KEY
    
    payload = {
        "jsonrpc": "2.0",
        "id": "my-id",
        "method": "getSignaturesForAddress",
        "params": [
            wallet_address,
            {
                "limit": limit
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                return result["result"]
        print(f"Helius API Error: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"Error fetching transactions: {str(e)}")
        return None

# Example usage:
transactions = fetch_solana_transactions(WALLET_ADDRESS)
if transactions:
    for tx in transactions:
        print(f"Signature: {tx.get('signature', 'Unknown')}, Slot: {tx.get('slot', 'N/A')}")


### Fetch Solana Analytics (Helius API) ###
def fetch_solana_analytics():
    """Fetch trending Solana analytics."""
    # Currently not implemented as the analytics endpoint is not available
    return None

### Fetch Token Price (DexScreener API) ###
def fetch_token_data(token_address):
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


### Generate Alert Message ###
def generate_alert_message(pair):
    """Generate alert messages based on token metrics."""

    if not pair:
        return "⚠️ No trading data found for this token."

    price_usd = float(pair["priceUsd"])
    volume_24h = float(pair["volume"]["h24"])
    liquidity = float(pair["liquidity"]["usd"])
    market_cap = pair.get("marketCap", "N/A")
    dex_url = pair["url"]
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
    price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))  # 5-minute change
    
    # Calculate approximate 15-minute change using 5-minute data
    price_change_15m = price_change_5m * 3

    message = f"💰 *Price Update*\n"
    message += f"Current Price: ${price_usd:.6f}\n"
    message += f"15min Change: {price_change_15m:+.2f}%\n"
    message += f"1h Change: {price_change_1h:+.2f}%\n"
    message += f"24h Volume: ${volume_24h:,.2f}\n"
    message += f"Liquidity: ${liquidity:,.2f}\n"

    # Add alerts based on conditions
    if abs(price_change_15m) > 10:  # More than 10% change in 15 minutes
        message += "\n🚨 *Significant Price Movement!*"
    if price_change_15m > 5:  # More than 5% increase
        message += "\n📈 *Upward Trend*"
    elif price_change_15m < -5:  # More than 5% decrease
        message += "\n📉 *Downward Trend*"

    return message

### Telegram Command: Fetch Alerts ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram command to fetch token price and transaction data."""
    user_id = update.message.chat_id
    wallet_address = DEFAULT_WALLET
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)

    pair = fetch_token_data(token_address)
    transactions = fetch_solana_transactions(wallet_address)

    message = "🔎 *Token Analytics & Transactions*\n\n"

    # DexScreener Price Alert
    if pair:
        alert_message = generate_alert_message(pair)
        if alert_message:
            message += f"{alert_message}\n\n"

    # Recent Transactions
    if transactions:
        message += "📜 *Recent Transactions:*\n"
        for tx in transactions[:5]:
            tx_hash = tx.get('signature', 'Unknown')
            slot = tx.get('slot', 'N/A')
            message += f"🔹 TX: [{tx_hash[:10]}...](https://explorer.solana.com/tx/{tx_hash}) (Slot {slot})\n"
    else:
        message += "⚠️ No recent transactions found.\n"

    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2", disable_web_page_preview=True)


async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Background job to fetch Solana transactions & send alerts to subscribed users."""
    for user_id in subscribed_users.keys():
        wallet_address = DEFAULT_WALLET
        token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)

        pair = fetch_token_data(token_address)
        transactions = fetch_solana_transactions(wallet_address)

        message = "🔎 *Token Analytics & Transactions*\n\n"

        # DexScreener Price Alert
        if pair:
            alert_message = generate_alert_message(pair)
            if alert_message:
                message += f"{alert_message}\n\n"

        # Recent Transactions
        if transactions:
            message += "📜 *Recent Transactions:*\n"
            for tx in transactions[:5]:
                tx_hash = tx.get('signature', 'Unknown')
                slot = tx.get('slot', 'N/A')
                message += f"🔹 TX: [{tx_hash[:10]}...](https://explorer.solana.com/tx/{tx_hash}) (Slot {slot})\n"
        else:
            message += "⚠️ No recent transactions found.\n"

        await context.bot.send_message(chat_id=user_id, text=escape_md(message), parse_mode="MarkdownV2", disable_web_page_preview=True)

### Telegram Command: Fetch Token Price ###
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch token price and market data."""
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    pair = fetch_token_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    price_usd = pair["priceUsd"]
    volume_24h = pair["volume"]["h24"]
    liquidity = pair["liquidity"]["usd"]
    dex_url = pair["url"]

    message = escape_md(
        f"💰 *Token Price (USD)*: ${price_usd}\n"
        f"📊 *24h Volume*: ${volume_24h:,}\n"
        f"💧 *Liquidity*: ${liquidity:,}\n"
        f"🔗 [View on DexScreener]({dex_url})"
    )

    await update.message.reply_text(message, parse_mode="MarkdownV2")


##Start##
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command to greet users."""
    await update.message.reply_text("Hello! I will notify you about token activity.")

##Ping##
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

### --- CHANGE TOKEN ADDRESS --- ###

async def change_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow users to change the token address they want to track."""
    user_id = update.message.chat_id

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /change <TOKEN_ADDRESS>")
        return

    token_address = context.args[0]
    user_addresses[user_id] = token_address
    await update.message.reply_text(f"✅ Token address updated! Now tracking: `{token_address}`", parse_mode="Markdown")


### Help ###
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = escape_md(
        "📌 *Available Commands:*\n"
        "/start - Greet the user\n"
        "/help - Show this help message\n"
        "/ping - Check if the bot is alive\n"
        "/price - Get token price\n"
        "/alert - Check for alerts manually\n"
        "/change <TOKEN_ADDRESS> - Change token address\n"
        "/subscribe_alerts - Enable auto alerts for 24h\n"
        "/unsubscribe_alerts - Disable auto alerts"
    )
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")


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

### --- AUTOMATIC ALERT FUNCTION (Scheduled Using JobQueue) --- ###
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Check alerts every 15 minutes for subscribed users."""
    current_time = time.time()
    expired_users = [user_id for user_id, expiry in subscribed_users.items() if current_time > expiry]

    # Remove expired subscriptions
    for user_id in expired_users:
        del subscribed_users[user_id]

    # Process active subscriptions
    for user_id in subscribed_users.keys():
        token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
        pair = fetch_token_data(token_address)

        if pair:
            alert_message = generate_alert_message(pair)
            if alert_message:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=escape_md(alert_message),
                    parse_mode="MarkdownV2"
                )

### Bot Main Function ###
def main():
    """Run the Telegram bot."""
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        job_queue = app.job_queue

        # Set up command handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("price", price_command))
        app.add_handler(CommandHandler("alert", alert_command))
        app.add_handler(CommandHandler("change", change_command))
        app.add_handler(CommandHandler("subscribe", subscribe_alerts_command))
        app.add_handler(CommandHandler("unsubscribe", unsubscribe_alerts_command))
        app.add_handler(CommandHandler("ping", ping_command))

        # Add error handler
        app.add_error_handler(error_handler)

        job_queue.run_repeating(check_alerts, interval=120, first=10)  # Auto-alert every 2 min

        print(f"Starting bot in {ENVIRONMENT} environment...")
        app.run_polling(drop_pending_updates=True)  # Add drop_pending_updates=True
    except Exception as e:
        print(f"Error starting bot: {str(e)}")
        if "Conflict" in str(e):
            print("Another instance of the bot is already running. This instance will not start.")
        raise

def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors in the telegram bot."""
    print(f"Update {update} caused error {context.error}")
    if isinstance(context.error, Conflict):
        print("Conflict error: Another instance of the bot is already running")
    elif isinstance(context.error, TimedOut):
        print("Request timed out. Will retry automatically.")

if __name__ == "__main__":
    main()
