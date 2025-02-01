import os
import asyncio
from datetime import datetime
from transaction_analyzer import TransactionAnalyzer
from collections import defaultdict

# Set Helius API key for testing
os.environ["HELIUS_API_KEY"] = "ba737b72-acf1-4d55-a893-20fdaf294be9"

def format_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def format_percentage(value):
    return f"{value:.1f}%" if value is not None else "N/A"

async def test_transactions():
    # Test token address
    token_address = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    minutes = 5
    
    print(f"\nTesting transaction analysis for last {minutes} minutes...")
    
    analyzer = TransactionAnalyzer()
    analysis = await analyzer.analyze_transactions(token_address, minutes)
    
    if analysis:
        print("\n=== Transaction Overview ===")
        print(f"Total Transactions: {analysis['transaction_count']}")
        print(f"Active Wallets: {analysis['active_wallets']}")
        print(f"Trading Velocity: {analysis['trading_velocity']:.2f} tx/min")
        print(f"Total Volume: {analysis['total_volume']:.2f} SOL")
        
        print("\n=== Volume Distribution ===")
        total_tx = analysis['transaction_count']
        vd = analysis['volume_distribution']
        
        def print_volume_category(name, data, total_tx):
            print(f"• {name}: {data['count']} trades ({data['count']/total_tx*100:.1f}%)")
            print(f"  Volume: {data['amount']:.2f} SOL")
            
        print_volume_category("Very Small (<0.1 SOL)", vd['very_small'], total_tx)
        print_volume_category("Small (0.1-1 SOL)", vd['small'], total_tx)
        print_volume_category("Medium (1-10 SOL)", vd['medium'], total_tx)
        print_volume_category("Large (10-100 SOL)", vd['large'], total_tx)
        print_volume_category("Very Large (>100 SOL)", vd['very_large'], total_tx)

        print("\n=== Trader Categories ===")
        tc = analysis['trader_categories']
        
        def print_category(name, data):
            total = data['buys'] + data['sells']
            if total > 0:
                buy_pct = (data['buys'] / total * 100) if total > 0 else 0
                sell_pct = (data['sells'] / total * 100) if total > 0 else 0
                tx_count = sum(1 for tx in data.get('transactions', []))
                print(f"{name}:")
                print(f"• Wallets: {data['count']}")
                print(f"• Transactions: {tx_count}")
                print(f"• Volume: {data['volume']:.2f} SOL")
                print(f"• Buy/Sell: {buy_pct:.1f}% / {sell_pct:.1f}%")
                print()

        print_category("Large Market Makers", tc['large_market_maker'])
        print_category("Market Making Bots", tc['market_making_bot'])
        print_category("Sniper Bots", tc['sniper_bot'])
        print_category("Whales", tc['whale'])
        print_category("Retail Traders", tc['retail'])

        print("\n=== Top Wallets by Volume ===")
        wallet_volumes = defaultdict(float)
        wallet_txs = defaultdict(int)
        wallet_buys = defaultdict(float)
        wallet_sells = defaultdict(float)
        
        for category in tc.values():
            for tx in category.get('transactions', []):
                wallet = tx.get('wallet', 'unknown')
                wallet_volumes[wallet] += tx['amount']
                wallet_txs[wallet] += 1
                if tx['is_buy']:
                    wallet_buys[wallet] += tx['amount']
                else:
                    wallet_sells[wallet] += tx['amount']
        
        top_by_volume = sorted(wallet_volumes.items(), key=lambda x: x[1], reverse=True)[:10]
        for wallet, volume in top_by_volume:
            total = wallet_buys[wallet] + wallet_sells[wallet]
            buy_pct = (wallet_buys[wallet] / total * 100) if total > 0 else 0
            sell_pct = (wallet_sells[wallet] / total * 100) if total > 0 else 0
            print(f"• {wallet[:8]}...")
            print(f"  - Volume: {volume:.2f} SOL")
            print(f"  - Transactions: {wallet_txs[wallet]}")
            print(f"  - Buy/Sell: {buy_pct:.1f}% / {sell_pct:.1f}%")
            print()

        print("\n=== Top Wallets by Transaction Count ===")
        top_by_txs = sorted(wallet_txs.items(), key=lambda x: x[1], reverse=True)[:10]
        for wallet, tx_count in top_by_txs:
            volume = wallet_volumes[wallet]
            total = wallet_buys[wallet] + wallet_sells[wallet]
            buy_pct = (wallet_buys[wallet] / total * 100) if total > 0 else 0
            sell_pct = (wallet_sells[wallet] / total * 100) if total > 0 else 0
            print(f"• {wallet[:8]}...")
            print(f"  - Transactions: {tx_count}")
            print(f"  - Volume: {volume:.2f} SOL")
            print(f"  - Buy/Sell: {buy_pct:.1f}% / {sell_pct:.1f}%")
            print()

        print("\n=== Suspicious Wallets ===")
        for wallet, tx_count in analysis['suspicious_wallets'].items():
            print(f"• {wallet[:8]}...: {tx_count} transactions")
        
        print()  
    else:
        print("Failed to analyze transactions")

if __name__ == "__main__":
    asyncio.run(test_transactions())
