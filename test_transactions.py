import os
import asyncio
from bot import analyze_recent_transactions

# Set Helius API key for testing
os.environ["HELIUS_API_KEY"] = "ba737b72-acf1-4d55-a893-20fdaf294be9"

async def test_transactions():
    # Test token address
    token_address = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    
    print("\nTesting transaction analysis...")
    analysis = await analyze_recent_transactions(token_address)
    
    if analysis:
        print("\nAnalysis Results:")
        print(f"Total Transactions: {analysis['transaction_count']}")
        print(f"Active Wallets: {analysis['active_wallets']}")
        print(f"Trading Velocity: {analysis['trading_velocity']:.2f} tx/min")
        
        print("\nPatterns:")
        patterns = analysis['patterns']
        for pattern, count in patterns.items():
            print(f"• {pattern}: {count}")
            
        print("\nSuspicious Wallets:")
        suspicious = analysis['suspicious_wallets']
        for wallet, count in suspicious.items():
            print(f"• {wallet[:8]}...: {count} transactions")
            
        print("\nRecent Transactions:")
        recent = analysis['recent_transactions']
        for tx in recent:
            print(f"• {tx['source'][:8]}...: {tx['amount']:.2f} tokens")
    else:
        print("Failed to analyze transactions")

if __name__ == "__main__":
    asyncio.run(test_transactions())
