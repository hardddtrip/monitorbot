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
    )
    
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to /ping command with 'Pong!'."""
    await update.message.reply_text("Pong!")

### --- PRICE FETCHING --- ###


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

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("change", change_command))  # NEW COMMAND

    app.run_polling()

if __name__ == "__main__":
    main()
