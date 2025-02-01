# MonitorBot - Solana Token Monitoring Bot

A Telegram bot for monitoring Solana tokens, providing real-time alerts, price tracking, and comprehensive token audits.

## Features

### Token Monitoring
- `/alert` - Get instant token price and transaction alerts
- `/price` - Check current token price and market data
- `/subscribe` - Subscribe to automatic price alerts
- `/unsubscribe` - Unsubscribe from automatic alerts

### Token Analysis
- `/audit` - Comprehensive token health analysis including:
  - Health score (0-100)
  - Price metrics and changes
  - Market metrics (MCap, FDV, Volume)
  - Liquidity analysis
  - Trading activity
  - Risk factor assessment

### Token Information
- `/holders` - View top token holders
- `/trades` - Monitor recent large trades
- `/liquidity` - Track liquidity changes
- `/metadata` - View token metadata

### Utility Commands
- `/start` - Start the bot
- `/help` - Show command help
- `/ping` - Check bot status
- `/change` - Change monitored token address

## Setup

1. Set up environment variables in Heroku:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from BotFather
   - `HELIUS_API_KEY`: Your Helius API key for Solana data

2. Deploy to Heroku:
   ```bash
   git push heroku main
   ```

## Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/hardddtrip/monitorbot.git
   cd monitorbot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with required environment variables:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   HELIUS_API_KEY=your_helius_api_key
   ```

4. Run the bot:
   ```bash
   python bot.py
   ```

## Testing

Run the test suite:
```bash
python test_audit.py
```

## Dependencies
- python-telegram-bot
- requests
- python-dotenv
- See requirements.txt for full list

## License
MIT License
