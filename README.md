# MonitorBot - Solana Meme Coin Research Hub

A comprehensive monitoring and analysis system for Solana tokens, featuring a Telegram bot for real-time alerts, transaction analysis, and a web-based metrics dashboard. The system is designed to auto-deploy to Heroku and provides deep insights into token activities.

## System Architecture

### Components

1. **Telegram Bot (`bot.py`)**
   - Real-time token monitoring and alerts
   - Price tracking and market data analysis
   - Transaction monitoring and pattern detection
   - User subscription management
   - Command interface for token analysis

2. **Transaction Analyzer (`transaction_analyzer.py`)**
   - Helius API integration for Solana transaction data
   - Advanced transaction pattern detection
   - Caching system for optimized performance
   - Metrics calculation and analysis
   - Real-time transaction monitoring

3. **Web Dashboard (`metrics.html`)**
   - Interactive token metrics visualization
   - Real-time price and volume charts
   - Transaction activity monitoring
   - Key metrics display (Market Cap, Volume, Holders)
   - Responsive design with modern UI

### Data Flow

1. **Data Collection**
   - Helius API: Real-time transaction data
   - DexScreener API: Price and market data
   - On-chain data: Token holder information

2. **Data Processing**
   - Transaction pattern analysis
   - Market metrics calculation
   - Risk assessment
   - Alert generation

3. **Data Distribution**
   - Telegram alerts
   - Web dashboard updates
   - Subscription-based notifications

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
- `/transactions` - Analyze recent transaction patterns

### Utility Commands
- `/start` - Start the bot
- `/help` - Show command help
- `/ping` - Check bot status
- `/change` - Change monitored token address

## Token Audit Bot

A Python-based tool for automated token auditing and analysis. The bot performs comprehensive token analysis using Birdeye API data and Claude AI, and posts results to Google Sheets.

### Features

- Real-time token data collection via Birdeye API
- Multi-timeframe analysis (short-term, mid-term, long-term)
- Risk assessment and scoring
- Automated Google Sheets reporting
- AI-powered market analysis using Claude API

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/monitorbot.git
cd monitorbot
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the example environment file and configure your settings:
```bash
cp .env.example .env
```

### Configuration

1. Set up your environment variables in `.env`:
   - `CLAUDE_API_KEY`: Your Claude API key
   - `BIRDEYE_API_KEY`: Your Birdeye API key
   - `GOOGLE_SHEETS_CREDENTIALS_FILE`: Path to your Google Sheets service account JSON file
   - `GOOGLE_SHEETS_SPREADSHEET_ID`: ID of your Google Sheets document

2. Set up Google Sheets:
   - Create a Google Cloud project
   - Enable the Google Sheets API
   - Create a service account and download the credentials JSON file
   - Share your Google Sheet with the service account email

### Usage

1. Run a single token audit:
```bash
python audit.py
```

2. Run the audit scheduler:
```bash
python audit_scheduler.py
```

### Output Format

The audit results are posted to Google Sheets with the following information:
- Timestamp
- Token symbol and contract address
- Market cap
- Short-term momentum analysis (score, comment, conviction, support/resistance levels)
- Mid-term momentum analysis
- Long-term outlook
- Risk assessment
- Overall rating

## Setup

### Prerequisites
- Python 3.8+
- Helius API key
- Telegram Bot Token
- Heroku account

### Deployment

1. **Environment Variables**
   ```bash
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   HELIUS_API_KEY=your_helius_api_key
   ```

2. **Heroku Deployment**
   ```bash
   git push heroku main
   ```
   The system will automatically deploy and start monitoring.

### Local Development

1. **Clone Repository**
   ```bash
   git clone https://github.com/hardddtrip/monitorbot.git
   cd monitorbot
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Create `.env` file with required variables.

4. **Run Components**
   ```bash
   # Start Telegram bot
   python bot.py
   
   # Access web dashboard
   open metrics.html
   ```

## Technical Details

### Transaction Analyzer
- Efficient caching system with TTL
- Asynchronous transaction processing
- Pattern detection algorithms
- Real-time market impact analysis

### Web Dashboard
- Built with Plot.ly for interactive charts
- Real-time data updates (30-second intervals)
- Responsive grid layout
- Modern UI/UX design

### Bot Features
- Asynchronous command handling
- Rate limiting protection
- Error handling and logging
- Automatic retry mechanisms

## Dependencies
- python-telegram-bot>=20.0
- aiohttp
- requests
- python-dotenv
- plotly
- See `requirements.txt` for full list

## Contributing
Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## License
MIT License
