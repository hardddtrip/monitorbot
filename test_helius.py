import os
import sys
import json
import requests
from datetime import datetime

# Test token address (BONK)
TEST_TOKEN = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

# Get Helius API key from environment
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
if not HELIUS_API_KEY:
    print("❌ HELIUS_API_KEY is missing! Set it in your environment variables.")
    sys.exit(1)

HELIUS_API_URL = "https://api.helius.xyz/v0"
HELIUS_RPC_URL = "https://mainnet.helius-rpc.com/?api-key=" + HELIUS_API_KEY

def print_response_debug(response, api_name):
    """Helper function to print detailed API response information"""
    print(f"\nDebug info for {api_name}:")
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print("Response Content:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)

def fetch_token_metadata(token_address):
    """Enhanced token metadata fetch using paid Helius API features."""
    try:
        url = f"{HELIUS_API_URL}/token-metadata?api-key={HELIUS_API_KEY}"
        payload = {"mintAccounts": [token_address]}
        response = requests.post(url, json=payload)
        print_response_debug(response, "Token Metadata API")
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                metadata = data[0]
                return {
                    "name": metadata.get("onChainMetadata", {}).get("metadata", {}).get("data", {}).get("name", "Unknown"),
                    "symbol": metadata.get("onChainMetadata", {}).get("metadata", {}).get("data", {}).get("symbol", "Unknown"),
                    "decimals": metadata.get("onChainAccountInfo", {}).get("accountInfo", {}).get("data", {}).get("parsed", {}).get("info", {}).get("decimals", 0),
                    "supply": metadata.get("onChainAccountInfo", {}).get("accountInfo", {}).get("data", {}).get("parsed", {}).get("info", {}).get("supply", "0")
                }
        return None
    except Exception as e:
        print(f"Error fetching token metadata: {str(e)}")
        return None

def fetch_token_holders(token_address, limit=20):
    """Enhanced token holders fetch with RPC API."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "my-id",
            "method": "getTokenLargestAccounts",
            "params": [token_address]
        }
        response = requests.post(HELIUS_RPC_URL, json=payload)
        print_response_debug(response, "Token Holders API")
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data and "value" in data["result"]:
                holders = []
                for holder in data["result"]["value"]:
                    holders.append({
                        "address": holder.get("address"),
                        "amount": holder.get("amount"),
                        "decimals": holder.get("decimals", 0),
                        "uiAmount": holder.get("uiAmount", 0)
                    })
                return holders
        return None
    except Exception as e:
        print(f"Error fetching token holders: {str(e)}")
        return None

def fetch_recent_trades(token_address, limit=10):
    """Enhanced recent trades fetch with RPC API."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "my-id",
            "method": "getSignaturesForAddress",
            "params": [
                token_address,
                {
                    "limit": limit
                }
            ]
        }
        response = requests.post(HELIUS_RPC_URL, json=payload)
        print_response_debug(response, "Recent Trades API")
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                trades = []
                for tx in data["result"]:
                    trade_info = {
                        "signature": tx.get("signature"),
                        "slot": tx.get("slot"),
                        "blockTime": tx.get("blockTime"),
                        "err": tx.get("err")
                    }
                    trades.append(trade_info)
                return trades
        return None
    except Exception as e:
        print(f"Error fetching recent trades: {str(e)}")
        return None

def test_token_metadata():
    print("\nTesting token metadata...")
    metadata = fetch_token_metadata(TEST_TOKEN)
    if metadata:
        print("✅ Token metadata:")
        for key, value in metadata.items():
            print(f"{key}: {value}")
    else:
        print("❌ Failed to fetch token metadata")

def test_token_holders():
    print("\nTesting token holders...")
    holders = fetch_token_holders(TEST_TOKEN)
    if holders:
        print("✅ Top holders:")
        for i, holder in enumerate(holders[:5], 1):
            print(f"{i}. Address: {holder['address']}, Amount: {holder['uiAmount']}")
    else:
        print("❌ Failed to fetch token holders")

def test_recent_trades():
    print("\nTesting recent trades...")
    trades = fetch_recent_trades(TEST_TOKEN)
    if trades:
        print("✅ Recent trades:")
        for i, trade in enumerate(trades[:5], 1):
            timestamp = datetime.fromtimestamp(trade['blockTime']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{i}. Signature: {trade['signature']}, Time: {timestamp}")
    else:
        print("❌ Failed to fetch recent trades")

if __name__ == "__main__":
    print(f"Using Helius API URL: {HELIUS_API_URL}")
    print(f"Using Helius RPC URL: {HELIUS_RPC_URL}")
    print(f"Testing with token: {TEST_TOKEN}")
    test_token_metadata()
    test_token_holders()
    test_recent_trades()
