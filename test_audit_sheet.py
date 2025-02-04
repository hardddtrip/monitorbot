import asyncio
from audit import TokenAuditor
from sheets_integration import GoogleSheetsIntegration
from birdeye_get_data import BirdeyeDataCollector
import os
from dotenv import load_dotenv
import json
import logging
import sys

# Load environment variables
load_dotenv()

async def main(token_address):
    try:
        # Get environment variables
        credentials_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'service-account.json')
        spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID', '1vz0RCZ-DVfWKCtaLgd1ekUuimbW-SqrUlQqYrMgY_eA')
        
        # Initialize
        logger.info("Initializing Google Sheets...")
        sheets = GoogleSheetsIntegration(
            credentials_file=credentials_file,
            spreadsheet_id=spreadsheet_id
        )
        
        # Initialize Birdeye
        logger.info("Initializing Birdeye...")
        birdeye_api_key = os.getenv('BIRDEYE_API_KEY')
        if not birdeye_api_key:
            raise ValueError("BIRDEYE_API_KEY environment variable must be set")
        birdeye = BirdeyeDataCollector(api_key=birdeye_api_key)
        auditor = TokenAuditor(birdeye=birdeye, sheets=sheets)
        
        # Run audit
        logger.info(f"Running audit for token: {token_address}")
        audit_results = await auditor.audit_token(token_address)
        
        # Debug print
        logger.info("Audit Results:")
        logger.info(json.dumps(audit_results, indent=2))
        
        # Post to sheet
        logger.info("Posting to Google Sheet...")
        await auditor.post_audit_to_sheets(audit_results)
        logger.info("Posted audit results to sheet!")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Get token address from command line argument, default to JPM if not provided
    token_address = sys.argv[1] if len(sys.argv) > 1 else "JEUrtQsEp69w2sbM8Hdbn9ykhejVC8yvpdjBjDkYJPM"
    
    asyncio.run(main(token_address))
