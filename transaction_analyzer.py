import os
import time
import statistics
from datetime import datetime
import requests
import asyncio
import json
from collections import defaultdict

class TransactionAnalyzer:
    # Static cache for all instances
    CACHE_TTL = 60  # Cache TTL in seconds
    CACHE_DIR = "/tmp/transaction_cache"
    
    def __init__(self, helius_api_key=None):
        """Initialize the transaction analyzer with optional API key."""
        self.api_key = helius_api_key or os.getenv("HELIUS_API_KEY")
        if not self.api_key:
            raise ValueError("Missing HELIUS_API_KEY")
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.CACHE_DIR, exist_ok=True)
    
    def _get_cache_path(self, token_address):
        """Get cache file path for a token address."""
        return os.path.join(self.CACHE_DIR, f"{token_address}.json")
    
    def _get_cached_transactions(self, token_address, cutoff_time):
        """Get cached transactions that are still valid."""
        cache_path = self._get_cache_path(token_address)
        if not os.path.exists(cache_path):
            return None
            
        # Check if cache is expired
        if time.time() - os.path.getmtime(cache_path) > self.CACHE_TTL:
            os.remove(cache_path)
            return None
            
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
                
            # Filter transactions by time
            cached_txs = [tx for tx in cached_data 
                         if self._get_tx_time(tx) >= cutoff_time]
            if cached_txs:
                print("Using cached transactions")
                return cached_txs
        except Exception as e:
            print(f"Error reading cache: {e}")
            
        return None
    
    def _cache_transactions(self, token_address, transactions):
        """Cache transactions for future use."""
        cache_path = self._get_cache_path(token_address)
        try:
            with open(cache_path, 'w') as f:
                json.dump(transactions, f)
        except Exception as e:
            print(f"Error writing cache: {e}")
    
    @staticmethod
    def _get_tx_time(tx):
        """Get transaction timestamp in seconds."""
        tx_time = tx.get('timestamp', 0)
        if tx_time > 1600000000000:  # If timestamp is in milliseconds
            tx_time = tx_time / 1000
        return tx_time
    
    async def fetch_transactions(self, token_address, minutes=5):
        """Fetch transactions from Helius API with caching and optimizations."""
        cutoff_time = time.time() - (minutes * 60)
        
        # Check cache first
        cached_txs = self._get_cached_transactions(token_address, cutoff_time)
        if cached_txs:
            print("Using cached transactions")
            return cached_txs
        
        base_url = f"https://api.helius.xyz/v0/addresses/{token_address}/transactions"
        all_transactions = []
        before_tx = None
        max_iterations = 10  # Limit maximum API calls
        iteration = 0
        
        while iteration < max_iterations:
            # Use optimized query parameters
            url = f"{base_url}?api-key={self.api_key}&commitment=finalized&maxVersion=0&limit=100"
            if before_tx:
                url += f"&before={before_tx}"
            
            print(f"Fetching transactions from Helius API (page {iteration + 1}/{max_iterations})")
            response = requests.get(url)
            print(f"API Response Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Error response: {response.text}")
                break
                
            transactions = response.json()
            if not transactions:
                break
            
            # Check the last transaction's time
            last_tx_time = self._get_tx_time(transactions[-1])
            if last_tx_time < cutoff_time:
                # Add only transactions within our time window
                valid_txs = [tx for tx in transactions 
                           if self._get_tx_time(tx) >= cutoff_time]
                all_transactions.extend(valid_txs)
                break
            
            all_transactions.extend(transactions)
            
            # Stop if we have enough transactions
            # Assuming max 20 tx/min as a reasonable limit
            if len(all_transactions) >= minutes * 20:
                break
            
            before_tx = transactions[-1].get('signature')
            iteration += 1
            
            await asyncio.sleep(0.2)  # Increased rate limiting
        
        # Cache the results
        if all_transactions:
            self._cache_transactions(token_address, all_transactions)
            print(f"Fetched {len(all_transactions)} transactions")
        
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
    
    def _get_token_price(self, token_address):
        """Get current token price in USD from DexScreener."""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get('pairs'):
                    # Get the first Solana pair
                    for pair in data['pairs']:
                        if pair.get('chainId') == 'solana':
                            return float(pair.get('priceUsd', 0))
            return 0
        except Exception as e:
            print(f"Error fetching token price: {e}")
            return 0

    def _get_transaction_value(self, tx, token_address):
        """Get the SOL or USD value from the transaction."""
        amount = 0
        is_sol_value = False
        token_transfers = tx.get('tokenTransfers', [])
        native_transfers = tx.get('nativeTransfers', [])

        # Check if it's a swap
        if tx.get('type') == 'SWAP':
            token_amount = 0
            sol_amount = 0
            other_token_amount = 0
            other_token_mint = None

            # Get token amount
            for transfer in token_transfers:
                if transfer.get('mint') == token_address:
                    token_amount = abs(float(transfer.get('tokenAmount', 0)))
                else:
                    other_token_amount = abs(float(transfer.get('tokenAmount', 0)))
                    other_token_mint = transfer.get('mint')

            # Check for SOL transfers
            for transfer in native_transfers:
                sol_amount += abs(float(transfer.get('amount', 0))) / 1e9  # Convert lamports to SOL

            if sol_amount > 0:
                amount = sol_amount
                is_sol_value = True
            elif other_token_amount > 0 and other_token_mint:
                # TODO: If needed, we could add USDC/USDT detection here
                amount = token_amount
                is_sol_value = False

        # Check for direct SOL transfers
        elif native_transfers:
            total_sol = sum(abs(float(transfer.get('amount', 0))) for transfer in native_transfers) / 1e9
            if total_sol > 0:
                amount = total_sol
                is_sol_value = True

        # Check for token transfers
        else:
            for transfer in token_transfers:
                if transfer.get('mint') == token_address:
                    amount = abs(float(transfer.get('tokenAmount', 0)))
                    break

        return amount, is_sol_value

    def _analyze_volume_patterns(self, tx, token_address, patterns, volume_by_type, volume_distribution):
        """Analyze volume-related patterns in a transaction."""
        amount, is_sol_value = self._get_transaction_value(tx, token_address)
        
        if amount > 0:
            # Track volume by type
            tx_type = tx.get('type', '')
            if tx_type == 'SWAP':
                volume_by_type['swaps']['amount'] += amount
                volume_by_type['swaps']['count'] += 1
            elif 'transfer' in tx.get('description', '').lower():
                volume_by_type['transfers']['amount'] += amount
                volume_by_type['transfers']['count'] += 1
            
            # Track volume distribution based on SOL value
            if is_sol_value:
                if amount < 0.1:  # < 0.1 SOL
                    volume_distribution['very_small']['count'] += 1
                    volume_distribution['very_small']['amount'] += amount
                elif amount < 1:  # 0.1 - 1 SOL
                    volume_distribution['small']['count'] += 1
                    volume_distribution['small']['amount'] += amount
                elif amount < 10:  # 1 - 10 SOL
                    volume_distribution['medium']['count'] += 1
                    volume_distribution['medium']['amount'] += amount
                elif amount < 100:  # 10 - 100 SOL
                    volume_distribution['large']['count'] += 1
                    volume_distribution['large']['amount'] += amount
                else:  # > 100 SOL
                    volume_distribution['very_large']['count'] += 1
                    volume_distribution['very_large']['amount'] += amount
            else:
                # Fallback to token amounts if no SOL value
                if amount < 100:
                    volume_distribution['very_small']['count'] += 1
                    volume_distribution['very_small']['amount'] += amount
                elif amount < 1000:
                    volume_distribution['small']['count'] += 1
                    volume_distribution['small']['amount'] += amount
                elif amount < 10000:
                    volume_distribution['medium']['count'] += 1
                    volume_distribution['medium']['amount'] += amount
                elif amount < 100000:
                    volume_distribution['large']['count'] += 1
                    volume_distribution['large']['amount'] += amount
                else:
                    volume_distribution['very_large']['count'] += 1
                    volume_distribution['very_large']['amount'] += amount
        
        return amount, is_sol_value

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
                            patterns['high_slippage']['count'] += 1
                            patterns['high_slippage']['amount'] += amount
                            volume_by_type['high_slippage']['amount'] += amount
                            volume_by_type['high_slippage']['count'] += 1
            except Exception as e:
                print(f"Error calculating price: {str(e)}")
    
    def _detect_flash_loans(self, tx, token_transfers, patterns, volume_by_type, amount):
        """Detect flash loan patterns."""
        token_in_out = {}
        for transfer in token_transfers:
            mint = transfer.get('mint')
            amt = float(transfer.get('tokenAmount', 0))
            if mint in token_in_out and abs(token_in_out[mint] + amt) < 0.01:
                patterns['flash_loans']['count'] += 1
                patterns['flash_loans']['amount'] += amount
                volume_by_type['flash_loans']['amount'] += amount
                volume_by_type['flash_loans']['count'] += 1
                break
            token_in_out[mint] = token_in_out.get(mint, 0) - amt
    
    def _categorize_trader(self, tx_history):
        """Categorize trader based on their transaction history."""
        total_volume = sum(tx['amount'] for tx in tx_history)
        avg_time_between_trades = 0
        if len(tx_history) > 1:
            times = [tx['timestamp'] for tx in tx_history]
            times.sort()
            time_diffs = [times[i+1] - times[i] for i in range(len(times)-1)]
            avg_time_between_trades = sum(time_diffs) / len(time_diffs)

        # Count specific patterns
        rapid_trades = sum(1 for tx in tx_history if tx.get('is_rapid', False))
        flash_loans = sum(1 for tx in tx_history if tx.get('is_flash_loan', False))
        high_slippage = sum(1 for tx in tx_history if tx.get('is_high_slippage', False))
        large_trades = sum(1 for tx in tx_history if tx['amount'] > 10)  # >10 SOL

        # Market Maker characteristics
        if len(tx_history) > 50 and avg_time_between_trades < 60:
            if rapid_trades / len(tx_history) > 0.8:
                return "market_making_bot"
            return "large_market_maker"

        # Sniper Bot characteristics
        if rapid_trades > 0 and flash_loans > 0 and high_slippage / len(tx_history) > 0.3:
            return "sniper_bot"

        # Whale characteristics
        if total_volume > 100 and large_trades / len(tx_history) > 0.5:
            return "whale"

        # Default to retail
        return "retail"

    async def analyze_transactions(self, token_address, minutes=5):
        """Main method to analyze transactions."""
        try:
            # Initialize metrics
            trader_categories = {
                'large_market_maker': {'buys': 0, 'sells': 0, 'volume': 0, 'count': 0, 'transactions': []},
                'market_making_bot': {'buys': 0, 'sells': 0, 'volume': 0, 'count': 0, 'transactions': []},
                'sniper_bot': {'buys': 0, 'sells': 0, 'volume': 0, 'count': 0, 'transactions': []},
                'whale': {'buys': 0, 'sells': 0, 'volume': 0, 'count': 0, 'transactions': []},
                'retail': {'buys': 0, 'sells': 0, 'volume': 0, 'count': 0, 'transactions': []}
            }
            
            # Track wallet history and price points
            wallet_history = defaultdict(list)
            price_points = []
            volume_distribution = {
                'very_small': {'count': 0, 'amount': 0},  # < 0.1 SOL
                'small': {'count': 0, 'amount': 0},       # 0.1 - 1 SOL
                'medium': {'count': 0, 'amount': 0},      # 1 - 10 SOL
                'large': {'count': 0, 'amount': 0},       # 10 - 100 SOL
                'very_large': {'count': 0, 'amount': 0}   # > 100 SOL
            }
            
            # Fetch and process transactions
            transactions = await self.fetch_transactions(token_address, minutes)
            
            if not transactions:
                return None
            
            # First pass: collect wallet history
            for tx in transactions:
                # Get the actual wallet address from the transaction
                source = None
                
                # Try to get the wallet from native transfers first
                for transfer in tx.get('nativeTransfers', []):
                    if transfer.get('fromUserAccount'):
                        source = transfer['fromUserAccount']
                        break
                
                # If no native transfer, try token transfers
                if not source:
                    for transfer in tx.get('tokenTransfers', []):
                        if transfer.get('fromUserAccount'):
                            source = transfer['fromUserAccount']
                            break
                
                # If still no source, try account data
                if not source:
                    for account in tx.get('accountData', []):
                        if account.get('owner') and not account['owner'].startswith('Jupiter'):
                            source = account['owner']
                            break
                
                # Last resort: use source field
                if not source:
                    source = tx.get('source', 'unknown')
                
                amount, is_sol_value = self._get_transaction_value(tx, token_address)
                
                # Determine if buy or sell
                is_buy = False
                token_transfers = tx.get('tokenTransfers', [])
                for transfer in token_transfers:
                    if transfer.get('mint') == token_address:
                        is_buy = float(transfer.get('tokenAmount', 0)) > 0
                        break
                
                # Track transaction info
                tx_info = {
                    'timestamp': tx['timestamp'],
                    'amount': amount,
                    'is_buy': is_buy,
                    'is_rapid': False,
                    'is_flash_loan': False,
                    'is_high_slippage': False,
                    'wallet': source
                }
                
                # Check for patterns
                if source in wallet_history:
                    last_tx = wallet_history[source][-1]
                    if tx['timestamp'] - last_tx['timestamp'] < 60:
                        tx_info['is_rapid'] = True
                
                if len(tx.get('tokenTransfers', [])) >= 2:
                    token_in_out = {}
                    for transfer in tx.get('tokenTransfers', []):
                        mint = transfer.get('mint')
                        amt = float(transfer.get('tokenAmount', 0))
                        if mint in token_in_out and abs(token_in_out[mint] + amt) < 0.01:
                            tx_info['is_flash_loan'] = True
                            break
                        token_in_out[mint] = token_in_out.get(mint, 0) - amt
                
                try:
                    if tx.get('type') == 'SWAP' and len(tx.get('tokenTransfers', [])) >= 2:
                        price = amount / float(token_transfers[0].get('tokenAmount', 1))
                        if len(price_points) > 1:
                            prev_price = price_points[-1][1]
                            price_impact = abs(price - prev_price) / prev_price
                            if price_impact > 0.05:  # 5% slippage
                                tx_info['is_high_slippage'] = True
                except Exception:
                    pass
                
                wallet_history[source].append(tx_info)
            
            # Second pass: categorize traders and aggregate metrics
            suspicious_wallets = {}
            for wallet, history in wallet_history.items():
                category = self._categorize_trader(history)
                trader_categories[category]['count'] += 1
                trader_categories[category]['transactions'].extend(history)
                
                for tx in history:
                    trader_categories[category]['volume'] += tx['amount']
                    if tx['is_buy']:
                        trader_categories[category]['buys'] += tx['amount']
                    else:
                        trader_categories[category]['sells'] += tx['amount']
                    
                    # Track volume distribution
                    amount = tx['amount']
                    if amount < 0.1:
                        volume_distribution['very_small']['count'] += 1
                        volume_distribution['very_small']['amount'] += amount
                    elif amount < 1:
                        volume_distribution['small']['count'] += 1
                        volume_distribution['small']['amount'] += amount
                    elif amount < 10:
                        volume_distribution['medium']['count'] += 1
                        volume_distribution['medium']['amount'] += amount
                    elif amount < 100:
                        volume_distribution['large']['count'] += 1
                        volume_distribution['large']['amount'] += amount
                    else:
                        volume_distribution['very_large']['count'] += 1
                        volume_distribution['very_large']['amount'] += amount
                
                if len(history) >= 3:
                    suspicious_wallets[wallet] = len(history)
            
            suspicious_wallets = dict(sorted(suspicious_wallets.items(), key=lambda x: x[1], reverse=True)[:10])
            
            return {
                'transaction_count': len(transactions),
                'active_wallets': len(wallet_history),
                'trading_velocity': len(transactions) / minutes,
                'total_volume': sum(cat['volume'] for cat in trader_categories.values()),
                'trader_categories': trader_categories,
                'suspicious_wallets': suspicious_wallets,
                'volume_distribution': volume_distribution
            }
            
        except Exception as e:
            print(f"Error analyzing transactions: {str(e)}")
            return None
