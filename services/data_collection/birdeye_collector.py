import logging
from typing import List, Dict
from datetime import datetime

from birdeye_get_data import BirdeyeDataCollector
from .base_collector import BaseCollector

logger = logging.getLogger(__name__)

class BirdeyeCollector(BaseCollector):
    def __init__(self, db_pool):
        super().__init__(db_pool)
        self.birdeye = BirdeyeDataCollector(None)  # No need for sheets integration
        
    async def get_historical_data(self, token_address: str) -> List[Dict]:
        """Get historical price data for the token."""
        try:
            # Get weekly OHLCV data for the past year
            data = await self.birdeye.get_1y_weekly_ohlcv(token_address)
            
            if not data:
                logger.error("No historical data found")
                return []
            
            # Convert the data to our expected format
            historical_data = []
            for entry in data:
                historical_data.append({
                    "timestamp": entry["timestamp"],
                    "open": entry["open"],
                    "high": entry["high"],
                    "low": entry["low"],
                    "close": entry["close"],
                    "volume": entry["volume"]
                })
            
            logger.info(f"Retrieved {len(historical_data)} historical data points")
            return historical_data
                    
        except Exception as e:
            logger.error(f"Error in get_historical_data: {str(e)}", exc_info=True)
            return []
