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
BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY")  # 🔹 New API Key for Bitquery
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

# ✅ Ensure API keys exist
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")
if not BITQUERY_API_KEY:
    raise ValueError("🚨 BITQUERY_API_KEY is missing! Set it in your environment variables.")

# ✅ Store user-tracked token addresses
user_addresses = {}
subscribed_users = {}  # {user_id: expiry_timestamp}

### --- MarkdownV2 Escaping Function --- ###
def escape_md(text):
    """Escape special characters for Telegram MarkdownV2 formatting."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))

### --- Fetch Solana Transaction Data (Bitquery API) --- ###
def fetch_solana_transactions(token_address):
    """Fetch latest token transactions from Bitquery API."""
    
    url = "https://graphql.bitquery.io"
    headers = {"X-API-KEY": BITQUERY_API_KEY, "Content-Type": "application/json"}
    
    query = """
    query ($token: String!) {
      solana {
        transfers(
          where: {currency: {is: $token}}
          limit: 5
          order: {block: DESC}
        ) {
          block
          amount
          sender { address }
          receiver { address }
          transaction { hash }
        }
      }
    }
    """
    
    payload = {"query": query, "variables": {"token": token_address}}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("data", {}).get("solana", {}).get("transfers"):
            return None  # No transactions found
        
        return data["data"]["solana"]["transfers"]
    
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Bitquery API Error: {e}")
        return None  # Return None on failure

### --- Generate Transaction Summary --- ###
def generate_transaction_summary(transactions):
    """Format transaction data into a readable summary."""
    
    if not transactions:
        return "🚫 No recent transactions."
    
    summary = []
    for tx in transactions:
        tx_hash = tx["transaction"]["hash"]
        sender = tx["sender"]["address"][:6] + "..." + tx["sender"]["address"][-4:]
        receiver = tx["receiver"]["address"][:6] + "..." + tx["receiver"]["address"][-4:]
        amount = f"{tx['amount']:.2f}"
        
        summary.append(f"🔹 {amount} tokens from `{sender}` → `{receiver}` [🔗 View](https://solscan.io/tx/{tx_hash})")
    
    return "\n".join(summary)

### --- Fetch Token Price Data (Dexscreener) --- ###
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
def generate_alert_message(pair, transactions):
    """Generate alert messages based on token metrics and recent transactions."""

    # 🔹 Extract Dexscreener Data
    token_name = pair.get("baseToken", {}).get("name", "Unknown Token")
    symbol = pair.get("baseToken", {}).get("symbol", "???")
    price_usd = float(pair["priceUsd"])
    liquidity = float(pair["liquidity"]["usd"])
    volume_24h = float(pair["volume"]["h24"])
    price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
    price_change_24h = float(pair.get("priceChange", {}).get("h24", 0))

    # 🔹 Format recent transactions
    transaction_summary = generate_transaction_summary(transactions)

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
        f"📈 *24h Volume:* ${volume_24h:,.0f}\n\n"
        f"⚠️ {alert_message}\n\n"
        f"🔎 *Recent Transactions:*\n{transaction_summary}"
    )
    
    return message

### --- Telegram Command Alert --- ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)

    # 🔹 Fetch Dexscreener and Bitquery transaction data
    pair = fetch_token_data(token_address)
    transactions = fetch_solana_transactions(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    # 🔹 Generate alert message
    alert_message = generate_alert_message(pair, transactions)
    if alert_message:
        await update.message.reply_text(escape_md(alert_message), parse_mode="MarkdownV2")
    else:
        await update.message.reply_text("🔍 No significant alerts detected.")

### --- Automatic Alert Function (JobQueue) --- ###
async def automatic_alert(context: ContextTypes.DEFAULT_TYPE):
    """Runs every 2 minutes to send alerts automatically."""
    for user_id in subscribed_users.keys():
        await alert_command(context.bot, context)

### --- Bot Main Function --- ###
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    job_queue = app.job_queue
    job_queue.run_repeating(automatic_alert, interval=120, first=10)  # ✅ Fixed JobQueue Alert

    app.add_handler(CommandHandler("alert", alert_command))
    
    app.run_polling()

if __name__ == "__main__":
    main()
