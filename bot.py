import os
import sys
import time
import json
import requests
from datetime import datetime
import telegram
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    ContextTypes
)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
HELIUS_API_URL = "https://api.helius.xyz/v0"

# Default token address (EGG)
DEFAULT_TOKEN_ADDRESS = "EfgEGG9PxLhyk1wqtqgGnwgfVC7JYic3vC9BCWLvpump"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")
if not HELIUS_API_KEY:
    raise ValueError("HELIUS_API_KEY is missing! Set it in your environment variables.")

# Helius API endpoints
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

    price_usd = float(pair["priceUsd"])
    volume_24h = float(pair["volume"]["h24"])
    liquidity = float(pair["liquidity"]["usd"])
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))

    if price_usd > 1.2 * price_change_1h:
        return "📈 *Pump Alert!* 🚀\nRapid price increase detected!"
    elif pair["txns"]["h1"]["buys"] > 500 and volume_24h < 1000000:
        return "🛍 *Retail Arrival Detected!*"
    elif liquidity > 2000000 and volume_24h > 5000000:
        return "🔄 *Market Maker Transfer!* 📊"
    elif price_usd < 0.8 * price_change_1h:
        return "⚠️ *Dump Alert!* 💥"
    elif pair["txns"]["h1"]["sells"] > 1000 and volume_24h < 500000:
        return "💀 *Retail Capitulation!* 🏳️"
    return None

### Telegram Command: Fetch Alerts ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram command to fetch token price and transaction data."""
    try:
        chat_id = update.message.chat_id
        token_address = context.application.user_data.get(chat_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)
        
        print(f"\n--- Fetching data for user {chat_id} ---")
        print(f"Token address: {token_address}")
        
        # Get token price data
        pair = fetch_token_data(token_address)
        if not pair:
            await update.message.reply_text("❌ Failed to fetch token data")
            return

        # Generate alert message
        alert_message = generate_alert_message(pair)
        
        # Generate price info
        price_usd = float(pair.get("priceUsd", 0))
        price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
        volume_24h = float(pair.get("volume", {}).get("h24", 0))
        liquidity = float(pair.get("liquidity", {}).get("usd", 0))
        buys_1h = int(pair.get("txns", {}).get("h1", {}).get("buys", 0))
        sells_1h = int(pair.get("txns", {}).get("h1", {}).get("sells", 0))

        price_info = (
            f"💰 *Price*: ${price_usd:.6f}\n"
            f"📊 *1h Change*: {price_change_1h:.2f}%\n"
            f"💧 *Liquidity*: ${liquidity:,.0f}\n"
            f"📈 *24h Volume*: ${volume_24h:,.0f}\n"
            f"🔄 *1h Transactions*:\n"
            f"  • Buys: {buys_1h}\n"
            f"  • Sells: {sells_1h}\n"
        )
        
        # Get recent trades
        trades = await fetch_recent_trades(token_address)
        trade_message = "\n\n" + generate_trade_alert_message(trades) if trades else ""
        
        # Combine messages
        full_message = f"{alert_message}\n\n{price_info}{trade_message}" if alert_message else f"{price_info}{trade_message}"
        
        await update.message.reply_text(
            text=escape_md(full_message),
            parse_mode='MarkdownV2',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        print(f"Error in alert command: {str(e)}")
        await update.message.reply_text(
            "⚠️ An error occurred while fetching data. Please try again later."
        )

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
    try:
        print("\n--- Running scheduled alert check ---")
        
        # Get subscribed users
        subscribed_users = context.application.user_data.get('subscribed_users', [])
        if not subscribed_users:
            print("No subscribed users")
            return
            
        print(f"Found {len(subscribed_users)} subscribed users")
        
        # Get token data
        pair = fetch_token_data(DEFAULT_TOKEN_ADDRESS)
        if not pair:
            print("Failed to fetch token data")
            return
            
        # Generate alert message
        price_message = generate_alert_message(pair)
        
        # Get recent trades
        trades = await fetch_recent_trades(DEFAULT_TOKEN_ADDRESS)
        trade_message = "\n\n" + generate_trade_alert_message(trades)
        
        # Combine messages
        full_message = price_message + trade_message
        
        # Send alerts to all subscribed users
        for user_id in subscribed_users:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=escape_md(full_message),
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=True
                )
                print(f"Sent alert to user {user_id}")
            except Exception as e:
                print(f"Failed to send alert to user {user_id}: {str(e)}")
                
    except Exception as e:
        print(f"Error in check_alerts: {str(e)}")

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

async def fetch_recent_trades(token_address, limit=10):
    """Enhanced recent trades fetch with DAS API integration."""
    try:
        print(f"Fetching trades for {token_address}")
        
        # Construct API URL
        url = f"{HELIUS_API_URL}/addresses/{token_address}/transactions"
        
        # Set up parameters
        params = {
            "api-key": HELIUS_API_KEY,
            "type": ["SWAP", "TRANSFER"],  # Include both swaps and transfers
            "limit": limit
        }
        
        # Make API request
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching trades: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
        data = response.json()
        trades = []
        
        for tx in data:
            trade_info = {
                "timestamp": tx.get("timestamp", 0),
                "signature": tx.get("signature", "Unknown"),
                "description": tx.get("description", "Unknown Trade")
            }
            
            # Add token transfers if available
            if "tokenTransfers" in tx:
                for transfer in tx["tokenTransfers"]:
                    if transfer.get("mint") == token_address:
                        trade_info["amount"] = float(transfer.get("tokenAmount", 0))
                        trade_info["from"] = transfer.get("fromUserAccount", "Unknown")
                        trade_info["to"] = transfer.get("toUserAccount", "Unknown")
                        break
            
            trades.append(trade_info)
            
        print(f"Found {len(trades)} trades")
        return trades
        
    except Exception as e:
        print(f"Error fetching trades: {str(e)}")
        return None

async def fetch_liquidity_changes(token_address):
    """Enhanced liquidity tracking with detailed pool information."""
    try:
        # Get recent transactions
        trades = await fetch_recent_trades(token_address, 50)  # Get more trades for better liquidity tracking
        if not trades:
            return None
            
        # Track liquidity changes
        liquidity_changes = []
        
        for trade in trades:
            description = trade.get("description", "").lower()
            # Look for liquidity-related transactions
            if any(word in description for word in ["liquidity", "pool", "swap", "raydium"]):
                liquidity_changes.append({
                    "timestamp": trade.get("timestamp", 0),
                    "description": trade.get("description", "Unknown"),
                    "signature": trade.get("signature", "Unknown"),
                    "amount": trade.get("amount", 0)
                })
                
        return liquidity_changes if liquidity_changes else None
        
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
    
    trades = await fetch_recent_trades(token_address)
    if not trades:
        await update.message.reply_text(escape_md("⚠️ Could not fetch trade data. This might be due to API rate limits or the token not being actively traded."), parse_mode="MarkdownV2")
        return
    
    message = "*🔄 Recent Trades*\n\n"
    for trade in trades[:5]:
        sig = trade["signature"]
        timestamp = datetime.fromtimestamp(trade["timestamp"]/1000).strftime("%Y-%m-%d %H:%M:%S")
        amount = trade.get("amount", 0)
        
        alert_message = (
            f"*Trade at {timestamp}*:\n"
            f"💰 Amount: {amount:,.2f} EGG\n"
            f"📤 From: `{trade.get('from', 'Unknown')}`\n"
            f"📥 To: `{trade.get('to', 'Unknown')}`\n"
            f"🔗 [View Transaction](https://solscan.io/tx/{sig})\n\n"
        )
        
        message += alert_message
    
    if not trades:
        message += "No recent trades found in the last hour."
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

async def liquidity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show liquidity changes."""
    user_id = update.message.chat_id
    token_address = context.application.user_data.get(user_id, {}).get('token_address', DEFAULT_TOKEN_ADDRESS)
    
    liquidity_data = await fetch_liquidity_changes(token_address)
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

def generate_trade_alert_message(trades):
    """Generate alert message from trade data."""
    if not trades:
        return "⚠️ Could not fetch trade data. This might be due to API rate limits or the token not being actively traded."
    
    message = "🔔 *Recent EGG Token Activity*\n\n"
    
    for trade in trades[:5]:  # Show last 5 trades
        try:
            # Extract trade info safely
            timestamp = datetime.fromtimestamp(trade.get("timestamp", 0))
            description = trade.get("description", "Unknown Trade")
            sig = trade.get("signature", "Unknown")[:8]
            
            # Format trade info
            message += f"• {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"  {description}\n"
            message += f"  Signature: {sig}...\n\n"
            
        except Exception as e:
            print(f"Error formatting trade: {e}")
            continue
    
    return message

async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send alert about recent trades."""
    try:
        chat_id = update.message.chat_id
        print(f"\n--- Fetching trades for user {chat_id} ---")
        print(f"Token address: {DEFAULT_TOKEN_ADDRESS}")
        
        # Get recent trades
        trades = await fetch_recent_trades(DEFAULT_TOKEN_ADDRESS)
        
        # Generate and send message
        message = generate_trade_alert_message(trades)
        await update.message.reply_text(
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        print(f"Error in alert command: {str(e)}")
        await update.message.reply_text(
            "⚠️ An error occurred while fetching trade data. Please try again later."
        )

### Bot Main Function ###
def main():
    """Run the Telegram bot."""
    try:
        print("Starting bot in production environment...")
        
        # Create application with proper timeouts and settings
        application = (
            ApplicationBuilder()
            .token(TELEGRAM_BOT_TOKEN)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .pool_timeout(30)
            .get_updates_connect_timeout(30)
            .get_updates_read_timeout(30)
            .get_updates_write_timeout(30)
            .get_updates_pool_timeout(30)
            .concurrent_updates(True)  # Allow concurrent updates
            .build()
        )

        # Add command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("alert", alert_command))
        application.add_handler(CommandHandler("trades", trades_command))
        application.add_handler(CommandHandler("metadata", metadata_command))
        application.add_handler(CommandHandler("price", price_command))
        application.add_handler(CommandHandler("ping", ping_command))
        application.add_handler(CommandHandler("change", change_command))
        application.add_handler(CommandHandler("holders", holders_command))
        application.add_handler(CommandHandler("liquidity", liquidity_command))
        application.add_handler(CommandHandler("subscribe", subscribe_alerts_command))
        application.add_handler(CommandHandler("unsubscribe", unsubscribe_alerts_command))

        # Add error handler
        application.add_error_handler(error_handler)

        # Start the bot with proper settings
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Important: Drop pending updates
            stop_signals=None,  # Don't stop on signals
            close_loop=False  # Don't close the event loop
        )

    except telegram.error.Conflict as e:
        print(f"Conflict error: {e}")
        print("Another instance is running. Waiting for it to terminate...")
        time.sleep(30)  # Wait longer to ensure other instance is gone
        sys.exit(1)
    except Exception as e:
        print(f"Error starting bot: {e}")
        time.sleep(10)  # Wait before exiting
        sys.exit(1)

def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors in the telegram bot."""
    try:
        if isinstance(context.error, telegram.error.Conflict):
            print("Conflict error: Another instance is running")
            return  # Just return and let the main error handler deal with it
            
        if isinstance(context.error, telegram.error.TimedOut):
            print("Request timed out. Will retry automatically.")
            return  # Return and let the framework retry
            
        if update:
            print(f"Update {update.update_id} caused error: {context.error}")
        else:
            print(f"Error without update: {context.error}")
            
    except Exception as e:
        print(f"Error in error handler: {e}")

if __name__ == "__main__":
    main()
