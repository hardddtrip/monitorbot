import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Get Telegram bot token from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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
        "\\- `/change <TOKEN_ADDRESS>` \\- Change the token address to track"
        "🔍 Automatic alerts run *every 15 minutes*"
    )
    
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to /ping command with 'Pong!'."""
    await update.message.reply_text("Pong!")

### --- PRICE FETCHING --- ###

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
    if price_usd > 1.2 * float(pair["priceChange"]["h1"]):  # Example: 20% increase in 1 hour
        alert_message = "📈 *Pump Alert!* 🚀\nRapid price increase detected!"

    # 🛒 Retail Arrival (Many small trades)
    elif pair["txns"]["h1"]["buys"] > 500 and volume_24h < 1000000:
        alert_message = "🛍 *Retail Arrival Detected!*\nMany small traders are buying in."

    # 💰 Market Maker Transfer (Large wallet outflow)
    elif liquidity > 2000000 and volume_24h > 5000000:
        alert_message = "🔄 *Market Maker Transfer!* 📊\nLarge liquidity shift detected."

    # 📉 Dump Detection (Massive sell-off)
    elif price_usd < 0.8 * float(pair["priceChange"]["h1"]):
        alert_message = "⚠️ *Dump Alert!* 💥\nHeavy selling detected!"

    # 😭 Retail Capitulation (Many small sells)
    elif pair["txns"]["h1"]["sells"] > 1000 and volume_24h < 500000:
        alert_message = "💀 *Retail Capitulation!* 🏳️\nRetail investors are selling in fear."

    # Send Alert to Telegram
    if alert_message:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")  # Set this to your chat/group ID
        bot = application.bot
        await bot.send_message(chat_id=chat_id, text=alert_message, parse_mode="MarkdownV2")

### --- Scheduled Task Setup --- ###

def setup_scheduler(application):
    """Setup a background scheduler to check meme coin status every 15 minutes."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(detect_meme_coin_stage, "interval", minutes=15, args=[application])
    scheduler.start()


### --- Price Task Setup --- ###


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch and display token price for the user's selected address."""
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)

    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    
    try:
        response = requests.get(url)
        data = response.json()

        if "pairs" not in data or len(data["pairs"]) == 0:
            await update.message.reply_text("⚠️ No trading data found for this token.")
            return

        pair = data["pairs"][0]
        price_usd = pair["priceUsd"]
        volume_24h = pair["volume"]["h24"]
        liquidity = pair["liquidity"]["usd"]
        market_cap = pair.get("marketCap", "N/A")
        dex_url = pair["url"]

        # Escape special characters for MarkdownV2
        def escape_md(text):
            special_chars = "_*[]()~`>#+-=|{}.!"
            return "".join(f"\\{char}" if char in special_chars else char for char in str(text))

        message = (
            f"💰 *Token Price \$begin:math:text$USD\\$end:math:text$*: \\${escape_md(price_usd)}\n"
            f"📊 *24h Volume*: \\${escape_md(f'{volume_24h:,}')}\n"
            f"💧 *Liquidity*: \\${escape_md(f'{liquidity:,}')}\n"
            f"🏦 *Market Cap \$begin:math:text$MC\\$end:math:text$*: \\${escape_md(f'{market_cap:,}')}\n"
            f"🔗 [View on DexScreener]({dex_url})"
        )

        await update.message.reply_text(message, parse_mode="MarkdownV2")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error fetching price data: {e}")

### --- CHANGE TOKEN ADDRESS --- ###

async def change_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow users to change the token address they want to track."""
    user_id = update.message.chat_id

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /change <TOKEN_ADDRESS>")
        return

    token_address = context.args[0]

    # Store the token address for the user
    user_addresses[user_id] = token_address
    await update.message.reply_text(f"✅ Token address updated! Now tracking: `{token_address}`", parse_mode="Markdown")

### --- BOT MAIN FUNCTION --- ###

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    #commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("change", change_command))  # NEW COMMAND

    # Start the scheduler for automatic alerts
    setup_scheduler(app)

    #Start the bot
    app.run_polling()

if __name__ == "__main__":
    main()
