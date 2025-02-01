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
from telegram.error import Conflict, TimedOut
from datetime import datetime

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")  # Helius API Key
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # Add environment variable
DEFAULT_TOKEN_ADDRESS = "EfgEGG9PxLhyk1wqtqgGnwgfVC7JYic3vC9BCWLvpump"  # EGG token

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")
if not HELIUS_API_KEY:
    raise ValueError("HELIUS_API_KEY is missing! Set it in your environment variables.")

# Helius API endpoints
HELIUS_API_URL = "https://api.helius.xyz/v0"
HELIUS_RPC_URL = "https://mainnet.helius-rpc.com/?api-key=" + HELIUS_API_KEY

### --- MarkdownV2 Escaping Function --- ###
def escape_md(text):
    """Escape special characters for Telegram MarkdownV2 formatting."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))


### Fetch Recent Solana Transactions (Helius API) ###
def fetch_solana_transactions(token_address, limit=10):
    """Fetch recent transactions for a token using enhanced Helius RPC."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "my-id",
            "method": "getSignaturesForAddress",
            "params": [
                token_address,
                {
                    "limit": limit
                }
            ]
        }
        response = requests.post(HELIUS_RPC_URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                return data["result"]
        return None
    except Exception as e:
        print(f"Error fetching transactions: {str(e)}")
        return None

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
    if not pair or "priceUsd" not in pair:
        return None

    price_usd = float(pair.get("priceUsd", 0))
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
    volume_24h = float(pair.get("volume", {}).get("h24", 0))
    liquidity = float(pair.get("liquidity", {}).get("usd", 0))
    buys_1h = int(pair.get("txns", {}).get("h1", {}).get("buys", 0))
    sells_1h = int(pair.get("txns", {}).get("h1", {}).get("sells", 0))

    # Initialize alert message
    alert_message = ""

    # Market condition alerts
    if price_change_1h > 0 and price_usd > 1.2 * (price_usd - price_change_1h):
        alert_message += "📈 *Pump Alert!* 🚀\nRapid price increase detected!\n\n"
    elif price_change_1h < 0 and price_usd < 0.8 * (price_usd - price_change_1h):
        alert_message += "⚠️ *Dump Alert!* 💥\nSignificant price decrease!\n\n"

    # Trading activity alerts
    if buys_1h > 500 and volume_24h < 1000000:
        alert_message += "🛍 *Retail Arrival Detected!*\nHigh number of buy transactions.\n\n"
    elif sells_1h > 1000 and volume_24h < 500000:
        alert_message += "💀 *Retail Capitulation!* 🏳️\nMass selling detected.\n\n"

    # Liquidity alerts
    if liquidity > 2000000 and volume_24h > 5000000:
        alert_message += "🔄 *Market Maker Activity!* 📊\nHigh liquidity movement.\n\n"

    # Base price information
    base_info = (
        f"💰 *Price*: ${price_usd:.6f}\n"
        f"📊 *1h Change*: {price_change_1h:.2f}%\n"
        f"💧 *Liquidity*: ${liquidity:,.0f}\n"
        f"📈 *24h Volume*: ${volume_24h:,.0f}\n"
        f"🔄 *1h Transactions*:\n"
        f"  • Buys: {buys_1h}\n"
        f"  • Sells: {sells_1h}\n"
    )

    return alert_message + base_info if alert_message else base_info


### Telegram Command: Fetch Alerts ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram command to fetch token price and transaction data."""
    user_id = update.message.chat_id
    token_address = context.application.user_data.get(user_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)

    pair = fetch_token_data(token_address)
    if not pair:
        await update.message.reply_text("❌ Failed to fetch token data")
        return

    message = generate_alert_message(pair)
    
    # Add recent trades info if available
    trades = fetch_recent_trades(token_address)
    if trades:
        message += "\n\n*Recent Trades:*\n"
        for trade in trades[:3]:  # Show last 3 trades
            timestamp = datetime.fromtimestamp(trade.get("blockTime", 0)/1000).strftime("%Y-%m-%d %H:%M:%S")
            trade_type = trade.get("type", "UNKNOWN")
            amount = trade.get("amount", 0)
            message += f"• {timestamp}: {trade_type} - Amount: {amount:,.0f}\n"
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

### Telegram Command: Fetch Token Price ###
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch token price and market data."""
    user_id = update.message.chat_id
    token_address = context.application.user_data.get(user_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)
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
    context.application.user_data[user_id] = {'token_address': token_address}
    await update.message.reply_text(f"✅ Token address updated! Now tracking: `{token_address}`", parse_mode="Markdown")


### Help ###
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "*🤖 Bot Commands:*\n\n"
        "📊 *Price & Analytics:*\n"
        "/price - Get current token price and stats\n"
        "/metadata - View token metadata\n"
        "/holders - View top token holders\n"
        "/trades - View recent trades\n"
        "/liquidity - View liquidity changes\n\n"
        "🔔 *Alerts:*\n"
        "/alert - Get a one-time alert\n"
        "/subscribe - Enable automatic alerts\n"
        "/unsubscribe - Disable automatic alerts\n\n"
        "⚙️ *Settings:*\n"
        "/change <address> - Track a different token\n"
        "/help - Show this help message\n"
        "/ping - Check if bot is running\n\n"
        "*Current Token:* EGG\n"
        "*Default Address:* `EfgEGG9PxLhyk1wqtqgGnwgfVC7JYic3vC9BCWLvpump`"
    )
    
    await update.message.reply_text(escape_md(help_text), parse_mode="MarkdownV2")

### --- SUBSCRIBE TO AUTOMATIC ALERTS --- ###
async def subscribe_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribe to automatic alerts."""
    user_id = update.message.chat_id
    context.application.user_data[user_id] = {'subscribed': True}
    
    # Send an immediate alert to confirm subscription
    token_address = context.application.user_data.get(user_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)
    pair = fetch_token_data(token_address)
    
    message = "✅ *You have subscribed to alerts for 24 hours!* \n\n"
    if pair:
        alert_message = generate_alert_message(pair)
        if alert_message:
            message += "Here's your first alert:\n\n" + alert_message
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

async def unsubscribe_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribe from automatic alerts."""
    user_id = update.message.chat_id
    if user_id in context.application.user_data and 'subscribed' in context.application.user_data[user_id]:
        del context.application.user_data[user_id]['subscribed']
        await update.message.reply_text(escape_md("❌ You have unsubscribed from alerts."), parse_mode="MarkdownV2")
    else:
        await update.message.reply_text(escape_md("⚠️ You are not subscribed to alerts."), parse_mode="MarkdownV2")

### --- AUTOMATIC ALERT FUNCTION (Scheduled Using JobQueue) --- ###
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Background job to check alerts for subscribed users."""
    for user_id in [user_id for user_id in context.application.user_data.keys() if 'subscribed' in context.application.user_data[user_id]]:
        try:
            token_address = context.application.user_data[user_id].get('token_address', DEFAULT_TOKEN_ADDRESS)
            pair = fetch_token_data(token_address)
            
            if pair:
                message = generate_alert_message(pair)
                
                # Add recent trades info
                trades = fetch_recent_trades(token_address)
                if trades:
                    message += "\n\n*Recent Trades:*\n"
                    for trade in trades[:3]:
                        timestamp = datetime.fromtimestamp(trade.get("blockTime", 0)/1000).strftime("%Y-%m-%d %H:%M:%S")
                        trade_type = trade.get("type", "UNKNOWN")
                        amount = trade.get("amount", 0)
                        message += f"• {timestamp}: {trade_type} - Amount: {amount:,.0f}\n"
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=escape_md(message),
                    parse_mode="MarkdownV2"
                )
        except Exception as e:
            print(f"Error sending alert to user {user_id}: {str(e)}")

### Helius API Functions ###

def fetch_token_metadata(token_address):
    """Enhanced token metadata fetch using paid Helius API features."""
    try:
        url = f"{HELIUS_API_URL}/token-metadata?api-key={HELIUS_API_KEY}"
        payload = {"mintAccounts": [token_address]}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                metadata = data[0]
                if metadata:
                    account_info = metadata.get("onChainAccountInfo", {}).get("accountInfo", {})
                    token_info = account_info.get("data", {}).get("parsed", {}).get("info", {})
                    
                    return {
                        "name": "EGG Token",  # Hardcoded name since metadata is not available
                        "symbol": "EGG",      # Hardcoded symbol
                        "decimals": token_info.get("decimals", 0),
                        "supply": token_info.get("supply", "0"),
                        "image": "",          # No image available
                        "description": "EGG Token on Solana"  # Hardcoded description
                    }
            print(f"No metadata found for token: {token_address}")
        else:
            print(f"Error fetching metadata. Status code: {response.status_code}")
            print(f"Response: {response.text}")
        return None
    except Exception as e:
        print(f"Error fetching token metadata: {str(e)}")
        return None

def fetch_token_holders(token_address, limit=20):
    """Enhanced token holders fetch with RPC API."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "my-id",
            "method": "getTokenLargestAccounts",
            "params": [token_address]
        }
        response = requests.post(HELIUS_RPC_URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data and "value" in data["result"]:
                holders = []
                for holder in data["result"]["value"]:
                    holders.append({
                        "address": holder.get("address"),
                        "amount": holder.get("amount"),
                        "decimals": holder.get("decimals", 0),
                        "uiAmount": holder.get("uiAmount", 0)
                    })
                return holders[:limit]
        return None
    except Exception as e:
        print(f"Error fetching token holders: {str(e)}")
        return None

def fetch_recent_trades(token_address, limit=10):
    """Enhanced recent trades fetch with RPC API."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "my-id",
            "method": "getSignaturesForAddress",
            "params": [
                token_address,
                {
                    "limit": limit
                }
            ]
        }
        response = requests.post(HELIUS_RPC_URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                trades = []
                for tx in data["result"]:
                    # Get detailed transaction info
                    tx_details = fetch_transaction_details(tx["signature"])
                    if tx_details:
                        trade_info = {
                            "signature": tx["signature"],
                            "blockTime": tx["blockTime"],
                            "type": tx_details.get("type", "unknown"),
                            "amount": tx_details.get("amount", 0),
                            "success": tx["err"] is None
                        }
                        trades.append(trade_info)
                return trades
        return None
    except Exception as e:
        print(f"Error fetching recent trades: {str(e)}")
        return None

def fetch_transaction_details(signature):
    """Enhanced transaction details fetch with enriched data."""
    try:
        url = f"{HELIUS_API_URL}/parsed-transaction?api-key={HELIUS_API_KEY}"
        payload = {"transactions": [signature]}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                tx = data[0]
                return {
                    "timestamp": tx.get("timestamp"),
                    "fee": tx.get("fee"),
                    "status": "success" if tx.get("success") else "failed",
                    "type": tx.get("type", "unknown"),
                    "tokenTransfers": tx.get("tokenTransfers", []),
                    "nativeTransfers": tx.get("nativeTransfers", [])
                }
        return None
    except Exception as e:
        print(f"Error fetching transaction details: {str(e)}")
        return None

def fetch_liquidity_changes(token_address):
    """Enhanced liquidity tracking with detailed pool information."""
    try:
        # First get token metadata
        metadata = fetch_token_metadata(token_address)
        if not metadata:
            return None

        # Get recent transactions
        trades = fetch_recent_trades(token_address, 50)
        if not trades:
            return None

        liquidity_events = []
        for trade in trades:
            if trade["type"] in ["ADD_LIQUIDITY", "REMOVE_LIQUIDITY", "SWAP"]:
                tx_details = fetch_transaction_details(trade["signature"])
                if tx_details:
                    event = {
                        "timestamp": trade["blockTime"],
                        "type": trade["type"],
                        "signature": trade["signature"],
                        "changes": tx_details.get("tokenTransfers", []),
                        "success": trade["success"]
                    }
                    liquidity_events.append(event)

        return liquidity_events
    except Exception as e:
        print(f"Error fetching liquidity changes: {str(e)}")
        return None

### New Telegram Commands ###

async def holders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top token holders."""
    user_id = update.message.chat_id
    token_address = context.application.user_data.get(user_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)
    
    holders = fetch_token_holders(token_address)
    if not holders:
        await update.message.reply_text(escape_md("⚠️ Could not fetch holder data."), parse_mode="MarkdownV2")
        return
    
    message = "*👥 Top Token Holders*\n\n"
    for i, holder in enumerate(holders[:10], 1):
        amount = float(holder.get("amount", 0)) / (10 ** holder.get("decimals", 0))
        percent = float(holder.get("amount", 0))
        message += f"{i}. `{holder['address'][:8]}...`: {percent:.2f}% ({amount:,.2f} tokens)\n"
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent large trades."""
    user_id = update.message.chat_id
    token_address = context.application.user_data.get(user_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)
    
    print(f"\n--- Fetching trades for user {user_id} ---")
    print(f"Token address: {token_address}")
    
    trades = fetch_recent_trades(token_address)
    if not trades:
        await update.message.reply_text(escape_md("⚠️ Could not fetch trade data. This might be due to API rate limits or the token not being actively traded."), parse_mode="MarkdownV2")
        return
    
    message = "*🔄 Recent Trades*\n\n"
    for trade in trades[:5]:
        sig = trade["signature"]
        timestamp = datetime.fromtimestamp(trade["blockTime"]/1000).strftime("%Y-%m-%d %H:%M:%S")
        amount = trade["amount"]
        trade_type = trade["type"]
        
        emoji = "🟢" if trade_type == "Buy" else "🔴" if trade_type == "Sell" else "⚪️"
        message += f"{emoji} *{trade_type}*: {amount:,.0f} tokens\n"
        message += f"🔹 [{sig[:8]}...](https://explorer.solana.com/tx/{sig})\n"
        message += f"📅 {timestamp}\n\n"
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

async def liquidity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show liquidity changes."""
    user_id = update.message.chat_id
    token_address = context.application.user_data.get(user_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)
    
    liquidity_data = fetch_liquidity_changes(token_address)
    if not liquidity_data:
        await update.message.reply_text(escape_md("⚠️ Could not fetch liquidity data."), parse_mode="MarkdownV2")
        return
    
    message = "*💧 Liquidity Analysis*\n\n"
    message += f"Current Liquidity: ${liquidity_data[0]['changes'][0]['amount']:,.2f}\n\n"
    
    if liquidity_data:
        message += "*Recent Events:*\n"
        for event in liquidity_data[:10]:
            timestamp = datetime.fromtimestamp(event["timestamp"]/1000).strftime("%Y-%m-%d %H:%M:%S")
            sig = event["signature"]
            emoji = "➕" if event["type"] == "Add Liquidity" else "➖"
            message += f"{emoji} {event['type']}: {event['changes'][0]['amount']:,.0f} tokens\n"
            message += f"🔹 [{sig[:8]}...](https://explorer.solana.com/tx/{sig})\n"
            message += f"📅 {timestamp}\n\n"
    else:
        message += "*No recent liquidity events found*"
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

async def metadata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show token metadata."""
    try:
        user_id = update.message.chat_id
        token_address = context.application.user_data.get(user_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)
        
        print(f"\n--- Fetching metadata for user {user_id} ---")
        print(f"Token address: {token_address}")
        
        metadata = fetch_token_metadata(token_address)
        if not metadata:
            await update.message.reply_text("❌ Could not fetch token metadata. Please verify the token address is correct.")
            return
        
        message = "*📊 Token Metadata*\n\n"
        message += f"Name: {metadata.get('name', 'Unknown')}\n"
        message += f"Symbol: {metadata.get('symbol', 'Unknown')}\n"
        message += f"Decimals: {metadata.get('decimals', 0)}\n"
        
        # Format supply with proper decimals
        supply = float(metadata.get('supply', '0')) / (10 ** metadata.get('decimals', 0))
        message += f"Total Supply: {supply:,.2f}\n"
        
        if metadata.get('description'):
            message += f"\nDescription: {metadata['description']}\n"
        
        if metadata.get('image'):
            message += f"\n[View Token Image]({metadata['image']})"
        
        await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")
        
    except Exception as e:
        print(f"Error in metadata command: {str(e)}")
        await update.message.reply_text("❌ An error occurred while fetching token metadata")

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
        app.add_handler(CommandHandler("holders", holders_command))
        app.add_handler(CommandHandler("trades", trades_command))
        app.add_handler(CommandHandler("liquidity", liquidity_command))
        app.add_handler(CommandHandler("metadata", metadata_command))

        # Add error handler
        app.add_error_handler(error_handler)

        # Set up job queue for alerts (every 2 minutes)
        job_queue.run_repeating(check_alerts, interval=120, first=10)

        print(f"Starting bot in {ENVIRONMENT} environment...")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"Error starting bot: {str(e)}")
        if "Conflict" in str(e):
            print("Another instance of the bot is already running. This instance will not start.")
        raise

def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors in the telegram bot."""
    print(f"Update {update} caused error {context.error}")
    try:
        if isinstance(context.error, Conflict):
            print("Conflict error: Another instance of the bot is already running")
        elif isinstance(context.error, TimedOut):
            print("Request timed out. Will retry automatically.")
        elif isinstance(context.error, (ValueError, TypeError)):
            print(f"Value/Type error: {str(context.error)}")
        else:
            print(f"Unexpected error: {str(context.error)}")
    except Exception as e:
        print(f"Error in error handler: {str(e)}")

if __name__ == "__main__":
    main()
