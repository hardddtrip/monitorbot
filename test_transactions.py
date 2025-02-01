import os
import asyncio
from datetime import datetime
from transaction_analyzer import TransactionAnalyzer

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
        print(f"Total Volume: {analysis['total_volume']:.2f} tokens")
        
        if analysis.get('price_metrics'):
            print("\n=== Price Analysis ===")
            pm = analysis['price_metrics']
            print(f"Price Change: {pm['price_change_pct']:.1f}%")
            print(f"Price Range: {pm['min_price']:.4f} - {pm['max_price']:.4f}")
            print(f"Volatility: {pm['volatility']:.4f}")
        
        print("\n=== Volume Distribution ===")
        vd = analysis['pattern_metrics']['volume_distribution']
        for size, data in vd.items():
            print(f"• {size.replace('_', ' ').title()}: {data['count']} trades ({format_percentage(data['percentage'])})")
        
        print("\n=== Volume by Type ===")
        vt = analysis['pattern_metrics']['volume_by_type']
        for type_, data in vt.items():
            if data['amount'] > 0:
                print(f"• {type_.replace('_', ' ').title()}: {data['amount']:.2f} tokens ({format_percentage(data['percentage'])})")
        
        print("\n=== Pattern Analysis (% of transactions) ===")
        pp = analysis['pattern_metrics']['pattern_percentages']
        for pattern, data in pp.items():
            if data['count'] > 0:
                print(f"• {pattern.replace('_', ' ').title()}: {data['count']} ({format_percentage(data['percentage'])})")
        
        print("\n=== Market Impact ===")
        mi = analysis['market_impact']
        print(f"Average Trade Size: {mi['avg_trade_size']:.2f} tokens")
        print(f"Large TX Impact: {format_percentage(mi['large_tx_impact'])}")
        print(f"Bot Volume: {format_percentage(mi['bot_volume_pct'])}")
        print(f"Flash Loan Volume: {format_percentage(mi['flash_loan_volume_pct'])}")
        
        print("\n=== Suspicious Wallets ===")
        suspicious = analysis['suspicious_wallets']
        for wallet, count in suspicious.items():
            print(f"• {wallet[:8]}...: {count} transactions")
            
        print("\n=== Recent Transactions ===")
        prev_time = None
        for tx in analysis['recent_transactions']:
            tx_time = format_timestamp(tx['timestamp'])
            if prev_time:
                time_diff = prev_time - tx['timestamp']
                print(f"• {tx['source'][:8]}... at {tx_time}: {tx['amount']:.2f} tokens ({tx['type']}) - {time_diff:.1f}s from prev")
            else:
                print(f"• {tx['source'][:8]}... at {tx_time}: {tx['amount']:.2f} tokens ({tx['type']})")
            prev_time = tx['timestamp']
            
        if analysis['recent_transactions']:
            first_tx = min(analysis['recent_transactions'], key=lambda x: x['timestamp'])
            last_tx = max(analysis['recent_transactions'], key=lambda x: x['timestamp'])
            print(f"\nFirst transaction: {format_timestamp(first_tx['timestamp'])}")
            print(f"Last transaction: {format_timestamp(last_tx['timestamp'])}")
            print(f"Time span: {(last_tx['timestamp'] - first_tx['timestamp']):.1f} seconds")
    else:
        print("Failed to analyze transactions")

if __name__ == "__main__":
    asyncio.run(test_transactions())
