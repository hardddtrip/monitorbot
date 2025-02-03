from google.oauth2 import service_account
from googleapiclient.discovery import build
import os.path
from datetime import datetime
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class GoogleSheetsIntegration:
    def __init__(self, credentials_file: str, spreadsheet_id: str):
        """Initialize the Google Sheets integration.
        
        Args:
            credentials_file: Path to the service account credentials JSON file
            spreadsheet_id: The ID of the Google Sheet to write to
        """
        self.credentials_file = credentials_file
        self.spreadsheet_id = spreadsheet_id
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets']
        self.service = None
        self.sheet_name = "Trade Data"  # Use a more descriptive sheet name
        self.authenticate()
        self._ensure_sheet_exists()

    def authenticate(self):
        """Authenticate with Google Sheets API using service account."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file, 
                scopes=self.scopes
            )
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Successfully authenticated with Google Sheets")
        except Exception as e:
            logger.error(f"Error authenticating with Google Sheets: {e}")
            raise

    def _ensure_sheet_exists(self):
        """Ensure the sheet exists and has the correct headers."""
        try:
            # Try to get the sheet to see if it exists
            self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            # Add a new sheet if it doesn't exist
            try:
                request = {
                    'addSheet': {
                        'properties': {
                            'title': self.sheet_name
                        }
                    }
                }
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [request]}
                ).execute()
                
                # Add headers
                headers = [
                    ['Transaction Hash', 'Block Time', 'Fetch Time', 'Side', 
                     'Source', 'From Amount', 'From Symbol', 'To Amount', 
                     'To Symbol', 'Price', 'Trading Recommendation', 'Market Cap', 'Token Code']
                ]
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{self.sheet_name}!A1:M1',
                    valueInputOption='RAW',
                    body={'values': headers}
                ).execute()
                
                logger.info(f"Created new sheet '{self.sheet_name}' with headers")
            except Exception as e:
                # Sheet might already exist, which is fine
                logger.info(f"Sheet '{self.sheet_name}' might already exist: {e}")
                
        except Exception as e:
            logger.error(f"Error ensuring sheet exists: {e}")
            raise

    def ensure_sheet_exists(self, sheet_name: str, headers: List[str] = None):
        """Ensure a sheet exists with the given name and headers."""
        try:
            # Try to add the sheet
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
            }
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            logger.info(f"Created new sheet: {sheet_name}")
        except Exception as e:
            logger.info(f"Sheet '{sheet_name}' might already exist: {str(e)}")
        
        # If headers are provided, check if they need to be added
        if headers:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1:Z1"
            ).execute()
            
            if not result.get('values'):
                # Sheet is empty, add headers
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A1",
                    valueInputOption="RAW",
                    body={
                        "values": [headers]
                    }
                ).execute()
                logger.info(f"Added headers to sheet: {sheet_name}")

    def append_to_sheet(self, sheet_name: str, rows: List[List]):
        """Append rows to a sheet."""
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={
                "values": rows
            }
        ).execute()
        logger.info(f"Appended {len(rows)} rows to sheet: {sheet_name}")

    def append_trades(self, trades: list, fetch_time: datetime):
        """Append trades to the Google Sheet.
        
        Args:
            trades: List of trade dictionaries
            fetch_time: Timestamp when the trades were fetched
        """
        if not trades:
            return

        # Prepare the values for the sheet
        values = []
        for trade in trades:
            values.append([
                trade['txHash'],
                datetime.fromtimestamp(trade['blockUnixTime']).isoformat(),
                fetch_time.isoformat(),
                trade['side'],
                trade['source'],
                trade['from_amount'],
                trade['from_symbol'],
                trade['to_amount'],
                trade['to_symbol'],
                trade['price'] if trade['price'] is not None else 'N/A',
                trade.get('trading_recommendation', ''),
                trade.get('market_cap', ''),
                trade.get('token_code', '')
            ])

        try:
            # Append the values to the sheet
            body = {
                'values': values
            }
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A:M',  # Use the new sheet name
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"Appended {len(values)} trades to Google Sheet")
            return result
        except Exception as e:
            logger.error(f"Error appending trades to Google Sheet: {e}")
            raise

    def append_audit_results(self, audit_results: List):
        """Append audit results to the sheet."""
        sheet_name = "Token Audits"
        try:
            # Get or create sheet
            sheet_id = self._get_sheet_id(sheet_name)
            if not sheet_id:
                print(f"Creating new sheet {sheet_name}")
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
                ).execute()
                
                # Add headers if new sheet
                print("Adding headers")
                headers = self._get_audit_headers()
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A1:V1",
                    valueInputOption="RAW",
                    body={"values": [headers]}
                ).execute()

            # Format data
            print("Formatting data")
            row = self._format_audit_row(audit_results)

            # Append data
            print("Appending data")
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:V",
                valueInputOption="RAW",
                body={"values": [row]}
            ).execute()
            print(f"Successfully appended audit results: {result}")

        except Exception as e:
            print(f"Error in append_audit_results: {str(e)}")
            raise

    def _get_sheet_id(self, sheet_name: str) -> int:
        """Get the sheet ID for a given sheet name."""
        try:
            sheets = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()['sheets']
            
            for sheet in sheets:
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
            return None
        except Exception as e:
            print(f"Error getting sheet ID: {e}")
            return None

    def _format_audit_row(self, audit_data: List) -> List:
        """Format audit results into a row for Google Sheets."""
        # audit_data is already formatted as a row
        return audit_data

    def _get_audit_headers(self) -> List[str]:
        """Get headers for the audit sheet"""
        return [
            "Time (UTC+8)",
            "Token",
            "Contract",
            "Name",
            "Market Cap ($)",
            "ST Momentum Score",
            "ST Momentum Comment",
            "ST Momentum Conviction",
            "ST Support Level",
            "ST Resistance Level",
            "MT Momentum Score",
            "MT Momentum Comment",
            "MT Momentum Conviction",
            "MT Support Level",
            "MT Resistance Level",
            "LT Outlook Score",
            "LT Outlook Comment",
            "LT Outlook Conviction",
            "Risks Score",
            "Risks Comment",
            "Risks Conviction",
            "Overall Rating"
        ]
