import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import asyncio
import json
import aiohttp
from dotenv import load_dotenv
from birdeye_get_data import BirdeyeDataCollector
from sheets_integration import GoogleSheetsIntegration
import time

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class TokenAuditor:
    def __init__(self, birdeye: BirdeyeDataCollector, sheets: GoogleSheetsIntegration = None):
        self.birdeye = birdeye
        self.sheets = sheets
        self.audit_sheet_name = "TokenAudits"  # Update to match sheets_integration.py

    async def analyze_metrics(self, token_data: Dict, ohlcv_15m: List[Dict], ohlcv_1h: List[Dict]) -> Dict:
        """Analyze token metrics locally without using Claude API"""
        try:
            # Calculate key metrics
            current_price = token_data.get('price', 0)
            price_change_24h = token_data.get('priceChange24h', 0)
            volume_24h = token_data.get('volume24hUSD', 0)
            volume_change_24h = token_data.get('volumeChange24h', 0)
            market_cap = token_data.get('marketCap', 0)
            
            # Calculate support and resistance from OHLCV data
            prices_1h = [float(candle['low']) for candle in ohlcv_1h] + [float(candle['high']) for candle in ohlcv_1h]
            prices_1h.sort()
            
            support_level = prices_1h[len(prices_1h)//4]  # 25th percentile
            resistance_level = prices_1h[3*len(prices_1h)//4]  # 75th percentile
            
            # Short-term analysis (15m - 1h)
            st_score = 3  # Neutral base score
            if price_change_24h > 5:  # Strong upward momentum
                st_score += 1
            if price_change_24h < -5:  # Strong downward momentum
                st_score -= 1
            if volume_change_24h > 20:  # High volume increase
                st_score += 1
            if volume_change_24h < -20:  # High volume decrease
                st_score -= 1
                
            # Mid-term analysis (1d - 1w)
            mt_score = 3
            if price_change_24h > 10:
                mt_score += 1
            if price_change_24h < -10:
                mt_score -= 1
            if volume_24h > 5000000:  # High liquidity
                mt_score += 1
                
            # Long-term analysis
            lt_score = 3
            if market_cap > 1000000000:  # $1B+ market cap
                lt_score += 1
            if volume_24h > 10000000:  # Very high liquidity
                lt_score += 1
                
            # Risk analysis
            risk_score = 3
            if market_cap < 100000000:  # Small cap
                risk_score -= 1
            if volume_24h < 1000000:  # Low liquidity
                risk_score -= 1
            if volume_24h > 5000000:  # High liquidity
                risk_score += 1
                
            # Overall rating
            overall = (st_score + mt_score + lt_score + risk_score) / 4
            
            return {
                "short_term": {
                    "rating": min(max(st_score, 1), 5),
                    "comment": f"{price_change_24h:+.1f}% 24h change, {volume_change_24h:+.1f}% vol change",
                    "conviction": min(abs(price_change_24h) * 5, 100),
                    "support_level": support_level,
                    "resistance_level": resistance_level
                },
                "mid_term": {
                    "rating": min(max(mt_score, 1), 5),
                    "comment": f"${volume_24h/1000000:.1f}M 24h volume, ${market_cap/1000000:.1f}M mcap",
                    "conviction": min(70 + abs(price_change_24h), 100),
                    "support_level": support_level * 0.9,
                    "resistance_level": resistance_level * 1.1
                },
                "long_term": {
                    "rating": min(max(lt_score, 1), 5),
                    "comment": f"Market cap ${market_cap/1000000:.1f}M with ${volume_24h/1000000:.1f}M daily volume",
                    "conviction": min(60 + market_cap/100000000, 100)
                },
                "risks": {
                    "rating": min(max(risk_score, 1), 5),
                    "comment": f"{'High' if volume_24h > 5000000 else 'Medium' if volume_24h > 1000000 else 'Low'} liquidity, {'Large' if market_cap > 1000000000 else 'Mid' if market_cap > 100000000 else 'Small'} cap",
                    "conviction": min(50 + volume_24h/1000000, 100)
                },
                "overall_rating": min(max(round(overall), 1), 5)
            }
            
        except Exception as e:
            logger.error(f"Error in local analysis: {str(e)}")
            return {
                "short_term": {"rating": 0, "comment": "Error in analysis", "conviction": 0, "support_level": 0, "resistance_level": 0},
                "mid_term": {"rating": 0, "comment": "Error in analysis", "conviction": 0, "support_level": 0, "resistance_level": 0},
                "long_term": {"rating": 0, "comment": "Error in analysis", "conviction": 0},
                "risks": {"rating": 0, "comment": "Error in analysis", "conviction": 0},
                "overall_rating": 0
            }

    async def get_claude_insight(self, prompt: str) -> Dict:
        """Get market insight from Claude API"""
        logger.info("Calling Claude API...")
        
        # Get API key from environment
        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            logger.error("CLAUDE_API_KEY environment variable not set")
            return None
        logger.info("API Key configured: Yes")
        logger.info(f"Prompt: {prompt}")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
                
                data = {
                    "model": "claude-3-opus-20240229",
                    "max_tokens": 1000,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
                
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status != 200:
                        logging.error(f"Claude API error: {response.status} - {await response.text()}")
                        return None
                    
                    response_data = await response.json()
                    logging.info(f"Claude API response: {response_data}")
                    
                    if "content" in response_data and len(response_data["content"]) > 0:
                        try:
                            # Extract text content and find the JSON object within it
                            content = response_data["content"][0]["text"]
                            # Find JSON object between curly braces
                            start = content.find('{')
                            end = content.rfind('}') + 1
                            if start >= 0 and end > start:
                                json_str = content[start:end]
                                return json.loads(json_str)
                            else:
                                logging.error("No JSON object found in Claude response")
                                return None
                        except (KeyError, json.JSONDecodeError) as e:
                            logging.error(f"Error parsing Claude response: {e}")
                            return None
                    else:
                        logging.error("Unexpected Claude API response format")
                        return None
                    
        except Exception as e:
            logger.error(f"Error getting Claude insight: {str(e)}")
            return {"error": str(e)}

    async def audit_token(self, token_address: str) -> Dict:
        """Run a comprehensive token audit."""
        logger.info("Starting token audit...")
        
        # Get token data and recent trades
        token_data = await self.birdeye.get_token_data(token_address)
        recent_trades = await self.birdeye.get_recent_trades(token_address)
        top_traders = await self.birdeye.get_top_traders(token_address)
        
        # Get OHLCV data
        now = int(time.time())
        ohlcv_5m = await self.birdeye.get_ohlcv(token_address, "5m", now - 3600, now)  # Last hour in 5m intervals
        ohlcv_1h = await self.birdeye.get_ohlcv(token_address, "1H", now - 604800, now)  # Last week in 1h intervals
        
        # Prepare data for Claude analysis
        prompt = f"""
        Analyze this token's market metrics and provide a detailed assessment:

        Token Data:
        - Name: {token_data.get('name')}
        - Symbol: {token_data.get('symbol')}
        - Price: ${token_data.get('price')}
        - Market Cap: ${token_data.get('marketCap')}
        - 24h Volume: ${token_data.get('volume24hUSD')}
        - 24h Price Change: {token_data.get('priceChange24h')}%
        - 24h Volume Change: {token_data.get('volumeChange24h')}%
        - Holders: {token_data.get('holders')}

        Recent Trading Activity:
        - 24h Trades: {token_data.get('trades24h')}
        - Buy/Sell Ratio: {token_data.get('buys24h')}/{token_data.get('sells24h')}
        - Unique Wallets 24h: {token_data.get('uniqueWallets24h')}

        Short-term Price Levels (5m Data for Last Hour):
        {json.dumps(ohlcv_5m, indent=2)}

        Mid-term Price Levels (1H Data for Last Week):
        {json.dumps(ohlcv_1h, indent=2)}

        Provide a detailed analysis with the following structure:
        1. Short-term momentum (rating 1-5, comment, conviction 0-1, support price, resistance price)
        2. Mid-term momentum (rating 1-5, comment, conviction 0-1, support price, resistance price)
        3. Long-term outlook (rating 1-5, comment, conviction 0-1)
        4. Risks (rating 1-5, comment, conviction 0-1)
        5. Overall rating (1-5)

        Format the response as a JSON object with these exact keys:
        {{
            "short_term": {{ "rating": "number 1-5", "comment": "string", "conviction": "number 0-1", "support_level": "number", "resistance_level": "number" }},
            "mid_term": {{ "rating": "number 1-5", "comment": "string", "conviction": "number 0-1", "support_level": "number", "resistance_level": "number" }},
            "long_term": {{ "rating": "number 1-5", "comment": "string", "conviction": "number 0-1" }},
            "risks": {{ "rating": "number 1-5", "comment": "string", "conviction": "number 0-1" }},
            "overall_rating": "number 1-5"
        }}
        """
        
        # Get analysis from Claude
        analysis_response = await self.get_claude_insight(prompt)
        if analysis_response is None:
            logger.error(f"Error getting Claude analysis")
            # Fallback to local analysis if Claude fails
            analysis = await self.analyze_metrics(token_data, ohlcv_5m, ohlcv_1h)
        else:
            try:
                # Parse Claude's response
                analysis = analysis_response
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error parsing Claude response: {str(e)}")
                # Fallback to local analysis
                analysis = await self.analyze_metrics(token_data, ohlcv_5m, ohlcv_1h)
        
        # Format audit results
        audit_results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "token": token_data.get("symbol", ""),
            "contract": token_address,
            "name": token_data.get("name", ""),
            "market_cap": token_data.get("marketCap", 0),
            "st_momentum": {
                "score": analysis["short_term"]["rating"],
                "comment": analysis["short_term"]["comment"],
                "conviction": analysis["short_term"]["conviction"],
                "support": analysis["short_term"]["support_level"],
                "resistance": analysis["short_term"]["resistance_level"]
            },
            "mt_momentum": {
                "score": analysis["mid_term"]["rating"],
                "comment": analysis["mid_term"]["comment"],
                "conviction": analysis["mid_term"]["conviction"],
                "support": analysis["mid_term"]["support_level"],
                "resistance": analysis["mid_term"]["resistance_level"]
            },
            "lt_outlook": {
                "score": analysis["long_term"]["rating"],
                "comment": analysis["long_term"]["comment"],
                "conviction": analysis["long_term"]["conviction"]
            },
            "risks": {
                "score": analysis["risks"]["rating"],
                "comment": analysis["risks"]["comment"],
                "conviction": analysis["risks"]["conviction"]
            },
            "overall_rating": analysis["overall_rating"]
        }
        
        return audit_results

    async def post_audit_to_sheets(self, audit_results: Dict):
        """Post audit results to Google Sheets if integration is enabled"""
        if not self.sheets:
            logger.warning("Google Sheets integration not enabled")
            return
            
        try:
            logger.info("Posting audit results to Google Sheets...")
            logger.info(f"Raw audit results: {json.dumps(audit_results, indent=2)}")
            
            # Format data for sheets
            row_data = [
                audit_results.get("timestamp", ""),  # Time (UTC+8)
                audit_results.get("token", ""),  # Token
                audit_results.get("contract", ""),  # Contract
                audit_results.get("name", ""),  # Name
                audit_results.get("market_cap", 0),  # Market Cap ($)
                
                # ST Momentum
                audit_results.get("st_momentum", {}).get("score", 0),  # ST Momentum Score
                audit_results.get("st_momentum", {}).get("comment", ""),  # ST Momentum Comment
                audit_results.get("st_momentum", {}).get("conviction", 0),  # ST Momentum Conviction
                audit_results.get("st_momentum", {}).get("support", 0),  # ST Support Level
                audit_results.get("st_momentum", {}).get("resistance", 0),  # ST Resistance Level
                
                # MT Momentum
                audit_results.get("mt_momentum", {}).get("score", 0),  # MT Momentum Score
                audit_results.get("mt_momentum", {}).get("comment", ""),  # MT Momentum Comment
                audit_results.get("mt_momentum", {}).get("conviction", 0),  # MT Momentum Conviction
                audit_results.get("mt_momentum", {}).get("support", 0),  # MT Support Level
                audit_results.get("mt_momentum", {}).get("resistance", 0),  # MT Resistance Level
                
                # LT Outlook
                audit_results.get("lt_outlook", {}).get("score", 0),  # LT Outlook Score
                audit_results.get("lt_outlook", {}).get("comment", ""),  # LT Outlook Comment
                audit_results.get("lt_outlook", {}).get("conviction", 0),  # LT Outlook Conviction
                
                # Risks
                audit_results.get("risks", {}).get("score", 0),  # Risks Score
                audit_results.get("risks", {}).get("comment", ""),  # Risks Comment
                audit_results.get("risks", {}).get("conviction", 0),  # Risks Conviction
                
                # Overall Rating
                audit_results.get("overall_rating", 0)  # Overall Rating
            ]
            
            logger.info(f"Formatted row data: {json.dumps(row_data, indent=2)}")
            
            # Append to sheet with the specified sheet name
            self.sheets.append_audit_results(row_data, sheet_name=self.audit_sheet_name)
            logger.info("Successfully posted audit results to Google Sheets")
            
        except Exception as e:
            logger.error(f"Error posting to sheets: {str(e)}")
            raise

async def main():
    try:
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        
        # Use BONK token for testing
        token_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK token
        logger.info(f"Auditing token: {token_address}")
        
        # Initialize with API keys from environment
        birdeye = BirdeyeDataCollector(api_key=os.getenv('BIRDEYE_API_KEY'))
        
        # Initialize Google Sheets integration
        sheets = GoogleSheetsIntegration(
            credentials_file='service-account.json',
            spreadsheet_id=os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        )
        
        # Initialize auditor with sheets integration
        auditor = TokenAuditor(birdeye=birdeye, sheets=sheets)
        
        # Run audit
        logger.info("Starting token audit...")
        audit_results = await auditor.audit_token(token_address)
        logger.info(f"Audit results: {json.dumps(audit_results, indent=2)}")
        
        # Post to sheets
        logger.info("Posting to Google Sheets...")
        await auditor.post_audit_to_sheets(audit_results)
        logger.info("Done!")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
