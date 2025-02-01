import os
import json
import requests
import time
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue
)

# ✅ Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")  # Ensure this is set
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"
DEFAULT_WALLET = "FvWskMZT4tsS1Nf4yyqvxJv4Sn3oM5GfX8udJhNYuY1N"  # Default Solana Wallet

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")
if not HELIUS_API_KEY:
    raise ValueError("🚨 HELIUS_API_KEY is missing! Set it in your environment variables.")

# ✅ Store user-tracked token addresses
user_addresses = {}
subscribed_users = {}  # {user_id: expiry_timestamp}


### --- MarkdownV2 Escaping Function --- ###
def escape_md(text):
    """Escape special characters for Telegram MarkdownV2 formatting."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))


### --- Helius: Fetch Solana Transactions --- ###
def fetch_solana_transactions(wallet_address, limit=5):
    """
    Fetch recent Solana transactions for a given wallet.
    """
    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [wallet_address, {"limit": limit}]
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if response.status_code == 200:
        return response.json().get("result", [])
    else:
        print(f"⚠️ Helius API Error: {response.status_code} - {response.text}")
        return None


### --- Helius: Fetch Solana Analytics --- ###
def fetch_solana_analytics():
    """
    Fetch trending Solana analytics, including trending wallets, token activity, and NFT transfers.
    """
    url = f"https://api.helius.xyz/v0/analytics?api-key={HELIUS_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"⚠️ Helius Analytics API Error: {response.status_code} - {response.text}")
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
    """
    Telegram command to fetch Solana transactions and analytics, then send alerts.
    """
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    wallet_address = DEFAULT_WALLET  # Modify for user-based tracking later

    # Fetch DexScreener & Solana Data
    pair = fetch_token_data(token_address)
    transactions = fetch_solana_transactions(wallet_address)
    analytics_data = fetch_solana_analytics()

    # Generate alert message
    alert_message = escape_md(f"🔎 *Solana Analytics & Transactions*\n\n")

    # 🔹 Add Recent Transactions to Message
    if transactions:
        alert_message += "📜 *Recent Transactions:*\n"
        for tx in transactions[:5]:
            tx_hash = tx.get("signature", "Unknown TX")
            slot = tx.get("slot", "N/A")
            alert_message += f"🔹 TX: [{tx_hash[:10]}...](https://explorer.solana.com/tx/{tx_hash}) (Slot {slot})\n"
    else:
        alert_message += "⚠️ No recent transactions found.\n"

    # 🔹 Add Solana Analytics Data
    if analytics_data:
        alert_message += "\n📊 *Trending Analytics:*\n"

        # Trending Tokens
        if "trendingTokens" in analytics_data:
            alert_message += "🔸 *Trending Tokens:*\n"
            for token in analytics_data["trendingTokens"][:5]:
                symbol = token.get("symbol", "Unknown")
                volume = token.get("volume", 0)
                alert_message += f"  • {symbol}: ${volume:,}\n"

        # Trending Wallets
        if "trendingWallets" in analytics_data:
            alert_message += "\n👛 *Top Wallets:* \n"
            for wallet in analytics_data["trendingWallets"][:5]:
                address = wallet.get("address", "Unknown")
                inflow = wallet.get("inflow", 0)
                outflow = wallet.get("outflow", 0)
                alert_message += f"  • [{address[:6]}...{address[-4:]}](https://explorer.solana.com/address/{address}):\n"
                alert_message += f"    📥 In: ${inflow:,} | 📤 Out: ${outflow:,}\n"

    await update.message.reply_text(alert_message, parse_mode="Markdown", disable_web_page_preview=True)


### --- BOT MAIN FUNCTION --- ###
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    job_queue = app.job_queue
    job_queue.run_repeating(alert_command, interval=120, first=10)  # 2 min interval

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("alert", alert_command))

    app.run_polling()

if __name__ == "__main__":
    main()
