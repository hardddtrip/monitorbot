import asyncio
import logging
import os
from datetime import datetime
from birdeye_get_data import BirdeyeDataCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SqliteDatabase:
    def __init__(self, db_path=":memory:"):
        self.db_path = db_path
        self._conn = None

    async def connect(self):
        """Create a connection"""
        if not self._conn:
            self._conn = await aiosqlite.connect(self.db_path)
            await self._create_tables()
        return self._conn

    async def _create_tables(self):
        """Create necessary tables"""
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT NOT NULL UNIQUE,
                block_time TIMESTAMP NOT NULL,
                fetch_time TIMESTAMP NOT NULL,
                side TEXT NOT NULL,
                source TEXT NOT NULL,
                from_amount REAL NOT NULL,
                from_symbol TEXT NOT NULL,
                to_amount REAL NOT NULL,
                to_symbol TEXT NOT NULL,
                price REAL
            )
        ''')
        await self._conn.commit()

    async def store_trades(self, trades: list, fetch_time: datetime):
        """Store trades in the database"""
        if not trades:
            return

        # Prepare the values for bulk insert
        values = []
        for trade in trades:
            values.append((
                trade['txHash'],
                datetime.fromtimestamp(trade['blockUnixTime']),
                fetch_time,
                trade['side'],
                trade['source'],
                trade['from_amount'],
                trade['from_symbol'],
                trade['to_amount'],
                trade['to_symbol'],
                trade['price']
            ))

        try:
            await self._conn.executemany('''
                INSERT OR IGNORE INTO trades (
                    tx_hash, block_time, fetch_time, side, source,
                    from_amount, from_symbol, to_amount, to_symbol, price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', values)
            await self._conn.commit()
            logger.info(f"Stored {len(values)} trades in database")
        except Exception as e:
            logger.error(f"Error storing trades: {e}")
            raise

async def main():
    """Main function to test the BirdeyeDataCollector class."""
    # Initialize collector with API key from environment
    collector = BirdeyeDataCollector(os.getenv('BIRDEYE_API_KEY'))
    
    # Test with BONK token
    token_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    
    print("\nTesting Birdeye API...")
    print(f"Token Address: {token_address}\n")
    
    try:
        # 1. Test get_current_price_and_volume
        print("1. Getting current price and volume...")
        price_volume = await collector.get_current_price_and_volume(token_address)
        print(f"Price/Volume data: {price_volume}\n")
        
        # 2. Test get_token_metadata
        print("2. Getting token metadata...")
        metadata = await collector.get_token_metadata(token_address)
        print(f"Token metadata: {metadata}\n")
        
        # 3. Test get_recent_trades
        print("3. Getting recent trades...")
        trades = await collector.get_recent_trades(token_address, limit=5)
        print(f"Recent trades (5): {trades}\n")
        
        # 4. Test get_token_data
        print("4. Getting comprehensive token data...")
        token_data = await collector.get_token_data(token_address)
        print(f"Token data: {token_data}\n")
        
        # 5. Test get_top_traders
        print("5. Getting top traders...")
        top_traders = await collector.get_top_traders(token_address, timeframe="1h", limit=5)
        print(f"Top traders: {top_traders}\n")
        
        # 6. Test get_historical_price_changes
        print("6. Getting historical price changes...")
        price_changes = await collector.get_historical_price_changes(token_address)
        print(f"Historical price changes: {price_changes}\n")
        
        # 7. Test get_ath_price_change
        print("7. Getting ATH price change...")
        ath_data = await collector.get_ath_price_change(token_address)
        print(f"ATH data: {ath_data}\n")
        
        # 8. Test get_24h_hourly_ohlcv
        print("8. Getting 24h hourly OHLCV...")
        hourly_data = await collector.get_24h_hourly_ohlcv(token_address)
        print(f"24h hourly data (first 2 entries): {hourly_data[:2]}\n")
        
        # 9. Test get_minute_ohlcv
        print("9. Getting minute OHLCV...")
        minute_data = await collector.get_minute_ohlcv(token_address, minutes=5)
        print(f"5-minute data (first 2 entries): {minute_data[:2]}\n")
        
        # 10. Test get_price_changes
        print("10. Getting price changes...")
        changes = await collector.get_price_changes(token_address)
        print(f"Price changes: {changes}\n")
        
        # 11. Test get_1y_weekly_ohlcv
        print("11. Getting 1Y weekly OHLCV data...")
        weekly_data = await collector.get_1y_weekly_ohlcv(token_address)
        print(f"Weekly data (first 2 entries): {weekly_data[:2] if weekly_data else []}\n")
        print(f"Total weeks of data: {len(weekly_data)}")
        
    except Exception as e:
        print(f"Error during testing: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
