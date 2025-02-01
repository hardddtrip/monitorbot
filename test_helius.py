import os
import json
import requests
from datetime import datetime
import time

# Load environment variables
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
if not HELIUS_API_KEY:
    raise ValueError("HELIUS_API_KEY is missing! Set it in your environment variables.")

# Test token address
TOKEN_ADDRESS = "EfgEGG9PxLhyk1wqtqgGnwgfVC7JYic3vC9BCWLvpump"
HELIUS_API_URL = "https://api.helius.xyz/v0"

def test_token_metadata():
    """Test fetching token metadata."""
    print(f"\nTesting token metadata for {TOKEN_ADDRESS}")
    
    try:
        url = f"{HELIUS_API_URL}/token-metadata?api-key={HELIUS_API_KEY}"
        payload = {"mintAccounts": [TOKEN_ADDRESS]}
        
        print("\nMaking API request...")
        response = requests.post(url, json=payload)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nRaw response:")
            print(json.dumps(data, indent=2))
            
            if data and len(data) > 0:
                metadata = data[0]
                if metadata:
                    account_info = metadata.get("onChainAccountInfo", {}).get("accountInfo", {})
                    token_info = account_info.get("data", {}).get("parsed", {}).get("info", {})
                    
                    parsed_metadata = {
                        "name": "EGG Token",
                        "symbol": "EGG",
                        "decimals": token_info.get("decimals", 0),
                        "supply": token_info.get("supply", "0"),
                        "image": "",
                        "description": "EGG Token on Solana"
                    }
                    print("\nParsed metadata:")
                    print(json.dumps(parsed_metadata, indent=2))
                else:
                    print("Metadata object is None")
            else:
                print("No metadata found in response")
        else:
            print(f"Error response: {response.text}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

def test_recent_trades():
    """Test fetching recent trades using DAS API."""
    print(f"\nTesting recent trades for {TOKEN_ADDRESS}")
    
    try:
        url = f"https://api.helius.xyz/v0/addresses/{TOKEN_ADDRESS}/transactions"
        
        params = {
            "api-key": HELIUS_API_KEY,
            "type": "SWAP"  # Only get swap transactions
        }
        
        print("\nMaking API request...")
        response = requests.get(url, params=params)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nRaw response:")
            print(json.dumps(data[:5], indent=2))  # Show first 5 transactions
            
            if data:
                print("\nParsing trades...")
                for tx in data[:10]:  # Look at first 10 transactions
                    timestamp = datetime.fromtimestamp(tx.get("timestamp", 0))
                    sig = tx.get("signature", "Unknown")
                    
                    print(f"\nTransaction at {timestamp}:")
                    print(f"Signature: {sig}")
                    
                    if "tokenTransfers" in tx:
                        for transfer in tx.get("tokenTransfers", []):
                            if transfer.get("mint") == TOKEN_ADDRESS:
                                amount = float(transfer.get("tokenAmount", 0)) / (10 ** 6)  # Convert to EGG
                                from_acc = transfer.get("fromUserAccount", "Unknown")
                                to_acc = transfer.get("toUserAccount", "Unknown")
                                
                                print(f"Amount: {amount:,.2f} EGG")
                                print(f"From: {from_acc}")
                                print(f"To: {to_acc}")
            else:
                print("No trades found")
        else:
            print(f"Error response: {response.text}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    test_token_metadata()
    test_recent_trades()
