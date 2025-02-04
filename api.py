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
        spreadsheet_id = os.getenv("SPREADSHEET_ID")
        google_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")
        
        # Log environment variables status (without exposing sensitive data)
        print(f"Environment variables check:")
        print(f"BIRDEYE_API_KEY present: {bool(birdeye_api_key)}")
        print(f"SPREADSHEET_ID present: {bool(spreadsheet_id)}")
        print(f"GOOGLE_CREDENTIALS_JSON present: {bool(google_creds)}")
        
        if not all([birdeye_api_key, google_creds, spreadsheet_id]):
            missing_vars = []
            if not birdeye_api_key: missing_vars.append("BIRDEYE_API_KEY")
            if not google_creds: missing_vars.append("GOOGLE_CREDENTIALS_JSON")
            if not spreadsheet_id: missing_vars.append("SPREADSHEET_ID")
            return jsonify({'error': f'Missing required environment variables: {", ".join(missing_vars)}'}), 500
        
        try:
            # Initialize services
            sheets = GoogleSheetsIntegration(None, spreadsheet_id)
            analyzer = HolderAnalyzer(birdeye_api_key, sheets)
            auditor = TokenAuditor(birdeye_api_key, sheets)
        except Exception as e:
            print(f"Error initializing services: {str(e)}")
            return jsonify({'error': f'Service initialization failed: {str(e)}'}), 500
        
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
