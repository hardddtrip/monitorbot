import os
import time
import statistics
from datetime import datetime
import requests
import asyncio

class TransactionAnalyzer:
    def __init__(self, helius_api_key=None):
        """Initialize the transaction analyzer with optional API key."""
        self.api_key = helius_api_key or os.getenv("HELIUS_API_KEY")
        if not self.api_key:
            raise ValueError("Missing HELIUS_API_KEY")
    
    async def fetch_transactions(self, token_address, minutes=5, max_pages=5):
        """Fetch transactions from Helius API with pagination."""
        base_url = f"https://api.helius.xyz/v0/addresses/{token_address}/transactions"
        all_transactions = []
        before_tx = None
        
        for page in range(max_pages):
            url = f"{base_url}?api-key={self.api_key}"
            if before_tx:
                url += f"&before={before_tx}"
            print(f"Fetching transactions page {page + 1} from Helius API")
            
            response = requests.get(url)
            print(f"API Response Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Error response: {response.text}")
                break
                
            transactions = response.json()
            if not transactions:
                break
                
            all_transactions.extend(transactions)
            
            if transactions:
                before_tx = transactions[-1].get('signature')
            
            await asyncio.sleep(0.1)  # Rate limiting
        
        return all_transactions
    
    def _filter_transactions_by_time(self, transactions, minutes):
        """Filter transactions within the specified time window."""
        current_time = int(time.time())
        cutoff_time = current_time - (minutes * 60)
        
        # Debug timestamps
        print(f"Current time: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Cutoff time: {datetime.fromtimestamp(cutoff_time).strftime('%Y-%m-%d %H:%M:%S')}")
        
        filtered_txs = []
        for tx in transactions:
            tx_time = tx.get('timestamp', 0)
            if tx_time > 1600000000000:  # If timestamp is in milliseconds
                tx_time = tx_time / 1000
            tx['timestamp'] = tx_time
            if tx_time >= cutoff_time:
                filtered_txs.append(tx)
        
        return filtered_txs
    
    def _analyze_volume_patterns(self, tx, token_address, patterns, volume_by_type, volume_distribution):
        """Analyze volume-related patterns in a transaction."""
        amount = 0
        token_transfers = tx.get('tokenTransfers', [])
        
        for transfer in token_transfers:
            if transfer.get('mint') == token_address:
                amount = abs(float(transfer.get('tokenAmount', 0)))
                break
        
        if amount > 0:
            # Track volume by type
            if tx.get('type', '') == 'SWAP':
                volume_by_type['swaps'] += amount
            elif 'transfer' in tx.get('description', '').lower():
                volume_by_type['transfers'] += amount
            
            # Track volume distribution
            if amount < 10:
                volume_distribution['very_small'] += 1
            elif amount < 100:
                volume_distribution['small'] += 1
            elif amount < 1000:
                volume_distribution['medium'] += 1
            elif amount < 10000:
                volume_distribution['large'] += 1
            else:
                volume_distribution['very_large'] += 1
        
        return amount
    
    def _analyze_price_impact(self, tx, token_address, price_points, volume_by_type, patterns, amount):
        """Analyze price impact and slippage."""
        if tx.get('type', '') == 'SWAP' and len(tx.get('tokenTransfers', [])) >= 2:
            try:
                token_amount = None
                other_amount = None
                for transfer in tx.get('tokenTransfers', []):
                    if transfer.get('mint') == token_address:
                        token_amount = abs(float(transfer.get('tokenAmount', 0)))
                    else:
                        other_amount = abs(float(transfer.get('tokenAmount', 0)))
                
                if token_amount and other_amount and token_amount > 0:
                    price = other_amount / token_amount
                    price_points.append((tx['timestamp'], price))
                    
                    # Check for high slippage
                    if len(price_points) > 1:
                        prev_price = price_points[-2][1]
                        price_impact = abs(price - prev_price) / prev_price
                        if price_impact > 0.05:  # 5% slippage
                            patterns['high_slippage'] += 1
                            volume_by_type['high_slippage'] += amount
            except Exception as e:
                print(f"Error calculating price: {str(e)}")
    
    def _detect_flash_loans(self, tx, token_transfers, patterns, volume_by_type, amount):
        """Detect flash loan patterns."""
        token_in_out = {}
        for transfer in token_transfers:
            mint = transfer.get('mint')
            amt = float(transfer.get('tokenAmount', 0))
            if mint in token_in_out and abs(token_in_out[mint] + amt) < 0.01:
                patterns['flash_loans'] += 1
                volume_by_type['flash_loans'] += amount
                break
            token_in_out[mint] = token_in_out.get(mint, 0) - amt
    
    async def analyze_transactions(self, token_address, minutes=5):
        """Main method to analyze transactions."""
        try:
            # Fetch and filter transactions
            transactions = await self.fetch_transactions(token_address, minutes)
            transactions = self._filter_transactions_by_time(transactions, minutes)
            
            if not transactions:
                return None
            
            # Initialize metrics
            transaction_count = len(transactions)
            active_wallets = set()
            total_volume = 0
            volume_by_type = {'swaps': 0, 'transfers': 0, 'flash_loans': 0, 'high_slippage': 0, 'bot_trades': 0}
            patterns = {
                'swaps': 0, 'transfers': 0, 'large_transfers': 0, 'multi_transfers': 0,
                'failed': 0, 'rapid_swaps': 0, 'wash_trades': 0, 'sandwich_attacks': 0,
                'flash_loans': 0, 'high_slippage': 0, 'arbitrage': 0, 'bot_trades': 0
            }
            volume_distribution = {
                'very_small': 0, 'small': 0, 'medium': 0, 'large': 0, 'very_large': 0
            }
            
            # Analysis state
            wallet_interactions = {}
            wallet_tx_counts = {}
            wallet_last_swap = {}
            large_swaps = []
            price_points = []
            recent_transactions = []
            
            # Process each transaction
            for tx in transactions:
                source = tx.get('feePayer', '')
                active_wallets.add(source)
                
                # Analyze volume and patterns
                amount = self._analyze_volume_patterns(tx, token_address, patterns, volume_by_type, volume_distribution)
                total_volume += amount
                
                # Analyze price impact
                self._analyze_price_impact(tx, token_address, price_points, volume_by_type, patterns, amount)
                
                # Detect flash loans
                self._detect_flash_loans(tx, tx.get('tokenTransfers', []), patterns, volume_by_type, amount)
                
                # Track bot trading
                if tx.get('type', '') == 'SWAP':
                    patterns['swaps'] += 1
                    if source in wallet_last_swap:
                        time_since_last = tx['timestamp'] - wallet_last_swap[source]
                        if time_since_last < 60:
                            patterns['rapid_swaps'] += 1
                            if time_since_last < 3:
                                patterns['bot_trades'] += 1
                                volume_by_type['bot_trades'] += amount
                    wallet_last_swap[source] = tx['timestamp']
                
                # Track other patterns
                if len(tx.get('tokenTransfers', [])) > 2:
                    patterns['multi_transfers'] += 1
                    if len(set(t.get('mint') for t in tx.get('tokenTransfers', []))) > 2:
                        patterns['arbitrage'] += 1
                
                if amount > 1000:
                    patterns['large_transfers'] += 1
                    large_swaps.append({'timestamp': tx['timestamp'], 'amount': amount, 'source': source})
                
                # Track wallet activity
                if source not in wallet_interactions:
                    wallet_interactions[source] = []
                wallet_interactions[source].append({
                    'timestamp': tx['timestamp'],
                    'amount': amount,
                    'type': tx.get('type', '')
                })
                wallet_tx_counts[source] = wallet_tx_counts.get(source, 0) + 1
                
                # Track recent transactions
                recent_transactions.append({
                    'type': tx.get('type', '').lower(),
                    'description': tx.get('description', ''),
                    'amount': amount,
                    'timestamp': tx['timestamp'],
                    'source': source,
                    'success': tx.get('transactionError') is None
                })
            
            # Post-process analysis
            recent_transactions.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Detect sandwich attacks
            if len(large_swaps) >= 2:
                for i in range(len(large_swaps) - 1):
                    if large_swaps[i+1]['timestamp'] - large_swaps[i]['timestamp'] < 60:
                        patterns['sandwich_attacks'] += 1
            
            # Detect wash trading
            for wallet, txs in wallet_interactions.items():
                if len(txs) >= 3 and txs[-1]['timestamp'] - txs[0]['timestamp'] < 300:
                    patterns['wash_trades'] += 1
            
            # Calculate metrics
            trading_velocity = transaction_count / minutes
            suspicious_wallets = dict(sorted(wallet_tx_counts.items(), key=lambda x: x[1], reverse=True)[:5])
            
            # Calculate price metrics
            price_metrics = {}
            if price_points:
                price_points.sort(key=lambda x: x[0])
                prices = [p[1] for p in price_points]
                price_metrics = {
                    'start_price': price_points[0][1],
                    'end_price': price_points[-1][1],
                    'price_change_pct': ((price_points[-1][1] - price_points[0][1]) / price_points[0][1]) * 100,
                    'volatility': statistics.stdev(prices) if len(prices) > 1 else 0,
                    'min_price': min(prices),
                    'max_price': max(prices)
                }
            
            # Calculate pattern metrics
            pattern_metrics = {
                'volume_distribution': {
                    k: {'count': v, 'percentage': (v / transaction_count * 100) if transaction_count > 0 else 0}
                    for k, v in volume_distribution.items()
                },
                'volume_by_type': {
                    k: {'amount': v, 'percentage': (v / total_volume * 100) if total_volume > 0 else 0}
                    for k, v in volume_by_type.items()
                },
                'pattern_percentages': {
                    k: {'count': v, 'percentage': (v / transaction_count * 100) if transaction_count > 0 else 0}
                    for k, v in patterns.items()
                }
            }
            
            # Calculate market impact
            market_impact = {
                'avg_trade_size': total_volume / transaction_count if transaction_count > 0 else 0,
                'large_tx_impact': sum(1 for tx in transactions if tx.get('amount', 0) > 1000) / transaction_count * 100 if transaction_count > 0 else 0,
                'bot_volume_pct': volume_by_type['bot_trades'] / total_volume * 100 if total_volume > 0 else 0,
                'flash_loan_volume_pct': volume_by_type['flash_loans'] / total_volume * 100 if total_volume > 0 else 0
            }
            
            return {
                'transaction_count': transaction_count,
                'active_wallets': len(active_wallets),
                'trading_velocity': trading_velocity,
                'total_volume': total_volume,
                'patterns': patterns,
                'suspicious_wallets': suspicious_wallets,
                'recent_transactions': recent_transactions[:5],
                'price_metrics': price_metrics,
                'pattern_metrics': pattern_metrics,
                'market_impact': market_impact
            }
            
        except Exception as e:
            print(f"Error analyzing transactions: {str(e)}")
            return None
