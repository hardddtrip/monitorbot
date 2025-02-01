import os
import logging
import requests
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def fetch_token_data(token_address):
    """Fetch token data from DexScreener API"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        response = requests.get(url)
        data = response.json()
        
        if not data or "pairs" not in data or not data["pairs"]:
            logging.error(f"No data found for token: {token_address}")
            return None
            
        # Get the pair with the highest liquidity
        pairs = data["pairs"]
        pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0)), reverse=True)
        return pairs[0]
        
    except Exception as e:
        logging.error(f"Error fetching token data: {str(e)}")
        return None

def fetch_token_metadata(token_address):
    """Fetch token metadata from Helius API"""
    try:
        HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
        if not HELIUS_API_KEY:
            logging.error("HELIUS_API_KEY not found in environment variables")
            return None

        url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
        payload = {"mintAccounts": [token_address]}
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            logging.error(f"Error fetching metadata: {response.status_code}")
            return None
            
        data = response.json()
        if not data or len(data) == 0:
            return None
            
        # Log raw response for debugging
        logging.debug(f"Raw metadata response: {json.dumps(data[0], indent=2)}")
        return data[0]
        
    except Exception as e:
        logging.error(f"Error fetching token metadata: {str(e)}")
        return None

def test_audit():
    """Test the token audit functionality without Telegram integration"""
    try:
        # Test with the default token address
        token_address = "EfgEGG9PxLhyk1wqtqgGnwgfVC7JYic3vC9BCWLvpump"
        logging.info(f"Fetching audit data for token: {token_address}")
        
        # Get market data
        pair = fetch_token_data(token_address)
        if not pair:
            logging.error("❌ Failed to fetch token data")
            return

        # Get token metadata
        metadata = fetch_token_metadata(token_address)
        if not metadata:
            logging.error("❌ Failed to fetch token metadata")
            return

        logging.info("\n=== Token Information ===")
        logging.info(f"Name: {metadata.get('metadata', {}).get('name', 'Unknown')}")
        logging.info(f"Symbol: {metadata.get('metadata', {}).get('symbol', 'Unknown')}")
        logging.info(f"Mint Authority: {'Frozen' if metadata.get('mint_authority') is None else 'Active'}")
        logging.info(f"Freeze Authority: {'Yes' if metadata.get('freeze_authority') else 'No'}")
        
        # Market metrics
        price_usd = float(pair["priceUsd"])
        volume_24h = float(pair["volume"]["h24"])
        volume_1h = float(pair.get("volume", {}).get("h1", 0))
        liquidity = float(pair["liquidity"]["usd"])
        market_cap = float(pair.get("marketCap", 0))
        fdv = float(pair.get("fdv", 0))
        
        logging.info("\n=== Market Metrics ===")
        logging.info(f"Price: ${price_usd:.6f}")
        logging.info(f"24h Volume: ${volume_24h:,.2f}")
        logging.info(f"1h Volume: ${volume_1h:,.2f}")
        logging.info(f"Liquidity: ${liquidity:,.2f}")
        logging.info(f"Market Cap: ${market_cap:,.2f}")
        logging.info(f"FDV: ${fdv:,.2f}")
        
        # Price changes
        price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
        price_change_24h = float(pair.get("priceChange", {}).get("h24", 0))
        price_change_7d = float(pair.get("priceChange", {}).get("d7", 0))
        
        logging.info("\n=== Price Changes ===")
        logging.info(f"1h: {price_change_1h:+.2f}%")
        logging.info(f"24h: {price_change_24h:+.2f}%")
        logging.info(f"7d: {price_change_7d:+.2f}%")
        
        # Trading activity
        txns_24h = pair.get("txns", {}).get("h24", {})
        txns_1h = pair.get("txns", {}).get("h1", {})
        buys_24h = int(txns_24h.get("buys", 0))
        sells_24h = int(txns_24h.get("sells", 0))
        buys_1h = int(txns_1h.get("buys", 0))
        sells_1h = int(txns_1h.get("sells", 0))
        
        logging.info("\n=== Trading Activity ===")
        logging.info("24h Activity:")
        logging.info(f"  • Buys: {buys_24h}")
        logging.info(f"  • Sells: {sells_24h}")
        logging.info("1h Activity:")
        logging.info(f"  • Buys: {buys_1h}")
        logging.info(f"  • Sells: {sells_1h}")
        
        # Risk Analysis
        logging.info("\n=== Risk Analysis ===")
        risks = []
        
        # Check for mintable token
        if metadata.get('mint_authority'):
            risks.append("Token is mintable - supply can be increased")
            
        # Check for freezable token
        if metadata.get('freeze_authority'):
            risks.append("Token has freeze authority - transfers can be disabled")
            
        # Check for low liquidity
        if liquidity < 50000:
            risks.append("Low liquidity - high price impact on trades")
            
        # Check for high price volatility
        if abs(price_change_1h) > 20:
            risks.append(f"High volatility - {abs(price_change_1h):.1f}% price change in 1h")
            
        # Check for suspicious trading patterns
        if buys_1h > 1000 and price_change_1h > 30:
            risks.append("Potential pump - high buy pressure and price increase")
        elif sells_1h > 1000 and price_change_1h < -30:
            risks.append("Potential dump - high sell pressure and price decrease")
            
        if risks:
            for risk in risks:
                logging.info(f"⚠️ {risk}")
        else:
            logging.info("✅ No major risks detected")
        
    except Exception as e:
        logging.error(f"Error in test_audit: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test_audit()
