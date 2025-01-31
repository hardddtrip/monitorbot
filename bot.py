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

        # Escape MarkdownV2 special characters
        def escape_md(text):
            special_chars = "_*[]()~`>#+-=|{}.!\\"
            return "".join(f"\\{char}" if char in special_chars else char for char in str(text))

        message = (
            f"💰 *Token Price (USD)*: \\${escape_md(price_usd)}\n"
            f"📊 *24h Volume*: \\${escape_md(f'{volume_24h:,}')}\n"
            f"💧 *Liquidity*: \\${escape_md(f'{liquidity:,}')}\n"
            f"🏦 *Market Cap (MC)*: \\${escape_md(f'{market_cap:,}')}\n"
            f"🔗 [View on DexScreener]({escape_md(dex_url)})"
        )

        await update.message.reply_text(message, parse_mode="MarkdownV2")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error fetching price data: {escape_md(str(e))}", parse_mode="MarkdownV2")
