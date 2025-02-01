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
    HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "my-id",
            "method": "getSignaturesForAddress",
            "params": [
                wallet_address,
                {
                    "limit": limit,
                    "before": "",
                    "until": ""
                }
            ]
        }
        response = requests.post(HELIUS_RPC_URL, json=payload)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                return data['result']
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
        return None

    price = float(pair.get("priceUsd", 0))
    price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))
    volume_24h = float(pair.get("volume", {}).get("h24", 0))
    liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))

    # Only alert if there's significant price movement in 5 minutes
    if abs(price_change_5m) < 1.0:  # Less than 1% change
        return None

    trend = "🟢" if price_change_5m > 0 else "🔴"
    message = (
        f"{trend} *Price Alert*\n\n"
        f"💵 Price: ${price:.6f}\n"
        f"📊 5m Change: {price_change_5m:+.2f}%\n"
        f"💧 Liquidity: ${liquidity_usd:,.0f}\n"
        f"📈 24h Volume: ${volume_24h:,.0f}"
    )
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
    """Send a message when the command /help is issued."""
    help_text = escape_md(
        "🤖 *Token Monitor Bot Commands*\n\n"
        "*Basic Commands:*\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/ping - Check if bot is alive\n\n"
        "*Price & Alerts:*\n"
        "/price - Get current token price\n"
        "/alert - Check alerts manually\n"
        "/subscribe - Enable auto alerts (24h)\n"
        "/unsubscribe - Disable auto alerts\n\n"
        "*Token Analysis:*\n"
        "/metadata - Show token info\n"
        "/holders - View top holders\n"
        "/trades - Recent large trades\n"
        "/liquidity - Liquidity analysis\n\n"
        "*Settings:*\n"
        "/change <TOKEN_ADDRESS> - Change token address"
    )
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")


### --- SUBSCRIBE TO AUTOMATIC ALERTS --- ###
async def subscribe_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribe to automatic alerts."""
    user_id = update.message.chat_id
    expiry_time = time.time() + 86400  # 24 hours from now
    subscribed_users[user_id] = expiry_time
    
    # Send an immediate alert to confirm subscription
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
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
    if user_id in subscribed_users:
        del subscribed_users[user_id]
        await update.message.reply_text(escape_md("❌ You have unsubscribed from alerts."), parse_mode="MarkdownV2")
    else:
        await update.message.reply_text(escape_md("⚠️ You are not subscribed to alerts."), parse_mode="MarkdownV2")

### --- AUTOMATIC ALERT FUNCTION (Scheduled Using JobQueue) --- ###
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Check alerts every 2 minutes for subscribed users."""
    current_time = time.time()
    expired_users = [user_id for user_id, expiry in subscribed_users.items() if current_time > expiry]

    # Remove expired subscriptions and notify users
    for user_id in expired_users:
        del subscribed_users[user_id]
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=escape_md("⏰ Your 24-hour alert subscription has expired. Use /subscribe to enable alerts again."),
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            print(f"Error notifying user {user_id} about subscription expiry: {str(e)}")

    # Process active subscriptions
    for user_id in subscribed_users.keys():
        try:
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
        except Exception as e:
            print(f"Error sending alert to user {user_id}: {str(e)}")

### Helius API Functions ###

def fetch_token_metadata(token_address):
    """Enhanced token metadata fetch using paid Helius API features."""
    HELIUS_API_URL = f"https://api.helius.xyz/v0"
    try:
        url = f"{HELIUS_API_URL}/token-metadata?api-key={HELIUS_API_KEY}"
        payload = {"mintAccounts": [token_address]}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                metadata = data[0]
                return {
                    "name": metadata.get("onChainMetadata", {}).get("metadata", {}).get("name", "Unknown"),
                    "symbol": metadata.get("onChainMetadata", {}).get("metadata", {}).get("symbol", "Unknown"),
                    "image": metadata.get("offChainMetadata", {}).get("image", ""),
                    "description": metadata.get("offChainMetadata", {}).get("description", ""),
                    "attributes": metadata.get("offChainMetadata", {}).get("attributes", []),
                    "collection": metadata.get("onChainMetadata", {}).get("metadata", {}).get("collection", {}),
                }
        return None
    except Exception as e:
        print(f"Error fetching token metadata: {str(e)}")
        return None

def fetch_token_holders(token_address, limit=20):
    """Enhanced token holders fetch with detailed balance information."""
    HELIUS_API_URL = f"https://api.helius.xyz/v0"
    try:
        url = f"{HELIUS_API_URL}/token-holdings?api-key={HELIUS_API_KEY}"
        payload = {
            "query": {
                "tokenAccount": token_address,
                "limit": limit,
                "sortBy": "BALANCE",
                "sortDirection": "DESC"
            }
        }
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            holders = []
            for holder in data.get("result", []):
                holders.append({
                    "owner": holder.get("owner"),
                    "balance": holder.get("balance"),
                    "delegated": holder.get("delegate") is not None,
                    "frozen": holder.get("isFrozen", False)
                })
            return holders
        return None
    except Exception as e:
        print(f"Error fetching token holders: {str(e)}")
        return None

def fetch_recent_trades(token_address, limit=10):
    """Enhanced recent trades fetch with DAS API integration."""
    HELIUS_API_URL = f"https://api.helius.xyz/v0"
    try:
        url = f"{HELIUS_API_URL}/token-transactions?api-key={HELIUS_API_KEY}"
        payload = {
            "query": {
                "tokens": [token_address],
                "transactionType": ["SWAP"],
                "limit": limit
            }
        }
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            trades = []
            for tx in data.get("result", []):
                trade_info = {
                    "signature": tx.get("signature"),
                    "timestamp": tx.get("timestamp"),
                    "type": determine_trade_type(tx),
                    "amount": extract_trade_amount(tx),
                    "fee": tx.get("fee", 0),
                    "success": tx.get("success", True)
                }
                trades.append(trade_info)
            return trades
        return None
    except Exception as e:
        print(f"Error fetching recent trades: {str(e)}")
        return None

def fetch_transaction_details(signature):
    """Enhanced transaction details fetch with enriched data."""
    HELIUS_API_URL = f"https://api.helius.xyz/v0"
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
                    "instructions": tx.get("instructions", []),
                    "tokenTransfers": tx.get("tokenTransfers", []),
                    "nativeTransfers": tx.get("nativeTransfers", [])
                }
        return None
    except Exception as e:
        print(f"Error fetching transaction details: {str(e)}")
        return None

def fetch_liquidity_changes(token_address):
    """Enhanced liquidity tracking with detailed pool information."""
    HELIUS_API_URL = f"https://api.helius.xyz/v0"
    try:
        url = f"{HELIUS_API_URL}/token-transactions?api-key={HELIUS_API_KEY}"
        payload = {
            "query": {
                "tokens": [token_address],
                "transactionType": ["SWAP", "ADD_LIQUIDITY", "REMOVE_LIQUIDITY"],
                "limit": 20
            }
        }
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            liquidity_events = []
            for tx in data.get("result", []):
                event = {
                    "timestamp": tx.get("timestamp"),
                    "type": tx.get("type"),
                    "signature": tx.get("signature"),
                    "changes": tx.get("tokenTransfers", []),
                    "success": tx.get("success", True)
                }
                liquidity_events.append(event)
            return liquidity_events
        return None
    except Exception as e:
        print(f"Error fetching liquidity changes: {str(e)}")
        return None

def is_trade_transaction(tx):
    """Check if transaction is a trade."""
    if not tx or "meta" not in tx:
        return False
    
    # Check program IDs for common DEX programs
    for account in tx.get("transaction", {}).get("message", {}).get("accountKeys", []):
        if account.get("pubkey") in [
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium
            "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",  # Jupiter
            "DjVE6JNiYqPL2QXyCUUh8rNjHrbz9hXHNYt99MQ59qw1",  # Orca
        ]:
            return True
    return False

def determine_trade_type(tx):
    """Determine if trade is a buy or sell."""
    if not tx or "meta" not in tx:
        return "Unknown"
    
    logs = tx["meta"].get("logMessages", [])
    for log in logs:
        if "swap" in log.lower():
            if "in" in log.lower():
                return "Buy"
            elif "out" in log.lower():
                return "Sell"
    return "Swap"

def extract_trade_amount(tx):
    """Extract trade amount from transaction."""
    if not tx or "meta" not in tx:
        return 0
    
    # Look for token balance changes
    for balance_change in tx["meta"].get("postTokenBalances", []):
        if balance_change.get("mint") == DEFAULT_TOKEN_ADDRESS:
            return float(balance_change.get("uiTokenAmount", {}).get("uiAmount", 0))
    return 0

### New Telegram Commands ###

async def holders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top token holders."""
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    
    holders = fetch_token_holders(token_address)
    if not holders:
        await update.message.reply_text(escape_md("⚠️ Could not fetch holder data."), parse_mode="MarkdownV2")
        return
    
    message = "*👥 Top Token Holders*\n\n"
    for i, holder in enumerate(holders[:10], 1):
        amount = float(holder.get("balance", 0))
        percent = float(holder.get("balance", 0))
        message += f"{i}. `{holder['owner'][:8]}...`: {percent:.2f}% ({amount:,.0f} tokens)\n"
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent large trades."""
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    
    print(f"\n--- Fetching trades for user {user_id} ---")
    print(f"Token address: {token_address}")
    
    trades = fetch_recent_trades(token_address)
    if not trades:
        await update.message.reply_text(escape_md("⚠️ Could not fetch trade data. This might be due to API rate limits or the token not being actively traded."), parse_mode="MarkdownV2")
        return
    
    message = "*🔄 Recent Trades*\n\n"
    for trade in trades[:5]:
        sig = trade["signature"]
        timestamp = datetime.fromtimestamp(trade["timestamp"]/1000).strftime("%Y-%m-%d %H:%M:%S")
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
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    
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
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    
    print(f"\n--- Fetching metadata for user {user_id} ---")
    print(f"Token address: {token_address}")
    
    metadata = fetch_token_metadata(token_address)
    if not metadata:
        await update.message.reply_text(
            escape_md("⚠️ Could not fetch token metadata. Please verify the token address is correct."),
            parse_mode="MarkdownV2"
        )
        return
    
    message = "*ℹ️ Token Metadata*\n\n"
    
    # Basic token info
    message += f"Name: {metadata.get('name', 'Unknown')}\n"
    message += f"Symbol: {metadata.get('symbol', 'Unknown')}\n"
    message += f"Decimals: {metadata.get('decimals', 'Unknown')}\n"
    
    # Supply info
    supply = metadata.get('supply')
    if supply is not None:
        try:
            supply_float = float(supply)
            message += f"Total Supply: {supply_float:,.0f}\n"
        except (ValueError, TypeError):
            message += f"Total Supply: {supply}\n"
    
    # Price info (if available)
    price = metadata.get('price')
    if price is not None:
        try:
            price_float = float(price)
            message += f"Price: ${price_float:.6f}\n"
        except (ValueError, TypeError):
            message += f"Price: {price}\n"
    
    # Volume info (if available)
    volume = metadata.get('volume24h')
    if volume is not None:
        try:
            volume_float = float(volume)
            message += f"24h Volume: ${volume_float:,.2f}\n"
        except (ValueError, TypeError):
            message += f"24h Volume: {volume}\n"
    
    # Data source
    source = "Helius"
    message += f"\nData Source: {source}"
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

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
