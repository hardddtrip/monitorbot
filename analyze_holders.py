import asyncio
import os
from dotenv import load_dotenv
import logging
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict
from sheets_integration import GoogleSheetsIntegration
from birdeye_get_data import BirdeyeDataCollector
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HolderAnalyzer:
    def __init__(self, birdeye_api_key: str, sheets: GoogleSheetsIntegration):
        """Initialize the analyzer with API key and sheets integration."""
        self.sheets = sheets
        self.birdeye = BirdeyeDataCollector(birdeye_api_key, sheets)

    async def get_top_holders(self, token_address: str) -> List[Dict]:
        """Get the top holders for a token."""
        try:
            # Get token info first
            token_info = await self.birdeye.get_token_data(token_address)
            if not token_info:
                logger.error("Failed to get token info")
                return []

            # Get holders data
            holders_data = await self.birdeye.get_token_holders(token_address)
            if not holders_data:
                logger.error("Failed to get holders data")
                return []

            # Process and return the holders data
            processed_holders = []
            for holder in holders_data:
                try:
                    processed_holder = {
                        'owner': str(holder.get('owner', '')),
                        'amount': float(holder.get('amount', 0)),
                        'percentage': float(holder.get('percentage', 0))
                    }
                    processed_holders.append(processed_holder)
                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing holder data: {e}")
                    continue

            return processed_holders

        except Exception as e:
            logger.error(f"Error in get_top_holders: {str(e)}")
            return []

    async def get_wallet_portfolio(self, wallet_address: str, limit: int = 5) -> Dict:
        """Get wallet portfolio from Birdeye API."""
        url = 'https://public-api.birdeye.so/v1/wallet/token_list'
        params = {
            "wallet": wallet_address
        }
        headers = {
            'X-API-KEY': self.birdeye.api_key,
            'accept': 'application/json',
            'x-chain': 'solana'
        }

        try:
            logger.info(f"Getting wallet portfolio for {wallet_address}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Wallet portfolio response: {data}")
                        if data.get('success'):
                            portfolio_data = data['data']
                            
                            # Sort items by USD value and get top tokens
                            items = portfolio_data['items']
                            sorted_items = sorted(items, key=lambda x: x.get('valueUsd', 0), reverse=True)
                            top_items = sorted_items[:limit]

                            # Get price changes for each token
                            for item in top_items:
                                logger.info(f"Getting price changes for token {item.get('symbol', item.get('address'))}")
                                price_changes = await self.get_token_price_changes(item['address'])
                                item['price_changes'] = price_changes

                            return {
                                'wallet': portfolio_data['wallet'],
                                'total_value': portfolio_data['totalUsd'],
                                'tokens': top_items
                            }
                    logger.error(f"Error getting wallet portfolio: {response.status}")
                    response_text = await response.text()
                    logger.error(f"Response text: {response_text}")
                    return None
        except Exception as e:
            logger.error(f"Error in get_wallet_portfolio: {str(e)}")
            return None

    async def get_token_price_changes(self, token_address: str) -> Dict:
        """Get token price changes from Birdeye API."""
        try:
            # Use the critical get_price_changes function
            price_changes = await self.birdeye.get_price_changes(token_address)
            return {
                'changes': {
                    '1W': price_changes.get('1W', 0.0),
                    '1M': price_changes.get('1M', 0.0),
                    '3M': price_changes.get('3M', 0.0),
                    '1Y': price_changes.get('1Y', 0.0)
                },
                'high_to_current': price_changes.get('1Y_high_to_current', 0.0)
            }
        except Exception as e:
            logger.error(f"Error getting price changes: {str(e)}")
            return {'changes': {}, 'high_to_current': 0.0}

    async def analyze_holder_tokens(self, wallet_address: str) -> Dict:
        """Analyze the tokens held by a wallet."""
        try:
            portfolio = await self.get_wallet_portfolio(wallet_address)
            if not portfolio or not isinstance(portfolio, dict):
                logger.error(f"Invalid portfolio data for wallet {wallet_address}")
                # Return empty portfolio data instead of None
                return {
                    'wallet': wallet_address,
                    'total_value': 0,
                    'tokens': [],
                    'analysis_summary': "No tokens found in wallet"
                }
                
            analyzed_tokens = []
            
            # Process top 5 tokens
            for token in portfolio.get('tokens', []):
                if not isinstance(token, dict):
                    continue
                    
                token_address = token.get('address')
                if not token_address:
                    continue
                    
                token_data = {
                    'symbol': token.get('symbol', 'Unknown'),
                    'address': token_address,
                    'amount': token.get('uiAmount', 0),
                    'valueUsd': token.get('valueUsd', 0),
                    'price_changes': token.get('price_changes', {})
                }
                
                analyzed_tokens.append(token_data)
            
            # Format token analysis with price changes
            analysis_lines = []
            for token_info in analyzed_tokens:
                token_name = token_info['symbol']
                value = token_info['valueUsd']
                amount = token_info['amount']
                price_changes = token_info.get('price_changes', {})
                
                # Format the line with | separators
                line = (
                    f"{token_name} (${value:,.2f}) | "
                    f"1W: {price_changes.get('changes', {}).get('1W', 0.0):+.2f}% | "
                    f"1M: {price_changes.get('changes', {}).get('1M', 0.0):+.2f}% | "
                    f"3M: {price_changes.get('changes', {}).get('3M', 0.0):+.2f}% | "
                    f"1Y: {price_changes.get('changes', {}).get('1Y', 0.0):+.2f}% | "
                    f"From 1Y High: {price_changes.get('high_to_current', 0.0):+.2f}%"
                )
                analysis_lines.append(line)
            
            # Join all lines with newlines
            analysis_summary = "\n".join(analysis_lines)
            
            return {
                'wallet': portfolio.get('wallet', wallet_address),
                'total_value': portfolio.get('total_value', 0),
                'tokens': analyzed_tokens,
                'analysis_summary': analysis_summary
            }
        except Exception as e:
            logger.error(f"Error analyzing tokens for wallet {wallet_address}: {str(e)}")
            return None

    async def analyze_holder_data(self, token_address: str, token_name: str):
        """Analyze top 10 holder data and post results to Google Sheets."""
        try:
            logger.info(f"Starting analysis of top 10 holders for token {token_name} ({token_address})")
            holders = await self.get_top_holders(token_address)
            if not holders:
                logger.error("No holders found")
                return

            logger.info(f"Processing {len(holders)} top holders for {token_name}")
            success_count = 0
            for idx, holder in enumerate(holders, 1):
                try:
                    wallet = holder.get('owner')
                    if not wallet:
                        logger.warning(f"Skipping holder #{idx} - missing wallet address")
                        continue

                    logger.info(f"Analyzing holder #{idx}: {wallet}")
                    portfolio = await self.get_wallet_portfolio(wallet)
                    
                    if not portfolio or not isinstance(portfolio, dict):
                        logger.error(f"Invalid portfolio data for holder #{idx} wallet {wallet}")
                        continue

                    # Create a serializable holder data dictionary
                    holder_data = {
                        'wallet': str(wallet),
                        'total_value': float(portfolio.get('total_value', 0)),
                        'tokens': []
                    }

                    # Process token data
                    for token in portfolio.get('tokens', []):
                        if not isinstance(token, dict):
                            logger.warning(f"Skipping invalid token data for holder #{idx} wallet {wallet}")
                            continue

                        token_data = {
                            'symbol': str(token.get('symbol', 'Unknown')),
                            'valueUsd': float(token.get('valueUsd', 0)),
                            'price_changes': {
                                'changes': {
                                    '1W': float(token.get('price_changes', {}).get('changes', {}).get('1W', 0)),
                                    '1M': float(token.get('price_changes', {}).get('changes', {}).get('1M', 0)),
                                    '3M': float(token.get('price_changes', {}).get('changes', {}).get('3M', 0)),
                                    '1Y': float(token.get('price_changes', {}).get('changes', {}).get('1Y', 0))
                                }
                            }
                        }
                        holder_data['tokens'].append(token_data)

                    logger.info(f"Posting analysis for holder #{idx} {wallet} to Google Sheets")
                    logger.info(f"Holder data: {json.dumps(holder_data, indent=2)}")
                    
                    # Post the serializable data to Google Sheets
                    if self.sheets.post_holder_token_analysis(holder_data):
                        success_count += 1
                        logger.info(f"Successfully posted analysis for holder #{idx} {wallet}")
                    else:
                        logger.error(f"Failed to post analysis for holder #{idx} {wallet}")
                    
                except Exception as e:
                    logger.error(f"Error processing holder #{idx} {wallet}: {str(e)}")
                    continue

            logger.info(f"Top holder analysis completed. Successfully processed {success_count} out of {len(holders)} holders")
            
        except Exception as e:
            logger.error(f"Error in analyze_holder_data: {str(e)}")
            raise

async def main():
    # Load environment variables
    load_dotenv()

    # Initialize components
    birdeye_api_key = os.getenv("BIRDEYE_API_KEY")
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    token_address = os.getenv("DEFAULT_TOKEN_ADDRESS")
    
    if not all([birdeye_api_key, credentials_file, spreadsheet_id, token_address]):
        logger.error("Missing required environment variables")
        return
    
    sheets = GoogleSheetsIntegration(credentials_file, spreadsheet_id)
    analyzer = HolderAnalyzer(birdeye_api_key, sheets)
    
    # Get token name from first holder's portfolio
    holders = await analyzer.get_top_holders(token_address)
    token_name = "Unknown Token"
    if holders:
        first_holder = holders[0].get('owner')
        portfolio = await analyzer.get_wallet_portfolio(first_holder)
        if portfolio and portfolio.get('tokens'):
            for token in portfolio.get('tokens', []):
                if token.get('address') == token_address:
                    token_name = token.get('name', token.get('symbol', token_name))
                    break
    
    await analyzer.analyze_holder_data(token_address, token_name)

if __name__ == "__main__":
    asyncio.run(main())
