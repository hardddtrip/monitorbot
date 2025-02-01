import os
import json
import time
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue
)

# ✅ Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")  # ✅ Helius API Key
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"
DEFAULT_WALLET = "your_default_solana_wallet_address"  # ✅ Replace with actual wallet

# ✅ Ensure tokens exist
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


### 🔹 Fetch Recent Solana Transactions (Helius API) ###
def fetch_solana_transactions(wallet_address, limit=5):
    """Fetch recent Solana transactions for a given wallet."""
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


### 🔹 Fetch Solana Analytics (Helius API) ###
def fetch_solana_analytics():
    """Fetch trending Solana analytics, including trending wallets, token activity, and NFT transfers."""
    url = f"https://api.helius.xyz/v0/analytics?api-key={HELIUS_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"⚠️ Helius Analytics API Error: {response.status_code} - {response.text}")
        return None


### 🔹 Fetch Token Price (DexScreener API) ###
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


### 🔹 Generate Alert Message ###
def generate_alert_message(pair):
    """Generate alert messages based on token metrics."""
    price_usd = float(pair["priceUsd"])
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))

    if price_usd > 1.2 * price_change_1h:
        return "📈 *Pump Alert!* 🚀\nRapid price increase detected!"
    elif price_usd < 0.8 * price_change_1h:
        return "⚠️ *Dump Alert!* 💥"
    return None


### 🔹 Telegram Command: Fetch Alerts ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram command to fetch Solana transactions and analytics, then send alerts."""
    user_id = update.message.chat_id
    wallet_address = DEFAULT_WALLET
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)

    pair = fetch_token_data(token_address)
    transactions = fetch_solana_transactions(wallet_address)
    analytics_data = fetch_solana_analytics()

    message = "🔎 *Solana Analytics & Transactions*\n\n"

    # 🔹 DexScreener Price Alert
    if pair:
        alert_message = generate_alert_message(pair)
        if alert_message:
            message += f"{alert_message}\n"

    # 🔹 Recent Transactions
    if transactions:
        message += "📜 *Recent Transactions:*\n"
        for tx in transactions[:5]:
            tx_hash = tx.get("signature", "Unknown TX")
            slot = tx.get("slot", "N/A")
            message += f"🔹 TX: [{tx_hash[:10]}...](https://explorer.solana.com/tx/{tx_hash}) (Slot {slot})\n"
    else:
        message += "⚠️ No recent transactions found.\n"

    # 🔹 Solana Analytics
    if analytics_data:
        message += "\n📊 *Trending Analytics:*\n"
        if "trendingTokens" in analytics_data:
            message += "🔸 *Trending Tokens:*\n"
            for token in analytics_data["trendingTokens"][:5]:
                symbol = token.get("symbol", "Unknown")
                volume = token.get("volume", 0)
                message += f"  • {symbol}: ${volume:,}\n"

    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2", disable_web_page_preview=True)


### 🔹 Telegram Command: Fetch Token Price ###
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


### 🔹 Bot Main Function ###
def main():
    """Run the Telegram bot."""
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    job_queue = app.job_queue
    job_queue.run_repeating(alert_command, interval=120, first=10)  # ✅ Auto-alert every 2 min

    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Hello! I will notify you about token activity.")))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text("Use /price or /alert to get updates.")))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("alert", alert_command))

    app.run_polling()


if __name__ == "__main__":
    main()
