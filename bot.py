import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ✅ Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DEFAULT_TOKEN_ADDRESS = "h5NciPdMZ5QCB5BYETJMYBMpVx9ZuitR6HcVjyBhood"

# ✅ Ensure token exists
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Set it in your environment variables.")

# ✅ User-tracked token addresses
user_addresses = {}

### --- MarkdownV2 Escaping Function --- ###
def escape_md(text):
    """Escape special characters for Telegram MarkdownV2 formatting."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{char}" if char in special_chars else char for char in str(text))

### --- CORE COMMANDS --- ###
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello from the bot!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = escape_md(
        "📌 *Available Commands:*\n"
        "/start - Greet the user\n"
        "/help - Show this help message\n"
        "/ping - Check if the bot is alive\n"
        "/price - Get token price\n"
        "/change <TOKEN_ADDRESS> - Change token address\n"
        "/alert - Check for alerts on demand"
    )
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

### --- PRICE FETCHING --- ###
async def fetch_token_data(token_address):
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
    user_id = update.message.chat_id
    token_address = user_addresses.get(user_id, DEFAULT_TOKEN_ADDRESS)
    pair = await fetch_token_data(token_address)

    if not pair:
        await update.message.reply_text("⚠️ No trading data found for this token.")
        return

    price_usd = float(pair["priceUsd"])
    volume_24h = float(pair["volume"]["h24"])
    liquidity = float(pair["liquidity"]["usd"])
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))

    alert_message = None
    if price_usd > 1.2 * price_change_1h:
        alert_message = "📈 *Pump Alert!* 🚀\nRapid price increase detected!"
    elif pair["txns"]["h1"]["buys"] > 500 and volume_24h < 1000000:
        alert_message = "🛍 *Retail Arrival Detected!*"
    elif liquidity > 2000000 and volume_24h > 5000000:
        alert_message = "🔄 *Market Maker Transfer!* 📊"
    elif price_usd < 0.8 * price_change_1h:
        alert_message = "⚠️ *Dump Alert!* 💥"
    elif pair["txns"]["h1"]["sells"] > 1000 and volume_24h < 500000:
        alert_message = "💀 *Retail Capitulation!* 🏳️"

    if alert_message:
        await update.message.reply_text(escape_md(alert_message), parse_mode="MarkdownV2")
    else:
        await update.message.reply_text("🔍 No significant alerts detected.")

### --- PRICE COMMAND --- ###
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    message = escape_md(
        f"💰 *Token Price (USD)*: ${price_usd}\n"
        f"📊 *24h Volume*: ${volume_24h:,}\n"
        f"💧 *Liquidity*: ${liquidity:,}\n"
        f"🏦 *Market Cap (MC)*: ${market_cap:,}\n"
        f"🔗 [View on DexScreener]({dex_url})"
    )

    await update.message.reply_text(message, parse_mode="MarkdownV2")

### --- CHANGE TOKEN ADDRESS --- ###
async def change_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow users to change the token address they want to track."""
    user_id = update.message.chat_id

    if not context.args or len(context.args[0]) < 10:  # Ensure valid input
        await update.message.reply_text("⚠️ Usage: /change <VALID_TOKEN_ADDRESS>")
        return

    token_address = context.args[0]
    user_addresses[user_id] = token_address
    await update.message.reply_text(f"✅ Token address updated! Now tracking: `{token_address}`", parse_mode="Markdown")

### --- BOT SETUP --- ###
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("ping", ping_command))
app.add_handler(CommandHandler("price", price_command))
app.add_handler(CommandHandler("change", change_command))
app.add_handler(CommandHandler("alert", alert_command))

async def main():
    """Start the bot."""
    print("⚡ Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())  # ✅ No event loop conflicts
