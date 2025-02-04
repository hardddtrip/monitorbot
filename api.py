from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
import asyncio
from analyze_holders import HolderAnalyzer
from audit import TokenAuditor
from sheets_integration import GoogleSheetsIntegration

app = Flask(__name__)
load_dotenv()

@app.route('/analyze', methods=['POST'])
def analyze_token():
    try:
        data = request.get_json()
        token_address = data.get('token_address')
        
        if not token_address:
            return jsonify({'error': 'Token address is required'}), 400
            
        # Initialize components
        birdeye_api_key = os.getenv("BIRDEYE_API_KEY")
        credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE")
        spreadsheet_id = os.getenv("SPREADSHEET_ID")
        
        if not all([birdeye_api_key, credentials_file, spreadsheet_id]):
            return jsonify({'error': 'Missing required environment variables'}), 500
        
        # Initialize services
        sheets = GoogleSheetsIntegration(credentials_file, spreadsheet_id)
        analyzer = HolderAnalyzer(birdeye_api_key, sheets)
        auditor = TokenAuditor(birdeye_api_key, sheets)
        
        # Run analysis asynchronously
        async def run_analysis():
            await asyncio.gather(
                analyzer.analyze_holder_data(token_address, ""),
                auditor.audit_token(token_address)
            )
        
        # Run the async function
        asyncio.run(run_analysis())
        
        return jsonify({'success': True, 'message': 'Analysis completed'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
