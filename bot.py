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
BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY")  # Using Bitquery for Solana transactions
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

# ✅ Ensure API keys exist
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")
if not BITQUERY_API_KEY:
    raise ValueError("🚨 BITQUERY_API_KEY is missing! Set it in your environment variables.")

# ✅ Store user-tracked token addresses
user_addresses = {}
subscribed_users = {}

### --- Fetch Solana Transaction Data (Bitquery API) --- ###
def fetch_solana_transactions(token_address):
    """Fetch latest token transactions from Bitquery API with timeout handling."""
    
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
        response = requests.post(url, json=payload, headers=headers, timeout=10)  # ✅ Increased timeout
        response.raise_for_status()
        data = response.json()
        
        if not data.get("data", {}).get("solana", {}).get("transfers"):
            return None  # No transactions found
        
        return data["data"]["solana"]["transfers"]
    
    except requests.exceptions.Timeout:
        print("⚠️ Bitquery API Timeout! Retrying in next cycle...")
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Bitquery API Error: {e}")
        return None  # Return None on failure

### --- Telegram Command Alert --- ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)

    # 🔹 Fetch Dexscreener and Bitquery transaction data
    transactions = fetch_solana_transactions(token_address)

    if not transactions:
        await update.message.reply_text("⚠️ No recent transactions found.")
        return

    message = "🔍 *Recent Solana Transactions:*\n"
    for tx in transactions:
        message += f"🔹 Block: {tx['block']}, Amount: {tx['amount']}\n"
        message += f"📤 Sender: {tx['sender']['address']}\n"
        message += f"📥 Receiver: {tx['receiver']['address']}\n"
        message += f"🔗 [View Transaction](https://solscan.io/tx/{tx['transaction']['hash']})\n\n"

    await update.message.reply_text(message, parse_mode="MarkdownV2")

### --- Automatic Alert Function (JobQueue) --- ###
async def automatic_alert(context: ContextTypes.DEFAULT_TYPE):
    """Runs every 2 minutes to send alerts automatically."""
    for user_id in subscribed_users.keys():
        await alert_command(context.bot, context)

### --- Bot Main Function --- ###
def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(60)  # ✅ Increased timeout
        .connect_timeout(30)
        .build()
    )
    
    job_queue = app.job_queue
    job_queue.run_repeating(automatic_alert, interval=120, first=10)  # ✅ Fixed JobQueue Alert

    app.add_handler(CommandHandler("alert", alert_command))
    
    app.run_polling()

if __name__ == "__main__":
    main()
