import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import asyncio
import json
import aiohttp
from birdeye_get_data import BirdeyeDataCollector
from sheets_integration import GoogleSheetsIntegration

logger = logging.getLogger(__name__)

class TokenAuditor:
    def __init__(self, birdeye: BirdeyeDataCollector, sheets: GoogleSheetsIntegration = None):
        self.birdeye = birdeye
        self.sheets = sheets
        self.audit_sheet_name = "TokenAudits"  # Update to match sheets_integration.py

    async def get_claude_insight(self, prompt: str) -> Dict:
        """Get market insight from Claude API"""
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            logger.error("CLAUDE_API_KEY environment variable not set")
            return {"error": "API key not configured"}

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "anthropic-api-key": api_key  # Include both for compatibility
        }
        
        try:
            logger.info("Calling Claude API...")
            logger.info("API Key configured: Yes")
            logger.info(f"Prompt: {prompt}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json={
                        "model": "claude-3-sonnet-20240229",
                        "max_tokens": 1024,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "system": "You are a token market analyst. Analyze the provided metrics and return a JSON response with scores and insights."
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Claude API error: {error_text}")
                        return {
                            "content": None,
                            "error": f"HTTP {response.status}: {error_text}"
                        }
                    
                    result = await response.json()
                    logger.info(f"Claude API response: {json.dumps(result, indent=2)}")
                    
                    # Handle the response correctly
                    if "content" not in result or not result["content"]:
                        return {
                            "content": None,
                            "error": "No content in response"
                        }
                    
                    content = result["content"][0]["text"] if isinstance(result["content"], list) else result["content"]
                    return {
                        "content": content,
                        "error": None
                    }
        except Exception as e:
            logger.error(f"Error getting Claude insight: {str(e)}")
            return {
                "content": None,
                "error": str(e)
            }

    async def get_claude_analysis(self, token_data: Dict, recent_trades: List = None, top_traders: List = None) -> Dict:
        default_response = {
            "scores": {
                "short_term_momentum": {
                    "score": 0,
                    "comment": "Error analyzing short-term metrics",
                    "conviction": 0,
                    "support": 0,
                    "resistance": 0
                },
                "mid_term_momentum": {
                    "score": 0,
                    "comment": "Error analyzing mid-term metrics",
                    "conviction": 0,
                    "support": 0,
                    "resistance": 0
                },
                "long_term_outlook": {
                    "score": 0,
                    "comment": "Error analyzing long-term metrics",
                    "conviction": 0
                },
                "key_risks_and_opportunities": {
                    "score": 0,
                    "comment": "Error analyzing risks and opportunities",
                    "conviction": 0
                },
                "rating": 0
            }
        }
        
        try:
            # Get OHLCV data
            minute_data = await self.birdeye.get_minute_ohlcv(token_data["address"])
            hourly_data = await self.birdeye.get_24h_hourly_ohlcv(token_data["address"])

            # Build Claude prompt for all timeframes
            prompt = f"""Analyze {token_data['symbol']} trading potential across multiple timeframes using:
            - Latest Price: ${token_data['price']}
            - Market Cap: ${token_data.get('realMc', 0)}
            - 24h Volume: ${token_data.get('v24hUSD', 0)}
            - Holders: {token_data.get('holder', 0)}
            - 15m OHLCV Data: {json.dumps(minute_data[-15:])}
            - 1h OHLCV Data: {json.dumps(hourly_data[-24:])}
            
            Provide JSON response with:
            {{
                "short_term": {{
                    "rating": 1-5 (1=Strong Sell, 5=Strong Buy),
                    "comment": "Brief rationale <100 chars",
                    "conviction": 0-100,
                    "support_level": number,
                    "resistance_level": number
                }},
                "mid_term": {{
                    "rating": 1-5,
                    "comment": "Brief rationale <100 chars",
                    "conviction": 0-100,
                    "support_level": number,
                    "resistance_level": number
                }},
                "long_term": {{
                    "rating": 1-5,
                    "comment": "Brief rationale <100 chars",
                    "conviction": 0-100
                }},
                "risks": {{
                    "rating": 1-5 (1=High Risk, 5=Low Risk),
                    "comment": "Key risks and opportunities <100 chars",
                    "conviction": 0-100
                }},
                "overall_rating": 1-5
            }}"""

            # Get Claude response
            claude_resp = await self.get_claude_insight(prompt)
            if claude_resp["error"] or not claude_resp["content"]:
                return default_response
            
            # Parse response
            try:
                analysis = json.loads(claude_resp["content"])
                return {
                    "scores": {
                        "short_term_momentum": {
                            "score": analysis["short_term"]["rating"],
                            "comment": analysis["short_term"]["comment"],
                            "conviction": analysis["short_term"]["conviction"],
                            "support": analysis["short_term"]["support_level"],
                            "resistance": analysis["short_term"]["resistance_level"]
                        },
                        "mid_term_momentum": {
                            "score": analysis["mid_term"]["rating"],
                            "comment": analysis["mid_term"]["comment"],
                            "conviction": analysis["mid_term"]["conviction"],
                            "support": analysis["mid_term"]["support_level"],
                            "resistance": analysis["mid_term"]["resistance_level"]
                        },
                        "long_term_outlook": {
                            "score": analysis["long_term"]["rating"],
                            "comment": analysis["long_term"]["comment"],
                            "conviction": analysis["long_term"]["conviction"]
                        },
                        "key_risks_and_opportunities": {
                            "score": analysis["risks"]["rating"],
                            "comment": analysis["risks"]["comment"],
                            "conviction": analysis["risks"]["conviction"]
                        },
                        "rating": analysis["overall_rating"]
                    }
                }
            except json.JSONDecodeError:
                logger.error("Failed to parse Claude response")
                return default_response
            
        except Exception as e:
            logger.error(f"Claude analysis error: {str(e)}")
            return default_response

    async def audit_token(self, token_address: str) -> Dict:
        """Run a comprehensive token audit."""
        try:
            # Get token data
            token_data = await self.birdeye.get_token_data(token_address)
            if not token_data:
                raise ValueError(f"No data found for token {token_address}")

            # Get recent trades
            recent_trades = await self.birdeye.get_recent_trades(token_address)
            
            # Get top traders
            top_traders = await self.birdeye.get_top_traders(token_address)

            # Get Claude's analysis
            claude_analysis = await self.get_claude_analysis(token_data, recent_trades, top_traders)
            
            # Get scores from Claude's analysis
            scores = claude_analysis.get("scores", {})
            st = scores.get("short_term_momentum", {})
            mt = scores.get("mid_term_momentum", {})
            lt = scores.get("long_term_outlook", {})
            risks = scores.get("key_risks_and_opportunities", {})
            
            # Combine all data
            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "token": token_data.get("symbol", ""),
                "contract": token_address,
                "name": token_data.get("name", ""),
                "market_cap": token_data.get("marketCap", 0),
                "st_momentum": {
                    "score": st.get("score", 0),
                    "comment": st.get("comment", ""),
                    "conviction": st.get("conviction", 0),
                    "support": st.get("support", 0),
                    "resistance": st.get("resistance", 0)
                },
                "mt_momentum": {
                    "score": mt.get("score", 0),
                    "comment": mt.get("comment", ""),
                    "conviction": mt.get("conviction", 0),
                    "support": mt.get("support", 0),
                    "resistance": mt.get("resistance", 0)
                },
                "lt_outlook": {
                    "score": lt.get("score", 0),
                    "comment": lt.get("comment", ""),
                    "conviction": lt.get("conviction", 0)
                },
                "risks": {
                    "score": risks.get("score", 0),
                    "comment": risks.get("comment", ""),
                    "conviction": risks.get("conviction", 0)
                },
                "overall_rating": scores.get("rating", 0)
            }
            
        except Exception as e:
            logger.error(f"Error in audit_token: {str(e)}")
            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "token": "ERROR",
                "contract": token_address,
                "name": "Error fetching data",
                "market_cap": 0,
                "st_momentum": {
                    "score": 0,
                    "comment": f"Error: {str(e)}",
                    "conviction": 0,
                    "support": 0,
                    "resistance": 0
                },
                "mt_momentum": {
                    "score": 0,
                    "comment": "Error fetching data",
                    "conviction": 0,
                    "support": 0,
                    "resistance": 0
                },
                "lt_outlook": {
                    "score": 0,
                    "comment": "Error fetching data",
                    "conviction": 0
                },
                "risks": {
                    "score": 0,
                    "comment": "Error fetching data",
                    "conviction": 0
                },
                "overall_rating": 0
            }

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
    """Test the token auditor"""
    try:
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        
        # Use BONK token for testing
        token_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK token
        logger.info(f"Auditing token: {token_address}")
        
        # Initialize with API keys from environment
        birdeye = BirdeyeDataCollector(api_key=os.getenv('BIRDEYE_API_KEY'))
        
        # Initialize Google Sheets integration
        spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')  # Use the correct env var name
        if not spreadsheet_id:
            raise ValueError("GOOGLE_SHEETS_SPREADSHEET_ID environment variable not set")
            
        # Try to get credentials from environment first
        sheets = None
        try:
            sheets = GoogleSheetsIntegration(
                credentials_file="service-account.json",  # Use the correct credentials file
                spreadsheet_id=spreadsheet_id
            )
            sheets.authenticate()
            logger.info("Successfully initialized Google Sheets integration")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {e}")
            logger.warning("Continuing without Google Sheets integration")
        
        # Initialize auditor with sheets integration
        auditor = TokenAuditor(birdeye=birdeye, sheets=sheets)
        
        # Run audit
        logger.info("Starting token audit...")
        audit_results = await auditor.audit_token(token_address)
        logger.info(f"Audit results: {json.dumps(audit_results, indent=2)}")
        
        # Post to sheets if available
        if sheets:
            logger.info("Posting to Google Sheets...")
            await auditor.post_audit_to_sheets(audit_results)
            logger.info("Done!")
        else:
            logger.warning("Skipping Google Sheets posting - no integration available")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
