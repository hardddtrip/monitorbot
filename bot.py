import os
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Get Telegram bot token from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Ensure this is set in your environment

# Default token address (if user hasn't changed it)
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

# Dictionary to store user-selected token addresses
user_addresses = {}

### --- CORE COMMANDS --- ###

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to /start command."""
    await update.message.reply_text("Hello from the new v20-style bot!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a list of commands with correct MarkdownV2 escaping."""
    help_text = (
        "📌 *Available Commands:*\n"
        "\\- `/start` \\- Greet the user\n"
        "\\- `/help` \\- Show this help message\n"
        "\\- `/ping` \\- Check if the bot is alive\n"
        "\\- `/price` \\- Get token price \\(default or user selected\\)\n"
        "\\- `/change <TOKEN_ADDRESS>` \\- Change the token address to track\n"
        "🔍 Automatic alerts run *every 15 minutes*"
    )
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to /ping command with 'Pong!'."""
    await update.message.reply_text("Pong!")

### --- PRICE FETCHING --- ###

def escape_md(text):
    """Escape MarkdownV2 special characters."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))

async def fetch_token_data(token_address):
    """Fetch token price & volume data from DexScreener API."""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        response = requests.get(url)
        data = response.json()
        if "pairs" not in data or len(data["pairs"]) == 0:
            return None
        return data["pairs"][0]  # Return first trading pair
    except Exception:
        return None

async def detect_meme_coin_stage(application):
    """Detect meme coin lifecycle stage & send alerts every 15 minutes."""
    token_address = DEFAULT_TOKEN_ADDRESS  # Tracking only one token for now
    pair = await fetch_token_data(token_address)

    if not pair:
        print("⚠️ No data found for the token.")
        return

    # Extract price & volume
    price_usd = float(pair["priceUsd"])
    volume_24h = float(pair["volume"]["h24"])
    liquidity = float(pair["liquidity"]["usd"])

    # Define detection logic (heuristics)
    alert_message = None

    # 🚀 Pump Detection (Rapid price increase)
    if price_usd > 1.2 * float(pair["priceChange"]["h1"]):  
        alert_message = escape_md("📈 *Pump Alert!* 🚀\nRapid price increase detected!")

    # 🛒 Retail Arrival (Many small trades)
    elif pair["txns"]["h1"]["buys"] > 500 and volume_24h < 1000000:
        alert_message = escape_md("🛍 *Retail Arrival Detected!*\nMany small traders are buying in.")

    # 💰 Market Maker Transfer (Large wallet outflow)
    elif liquidity > 2000000 and volume_24h > 5000000:
        alert_message = escape_md("🔄 *Market Maker Transfer!* 📊\nLarge liquidity shift detected.")

    # 📉 Dump Detection (Massive sell-off)
    elif price_usd < 0.8 * float(pair["priceChange"]["h1"]):
        alert_message = escape_md("⚠️ *Dump Alert!* 💥\nHeavy selling detected!")

    # 😭 Retail Capitulation (Many small sells)
    elif pair["txns"]["h1"]["sells"] > 1000 and volume_24h < 500000:
        alert_message = escape_md("💀 *Retail Capitulation!* 🏳️\nRetail investors are selling in fear.")

    # Send Alert to Telegram
    if alert_message:
        bot = application.bot
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=alert_message, parse_mode="MarkdownV2")

### --- Scheduled Task Setup --- ###

def setup_scheduler(application):
    """Setup a background scheduler to check meme coin status every 15 minutes."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(detect_meme_coin_stage, "interval", minutes=15, args=[application])
    scheduler.start()

### --- PRICE COMMAND --- ###

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch and display token price for the user's selected address."""
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)

    pair = await fetch_token_data(token_address)
    
    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    price_usd = pair["priceUsd"]
    volume_24h = pair["volume"]["h24"]
    liquidity = pair["liquidity"]["usd"]
    market_cap = pair.get("marketCap", "N/A")
    dex_url = pair["url"]

    message = (
        f"💰 *Token Price \$begin:math:text$USD\\$end:math:text$*: \\${escape_md(price_usd)}\n"
        f"📊 *24h Volume*: \\${escape_md(f'{volume_24h:,}')}\n"
        f"💧 *Liquidity*: \\${escape_md(f'{liquidity:,}')}\n"
        f"🏦 *Market Cap \$begin:math:text$MC\\$end:math:text$*: \\${escape_md(f'{market_cap:,}')}\n"
        f"🔗 [View on DexScreener]({dex_url})"
    )

    await update.message.reply_text(message, parse_mode="MarkdownV2")

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

### --- BOT MAIN FUNCTION --- ###

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("change", change_command))

    # Start the scheduler
    setup_scheduler(app)

    # Start the bot
    await app.run_polling()

# ✅ FIX: Ensure the event loop is correctly handled
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
