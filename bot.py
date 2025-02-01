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
import logging
import base58

# Load environment variables
# Note: In production, these environment variables are configured on Heroku
# Required environment variables:
# - TELEGRAM_BOT_TOKEN: The bot token from BotFather
# - HELIUS_API_KEY: API key for Helius API
# For local development, create a .env file with these variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
HELIUS_API_URL = "https://api.helius.xyz/v0"

# Default token address (EGG)
DEFAULT_TOKEN_ADDRESS = "EfgEGG9PxLhyk1wqtqgGnwgfVC7JYic3vC9BCWLvpump"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN is missing! "
        "This token should be configured in your Heroku environment variables. "
        "For local development, you can set it in a .env file."
    )
if not HELIUS_API_KEY:
    raise ValueError(
        "HELIUS_API_KEY is missing! "
        "This token should be configured in your Heroku environment variables. "
        "For local development, you can set it in a .env file."
    )

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
    """Fetch token data from DexScreener API"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        response = requests.get(url)
        data = response.json()
        
        if not data or "pairs" not in data or not data["pairs"]:
            return None
            
        # Get the pair with the highest liquidity
        pairs = data["pairs"]
        pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0)), reverse=True)
        return pairs[0]
        
    except Exception as e:
        return None


### Generate Alert Message ###
def generate_alert_message(pair):
    """Generate alert messages based on token metrics."""
    if not pair or "priceUsd" not in pair:
        return None

    # Extract metrics
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
    price_change_24h = float(pair.get("priceChange", {}).get("h24", 0))
    volume_1h = float(pair.get("volume", {}).get("h1", 0))
    volume_24h = float(pair.get("volume", {}).get("h24", 0))
    liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))
    txns = pair.get("txns", {})
    buys_1h = int(txns.get("h1", {}).get("buys", 0))
    sells_1h = int(txns.get("h1", {}).get("sells", 0))
    avg_buy_1h = volume_1h / buys_1h if buys_1h > 0 else 0
    avg_sell_1h = volume_1h / sells_1h if sells_1h > 0 else 0

    # Log metrics for debugging
    print(f"Alert Metrics - Price Change 1h: {price_change_1h}%, 24h: {price_change_24h}%")
    print(f"Volume 1h: ${volume_1h:,.2f}, 24h: ${volume_24h:,.2f}")
    print(f"Liquidity: ${liquidity_usd:,.2f}")
    print(f"Transactions 1h - Buys: {buys_1h}, Sells: {sells_1h}")
    print(f"Avg Transaction 1h - Buy: ${avg_buy_1h:,.2f}, Sell: ${avg_sell_1h:,.2f}")

    # Pump Alert - Price increase and high volume
    if price_change_1h > 20 and volume_1h > volume_24h / 12:  
        return "📈 Pump Alert! 🚀\n\n" \
               f"Price up {price_change_1h:.1f}% in 1h\n" \
               f"Volume: ${volume_1h:,.0f} (1h)"

    # Retail Arrival - Many small buys
    if buys_1h > 50 and avg_buy_1h < 100 and price_change_1h > 10:  
        return "👥 Retail Arrival! 📱\n\n" \
               f"Price up {price_change_1h:.1f}% in 1h\n" \
               f"Buys: {buys_1h} (1h)\n" \
               f"Avg Buy: ${avg_buy_1h:,.0f}"

    # Market Maker - Large liquidity changes
    if liquidity_usd > 100000:  
        return "🏦 Market Maker Alert! 💰\n\n" \
               f"Liquidity: ${liquidity_usd:,.0f}\n" \
               f"Price change: {price_change_1h:.1f}% (1h)"

    # Dump Alert - Price decrease and high volume
    if price_change_1h < -15 and volume_1h > volume_24h / 12:  
        return "📉 Dump Alert! 🚨\n\n" \
               f"Price down {price_change_1h:.1f}% in 1h\n" \
               f"Volume: ${volume_1h:,.0f} (1h)"

    # Retail Capitulation - Many small sells
    if sells_1h > 50 and avg_sell_1h < 100 and price_change_1h < -10:  
        return "🏃 Retail Capitulation! 💨\n\n" \
               f"Price down {price_change_1h:.1f}% in 1h\n" \
               f"Sells: {sells_1h} (1h)\n" \
               f"Avg Sell: ${avg_sell_1h:,.0f}"

    return None

### Generate Trade Alert Message ###
def generate_trade_alert_message(trades):
    """Generate alert message for recent trades."""
    if not trades or len(trades) == 0:
        return None

    message = "*Recent Large Trades*\n"
    for trade in trades:
        # Extract trade info
        amount_usd = trade.get("amount_usd", 0)
        amount_token = trade.get("amount_token", 0)
        trade_type = trade.get("type", "").upper()
        price = trade.get("price_usd", 0)
        
        # Skip small trades (less than $1000)
        if amount_usd < 1000:
            continue
            
        # Add emoji based on trade type
        emoji = "🟢" if trade_type == "BUY" else "🔴"
        
        # Format trade info
        message += (
            f"{emoji} {trade_type}: ${amount_usd:,.0f}\n"
            f"   • Amount: {amount_token:,.0f} tokens\n"
            f"   • Price: ${price:.6f}\n"
        )

    return message if len(message) > 20 else None

### Telegram Command: Fetch Alerts ###
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram command to fetch token price and transaction data."""
    try:
        chat_id = update.message.chat_id
        token_address = context.user_data.get('token_address', DEFAULT_TOKEN_ADDRESS)
        
        print(f"\n--- Fetching data for user {chat_id} ---")
        print(f"Token address: {token_address}")
        
        # Get token price data
        pair = fetch_token_data(token_address)
        if not pair:
            await update.message.reply_text("❌ Failed to fetch token data")
            return

        # Generate alert message
        alert_message = generate_alert_message(pair)
        if alert_message:
            print(f"Generated alert: {alert_message}")
        
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
        
        # Escape special characters for MarkdownV2 but preserve emoji and newlines
        escaped_message = full_message
        for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            escaped_message = escaped_message.replace(char, f'\\{char}')
        
        await update.message.reply_text(
            text=escaped_message,
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
    token_address = context.user_data.get('token_address', DEFAULT_TOKEN_ADDRESS)
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
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /change <TOKEN_ADDRESS>")
        return

    token_address = context.args[0]
    context.user_data['token_address'] = token_address
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
        "/liquidity - View liquidity changes\n"
        "/transactions - Analyze recent transactions\n"
        "/audit - Full token health analysis\n\n"
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
    context.user_data['subscribed'] = True
    
    # Send an immediate alert to confirm subscription
    token_address = context.user_data.get('token_address', DEFAULT_TOKEN_ADDRESS)
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
    if 'subscribed' in context.user_data:
        del context.user_data['subscribed']
        await update.message.reply_text(escape_md("❌ You have unsubscribed from alerts."), parse_mode="MarkdownV2")
    else:
        await update.message.reply_text(escape_md("⚠️ You are not subscribed to alerts."), parse_mode="MarkdownV2")

### --- AUTOMATIC ALERT FUNCTION (Scheduled Using JobQueue) --- ###
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Background job to check alerts for subscribed users."""
    try:
        print("\n--- Running scheduled alert check ---")
        
        # Get subscribed users
        subscribed_users = [user_id for user_id, data in context.application.user_data.items() if 'subscribed' in data]
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
        trade_message = "\n\n" + generate_trade_alert_message(trades) if trades else ""
        
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
    """Fetch token metadata prioritizing DexScreener data"""
    try:
        # Get token data from DexScreener
        url = f"https://api.dexscreener.com/tokens/v1/solana/{token_address}"
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Error response from DexScreener: {response.text}")
            return None
            
        pairs = response.json()
        if not pairs:
            print(f"No pairs found for token")
            return None
            
        # Get the pair with highest liquidity
        pair = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0)) if x.get("liquidity", {}).get("usd") else 0)
        
        # Get base token info
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        # Determine if our token is base or quote
        token_info = base_token if base_token.get("address").lower() == token_address.lower() else quote_token
        
        # Get holder count from Helius as backup
        holder_count = 0
        HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
        if HELIUS_API_KEY:
            url = f"https://api.helius.xyz/v0/addresses/{token_address}/balances?api-key={HELIUS_API_KEY}"
            response = requests.get(url)
            holder_count = response.json().get("numHolders", 0) if response.status_code == 200 else 0
            
        # Get additional metadata from Helius as backup
        metadata = {}
        if HELIUS_API_KEY:
            url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
            payload = {"mintAccounts": [token_address]}
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                metadata = response.json()[0] if response.json() else {}
        
        # Combine data from both sources
        return {
            "name": token_info.get("name"),
            "symbol": token_info.get("symbol"),
            "decimals": metadata.get("decimals"),
            "supply": metadata.get("supply"),
            "mintAuthority": metadata.get("mintAuthority"),
            "freezeAuthority": metadata.get("freezeAuthority"),
            "holder_count": holder_count,
            "token_standard": "SPL",
            "creators": metadata.get("creators", []),
            "royalties": metadata.get("sellerFeeBasisPoints", 0) / 100 if metadata.get("sellerFeeBasisPoints") else 0,
            "collection": metadata.get("collection", {}).get("name"),
            "description": metadata.get("description"),
            "image": pair.get("info", {}).get("imageUrl"),
            "attributes": metadata.get("attributes", []),
            "external_url": next((w.get("url") for w in pair.get("info", {}).get("websites", []) if w.get("url")), None)
        }
        
    except Exception as e:
        print(f"Error fetching token metadata: {str(e)}")
        return None

def fetch_token_holders(token_address, limit=20):
    """Enhanced token holders fetch with RPC API."""
    try:
        # Fetch holders using Helius DAS API for better holder parsing
        HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
        if not HELIUS_API_KEY:
            return None
            
        url = f"https://api.helius.xyz/v0/addresses/{token_address}/balances?api-key={HELIUS_API_KEY}"
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return None
            
        holders = response.json()
        
        # Filter and sort holders
        sorted_holders = sorted(holders, key=lambda x: float(x.get("amount", 0)), reverse=True)
        
        return sorted_holders[:limit]
        
    except Exception as e:
        print(f"Error fetching token holders: {str(e)}")
        return None

async def fetch_recent_trades(token_address, limit=10):
    """Enhanced recent trades fetch with DAS API integration."""
    try:
        print(f"Fetching trades for {token_address}")
        
        # Get current price for USD conversion
        pair = fetch_token_data(token_address)
        if not pair:
            return None
        current_price = float(pair.get("priceUsd", 0))
        
        # Construct API URL
        url = f"{HELIUS_API_URL}/addresses/{token_address}/transactions"
        
        # Set up parameters
        params = {
            "api-key": HELIUS_API_KEY,
            "type": ["SWAP"],  # Focus on swaps only for more accurate trade data
            "limit": limit * 2  # Fetch more to account for filtered transactions
        }
        
        # Make API request
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching trades: {response.status_code}")
            return None
            
        trades_data = response.json()
        print(f"Found {len(trades_data)} trades")
        
        trades = []
        for tx in trades_data:
            try:
                # Extract transfer amounts
                description = tx.get("description", "")
                if not description or "Swap" not in description:
                    continue
                    
                # Parse amounts from description
                # Example: "Swap 1000 TOKEN for 5 SOL"
                parts = description.split()
                amount_index = parts.index("Swap") + 1
                amount_token = float(parts[amount_index])
                
                # Determine if it's a buy or sell based on token flow
                is_buy = "for" in description
                
                # Calculate USD amount
                amount_usd = amount_token * current_price
                
                trades.append({
                    "type": "BUY" if is_buy else "SELL",
                    "amount_token": amount_token,
                    "amount_usd": amount_usd,
                    "price_usd": current_price,
                    "timestamp": tx.get("timestamp", 0)
                })
                
                if len(trades) >= limit:
                    break
                    
            except Exception as e:
                print(f"Error parsing trade: {str(e)}")
                continue
        
        return trades
        
    except Exception as e:
        print(f"Error in fetch_recent_trades: {str(e)}")
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
    token_address = context.user_data.get('token_address', DEFAULT_TOKEN_ADDRESS)
    
    holders = fetch_token_holders(token_address)
    if not holders:
        await update.message.reply_text(escape_md("⚠️ Could not fetch holder data."), parse_mode="MarkdownV2")
        return
    
    message = "*👥 Top Token Holders*\n\n"
    for i, holder in enumerate(holders[:10], 1):
        amount = float(holder.get("amount", 0))
        percent = float(holder.get("amount", 0))
        message += f"{i}. `{holder['address'][:8]}...`: {percent:.2f}% ({amount:,.2f} tokens)\n"
    
    await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")

async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent large trades."""
    user_id = update.message.chat_id
    token_address = context.user_data.get('token_address', DEFAULT_TOKEN_ADDRESS)
    
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
    token_address = context.user_data.get('token_address', DEFAULT_TOKEN_ADDRESS)
    
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
        token_address = context.user_data.get('token_address', DEFAULT_TOKEN_ADDRESS)
        
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
        supply = float(metadata.get('supply', '0')) / (10**metadata.get('decimals', 0))
        message += f"Total Supply: {supply:,.2f}\n"
        
        if metadata.get('description'):
            message += f"\nDescription: {metadata['description']}\n"
        
        if metadata.get('image'):
            message += f"\n[View Token Image]({metadata['image']})"
        
        await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")
        
    except Exception as e:
        print(f"Error in metadata command: {str(e)}")
        await update.message.reply_text("❌ An error occurred while fetching token metadata")

async def audit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze the health and risk factors of a token"""
    try:
        token_address = DEFAULT_TOKEN_ADDRESS
        if context.args and len(context.args) > 0:
            token_address = context.args[0]

        # Fetch both market data and token info
        pair = fetch_token_data(token_address)
        if not pair:
            await update.message.reply_text("❌ Failed to fetch token data")
            return

        # Build message sections
        sections = []

        # Token Information section
        info = pair.get('info', {})
        token_info_section = "*Token Information*\n"
        token_info_section += (
            f"• Name: {info.get('name', 'Unknown')}\n"
            f"• Symbol: {info.get('symbol', 'Unknown')}\n"
            f"• Created: {datetime.fromtimestamp(int(pair.get('pairCreatedAt', 0)/1000)).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"• DEX: {pair.get('dexId', 'Unknown').title()}\n"
        )
        sections.append(token_info_section)

        # Market Metrics section
        price_usd = float(pair.get("priceUsd", 0))
        volume_24h = float(pair.get("volume", {}).get("h24", 0))
        volume_1h = float(pair.get("volume", {}).get("h1", 0))
        volume_5m = float(pair.get("volume", {}).get("m5", 0))
        liquidity = float(pair.get("liquidity", {}).get("usd", 0))
        market_cap = float(pair.get("marketCap", 0))
        fdv = float(pair.get("fdv", 0))

        market_section = (
            "*Market Metrics*\n"
            f"• Price: ${price_usd:.6f}\n"
            f"• 24h Volume: ${volume_24h:,.2f}\n"
            f"• 1h Volume: ${volume_1h:,.2f}\n"
            f"• 5m Volume: ${volume_5m:,.2f}\n"
            f"• Liquidity: ${liquidity:,.2f}\n"
            f"• Market Cap: ${market_cap:,.2f}\n"
            f"• FDV: ${fdv:,.2f}\n"
        )
        sections.append(market_section)

        # Price Changes section
        price_change = pair.get('priceChange', {})
        price_section = (
            "*Price Changes*\n"
            f"• 5m: {price_change.get('m5', 0):+.2f}%\n"
            f"• 1h: {price_change.get('h1', 0):+.2f}%\n"
            f"• 6h: {price_change.get('h6', 0):+.2f}%\n"
            f"• 24h: {price_change.get('h24', 0):+.2f}%\n"
            f"• 7d: {price_change.get('d7', 0):+.2f}%\n"
        )
        sections.append(price_section)

        # Trading Activity section
        txns = pair.get('txns', {})
        h24 = txns.get('h24', {})
        h1 = txns.get('h1', {})
        buys_24h = int(h24.get('buys', 0))
        sells_24h = int(h24.get('sells', 0))
        buys_1h = int(h1.get('buys', 0))
        sells_1h = int(h1.get('sells', 0))
        
        activity_section = (
            "*Trading Activity*\n"
            f"• 24h Transactions: {buys_24h + sells_24h:,}\n"
            f"  - Buys: {buys_24h:,} ({buys_24h/(buys_24h + sells_24h)*100:.1f}%)\n"
            f"  - Sells: {sells_24h:,} ({sells_24h/(buys_24h + sells_24h)*100:.1f}%)\n"
            f"• 1h Transactions: {buys_1h + sells_1h:,}\n"
            f"  - Buys: {buys_1h:,} ({buys_1h/(buys_1h + sells_1h)*100:.1f}%)\n"
            f"  - Sells: {sells_1h:,} ({sells_1h/(buys_1h + sells_1h)*100:.1f}%)\n"
            f"• Buy/Sell Ratio 24h: {buys_24h/sells_24h:.2f}\n"
            f"• Buy/Sell Ratio 1h: {buys_1h/sells_1h:.2f}\n"
        )
        sections.append(activity_section)

        # Social Links section
        social_section = "*Social Links*\n"
        websites = info.get('websites', [])
        socials = info.get('socials', [])
        
        if websites:
            social_section += "• Websites:\n"
            for website in websites:
                social_section += f"  - {website.get('url')}\n"
                
        if socials:
            social_section += "• Social Media:\n"
            for social in socials:
                social_section += f"  - {social.get('type').title()}: {social.get('url')}\n"
                
        if websites or socials:
            sections.append(social_section)

        # Risk Analysis section
        risks = []
        
        # Age risk
        pair_age_hours = (datetime.now().timestamp() - int(pair.get('pairCreatedAt', 0)/1000)) / 3600
        if pair_age_hours < 24:
            risks.append(f"New token - only {pair_age_hours:.1f} hours old")
            
        # Liquidity risk
        if liquidity < 50000:
            risks.append(f"Low liquidity (${liquidity:,.2f}) - high price impact on trades")
            
        # Volume vs Liquidity risk
        if volume_24h > liquidity * 10:
            risks.append(f"High volume/liquidity ratio ({volume_24h/liquidity:.1f}x) - potential manipulation")
            
        # Price volatility risk
        if abs(float(price_change.get('h1', 0))) > 20:
            risks.append(f"High volatility - {abs(float(price_change.get('h1', 0))):.1f}% price change in 1h")
            
        # Trading pattern risks
        if buys_1h > 1000 and float(price_change.get('h1', 0)) > 30:
            risks.append("Potential pump - high buy pressure and price increase")
        elif sells_1h > 1000 and float(price_change.get('h1', 0)) < -30:
            risks.append("Potential dump - high sell pressure and price decrease")
            
        # Buy/Sell ratio risks
        if buys_24h/sells_24h > 3:
            risks.append(f"Unusual buy pressure - {buys_24h/sells_24h:.1f}x more buys than sells")
        elif sells_24h/buys_24h > 3:
            risks.append(f"Unusual sell pressure - {sells_24h/buys_24h:.1f}x more sells than buys")

        risk_section = "*Risk Analysis*\n"
        if risks:
            for risk in risks:
                risk_section += f"⚠️ {risk}\n"
        else:
            risk_section += "✅ No major risks detected\n"
        sections.append(risk_section)

        # Combine all sections
        message = "\n\n".join(sections)
        await update.message.reply_text(escape_md(message), parse_mode="MarkdownV2")
        
    except Exception as e:
        print(f"Error in audit command: {str(e)}")
        await update.message.reply_text("❌ An error occurred while analyzing the token")

def fetch_token_info(token_address):
    """Fetch comprehensive token information from multiple sources"""
    try:
        # Fetch token metadata from Helius
        metadata = fetch_token_metadata(token_address)
        if not metadata:
            return None
        
        # Fetch social info and additional data from DexScreener
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        response = requests.get(url)
        data = response.json()
        
        if not data or "pairs" not in data or not data["pairs"]:
            return None
            
        # Get the pair with the highest liquidity
        pairs = data["pairs"]
        pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0)), reverse=True)
        pair = pairs[0]
        
        # Extract social links and info
        info = pair.get("info", {})
        socials = {social["type"]: social["url"] for social in info.get("socials", [])} if info.get("socials") else {}
        websites = [site["url"] for site in info.get("websites", [])] if info.get("websites") else []
        
        return {
            "name": metadata.get("name"),
            "symbol": metadata.get("symbol"),
            "decimals": metadata.get("decimals"),
            "supply": metadata.get("supply"),
            "description": info.get("description"),
            "website": websites[0] if websites else None,
            "twitter": socials.get("twitter"),
            "image": info.get("imageUrl"),
            "is_mintable": metadata.get("mintAuthority") is not None,
            "is_freezable": metadata.get("freezeAuthority") is not None,
        }
        
    except Exception as e:
        return None

def analyze_recent_transactions(token_address, minutes=15):
    """Analyze recent transactions for patterns and unusual activity"""
    try:
        # Get transactions from the last 15 minutes
        current_time = int(time.time())
        cutoff_time = current_time - (minutes * 60)
        
        # Fetch transactions using Helius DAS API for better transaction parsing
        HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
        if not HELIUS_API_KEY:
            print("Missing HELIUS_API_KEY")
            return None
            
        # Use Helius Enhanced Transaction History API
        url = f"https://api.helius.xyz/v0/token-transactions?api-key={HELIUS_API_KEY}"
        payload = {
            "query": {
                "accounts": [token_address],
                "startTime": cutoff_time,
                "endTime": current_time
            }
        }
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return None
            
        transactions = response.json()
        if not transactions:
            print("No transactions found")
            return {
                "transaction_count": 0,
                "active_wallets": 0,
                "trading_velocity": 0,
                "patterns": {
                    "swaps": 0,
                    "rapid_swaps": 0,
                    "bot_trades": 0,
                    "wash_trades": 0,
                    "sandwich_attacks": 0,
                    "flash_loans": 0,
                    "high_slippage": 0,
                    "arbitrage": 0,
                    "failed": 0
                },
                "risk_metrics": {
                    "bot_activity": 0,
                    "wash_trading": 0,
                    "failed_tx_ratio": 0,
                    "large_trade_ratio": 0
                }
            }
        
        # Filter and analyze transactions
        wallets = set()
        wallet_last_trade = {}  # Last trade time per wallet
        wallet_trade_counts = {}  # Number of trades per wallet
        patterns = {
            "swaps": 0,
            "rapid_swaps": 0,
            "bot_trades": 0,
            "wash_trades": 0,
            "sandwich_attacks": 0,
            "flash_loans": 0,
            "high_slippage": 0,
            "arbitrage": 0,
            "failed": 0
        }
        
        large_trades = []  # Track large trades for sandwich detection
        
        for tx in transactions:
            # Extract transaction details
            source = tx.get('sourceAddress', '')
            instructions = tx.get('instructions', [])
            timestamp = tx.get('timestamp', 0)
            signatures = tx.get('signatures', [])
            
            if source:
                wallets.add(source)
            
            # Track wallet trading patterns
            if source in wallet_last_trade:
                time_since_last = timestamp - wallet_last_trade[source]
                if time_since_last < 60:  # Within 1 minute
                    patterns["rapid_swaps"] += 1
                    if time_since_last < 3:  # Within 3 seconds
                        patterns["bot_trades"] += 1
            
            wallet_last_trade[source] = timestamp
            wallet_trade_counts[source] = wallet_trade_counts.get(source, 0) + 1
            
            # Analyze transaction type
            for inst in instructions:
                program = inst.get('programId', '')
                if program in ['9qvG1zUp8xF1Bi4m6UdRNby1BAAuaDrUxSpv4CmRRMjL']:  # Jupiter/Raydium
                    patterns["swaps"] += 1
                    
                    # Check for high slippage
                    if inst.get('slippage', 0) > 5:
                        patterns["high_slippage"] += 1
                        
                    # Check for arbitrage (multiple DEX interactions)
                    if len([i for i in instructions if i.get('programId') in ['9qvG1zUp8xF1Bi4m6UdRNby1BAAuaDrUxSpv4CmRRMjL']]) > 1:
                        patterns["arbitrage"] += 1
                
                if program in ['LendZqTs7gn5CTSJU1jWKhKuVpjJGom45nnwPb2AMTi']:  # Lending protocols
                    if any('flash' in str(inst.get('data', '')).lower() for inst in instructions):
                        patterns["flash_loans"] += 1
            
            # Check for failed transactions
            if tx.get('successful') is False:
                patterns["failed"] += 1
        
        # Calculate trading velocity (tx/min)
        trading_velocity = len(transactions) / minutes if minutes > 0 else 0
        
        # Calculate risk metrics
        total_trades = len(transactions)
        if total_trades > 0:
            bot_activity = (patterns["bot_trades"] / total_trades) * 100
            wash_trading = (patterns["wash_trades"] / total_trades) * 100
            failed_tx_ratio = (patterns["failed"] / total_trades) * 100
            large_trade_ratio = (len(large_trades) / total_trades) * 100
        else:
            bot_activity = wash_trading = failed_tx_ratio = large_trade_ratio = 0
        
        return {
            "transaction_count": total_trades,
            "active_wallets": len(wallets),
            "trading_velocity": round(trading_velocity, 2),
            "patterns": patterns,
            "risk_metrics": {
                "bot_activity": round(bot_activity, 1),
                "wash_trading": round(wash_trading, 1),
                "failed_tx_ratio": round(failed_tx_ratio, 1),
                "large_trade_ratio": round(large_trade_ratio, 1)
            }
        }
        
    except Exception as e:
        print(f"Error analyzing transactions: {str(e)}")
        return None

async def transactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent transaction analysis."""
    user_id = update.message.chat_id
    token_address = context.user_data.get('token_address', DEFAULT_TOKEN_ADDRESS)
    
    print(f"\n--- Analyzing transactions for user {user_id} ---")
    print(f"Token address: {token_address}")
    
    # Get analysis timeframe from command arguments
    minutes = 15  # default timeframe
    if context.args and context.args[0].isdigit():
        minutes = int(context.args[0])
    
    analysis = analyze_recent_transactions(token_address, minutes)
    if not analysis:
        await update.message.reply_text("❌ Failed to analyze transactions. Please try again later.")
        return
        
    # Format the response
    message = f"📊 *Transaction Analysis* (Last {minutes} min)\n\n"
    
    message += f"*Overview*:\n"
    message += f"• Total Transactions: {analysis['transaction_count']}\n"
    message += f"• Active Wallets: {analysis['active_wallets']}\n"
    message += f"• Trading Velocity: {analysis['trading_velocity']:.2f} tx/min\n\n"
    
    message += f"*Transaction Patterns*:\n"
    patterns = analysis['patterns']
    message += f"• Swaps: {patterns['swaps']}\n"
    message += f"• Rapid Swaps: {patterns['rapid_swaps']}\n"
    message += f"• Bot Trades: {patterns['bot_trades']}\n"
    message += f"• Wash Trades: {patterns['wash_trades']}\n"
    message += f"• Sandwich Attacks: {patterns['sandwich_attacks']}\n"
    message += f"• Flash Loans: {patterns['flash_loans']}\n"
    message += f"• High Slippage: {patterns['high_slippage']}\n"
    message += f"• Arbitrage: {patterns['arbitrage']}\n"
    message += f"• Failed Transactions: {patterns['failed']}\n\n"
    
    message += f"*Risk Metrics*:\n"
    summary = analysis['risk_metrics']
    message += f"• Bot Activity: {summary['bot_activity']}%\n"
    message += f"• Wash Trading: {summary['wash_trading']}%\n"
    message += f"• Failed Tx Ratio: {summary['failed_tx_ratio']}%\n"
    message += f"• Large Trade Ratio: {summary['large_trade_ratio']}%\n\n"
    
    if analysis['suspicious_wallets']:
        message += f"*Suspicious Wallets*:\n"
        for wallet, count in list(analysis['suspicious_wallets'].items())[:5]:  # Show top 5
            message += f"• `{wallet[:8]}...`: {count} txs\n"
        message += "\n"
        
    if analysis['suspicious_pairs']:
        message += f"*Suspicious Trading Pairs*:\n"
        for pair, count in list(analysis['suspicious_pairs'].items())[:3]:  # Show top 3
            w1, w2 = pair.split(":")
            message += f"• `{w1[:6]}..` ↔️ `{w2[-6:]}`: {count} interactions\n"
        message += "\n"
        
    if analysis['unusual_activity']:
        message += f"*Unusual Activity*:\n"
        for activity in analysis['unusual_activity'][:5]:  # Show top 5
            wallet = activity['wallet']
            message += f"• {activity['type']}: {activity.get('amount') or activity.get('fee')} "
            message += f"(`{wallet[:6]}...{wallet[-4:]}`)\n"
            
    await update.message.reply_text(
        message,
        parse_mode='Markdown'
    )

### Bot Main Function ###
def main():
    """Run the Telegram bot."""
    try:
        print("Starting bot in production environment...")
        
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
            .concurrent_updates(True)  
            .build()
        )

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
        application.add_handler(CommandHandler("audit", audit_command))
        application.add_handler(CommandHandler("transactions", transactions_command))

        application.add_error_handler(error_handler)

        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  
            stop_signals=None,  
            close_loop=False  
        )

    except telegram.error.Conflict as e:
        print(f"Conflict error: {e}")
        print("Another instance is running. Waiting for it to terminate...")
        time.sleep(30)  
        sys.exit(1)
    except Exception as e:
        print(f"Error starting bot: {e}")
        time.sleep(10)  
        sys.exit(1)

def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors in the telegram bot."""
    try:
        if isinstance(context.error, telegram.error.Conflict):
            print("Conflict error: Another instance is running")
            return  
            
        if isinstance(context.error, telegram.error.TimedOut):
            print("Request timed out. Will retry automatically.")
            return  
            
        if update:
            print(f"Update {update.update_id} caused error: {context.error}")
        else:
            print(f"Error without update: {context.error}")
            
    except Exception as e:
        print(f"Error in error handler: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
