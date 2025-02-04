from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
import asyncio
import threading
from analyze_holders import HolderAnalyzer
from audit import TokenAuditor
from sheets_integration import GoogleSheetsIntegration
from birdeye_get_data import BirdeyeDataCollector

app = Flask(__name__)
load_dotenv()

def run_analysis_background(token_address: str, birdeye_api_key: str, spreadsheet_id: str):
    """Run the analysis in a background thread"""
    async def analyze():
        try:
            # Initialize services
            sheets = GoogleSheetsIntegration(None, spreadsheet_id)
            birdeye = BirdeyeDataCollector(birdeye_api_key, sheets)
            analyzer = HolderAnalyzer(birdeye_api_key, sheets)  # Pass API key instead of birdeye instance
            auditor = TokenAuditor(birdeye, sheets)

            # Run analysis and wait for both to complete
            await asyncio.gather(
                analyzer.analyze_holder_data(token_address, ""),
                auditor.audit_token(token_address)
            )
            
            # Log completion
            print(f"Analysis completed for token {token_address}")
            
        except Exception as e:
            print(f"Error in background analysis: {str(e)}")
            raise

    # Create a new event loop for the background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(analyze())
    finally:
        loop.close()

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

        # Start analysis in background thread
        thread = threading.Thread(
            target=run_analysis_background,
            args=(token_address, birdeye_api_key, spreadsheet_id)
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Analysis started. Results will be posted to Google Sheets shortly.'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
