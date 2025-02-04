import asyncio
import os
from birdeye_get_data import BirdeyeDataCollector
from audit import TokenAuditor

async def test():
    birdeye = BirdeyeDataCollector(api_key=os.getenv('BIRDEYE_API_KEY'))
    auditor = TokenAuditor(birdeye=birdeye)
    
    # Get BONK token data
    token_data = await birdeye.get_token_data("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
    token_data["address"] = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # Add address to token data
    
    # Get Claude analysis
    analysis = await auditor.get_claude_analysis(token_data)
    
    # Print raw data first
    price_changes = await birdeye.get_historical_price_changes(token_data["address"])
    ath_data = await birdeye.get_ath_price_change(token_data["address"])
    print("\n=== Raw Price Data ===")
    print("Price Changes:")
    print(f"- 1W: {price_changes.get('1W')}%")
    print(f"- 2W: {price_changes.get('2W')}%")
    print(f"- 1M: {price_changes.get('1M')}%")
    print(f"- 1Y: {price_changes.get('1Y')}%")
    print("\n1Y High Data:")
    print(f"- High Price: ${ath_data['ath_price']:.8f}")
    print(f"- Current Price: ${ath_data['current_price']:.8f}")
    print(f"- Change from High: {ath_data['change_from_ath']}%")
    print(f"- High Date: {ath_data['ath_date']}")
    
    print("\n=== Claude Analysis ===")
    print("\nShort-term Analysis:")
    print(analysis["short_term_analysis"])
    print("\nMid-term Momentum:")
    print(analysis["mid_term_momentum"])
    print("\nLong-term Outlook:")
    print(analysis["long_term_outlook"])
    print("\nKey Risks and Opportunities:")
    print(analysis["key_risks_and_opportunities"])
    print("\nOverall Rating:")
    print(analysis["rating"])

if __name__ == "__main__":
    asyncio.run(test())
