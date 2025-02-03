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
        self.audit_sheet_name = "Audit"

    async def _get_short_term_score(self, price_change: float) -> Tuple[float, str]:
        """Calculate short-term price momentum score"""
        if price_change >= 10:
            return 5.0, "Very strong upward momentum"
        elif price_change >= 5:
            return 4.0, "Strong upward momentum"
        elif price_change >= 2:
            return 3.5, "Moderate upward momentum"
        elif price_change >= -2:
            return 3.0, "Stable price"
        elif price_change >= -5:
            return 2.0, "Moderate downward momentum"
        elif price_change >= -10:
            return 1.0, "Strong downward momentum"
        else:
            return 0.0, "Very strong downward momentum"

    async def _get_mid_term_score(self, price_change: float) -> Tuple[float, str]:
        """Calculate mid-term price momentum score"""
        if price_change >= 100:
            return 5.0, "Exceptional growth"
        elif price_change >= 50:
            return 4.0, "Very strong growth"
        elif price_change >= 20:
            return 3.5, "Strong growth"
        elif price_change >= -20:
            return 3.0, "Moderate performance"
        elif price_change >= -50:
            return 2.0, "Significant decline"
        elif price_change >= -70:
            return 1.0, "Major decline"
        else:
            return 0.0, "Severe decline"

    async def _get_liquidity_score(self, liquidity: float, volume_24h: float) -> Tuple[float, str]:
        """Calculate liquidity score"""
        if liquidity >= 1000000 and volume_24h >= 500000:
            return 5.0, "Excellent liquidity"
        elif liquidity >= 500000 and volume_24h >= 250000:
            return 4.0, "Very good liquidity"
        elif liquidity >= 100000 and volume_24h >= 50000:
            return 3.5, "Good liquidity"
        elif liquidity >= 50000 and volume_24h >= 25000:
            return 3.0, "Moderate liquidity"
        elif liquidity >= 10000 and volume_24h >= 5000:
            return 2.0, "Limited liquidity"
        elif liquidity >= 5000 and volume_24h >= 1000:
            return 1.0, "Poor liquidity"
        else:
            return 0.0, "Very poor liquidity"

    async def _get_manipulation_risk(self, top_holder_percent: float, volume_24h: float, liquidity: float) -> Tuple[float, str]:
        """Calculate manipulation risk score (higher is better/safer)"""
        # Base score from top holder concentration
        if top_holder_percent >= 80:
            base_score = 0.0
            desc = "Extremely high concentration"
        elif top_holder_percent >= 60:
            base_score = 1.0
            desc = "Very high concentration"
        elif top_holder_percent >= 40:
            base_score = 2.0
            desc = "High concentration"
        elif top_holder_percent >= 20:
            base_score = 3.0
            desc = "Moderate concentration"
        else:
            base_score = 4.0
            desc = "Well distributed"

        # Adjust based on liquidity and volume
        if liquidity >= 1000000 and volume_24h >= 500000:
            base_score += 1.0
            desc += " with strong market depth"
        elif liquidity >= 100000 and volume_24h >= 50000:
            base_score += 0.5
            desc += " with decent market depth"
        elif liquidity < 10000 or volume_24h < 5000:
            base_score = max(0, base_score - 1.0)
            desc += " but low market depth"

        return min(5.0, base_score), desc

    async def get_claude_insight(self, prompt: str) -> Dict:
        """Get market insight from Claude API"""
        headers = {
            "x-api-key": os.getenv('CLAUDE_API_KEY'),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "anthropic-api-key": os.getenv('CLAUDE_API_KEY')  # Include both for compatibility
        }
        
        try:
            logger.info("Calling Claude API...")
            logger.info(f"API Key: {headers['x-api-key']}")
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
                    
                    if not result.get("content"):
                        return {
                            "content": None,
                            "error": "No content in response"
                        }
                    
                    return {
                        "content": result["content"][0]["text"],
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
            - Market Cap: ${token_data.get('marketCap', 0)}
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
                            "conviction": analysis["short_term"]["conviction"] / 100,
                            "support": analysis["short_term"]["support_level"],
                            "resistance": analysis["short_term"]["resistance_level"]
                        },
                        "mid_term_momentum": {
                            "score": analysis["mid_term"]["rating"],
                            "comment": analysis["mid_term"]["comment"],
                            "conviction": analysis["mid_term"]["conviction"] / 100,
                            "support": analysis["mid_term"]["support_level"],
                            "resistance": analysis["mid_term"]["resistance_level"]
                        },
                        "long_term_outlook": {
                            "score": analysis["long_term"]["rating"],
                            "comment": analysis["long_term"]["comment"],
                            "conviction": analysis["long_term"]["conviction"] / 100
                        },
                        "key_risks_and_opportunities": {
                            "score": analysis["risks"]["rating"],
                            "comment": analysis["risks"]["comment"],
                            "conviction": analysis["risks"]["conviction"] / 100
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
            
            # Append to sheet
            self.sheets.append_audit_results(row_data)
            logger.info("Successfully posted audit results to Google Sheets")
            
        except Exception as e:
            logger.error(f"Error posting to sheets: {str(e)}")
            raise

    def _analyze_token_metrics(self, token_data: Dict, recent_trades: List[Dict], top_traders: List[Dict]) -> Dict:
        """Analyze token metrics using algorithmic approach with all available data"""
        # Basic metrics
        price_15m = float(token_data.get("priceChange15mPercent", 0))
        price_1h = float(token_data.get("priceChange1h", 0))
        trades_24h = int(token_data.get("trades24h", 0))
        volume_24h = float(token_data.get("volume24hUSD", 0))
        
        # Enhanced analysis using trade data
        trade_sizes = [float(trade.get("volumeUSD", 0)) for trade in recent_trades]
        avg_trade_size = sum(trade_sizes) / len(trade_sizes) if trade_sizes else 0
        max_trade_size = max(trade_sizes) if trade_sizes else 0
        trade_size_variance = sum((x - avg_trade_size) ** 2 for x in trade_sizes) / len(trade_sizes) if trade_sizes else 0
        
        # Top trader concentration
        top_trader_volume = sum(float(trader.get("volumeUSD", 0)) for trader in top_traders)
        top_trader_concentration = top_trader_volume / volume_24h if volume_24h > 0 else 0
        
        # Short-term momentum analysis with enhanced metrics
        short_term_score = 3.0
        if abs(price_15m) > 10 or abs(price_1h) > 20:
            short_term_score = 4.0 if price_15m > 0 and price_1h > 0 else 2.0
        if trades_24h > 50000 and volume_24h > 5000000:
            short_term_score += 1.0
        if top_trader_concentration < 0.3:  # Healthy distribution
            short_term_score += 0.5
        
        # Mid-term momentum analysis
        price_24h = float(token_data.get("priceChange24h", 0))
        volume_change = float(token_data.get("volumeChange24h", 0))
        market_cap = float(token_data.get("marketCap", 0))
        
        mid_term_score = 3.0
        if abs(price_24h) > 50:
            mid_term_score = 4.0 if price_24h > 0 else 2.0
        if volume_change > 100 and market_cap > 1000000:
            mid_term_score += 1.0
            
        # Enhanced liquidity analysis
        liquidity = float(token_data.get("liquidity", 0))
        markets = int(token_data.get("numberMarkets", 0))
        buy_sell_ratio = float(token_data.get("buyVolume24h", 0)) / float(token_data.get("sellVolume24h", 1))
        
        liquidity_score = 3.0
        if liquidity > 1000000:
            liquidity_score += 1.0
        if markets > 100:
            liquidity_score += 0.5
        if 0.8 <= buy_sell_ratio <= 1.2:  # Balanced buy/sell ratio
            liquidity_score += 0.5
            
        # Enhanced manipulation risk analysis with trade patterns
        holders = int(token_data.get("holders", 0))
        active_wallets = int(token_data.get("uniqueWallets24h", 0))
        
        # Analyze trade patterns for wash trading
        trade_addresses = [trade.get("taker", "") for trade in recent_trades]
        unique_traders = len(set(trade_addresses))
        trade_frequency = {}
        for addr in trade_addresses:
            trade_frequency[addr] = trade_frequency.get(addr, 0) + 1
        suspicious_traders = sum(1 for freq in trade_frequency.values() if freq > 10)  # More than 10 trades/hour
        
        manipulation_score = 3.0
        if holders > 10000 and active_wallets > 1000:
            manipulation_score += 1.0
        if liquidity/market_cap > 0.1:
            manipulation_score += 1.0
        if suspicious_traders / len(trade_frequency) < 0.1 if trade_frequency else True:
            manipulation_score += 0.5
        if top_trader_concentration < 0.4:
            manipulation_score += 0.5

        # Calculate scam risk score
        scam_indicators = self._analyze_scam_indicators(token_data, recent_trades, top_traders)
        scam_risk = 5.0 - (len(scam_indicators.get("indicators", [])) * 1.0)  # Each indicator reduces score by 1
        scam_risk = max(0.5, min(5.0, scam_risk))  # Clamp between 0.5 and 5
            
        # Determine trading recommendation
        if scam_risk < 2:  # High scam risk
            action = "SELL"
            conviction = 5
            reasoning = "Multiple high-risk indicators suggest this token is likely fraudulent. "
            risk_warning = "This token shows strong characteristics of a scam. Immediate exit recommended. "
        elif manipulation_score < 2:  # High manipulation risk
            action = "SELL"
            conviction = 4
            reasoning = "Significant manipulation risk detected. Market behavior appears artificial. "
            risk_warning = "High risk of market manipulation. Exercise extreme caution. "
        elif liquidity_score < 2:  # Very low liquidity
            action = "HOLD"
            conviction = 3
            reasoning = "Insufficient liquidity for safe trading. Wait for improved market conditions. "
            risk_warning = "Low liquidity may result in significant slippage and difficulty exiting positions. "
        else:
            # Weight the momentum scores
            weighted_momentum = (short_term_score * 0.4 + mid_term_score * 0.6)
            if weighted_momentum >= 4:
                action = "BUY"
                conviction = min(5, int(weighted_momentum))
                reasoning = "Strong momentum indicators with acceptable risk metrics. "
                risk_warning = "Monitor for changes in momentum and increasing manipulation risk. "
            elif weighted_momentum <= 2:
                action = "SELL"
                conviction = min(5, int(6 - weighted_momentum))
                reasoning = "Poor momentum indicators suggest declining market interest. "
                risk_warning = "Further price decline likely. Consider exit strategies. "
            else:
                action = "HOLD"
                conviction = 3
                reasoning = "Mixed signals suggest cautious observation. "
                risk_warning = "Market direction unclear. Monitor for stronger signals. "

        analysis = {
            "scores": {
                "short_term_momentum": {
                    "score": min(5.0, short_term_score),
                    "description": "Healthy movement" if short_term_score >= 4 else "Moderate" if short_term_score >= 3 else "Weak",
                    "insight": f"Short-term analysis shows {'healthy' if short_term_score >= 4 else 'moderate' if short_term_score >= 3 else 'weak'} momentum. "
                             f"Price change: 15m={price_15m:.2f}%, 1h={price_1h:.2f}%. Volume: ${volume_24h:,.2f} with {trades_24h:,} trades. "
                             f"Average trade size: ${avg_trade_size:,.2f}, Top trader concentration: {top_trader_concentration*100:.1f}%"
                },
                "mid_term_momentum": {
                    "score": min(5.0, mid_term_score),
                    "description": "Strong" if mid_term_score >= 4 else "Moderate" if mid_term_score >= 3 else "Poor",
                    "insight": f"Mid-term performance is {'strong' if mid_term_score >= 4 else 'moderate' if mid_term_score >= 3 else 'poor'}. "
                             f"24h changes: Price={price_24h:.2f}%, Volume={volume_change:.2f}%. Market cap: ${market_cap:,.2f}. "
                             f"Active wallets: {active_wallets:,} ({token_data.get('uniqueWalletsChange24h', 0):.2f}% change)"
                },
                "liquidity": {
                    "score": min(5.0, liquidity_score),
                    "description": "Excellent liquidity" if liquidity_score >= 4.5 else "Good liquidity" if liquidity_score >= 3.5 else "Moderate liquidity" if liquidity_score >= 2.5 else "Poor liquidity",
                    "insight": f"Liquidity analysis shows {'excellent' if liquidity_score >= 4.5 else 'good' if liquidity_score >= 3.5 else 'moderate' if liquidity_score >= 2.5 else 'poor'} metrics. "
                             f"Total liquidity: ${liquidity:,.2f}, Markets: {markets}. Buy/Sell ratio: {buy_sell_ratio:.2f}. "
                             f"Trade size variance: ${trade_size_variance:,.2f}"
                },
                "manipulation_risk": {
                    "score": min(5.0, manipulation_score),
                    "description": "Very low risk" if manipulation_score >= 4.5 else "Low risk" if manipulation_score >= 3.5 else "Moderate risk" if manipulation_score >= 2.5 else "High risk",
                    "insight": f"Manipulation risk is {'very low' if manipulation_score >= 4.5 else 'low' if manipulation_score >= 3.5 else 'moderate' if manipulation_score >= 2.5 else 'high'}. "
                             f"Holders: {holders:,}, Active: {active_wallets:,} ({active_wallets/holders*100 if holders > 0 else 0:.1f}% active). "
                             f"Unique traders: {unique_traders}, Suspicious patterns: {suspicious_traders}. "
                             f"Top trader concentration: {top_trader_concentration*100:.1f}%"
                },
                "scam_risk": {
                    "score": scam_risk,
                    "description": "Very low risk" if scam_risk >= 4.5 else "Low risk" if scam_risk >= 3.5 else "Moderate risk" if scam_risk >= 2.5 else "High risk" if scam_risk >= 1.5 else "Extreme risk - Almost certainly a scam",
                    "indicators": scam_indicators.get("indicators", []),
                    "insight": scam_indicators.get("insight", "No significant scam indicators detected.")
                },
                "trading_recommendation": {
                    "action": action,
                    "conviction": conviction,
                    "reasoning": reasoning + f"Short-term momentum: {short_term_score:.1f}/5, Mid-term momentum: {mid_term_score:.1f}/5, "
                               f"Liquidity: {liquidity_score:.1f}/5, Manipulation risk: {manipulation_score:.1f}/5, "
                               f"Scam risk: {scam_risk:.1f}/5.",
                    "risk_warning": risk_warning
                }
            }
        }
        
        return analysis

    def _analyze_scam_indicators(self, token_data: Dict, recent_trades: List[Dict], top_traders: List[Dict]) -> Dict:
        """Enhanced scam detection using all available data"""
        indicators = []
        risk_level = 0
        
        # Previous brand impersonation checks
        name = token_data.get("name", "").lower()
        symbol = token_data.get("symbol", "").lower()
        description = token_data.get("description", "").lower()
        website = token_data.get("website", "").lower()
        
        major_brands = {
            "jp morgan": ["jpmorgan", "jp morgan", "jpm"],
            "bitcoin": ["bitcoin", "btc"],
            "ethereum": ["ethereum", "eth"],
            "binance": ["binance", "bnb"],
            "tesla": ["tesla", "tsla"],
            "apple": ["apple", "aapl"],
            "microsoft": ["microsoft", "msft"],
            "meta": ["meta", "facebook", "instagram"],
            "google": ["google", "alphabet", "googl"],
            "amazon": ["amazon", "amzn"]
        }
        
        for brand, keywords in major_brands.items():
            if any(keyword in name.lower() for keyword in keywords) or \
               any(keyword in symbol.lower() for keyword in keywords) or \
               any(keyword in description.lower() for keyword in keywords):
                indicators.append(f"Potential impersonation of {brand}")
                risk_level += 2
        
        # Enhanced website analysis
        if website:
            suspicious_domains = ["official", "real", "true", "genuine", "verify", "ico", "airdrop"]
            if any(domain in website for domain in suspicious_domains):
                indicators.append("Suspicious website domain patterns")
                risk_level += 1
            
            if not website.startswith("https://"):
                indicators.append("Non-HTTPS website")
                risk_level += 1
        
        # Enhanced market manipulation checks
        market_cap = float(token_data.get("marketCap", 0))
        volume_24h = float(token_data.get("volume24hUSD", 0))
        if market_cap > 0 and volume_24h/market_cap > 5:
            indicators.append("Extremely high volume relative to market cap")
            risk_level += 2
        
        # Enhanced wallet activity analysis
        unique_wallets_change = float(token_data.get("uniqueWalletsChange24h", 0))
        if abs(unique_wallets_change) > 1000:
            indicators.append(f"Suspicious wallet activity spike ({unique_wallets_change:.2f}%)")
            risk_level += 2
        
        # Trade pattern analysis
        if recent_trades:
            trade_addresses = [trade.get("taker", "") for trade in recent_trades]
            trade_frequency = {}
            for addr in trade_addresses:
                trade_frequency[addr] = trade_frequency.get(addr, 0) + 1
            
            # Check for wash trading
            suspicious_traders = sum(1 for freq in trade_frequency.values() if freq > 10)
            if suspicious_traders > len(trade_frequency) * 0.1:
                indicators.append(f"Potential wash trading detected ({suspicious_traders} suspicious traders)")
                risk_level += 2
            
            # Analyze trade size distribution
            trade_sizes = [float(trade.get("volumeUSD", 0)) for trade in recent_trades]
            if trade_sizes:
                avg_size = sum(trade_sizes) / len(trade_sizes)
                size_variance = sum((x - avg_size) ** 2 for x in trade_sizes) / len(trade_sizes)
                if size_variance > avg_size * 100:
                    indicators.append("Highly irregular trade size patterns")
                    risk_level += 1
        
        # Top trader concentration analysis
        if top_traders:
            top_volume = sum(float(trader.get("volumeUSD", 0)) for trader in top_traders)
            if volume_24h > 0:
                concentration = top_volume / volume_24h
                if concentration > 0.7:
                    indicators.append(f"High trading concentration ({concentration*100:.1f}% by top 10 traders)")
                    risk_level += 2
        
        # Price volatility checks
        price_change_24h = float(token_data.get("priceChange24h", 0))
        price_change_1h = float(token_data.get("priceChange1h", 0))
        if abs(price_change_24h) > 200 or abs(price_change_1h) > 50:
            indicators.append(f"Extreme price volatility (24h: {price_change_24h:.2f}%, 1h: {price_change_1h:.2f}%)")
            risk_level += 2
        
        # Liquidity analysis
        liquidity = float(token_data.get("liquidity", 0))
        if market_cap > 0 and liquidity/market_cap < 0.05:
            indicators.append("Very low liquidity relative to market cap")
            risk_level += 1
        
        # Social media verification
        twitter = token_data.get("twitter", "")
        discord = token_data.get("discord", "")
        if not twitter and not discord:
            indicators.append("No social media presence")
            risk_level += 1
        
        # Normalize risk level to 0-5 scale
        risk_level = min(risk_level, 10)
        normalized_risk = risk_level / 2
        
        risk_descriptions = {
            (0, 1): "Low risk - No major scam indicators detected",
            (1, 2): "Moderate risk - Some suspicious patterns",
            (2, 3): "High risk - Multiple suspicious indicators",
            (3, 4): "Very high risk - Strong scam indicators",
            (4, 5): "Extreme risk - Almost certainly a scam"
        }
        
        risk_description = next(desc for (min_val, max_val), desc in risk_descriptions.items() 
                              if min_val <= normalized_risk <= max_val)
        
        return {
            "score": 5 - normalized_risk,  # Invert so 5 is safest
            "description": risk_description,
            "indicators": indicators,
            "insight": f"Scam analysis reveals {len(indicators)} risk indicators. " + 
                      f"Key concerns: {', '.join(indicators[:3]) if indicators else 'None found'}. " +
                      f"Analysis based on {len(recent_trades)} recent trades and {len(top_traders)} top traders."
        }

async def main():
    """Test the token auditor"""
    try:
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        
        # Use BONK token for testing
        token_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK token
        logger.info(f"Auditing token: {token_address}")
        
        # Initialize with API keys from environment
        birdeye = BirdeyeDataCollector(api_key=os.getenv('BIRDEYE_API_KEY', '37f87df908cb48fb88fffd6911bc74b3'))
        
        # Initialize Google Sheets integration
        sheets = GoogleSheetsIntegration(
            os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE'),
            os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
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
