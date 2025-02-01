import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

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

def test_audit():
    """Test the token audit functionality without Telegram integration"""
    try:
        # Test with the default token address
        token_address = "EfgEGG9PxLhyk1wqtqgGnwgfVC7JYic3vC9BCWLvpump"
        logging.info(f"Fetching audit data for token: {token_address}")
        
        pair = fetch_token_data(token_address)
        if not pair:
            logging.error("❌ Failed to fetch token data")
            return

        # Extract and log basic metrics
        price_usd = float(pair["priceUsd"])
        volume_24h = float(pair["volume"]["h24"])
        volume_1h = float(pair.get("volume", {}).get("h1", 0))
        liquidity = float(pair["liquidity"]["usd"])
        market_cap = float(pair.get("marketCap", 0))
        fdv = float(pair.get("fdv", 0))
        
        logging.info("\n=== Token Audit Results ===")
        logging.info(f"Price: ${price_usd:.6f}")
        logging.info(f"24h Volume: ${volume_24h:,.2f}")
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
        
        # Transaction metrics
        txns_24h = pair.get("txns", {}).get("h24", {})
        buys_24h = int(txns_24h.get("buys", 0))
        sells_24h = int(txns_24h.get("sells", 0))
        
        logging.info("\n=== Trading Activity (24h) ===")
        logging.info(f"Buy Transactions: {buys_24h}")
        logging.info(f"Sell Transactions: {sells_24h}")
        
        # Raw response for debugging
        logging.info("\n=== Raw Response ===")
        logging.info(f"Response: {pair}")
        
    except Exception as e:
        logging.error(f"Error in test_audit: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test_audit()
