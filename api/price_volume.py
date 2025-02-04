from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
import asyncpg
import logging

from api.dependencies import get_db_pool
from services.data_collection.dexscreener_collector import DexScreenerCollector
from birdeye_get_data import BirdeyeDataCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/price-volume/{token_address}")
async def get_price_volume(
    token_address: str,
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):
    logger.info(f"Received request for token: {token_address}")
    try:
        collector = DexScreenerCollector(db_pool)
        # First update the current candlestick
        logger.info("Collecting current candlestick data")
        await collector.collect_and_store_candlestick(token_address)
        
        # Then get historical data
        logger.info("Fetching historical candlestick data")
        data = await collector.get_historical_candlesticks(token_address)
        logger.info(f"Retrieved {len(data)} candlesticks")
        return data
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise

@router.get("/price-volume/{token_address}/history")
async def get_historical_price_volume(
    token_address: str,
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):
    """Get historical price and volume data for a token."""
    try:
        collector = BirdeyeDataCollector(None)  # No need for sheets integration here
        # Get 1 year of weekly OHLCV data
        data = await collector.get_1y_weekly_ohlcv(token_address)
        if not data:
            raise HTTPException(status_code=404, detail="No historical data found")
        return data
    except Exception as e:
        logger.error(f"Error fetching historical data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
