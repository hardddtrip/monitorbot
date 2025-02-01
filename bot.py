import requests
import json
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Your API keys
HELIUS_API_KEY = "ba737b72-acf1-4d55-a893-20fdaf294be9"
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# Default tracked Solana wallet
DEFAULT_WALLET = "your_wallet_address_here"


### 🔹 Fetch Recent Solana Transactions (Helius API) ###
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


### 🔹 Fetch Solana Analytics (Helius API) ###
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


### 🔹 Telegram Alert Command - Fetch & Send Transaction + Analytics Data ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram command to fetch Solana transactions and analytics, then send alerts.
    """
    user_id = update.message.chat_id
    wallet_address = DEFAULT_WALLET  # You can customize this per user later

    transactions = fetch_solana_transactions(wallet_address)
    analytics_data = fetch_solana_analytics()

    message = "🔎 *Solana Analytics & Transactions*\n\n"

    # 🔹 Add Recent Transactions to Message
    if transactions:
        message += "📜 *Recent Transactions:*\n"
        for tx in transactions[:5]:
            tx_hash = tx.get("signature", "Unknown TX")
            slot = tx.get("slot", "N/A")
            message += f"🔹 TX: [{tx_hash[:10]}...](https://explorer.solana.com/tx/{tx_hash}) (Slot {slot})\n"
    else:
        message += "⚠️ No recent transactions found.\n"

    # 🔹 Add Solana Analytics Data
    if analytics_data:
        message += "\n📊 *Trending Analytics:*\n"

        # Trending Tokens
        if "trendingTokens" in analytics_data:
            message += "🔸 *Trending Tokens:*\n"
            for token in analytics_data["trendingTokens"][:5]:
                symbol = token.get("symbol", "Unknown")
                volume = token.get("volume", 0)
                message += f"  • {symbol}: ${volume:,}\n"

        # Trending Wallets
        if "trendingWallets" in analytics_data:
            message += "\n👛 *Top Wallets:* \n"
            for wallet in analytics_data["trendingWallets"][:5]:
                address = wallet.get("address", "Unknown")
                inflow = wallet.get("inflow", 0)
                outflow = wallet.get("outflow", 0)
                message += f"  • [{address[:6]}...{address[-4:]}](https://explorer.solana.com/address/{address}):\n"
                message += f"    📥 In: ${inflow:,} | 📤 Out: ${outflow:,}\n"

    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)


### 🔹 Telegram Bot Setup ###
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("alert", alert_command))

### 🔹 Start the Bot ###
app.run_polling()
