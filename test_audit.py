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

# Set Helius API key for testing
os.environ["HELIUS_API_KEY"] = "ba737b72-acf1-4d55-a893-20fdaf294be9"

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

def analyze_recent_transactions(token_address):
    """Analyze recent transactions"""
    try:
        # Simulate transaction analysis with more patterns
        analysis = {
            "transaction_count": 150,
            "active_wallets": 75,
            "trading_velocity": 10.0,  # 10 transactions per minute
            "patterns": {
                "swaps": 50,
                "transfers": 30,
                "large_transfers": 5,
                "multi_transfers": 10,
                "failed": 8,
                "rapid_swaps": 15,
                "wash_trades": 5,
                "sandwich_attacks": 2,
                "flash_loans": 3,
                "high_slippage": 12,
                "arbitrage": 8,
                "bot_trades": 20
            },
            "suspicious_wallets": {
                "wallet1": 15,
                "wallet2": 12,
                "wallet3": 10,
                "wallet4": 8,
                "wallet5": 7
            },
            "suspicious_pairs": {
                "wallet1:wallet2": 8,
                "wallet3:wallet4": 6,
                "wallet2:wallet5": 5
            },
            "unusual_activity": [
                {"type": "Large Swap", "amount": "$50,000.00", "wallet": "wallet1", "timestamp": 1643723400},
                {"type": "Flash Loan", "amount": "$100,000.00", "wallet": "wallet2", "timestamp": 1643723500},
                {"type": "High Slippage", "amount": "8.5%", "wallet": "wallet3", "timestamp": 1643723600},
                {"type": "Sandwich Attack", "amount": "$25,000.00", "wallet": "wallet4", "timestamp": 1643723700},
                {"type": "Rapid Swaps", "count": "10 in 1min", "wallet": "wallet5", "timestamp": 1643723800}
            ],
            "recent_transactions": [
                {"type": "swap", "description": "Large swap", "wallet": "wallet1", "destination": "wallet2", "amount_usd": 50000, "timestamp": 1643723900, "successful": True},
                {"type": "flash_loan", "description": "Flash loan", "wallet": "wallet2", "destination": "wallet2", "amount_usd": 100000, "timestamp": 1643724000, "successful": True},
                {"type": "swap", "description": "High slippage swap", "wallet": "wallet3", "destination": "wallet4", "amount_usd": 10000, "timestamp": 1643724100, "successful": True},
                {"type": "sandwich", "description": "Sandwich attack", "wallet": "wallet4", "destination": "wallet5", "amount_usd": 25000, "timestamp": 1643724200, "successful": True},
                {"type": "rapid_swap", "description": "Bot trading", "wallet": "wallet5", "destination": "wallet1", "amount_usd": 5000, "timestamp": 1643724300, "successful": True}
            ],
            "pattern_summary": {
                "bot_activity": 0.40,      # 40% of swaps are from bots
                "wash_trading": 0.033,     # 3.3% of transactions are wash trades
                "failed_ratio": 0.053,     # 5.3% of transactions failed
                "large_trade_ratio": 0.053 # 5.3% are large trades or flash loans
            }
        }
        return analysis
        
    except Exception as e:
        logging.error(f"Error analyzing transactions: {str(e)}")
        return None

def test_token(token_address):
    """Test comprehensive token data fetching"""
    print("\n=== Testing Token Data Fetching ===")
    print(f"Token: {token_address}")
    
    # 1. Test Helius Data
    print("\n--- Helius Data ---")
    helius_data = fetch_token_metadata(token_address)
    if helius_data:
        print("\nBasic Token Info:")
        print(f"• Name: {helius_data.get('name')}")
        print(f"• Symbol: {helius_data.get('symbol')}")
        print(f"• Description: {helius_data.get('description')}")
        print(f"• Decimals: {helius_data.get('decimals')}")
        print(f"• Supply: {float(helius_data.get('supply', 0))/(10**helius_data.get('decimals', 0)) if helius_data.get('supply') and helius_data.get('decimals') else 0:,.0f}")
        
        print("\nToken Standard:")
        print(f"• Standard: {helius_data.get('token_standard')}")
        
        print("\nAuthority Info:")
        print(f"• Mint Authority: {helius_data.get('mintAuthority')}")
        print(f"• Freeze Authority: {helius_data.get('freezeAuthority')}")
        
        print("\nHolder Info:")
        print(f"• Total Holders: {helius_data.get('holder_count', 0):,}")
        
        print("\nCreator Info:")
        creators = helius_data.get('creators', [])
        if creators:
            for idx, creator in enumerate(creators, 1):
                print(f"• Creator {idx}:")
                print(f"  - Address: {creator.get('address')}")
                print(f"  - Share: {creator.get('share')}%")
                print(f"  - Verified: {creator.get('verified', False)}")
        
        print("\nRoyalties:")
        print(f"• Percentage: {helius_data.get('royalties')}%")
        
        print("\nCollection:")
        print(f"• Collection: {helius_data.get('collection')}")
        
        print("\nExternal Links:")
        print(f"• Image: {helius_data.get('image')}")
        print(f"• Website: {helius_data.get('external_url')}")
        
        print("\nAttributes:")
        attributes = helius_data.get('attributes', [])
        if attributes:
            for attr in attributes:
                print(f"• {attr.get('trait_type')}: {attr.get('value')}")
    else:
        print("Failed to fetch Helius data")
    
    # 2. Test DexScreener Data
    print("\n--- DexScreener Data ---")
    dex_data = fetch_token_data(token_address)
    if dex_data:
        print("\nBasic Pair Info:")
        print(f"• Chain ID: {dex_data.get('chainId')}")
        print(f"• DEX ID: {dex_data.get('dexId')}")
        print(f"• Pair Address: {dex_data.get('pairAddress')}")
        print(f"• Pair Created At: {datetime.fromtimestamp(int(dex_data.get('pairCreatedAt', 0)/1000)).strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\nPrice Info:")
        print(f"• Price USD: ${float(dex_data.get('priceUsd', 0)):.6f}")
        print(f"• Price Native: {dex_data.get('priceNative')}")
        
        print("\nVolume Info:")
        volume = dex_data.get('volume', {})
        print(f"• Volume 24h: ${float(volume.get('h24', 0)):,.2f}")
        print(f"• Volume 5m: ${float(volume.get('m5', 0)):,.2f}")
        print(f"• Volume 1h: ${float(volume.get('h1', 0)):,.2f}")
        
        print("\nLiquidity Info:")
        liquidity = dex_data.get('liquidity', {})
        print(f"• Liquidity USD: ${float(liquidity.get('usd', 0)):,.2f}")
        print(f"• Liquidity Base: {liquidity.get('base')}")
        print(f"• Liquidity Quote: {liquidity.get('quote')}")
        
        print("\nPrice Changes:")
        price_change = dex_data.get('priceChange', {})
        print(f"• 5m: {price_change.get('m5', 0):+.2f}%")
        print(f"• 1h: {price_change.get('h1', 0):+.2f}%")
        print(f"• 6h: {price_change.get('h6', 0):+.2f}%")
        print(f"• 24h: {price_change.get('h24', 0):+.2f}%")
        print(f"• 7d: {price_change.get('d7', 0):+.2f}%")
        
        print("\nTransaction Counts:")
        txns = dex_data.get('txns', {})
        h24 = txns.get('h24', {})
        h1 = txns.get('h1', {})
        print(f"• 24h Buys: {h24.get('buys', 0)}")
        print(f"• 24h Sells: {h24.get('sells', 0)}")
        print(f"• 1h Buys: {h1.get('buys', 0)}")
        print(f"• 1h Sells: {h1.get('sells', 0)}")
        
        print("\nSocial Links:")
        info = dex_data.get('info', {})
        for social in info.get('socials', []):
            print(f"• {social.get('type')}: {social.get('url')}")
            
        print("\nWebsites:")
        for website in info.get('websites', []):
            print(f"• {website.get('url')}")
    else:
        print("Failed to fetch DexScreener data")

def test_transactions(token_address):
    """Test transaction analysis"""
    print("\n=== Testing Transaction Analysis ===")
    print(f"Token: {token_address}\n")
    
    analysis = analyze_recent_transactions(token_address)
    if not analysis:
        print("❌ Failed to analyze transactions")
        return
        
    print("--- Transaction Overview ---")
    print(f"Total Transactions: {analysis['transaction_count']}")
    print(f"Active Wallets: {analysis['active_wallets']}")
    print(f"Trading Velocity: {analysis['trading_velocity']:.1f} tx/min\n")
    
    print("--- Transaction Patterns ---")
    patterns = analysis['patterns']
    print(f"Basic Patterns:")
    print(f"• Swaps: {patterns['swaps']}")
    print(f"• Transfers: {patterns['transfers']}")
    print(f"• Failed Transactions: {patterns['failed']}\n")
    
    print(f"Advanced Patterns:")
    print(f"• Rapid Swaps: {patterns['rapid_swaps']}")
    print(f"• Bot Trades: {patterns['bot_trades']}")
    print(f"• Wash Trades: {patterns['wash_trades']}")
    print(f"• Sandwich Attacks: {patterns['sandwich_attacks']}")
    print(f"• Flash Loans: {patterns['flash_loans']}")
    print(f"• High Slippage: {patterns['high_slippage']}")
    print(f"• Arbitrage: {patterns['arbitrage']}\n")
    
    print("--- Risk Metrics ---")
    summary = analysis['pattern_summary']
    print(f"• Bot Activity: {summary['bot_activity']*100:.1f}%")
    print(f"• Wash Trading: {summary['wash_trading']*100:.1f}%")
    print(f"• Failed Transaction Ratio: {summary['failed_ratio']*100:.1f}%")
    print(f"• Large Trade Ratio: {summary['large_trade_ratio']*100:.1f}%\n")
    
    if analysis['suspicious_wallets']:
        print("--- Suspicious Wallets ---")
        for wallet, count in analysis['suspicious_wallets'].items():
            print(f"• {wallet[:8]}...{wallet[-4:]}: {count} transactions")
        print()
        
    if analysis['suspicious_pairs']:
        print("--- Suspicious Trading Pairs ---")
        for pair, count in analysis['suspicious_pairs'].items():
            w1, w2 = pair.split(":")
            print(f"• {w1[:6]}.. ↔️ {w2[-6:]}: {count} interactions")
        print()
        
    if analysis['unusual_activity']:
        print("--- Unusual Activity ---")
        for activity in analysis['unusual_activity']:
            print(f"• {activity['type']}: {activity.get('amount') or activity.get('fee')}")
            print(f"  Wallet: {activity['wallet'][:8]}...{activity['wallet'][-4:]}")
            print(f"  Time: {datetime.fromtimestamp(activity['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
    print("--- Recent Transactions ---")
    for tx in analysis['recent_transactions']:
        print(f"• Type: {tx['type']}")
        print(f"  Description: {tx['description']}")
        print(f"  From: {tx['wallet'][:8]}...{tx['wallet'][-4:]}")
        print(f"  To: {tx['destination'][:8]}...{tx['destination'][-4:]}")
        print(f"  Amount: ${tx['amount_usd']:,.2f}")
        print(f"  Time: {datetime.fromtimestamp(tx['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Status: {'✅' if tx['successful'] else '❌'}\n")

def test_helius_api(token_address):
    """Test different Helius API endpoints to find the correct one"""
    HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
    if not HELIUS_API_KEY:
        logging.error("HELIUS_API_KEY not found")
        return
        
    # Test endpoints
    endpoints = [
        {
            "name": "Enhanced Transactions API v1",
            "url": f"https://api.helius.xyz/v0/transactions?api-key={HELIUS_API_KEY}",
            "method": "POST",
            "payload": {
                "query": {
                    "accounts": [token_address],
                    "startSlot": 0,
                    "limit": 5
                }
            }
        },
        {
            "name": "Address History API",
            "url": f"https://api.helius.xyz/v0/addresses/{token_address}/transactions?api-key={HELIUS_API_KEY}",
            "method": "GET"
        },
        {
            "name": "Raw Transaction API",
            "url": f"https://api.helius.xyz/v0/raw-transactions?api-key={HELIUS_API_KEY}",
            "method": "POST",
            "payload": {
                "query": {
                    "accounts": [token_address],
                    "startSlot": 0,
                    "limit": 5
                }
            }
        },
        {
            "name": "Parsed Transaction History API",
            "url": f"https://api.helius.xyz/v0/addresses/{token_address}/parsed-transactions?api-key={HELIUS_API_KEY}",
            "method": "GET"
        }
    ]
    
    print("\n=== Testing Helius API Endpoints ===")
    for endpoint in endpoints:
        print(f"\nTesting {endpoint['name']}...")
        print(f"URL: {endpoint['url']}")
        print(f"Method: {endpoint['method']}")
        
        try:
            if endpoint['method'] == 'POST':
                print(f"Payload: {json.dumps(endpoint['payload'], indent=2)}")
                response = requests.post(endpoint['url'], json=endpoint['payload'])
            else:
                response = requests.get(endpoint['url'])
                
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("Success! Sample response:")
                print(json.dumps(data[:2] if isinstance(data, list) else data, indent=2))
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Error testing endpoint: {str(e)}")

if __name__ == "__main__":
    # Test token data fetching
    token_address = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    
    print("\n=== Testing Token Data Fetching ===")
    test_token(token_address)
    
    print("\n=== Testing Helius API Endpoints ===")
    test_helius_api(token_address)
    
    print("\n=== Testing Transaction Analysis ===")
    test_transactions(token_address)
