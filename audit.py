import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import asyncio
import json
import requests
from birdeye_get_data import BirdeyeDataCollector
from sheets_integration import GoogleSheetsIntegration

logger = logging.getLogger(__name__)

CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

class TokenAuditor:
    def __init__(self, birdeye: BirdeyeDataCollector, sheets: GoogleSheetsIntegration):
        self.birdeye = birdeye
        self.sheets = sheets
        self.audit_sheet_name = "Audit"

    async def get_claude_insight(self, prompt: str) -> str:
        """Get market insight from Claude API"""
        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        data = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 150,
            "messages": [{
                "role": "user",
                "content": prompt
            }]
        }
        
        try:
            response = requests.post(CLAUDE_API_URL, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()['content'][0]['text']
            logger.error(f"Claude API Error: {response.status_code} - {response.text}")
            return ""
        except Exception as e:
            logger.error(f"Error getting Claude insight: {str(e)}")
            return ""

    async def calculate_short_term_price_momentum(self, token_data: Dict) -> Tuple[float, str, str]:
        """Calculate 15-minute price momentum score (0-5) with Claude insight"""
        price_change_15m = token_data.get('priceChange15mPercent', 0)
        
        # Get base score and description
        score, desc = await self._get_short_term_score(price_change_15m)
        
        # Generate Claude insight
        prompt = f"""You are a crypto market analyst. Given the following 15-minute price data, provide a brief, insightful comment about the short-term market sentiment and potential trading implications. Be specific but concise.

Data:
- 15min Price Change: {price_change_15m}%
- Current Price: ${token_data.get('price', 0):.6f}
- Volume Change: {token_data.get('volumeChange15m', 0)}%

Respond in 2-3 short sentences."""

        insight = await self.get_claude_insight(prompt)
        return score, desc, insight

    async def calculate_mid_term_price_momentum(self, token_data: Dict) -> Tuple[float, str, str]:
        """Calculate 7-day price momentum score (0-5) with Claude insight"""
        price_change_7d = token_data.get('priceChange7dPercent', 0)
        
        # Get base score and description
        score, desc = await self._get_mid_term_score(price_change_7d)
        
        # Generate Claude insight
        prompt = f"""You are a crypto market analyst. Given the following 7-day price data, provide a brief, insightful comment about the mid-term market trend and potential investment outlook. Be specific but concise.

Data:
- 7d Price Change: {price_change_7d}%
- 24h Change: {token_data.get('priceChange24h', 0)}%
- Market Cap: ${token_data.get('marketCap', 0):,.2f}
- 7d Volume Change: {token_data.get('volumeChange7d', 0)}%

Respond in 2-3 short sentences."""

        insight = await self.get_claude_insight(prompt)
        return score, desc, insight

    async def calculate_liquidity_score(self, token_data: Dict) -> Tuple[float, str, str]:
        """Calculate liquidity score (0-5) with Claude insight"""
        liquidity = token_data.get('liquidity', 0)
        mcap = token_data.get('marketCap', 0)
        
        # Get base score and description
        score, desc = await self._get_liquidity_score(liquidity, mcap)
        
        # Generate Claude insight
        prompt = f"""You are a crypto market analyst. Given the following liquidity data, provide a brief, insightful comment about the market depth and trading implications. Be specific but concise.

Data:
- Total Liquidity: ${liquidity:,.2f}
- Market Cap: ${mcap:,.2f}
- Liquidity/MCap Ratio: {(liquidity/mcap if mcap > 0 else 0):.3f}
- 24h Liquidity Change: {token_data.get('liquidityChange24h', 0)}%

Respond in 2-3 short sentences."""

        insight = await self.get_claude_insight(prompt)
        return score, desc, insight

    async def calculate_manipulation_risk(self, token_data: Dict, trades: List[Dict]) -> Tuple[float, str, str]:
        """Calculate manipulation risk score (0-5) with Claude insight"""
        # Calculate basic metrics
        total_trades = len(trades)
        unique_wallets = set(trade['wallet'] for trade in trades if 'wallet' in trade)
        unique_ratio = len(unique_wallets) / total_trades if total_trades > 0 else 0
        
        # Get base score and description
        score, desc = await self._get_manipulation_score(unique_ratio)
        
        # Generate Claude insight
        prompt = f"""You are a crypto market analyst. Given the following trading data, provide a brief, insightful comment about potential market manipulation risks. Be specific but concise.

Data:
- Total Trades: {total_trades}
- Unique Wallets: {len(unique_wallets)}
- Unique Wallet Ratio: {unique_ratio:.2f}
- Avg Trade Size: ${token_data.get('avgTradeSize', 0):,.2f}
- Top Holder Concentration: {token_data.get('topHolderPercent', 0)}%

Respond in 2-3 short sentences."""

        insight = await self.get_claude_insight(prompt)
        return score, desc, insight

    async def audit_token(self, token_address: str) -> Dict:
        """Perform a comprehensive token audit with Claude insights"""
        token_data = await self.birdeye.get_token_data(token_address)
        recent_trades = await self.birdeye.get_recent_trades(token_address)
        
        # Get all scores and insights
        price_short, desc_short, insight_short = await self.calculate_short_term_price_momentum(token_data)
        price_mid, desc_mid, insight_mid = await self.calculate_mid_term_price_momentum(token_data)
        liquidity, desc_liq, insight_liq = await self.calculate_liquidity_score(token_data)
        manip_risk, desc_manip, insight_manip = await self.calculate_manipulation_risk(token_data, recent_trades)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "token_address": token_address,
            "scores": {
                "short_term_momentum": {
                    "score": price_short,
                    "description": desc_short,
                    "insight": insight_short
                },
                "mid_term_momentum": {
                    "score": price_mid,
                    "description": desc_mid,
                    "insight": insight_mid
                },
                "liquidity": {
                    "score": liquidity,
                    "description": desc_liq,
                    "insight": insight_liq
                },
                "manipulation_risk": {
                    "score": manip_risk,
                    "description": desc_manip,
                    "insight": insight_manip
                }
            },
            "raw_data": token_data
        }

    async def post_audit_to_sheets(self, audit_results: Dict):
        """Post audit results to Google Sheets"""
        headers = [
            "Token Address",
            "Token Name",
            "Token Symbol",
            "Audit Time",
            "Price Momentum (15m) Score",
            "Price Momentum (15m) Description",
            "Price Momentum (15m) Insight",
            "Price Momentum (7d) Score",
            "Price Momentum (7d) Description",
            "Price Momentum (7d) Insight",
            "Liquidity Score",
            "Liquidity Description",
            "Liquidity Insight",
            "Manipulation Risk Score",
            "Manipulation Risk Description",
            "Manipulation Risk Insight",
            "Composite Score"
        ]
        
        row = [
            audit_results["token_address"],
            audit_results["raw_data"]["name"],
            audit_results["raw_data"]["symbol"],
            audit_results["timestamp"],
            audit_results["scores"]["short_term_momentum"]["score"],
            audit_results["scores"]["short_term_momentum"]["description"],
            audit_results["scores"]["short_term_momentum"]["insight"],
            audit_results["scores"]["mid_term_momentum"]["score"],
            audit_results["scores"]["mid_term_momentum"]["description"],
            audit_results["scores"]["mid_term_momentum"]["insight"],
            audit_results["scores"]["liquidity"]["score"],
            audit_results["scores"]["liquidity"]["description"],
            audit_results["scores"]["liquidity"]["insight"],
            audit_results["scores"]["manipulation_risk"]["score"],
            audit_results["scores"]["manipulation_risk"]["description"],
            audit_results["scores"]["manipulation_risk"]["insight"],
            (audit_results["scores"]["short_term_momentum"]["score"] + 
             audit_results["scores"]["mid_term_momentum"]["score"] + 
             audit_results["scores"]["liquidity"]["score"] + 
             audit_results["scores"]["manipulation_risk"]["score"]) / 4
        ]
        
        # Ensure the audit sheet exists with headers
        self.sheets.ensure_sheet_exists(self.audit_sheet_name, headers)
        
        # Append the audit results
        self.sheets.append_to_sheet(self.audit_sheet_name, [row])

async def main():
    """Test the token auditor"""
    # Initialize Google Sheets integration
    sheets = GoogleSheetsIntegration(
        'service-account.json',
        '1vz0RCZ-DVfWKCtaLgd1ekUuimbW-SqrUlQqYrMgY_eA'
    )
    
    # Initialize Birdeye collector
    birdeye = BirdeyeDataCollector("37f87df908cb48fb88fffd6911bc74b3", sheets)
    
    # Initialize auditor
    auditor = TokenAuditor(birdeye, sheets)
    
    # Test with BONK token
    token_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    
    print(f"\nAuditing token: {token_address}")
    audit_results = await auditor.audit_token(token_address)
    print("\nAudit Results:")
    print(json.dumps(audit_results, indent=2))
    
    await auditor.post_audit_to_sheets(audit_results)

if __name__ == "__main__":
    asyncio.run(main())
