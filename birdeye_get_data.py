"""
BirdEye Data Collection Module

This module provides a comprehensive interface to the BirdEye API for collecting and analyzing token data on Solana.
The BirdeyeDataCollector class contains the following key functions:

1. __init__(api_key: str, sheets: GoogleSheetsIntegration = None)
   - Initializes the data collector with API key and optional Google Sheets integration
   - Sets up base URL and headers for API requests

2. _make_request(endpoint: str, params: Dict = None)
   - Internal helper function to make API requests with retry logic
   - Handles server errors and JSON parsing
   - Implements exponential backoff for retries

3. get_current_price_and_volume(token_address: str)
   - Fetches current price and 24h volume data for a token
   - Returns dictionary with price and volume metrics

4. get_recent_trades(token_address: str, limit: int = 100)
   - Retrieves recent trade history for a token
   - Returns list of trades with timestamp, price, and volume

5. get_token_metadata(token_address: str)
   - Fetches basic token information like name, symbol, decimals
   - Returns dictionary of token metadata

6. get_token_data(token_address: str)
   - Comprehensive token data including price, volume, liquidity metrics
   - Returns detailed dictionary with market metrics and trading activity

7. get_top_traders(token_address: str, timeframe: str = "1h", limit: int = 10)
   - Analyzes top traders by volume for manipulation detection
   - Returns list of trader addresses and their trading volumes

8. get_historical_price_changes(token_address: str)
   - Calculates price changes over 1W, 2W, 1M, and 1Y periods
   - Uses OHLCV data for accurate price change calculation

9. get_ath_price_change(token_address: str)
   - Finds 1-Year High price and calculates change from current price
   - Filters out single highest spike to avoid anomalies

10. get_24h_hourly_ohlcv(token_address: str)
    - Retrieves hourly OHLCV data for the last 24 hours
    - Returns formatted list of hourly price and volume data

11. get_minute_ohlcv(token_address: str, minutes: int = 15)
    - Gets 1-minute OHLCV data for specified time period
    - Useful for short-term price movement analysis

12. get_price_changes(token_address: str)
    - Simplified interface for 1W, 1M, 3M, and 1Y price changes
    - Returns percentage changes in dictionary format

13. get_1y_weekly_ohlcv(token_address: str)
    - Get weekly OHLCV data for the past year
    - Returns list of weekly OHLCV data points

14. get_token_holders(token_address: str, limit: int = 100)
    - Get the top holders for a token
    - Returns list of holder information including address and balance
"""

import logging
from typing import Dict, List
import aiohttp
from datetime import datetime
import json
import asyncio
from sheets_integration import GoogleSheetsIntegration
import time

logger = logging.getLogger(__name__)

class BirdeyeDataCollector:
    """Class to collect and process data from Birdeye API"""
    
    def __init__(self, api_key: str, sheets: GoogleSheetsIntegration = None):
        """Initialize the data collector with API key and Google Sheets integration."""
        self.api_key = api_key
        self.sheets = sheets
        self.base_url = "https://public-api.birdeye.so/defi"
        self.headers = {
            "X-API-KEY": str(api_key),  # Ensure API key is a string
            "accept": "application/json",
            "x-chain": "solana"
        }

    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make a request to the Birdeye API with retry logic."""
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    logger.info(f"Making request to {url} with params {params} (attempt {attempt + 1}/3)")
                    async with session.get(url, headers=self.headers, params=params) as response:
                        if response.status == 521:
                            logger.warning(f"Birdeye API server is down (attempt {attempt + 1}/3)")
                            if attempt < 2:
                                await asyncio.sleep(5)
                                continue
                            return {}
                            
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Birdeye API error: {response.status} - {error_text}")
                            if attempt < 2:
                                await asyncio.sleep(5)
                                continue
                            return {}
                        
                        try:
                            response_text = await response.text()
                            logger.info(f"Raw response from {endpoint}: {response_text}")
                            data = json.loads(response_text)
                            logger.info(f"Parsed response from {endpoint}: {json.dumps(data, indent=2)}")
                            return data
                        except json.JSONDecodeError as e:
                            logger.error(f"Error decoding JSON response: {str(e)}", exc_info=True)
                            if attempt < 2:
                                await asyncio.sleep(5)
                                continue
                            return {}
            except Exception as e:
                logger.error(f"Error making request to {endpoint}: {str(e)}", exc_info=True)
                if attempt < 2:
                    await asyncio.sleep(5)
                    continue
                return {}
        
        return {}

    async def get_current_price_and_volume(self, token_address: str) -> Dict:
        """Get current price and volume data for a token"""
        url = f"{self.base_url}/price_volume/single"
        params = {
            "address": token_address,
            "type": "24h"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success", False):
                            return data.get("data", {})
                    return {}
        except Exception as e:
            logger.error(f"Error getting price and volume: {str(e)}")
            return {}

    async def get_recent_trades(self, token_address: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for a token"""
        url = f"{self.base_url}/v3/token/trade-data/single"
        params = {
            "address": token_address,
            "limit": limit
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success", False):
                            return data.get("data", {}).get("items", [])
                    return []
        except Exception as e:
            logger.error(f"Error getting recent trades: {str(e)}")
            return []

    async def get_token_metadata(self, token_address: str) -> Dict:
        """Get token metadata."""
        params = {
            "address": token_address
        }
        
        logger.info(f"Fetching token metadata from Birdeye for token {token_address}")
        data = await self._make_request("token_overview", params)
        return data.get("data", {})

    async def get_token_data(self, token_address: str) -> Dict:
        """Get comprehensive token data including price, volume, and liquidity metrics"""
        params = {"address": token_address}
        data = await self._make_request("token_overview", params)
        
        if not data or not data.get("success", False):
            logger.error(f"Failed to get token data for {token_address}")
            return {}
            
        token_info = data.get("data", {})
        if not token_info:
            logger.error(f"No token info found for {token_address}")
            return {}
            
        logger.info(f"Raw token info: {json.dumps(token_info, indent=2)}")
        
        # Helper function to safely get numeric values
        def safe_get(d: Dict, key: str, default: float = 0.0) -> float:
            value = d.get(key)
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        # Helper function to calculate percentage change
        def calc_percent_change(current: float, previous: float) -> float:
            if previous == 0:
                return 0.0
            return (current - previous) / previous * 100

        token_data = {
            # Basic Info
            "address": token_address,
            "name": str(token_info.get("name", "")),
            "symbol": str(token_info.get("symbol", "")),
            "decimals": int(safe_get(token_info, "decimals")),
            "supply": safe_get(token_info, "supply"),
            "circulatingSupply": safe_get(token_info, "circulatingSupply"),
            
            # Price Data
            "price": safe_get(token_info, "price"),
            "priceChange15mPercent": safe_get(token_info, "priceChange30mPercent") / 2,  # Estimate 15m
            "priceChange1h": safe_get(token_info, "priceChange1hPercent"),
            "priceChange24h": safe_get(token_info, "priceChange24hPercent"),
            "priceChange7dPercent": safe_get(token_info, "priceChange7dPercent", 0.0),
            
            # Market Metrics
            "marketCap": safe_get(token_info, "realMc"),
            "liquidity": safe_get(token_info, "liquidity"),
            "lastTradeTime": int(safe_get(token_info, "lastTradeUnixTime")),
            
            # Volume Data
            "volume24h": safe_get(token_info, "v24h"),
            "volume24hUSD": safe_get(token_info, "v24hUSD"),
            "volumeChange24h": calc_percent_change(
                safe_get(token_info, "v24h"),
                safe_get(token_info, "vHistory24h")
            ),
            
            # Trading Activity
            "trades24h": int(safe_get(token_info, "trade24h")),
            "buys24h": int(safe_get(token_info, "buy24h")),
            "sells24h": int(safe_get(token_info, "sell24h")),
            "buyVolume24h": safe_get(token_info, "vBuy24h"),
            "sellVolume24h": safe_get(token_info, "vSell24h"),
            
            # Wallet Activity
            "uniqueWallets24h": int(safe_get(token_info, "uniqueWallet24h")),
            "uniqueWalletsChange24h": safe_get(token_info, "uniqueWallet24hChangePercent"),
            "holders": int(safe_get(token_info, "holders", 0))
        }
        
        logger.info(f"Processed token data: {json.dumps(token_data, indent=2)}")
        return token_data

    async def get_top_traders(self, token_address: str, timeframe: str = "1h", limit: int = 10) -> Dict:
        """Get top traders data for manipulation analysis"""
        # Format token address to remove any prefix/suffix
        clean_address = token_address.strip().replace('0x', '')
        
        url = f"{self.base_url}/v2/tokens/top_traders"
        params = {
            "address": clean_address,
            "time_frame": timeframe,
            "sort_type": "desc",
            "sort_by": "volume",
            "offset": 0,
            "limit": limit
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success", False):
                            return data.get("data", {}).get("items", [])
                    
                    logger.error(f"Error fetching top traders: {response.status} - {await response.text()}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error in get_top_traders: {str(e)}")
            return []

    async def get_historical_price_changes(self, token_address: str) -> Dict[str, float]:
        """Get historical price changes for 1W, 2W, 1M, and 1Y using OHLCV data.
        
        Args:
            token_address: The token address to get price changes for
            
        Returns:
            Dictionary containing price changes for different timeframes
        """
        # Calculate timestamps
        now = int(datetime.now().timestamp())
        one_week = 7 * 24 * 60 * 60
        two_weeks = 2 * one_week
        one_month = 30 * 24 * 60 * 60
        one_year = 365 * 24 * 60 * 60
        
        timeframes = {
            "1W": (now - one_week, now, "1H"),
            "2W": (now - two_weeks, now, "4H"),
            "1M": (now - one_month, now, "1D"),
            "1Y": (now - one_year, now, "1W")
        }
        
        results = {}
        
        for period, (time_from, time_to, interval_type) in timeframes.items():
            try:
                url = f"{self.base_url}/ohlcv"
                params = {
                    "address": token_address,
                    "type": interval_type,
                    "time_from": time_from,
                    "time_to": time_to
                }
                
                data = await self._make_request("ohlcv", params)
                if data and "data" in data and "items" in data["data"] and len(data["data"]["items"]) > 1:
                    items = data["data"]["items"]
                    first_price = items[0]["o"]  # Opening price of first candle
                    last_price = items[-1]["c"]  # Closing price of last candle
                    
                    if first_price > 0:  # Avoid division by zero
                        price_change = ((last_price - first_price) / first_price) * 100
                        results[period] = round(price_change, 2)
                    else:
                        results[period] = 0
                    
            except Exception as e:
                logger.error(f"Error getting {period} price change: {str(e)}")
                results[period] = 0
        
        return results

    async def get_ath_price_change(self, token_address: str) -> Dict[str, float]:
        """Get 1-Year High price and calculate change from current price.
        Ignores the single highest spike to filter out potential anomalies.
        
        Args:
            token_address: The token address to analyze
            
        Returns:
            Dictionary containing 1Y high price, current price, and percentage change
        """
        try:
            # Get current price from token overview
            current_data = await self.get_token_data(token_address)
            current_price = current_data.get('price', 0) if current_data else 0
            
            # Use 1-year timeframe with 1D candles to find ATH
            now = int(datetime.now().timestamp())
            one_year_ago = now - (365 * 24 * 60 * 60)
            
            params = {
                "address": token_address,
                "type": "1D",  # Daily candles
                "time_from": one_year_ago,
                "time_to": now
            }
            
            data = await self._make_request("ohlcv", params)
            if data and "data" in data and "items" in data["data"] and len(data["data"]["items"]) > 0:
                items = data["data"]["items"]
                
                # Sort by high price, descending
                sorted_items = sorted(items, key=lambda x: float(x["h"]), reverse=True)
                
                # Skip the highest spike and use the second highest as ATH
                if len(sorted_items) > 1:
                    ath_item = sorted_items[1]  # Use second highest
                    ath_price = float(ath_item["h"])
                    ath_date = datetime.fromtimestamp(int(ath_item["unixTime"])).strftime("%Y-%m-%d")
                    
                    if ath_price > 0 and current_price > 0:
                        change_from_ath = ((current_price - ath_price) / ath_price) * 100
                        return {
                            "ath_price": ath_price,
                            "current_price": current_price,
                            "change_from_ath": round(change_from_ath, 2),
                            "ath_date": ath_date
                        }
            
            return {
                "ath_price": 0,
                "current_price": current_price,
                "change_from_ath": 0,
                "ath_date": None
            }
            
        except Exception as e:
            logger.error(f"Error getting ATH price change: {str(e)}")
            return {
                "ath_price": 0,
                "current_price": 0,
                "change_from_ath": 0,
                "ath_date": None
            }

    async def get_24h_hourly_ohlcv(self, token_address: str) -> List[Dict]:
        """Get hourly OHLCV data for the last 24 hours.
        
        Args:
            token_address: The token address to analyze
            
        Returns:
            List of hourly OHLCV data points, each containing timestamp, o, h, l, c, v
        """
        try:
            now = int(datetime.now().timestamp())
            one_day_ago = now - (24 * 60 * 60)
            
            params = {
                "address": token_address,
                "type": "1H",  # 1-hour candles
                "time_from": one_day_ago,
                "time_to": now
            }
            
            data = await self._make_request("ohlcv", params)
            if data and "data" in data and "items" in data["data"]:
                items = data["data"]["items"]
                
                # Format the data for Claude
                formatted_items = []
                for item in sorted(items, key=lambda x: int(x["unixTime"])):
                    formatted_items.append({
                        "timestamp": datetime.fromtimestamp(int(item["unixTime"])).strftime("%Y-%m-%d %H:%M"),
                        "open": float(item["o"]),
                        "high": float(item["h"]),
                        "low": float(item["l"]),
                        "close": float(item["c"]),
                        "volume": float(item["v"])
                    })
                
                return formatted_items
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting 24h hourly OHLCV: {str(e)}")
            return []

    async def get_minute_ohlcv(self, token_address: str, minutes: int = 15) -> List[Dict]:
        """Get 1-minute OHLCV data for the specified number of minutes."""
        try:
            # Calculate timestamps
            end_time = int(time.time())
            start_time = end_time - (minutes * 60)  # Convert minutes to seconds
            
            params = {
                "address": token_address,
                "type": "1m",  # 1-minute intervals
                "time_from": start_time,
                "time_to": end_time
            }
            
            data = await self._make_request("ohlcv", params)
            if data and "data" in data and "items" in data["data"]:
                items = data["data"]["items"]
                
                # Format the data
                ohlcv_data = []
                for item in sorted(items, key=lambda x: int(x["unixTime"])):
                    ohlcv_data.append({
                        "timestamp": datetime.fromtimestamp(int(item["unixTime"])).strftime("%Y-%m-%d %H:%M"),
                        "open": float(item["o"]),
                        "high": float(item["h"]),
                        "low": float(item["l"]),
                        "close": float(item["c"]),
                        "volume": float(item["v"])
                    })
                return ohlcv_data
                
            logger.error(f"Error getting minute OHLCV data: {data}")
            return []
                    
        except Exception as e:
            logger.error(f"Error getting minute OHLCV data: {str(e)}")
            return []

    async def get_price_changes(self, token_address: str) -> Dict:
        """Get price changes for different time periods using weekly OHLCV data.
        
        !!! CRITICAL FUNCTION - DO NOT MODIFY WITHOUT CAREFUL CONSIDERATION !!!
        This function has been carefully implemented and tested to provide accurate
        price change calculations across multiple timeframes. Any modifications could
        impact monitoring systems and analysis tools.
        
        Args:
            token_address: The token address to analyze
            
        Returns:
            Dictionary containing price changes for:
            - 1W: One week price change %
            - 1M: One month price change % (4 weeks)
            - 3M: Three month price change % (13 weeks)
            - 1Y: One year price change %
            - 1Y_high_to_current: % change from 1 year high to current price
        """
        try:
            # Get weekly OHLCV data for the past year
            weekly_data = await self.get_1y_weekly_ohlcv(token_address)
            
            if not weekly_data:
                logger.error("No weekly data available for price change calculation")
                return {
                    "1W": 0.0,
                    "1M": 0.0,
                    "3M": 0.0,
                    "1Y": 0.0,
                    "1Y_high_to_current": 0.0
                }
            
            # Sort data by timestamp to ensure correct order
            weekly_data.sort(key=lambda x: x["timestamp"])
            
            # Get current price (latest close)
            current_price = weekly_data[-1]["close"]
            
            # Calculate price changes
            result = {}
            
            # 1W change - compare current price with previous week's close
            if len(weekly_data) >= 2:
                prev_week_price = weekly_data[-2]["close"]
                result["1W"] = ((current_price - prev_week_price) / prev_week_price) * 100
            else:
                result["1W"] = 0.0
            
            # 1M change - compare current price with price 4 weeks ago
            if len(weekly_data) >= 5:
                month_ago_price = weekly_data[-5]["close"]
                result["1M"] = ((current_price - month_ago_price) / month_ago_price) * 100
            else:
                result["1M"] = 0.0

            # 3M change - compare current price with price 13 weeks ago
            if len(weekly_data) >= 14:
                three_month_ago_price = weekly_data[-14]["close"]
                result["3M"] = ((current_price - three_month_ago_price) / three_month_ago_price) * 100
            else:
                result["3M"] = 0.0
            
            # 1Y change - compare current price with oldest available price
            if len(weekly_data) >= 2:
                year_ago_price = weekly_data[0]["close"]
                result["1Y"] = ((current_price - year_ago_price) / year_ago_price) * 100
            else:
                result["1Y"] = 0.0
            
            # Calculate 1Y high and % change from high
            if weekly_data:
                # Get all closing prices and high prices
                highs = [week["high"] for week in weekly_data]
                year_high = max(highs)
                result["1Y_high_to_current"] = ((current_price - year_high) / year_high) * 100
            else:
                result["1Y_high_to_current"] = 0.0
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating price changes: {str(e)}")
            return {
                "1W": 0.0,
                "1M": 0.0,
                "3M": 0.0,
                "1Y": 0.0,
                "1Y_high_to_current": 0.0
            }

    async def get_1y_weekly_ohlcv(self, token_address: str) -> List[Dict]:
        """Get weekly OHLCV data for the past year.
        
        !!! CRITICAL FUNCTION - DO NOT MODIFY WITHOUT CAREFUL CONSIDERATION !!!
        This function is essential for historical price analysis and provides
        the foundation for price change calculations. It has been carefully
        implemented to ensure accurate data retrieval and formatting.
        
        Args:
            token_address: The token address to get OHLCV data for
            
        Returns:
            List of dictionaries containing weekly OHLCV data with fields:
            - timestamp: YYYY-MM-DD format
            - open: Opening price
            - high: Highest price
            - low: Lowest price
            - close: Closing price
            - volume: Trading volume
        """
        try:
            # Calculate timestamps for 1 year ago
            now = int(datetime.now().timestamp())
            one_year_ago = now - (365 * 24 * 60 * 60)
            
            params = {
                "address": token_address,
                "type": "1W",  # Weekly candles
                "time_from": one_year_ago,
                "time_to": now
            }
            
            data = await self._make_request("ohlcv", params)
            if data and "data" in data and "items" in data["data"]:
                items = data["data"]["items"]
                
                # Format the data
                weekly_data = []
                for item in sorted(items, key=lambda x: int(x["unixTime"])):
                    weekly_data.append({
                        "timestamp": datetime.fromtimestamp(int(item["unixTime"])).strftime("%Y-%m-%d"),
                        "open": float(item["o"]),
                        "high": float(item["h"]),
                        "low": float(item["l"]),
                        "close": float(item["c"]),
                        "volume": float(item["v"])
                    })
                
                return weekly_data
            
            logger.error(f"Error getting weekly OHLCV data: {data}")
            return []
                    
        except Exception as e:
            logger.error(f"Error getting weekly OHLCV data: {str(e)}")
            return []

    async def get_token_holders(self, token_address: str, limit: int = 10) -> List[Dict]:
        """Get the top holders for a token.
        
        Args:
            token_address: The token address to get holders for
            limit: Maximum number of holders to return (default: 10)
            
        Returns:
            List of dictionaries containing holder information:
            - owner: Wallet address of the holder
            - amount: Token balance in UI units (adjusted for decimals)
            - percentage: Percentage of total supply held
            
        Note:
            The Birdeye API response is expected to contain a list of holders under the 'data.items' field,
            where each holder has 'owner' (wallet address) and 'ui_amount' (token balance) fields.
        """
        endpoint = "v3/token/holder"
        params = {
            "address": token_address,
            "limit": limit,
            "offset": 0
        }

        try:
            response = await self._make_request(endpoint, params)
            if not response or not response.get("success"):
                logging.error(f"Failed to get token holders: {response}")
                return []

            holders_data = response.get("data", {}).get("items", [])
            if not holders_data:
                logging.warning("No holders data found in response")
                return []

            # Calculate total supply for percentage calculation
            total_supply = sum(float(holder.get("ui_amount", 0)) for holder in holders_data)
            if total_supply == 0:
                logging.warning("Total supply is 0, cannot calculate percentages")
                return []

            holders = []
            for holder in holders_data:
                try:
                    # Validate required fields exist
                    if "owner" not in holder:
                        logging.warning(f"Skipping holder, missing owner field: {holder}")
                        continue
                    if "ui_amount" not in holder:
                        logging.warning(f"Skipping holder, missing ui_amount field: {holder}")
                        continue

                    # Validate and convert amount
                    try:
                        amount = float(holder["ui_amount"])
                        percentage = (amount / total_supply) * 100 if total_supply > 0 else 0
                    except (ValueError, TypeError):
                        logging.warning(f"Invalid amount format for holder {holder['owner']}: {holder['ui_amount']}")
                        continue

                    holders.append({
                        "owner": holder["owner"],
                        "amount": amount,
                        "percentage": percentage
                    })
                except Exception as e:
                    logging.warning(f"Error processing holder data: {e}, holder: {holder}")
                    continue

            return holders

        except Exception as e:
            logging.error(f"Error getting token holders: {e}")
            return []

async def main():
    """Main function to test the BirdeyeDataCollector class."""
    # Initialize Google Sheets integration
    sheets = GoogleSheetsIntegration(
        credentials_file='credentials.json',  # You'll need to get this from Google Cloud Console
        token_file='token.json',
        spreadsheet_id='YOUR_SPREADSHEET_ID'  # You'll need to create a sheet and get its ID
    )
    sheets.authenticate()
    
    # Initialize collector with API key and sheets integration
    collector = BirdeyeDataCollector("YOUR_API_KEY", sheets)
    
    # Test with USDC token
    token_address = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    print("\nTesting Birdeye API...")
    print(f"API Key: YOUR_API_KEY")
    print(f"Token Address: {token_address}\n")
    
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
    trades = await collector.get_recent_trades(token_address)
    print(f"Recent trades: {trades}")

if __name__ == "__main__":
    asyncio.run(main())
