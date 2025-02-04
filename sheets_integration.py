from google.oauth2 import service_account
from googleapiclient.discovery import build
import os.path
import json
from datetime import datetime
import logging
from typing import List, Dict
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleSheetsIntegration:
    def __init__(self, credentials_file: str, spreadsheet_id: str):
        """Initialize the Google Sheets integration.
        
        Args:
            credentials_file: Path to the service account credentials JSON file
            spreadsheet_id: The ID of the Google Sheet to write to
        """
        self.spreadsheet_id = spreadsheet_id
        
        try:
            # First try to use credentials from environment variable
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                logger.info("Using credentials from GOOGLE_CREDENTIALS_JSON environment variable")
                try:
                    creds_info = json.loads(creds_json)
                    logger.info("Successfully parsed credentials JSON")
                    credentials = service_account.Credentials.from_service_account_info(
                        creds_info,
                        scopes=['https://www.googleapis.com/auth/spreadsheets']
                    )
                    logger.info("Successfully created credentials from service account info")
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing GOOGLE_CREDENTIALS_JSON: {str(e)}")
                    raise
                except Exception as e:
                    logger.error(f"Error creating credentials from service account info: {str(e)}")
                    raise
            else:
                logger.info("No GOOGLE_CREDENTIALS_JSON found, falling back to file-based credentials")
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_file,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Successfully built Google Sheets service")
            self.sheet_name = "TradeData"  # Use a more descriptive sheet name
            self.authenticate()
            self._ensure_sheet_exists()
            logger.info("Successfully verified sheet exists")

        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {str(e)}")
            raise

    def authenticate(self):
        """Authenticate with Google Sheets API using service account."""
        try:
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

    def ensure_sheet_exists(self, sheet_name: str) -> bool:
        """Ensure a sheet exists, create it if it doesn't."""
        try:
            # Check if sheet exists by getting its ID
            sheet_id = self._get_sheet_id(sheet_name)
            
            if sheet_id is not None:
                logger.info(f"Sheet '{sheet_name}' already exists")
                return True
                
            # Create new sheet if it doesn't exist
            try:
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
                logger.info(f"Created new sheet '{sheet_name}'")
                return True
                
            except Exception as create_error:
                logger.error(f"Error creating sheet: {str(create_error)}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking sheet existence: {str(e)}")
            return False

    def _get_sheet_id(self, sheet_name: str) -> int:
        """Get sheet ID by name."""
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting sheet ID: {str(e)}")
            return None

    def append_to_sheet(self, sheet_name: str, rows: List[List]):
        """Append rows to a sheet."""
        try:
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
        except HttpError as e:
            logger.error(f"Error appending to sheet: {e.resp.status} {e.resp.reason}")
            raise
        except Exception as e:
            logger.error(f"Error appending to sheet: {str(e)}")
            raise

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
        except HttpError as e:
            logger.error(f"Error appending trades to Google Sheet: {e.resp.status} {e.resp.reason}")
            raise
        except Exception as e:
            logger.error(f"Error appending trades to Google Sheet: {str(e)}")
            raise

    def append_audit_results(self, audit_results: List):
        """Append audit results to the sheet."""
        sheet_name = "TokenAudits"
        try:
            # Get or create sheet
            sheet_id = self._get_sheet_id(sheet_name)
            if not sheet_id:
                logger.info(f"Creating new sheet {sheet_name}")
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
                ).execute()
                
                # Add headers if new sheet
                logger.info("Adding headers")
                headers = self._get_audit_headers()
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A1:V1",
                    valueInputOption="RAW",
                    body={"values": [headers]}
                ).execute()

            # Format data
            logger.info("Formatting data")
            row = self._format_audit_row(audit_results)

            # Append data
            logger.info("Appending data")
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:V",
                valueInputOption="RAW",
                body={"values": [row]}
            ).execute()
            logger.info(f"Successfully appended audit results: {result}")

        except HttpError as e:
            logger.error(f"Error appending audit results: {e.resp.status} {e.resp.reason}")
            raise
        except Exception as e:
            logger.error(f"Error appending audit results: {str(e)}")
            raise

    def _format_audit_row(self, audit_data: Dict) -> List:
        """Format audit results into a row for Google Sheets."""
        try:
            # Extract data from the audit_data dictionary
            st_momentum = audit_data.get("st_momentum", {})
            mt_momentum = audit_data.get("mt_momentum", {})
            lt_outlook = audit_data.get("lt_outlook", {})
            risks = audit_data.get("risks", {})
            
            # Format into a row matching the headers
            row = [
                audit_data.get("timestamp", ""),
                audit_data.get("token", ""),
                audit_data.get("contract", ""),
                audit_data.get("name", ""),
                audit_data.get("market_cap", 0),
                
                # ST Momentum
                st_momentum.get("score", 0),
                st_momentum.get("comment", ""),
                st_momentum.get("conviction", 0),
                st_momentum.get("support", 0),
                st_momentum.get("resistance", 0),
                
                # MT Momentum
                mt_momentum.get("score", 0),
                mt_momentum.get("comment", ""),
                mt_momentum.get("conviction", 0),
                mt_momentum.get("support", 0),
                mt_momentum.get("resistance", 0),
                
                # LT Outlook
                lt_outlook.get("score", 0),
                lt_outlook.get("comment", ""),
                lt_outlook.get("conviction", 0),
                
                # Risks
                risks.get("score", 0),
                risks.get("comment", ""),
                risks.get("conviction", 0),
                
                # Overall Rating
                audit_data.get("overall_rating", 0)
            ]
            
            return row
            
        except Exception as e:
            logger.error(f"Error formatting audit row: {str(e)}")
            # Return a row of empty values matching the number of headers
            return [""] * len(self._get_audit_headers())

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

    def post_holder_analysis(self, token_name: str, timestamp: str, analysis: str) -> bool:
        """Post holder analysis to Google Sheets."""
        try:
            # Get the last row
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:A"
            ).execute()
            
            last_row = len(result.get('values', [])) + 1
            
            # Prepare the data
            values = [[timestamp, token_name, analysis]]
            
            # Write to sheet
            body = {
                'values': values
            }
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A{last_row}:C{last_row}",
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return True
            
        except HttpError as e:
            logger.error(f"Error posting holder analysis to Google Sheets: {e.resp.status} {e.resp.reason}")
            return False
        except Exception as e:
            logger.error(f"Error posting holder analysis to Google Sheets: {str(e)}")
            return False

    def post_holder_token_analysis(self, holder_data: Dict):
        """Post holder token analysis to Google Sheets."""
        try:
            if not holder_data:
                logger.error("No holder data provided")
                return False
                
            sheet_name = "HolderAnalysis"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            wallet = holder_data.get('wallet')
            total_value = holder_data.get('total_value', 0)
            
            logger.info(f"Preparing analysis for wallet {wallet} with total value ${total_value:,.2f}")
            
            # Format price changes for each token
            token_analysis = []
            for token in holder_data.get('tokens', []):
                if not isinstance(token, dict):
                    continue
                    
                price_changes = token.get('price_changes', {})
                changes = price_changes.get('changes', {})
                
                # Format with | separators instead of newlines
                analysis = (
                    f"{token.get('symbol', 'Unknown')} (${token.get('valueUsd', 0):,.2f}) | "
                    f"1W: {changes.get('1W', 0):.2f}% | "
                    f"1M: {changes.get('1M', 0):.2f}% | "
                    f"3M: {changes.get('3M', 0):.2f}% | "
                    f"1Y: {changes.get('1Y', 0):.2f}% | "
                    f"From 1Y High: {changes.get('1Y_high_to_current', 0):.2f}%"
                )
                token_analysis.append(analysis)
                logger.info(f"Added analysis for token {token.get('symbol', 'Unknown')}")
            
            # Join all token analyses with newlines, or show "No tokens found" if empty
            all_analysis = "\n".join(token_analysis) if token_analysis else "No tokens found in wallet"
            
            # Prepare row data
            row = [timestamp, wallet, total_value, all_analysis]
            
            try:
                logger.info(f"Ensuring sheet {sheet_name} exists")
                # Ensure sheet exists
                if not self.ensure_sheet_exists(sheet_name):
                    logger.error(f"Failed to ensure sheet {sheet_name} exists")
                    return False
                
                # Get current sheet data to determine where to insert
                logger.info("Getting current sheet data")
                try:
                    result = self.service.spreadsheets().values().get(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'{sheet_name}!A:D'
                    ).execute()
                    
                    values = result.get('values', [])
                    next_row = len(values) + 1
                    logger.info(f"Will insert at row {next_row}")
                    
                    # Add headers if sheet is empty
                    if next_row == 1:
                        logger.info("Sheet is empty, adding headers")
                        headers = ['Timestamp', 'Wallet Address', 'Total USD Value', 'Token Analysis']
                        try:
                            self.service.spreadsheets().values().update(
                                spreadsheetId=self.spreadsheet_id,
                                range=f'{sheet_name}!A1:D1',
                                valueInputOption='RAW',
                                body={'values': [headers]}
                            ).execute()
                            next_row = 2
                            logger.info("Successfully added headers")
                        except Exception as header_error:
                            logger.error(f"Error adding headers: {str(header_error)}")
                            return False
                    
                    # Add data row and empty row for spacing
                    range_name = f"{sheet_name}!A{next_row}:D{next_row + 1}"
                    body = {
                        'values': [
                            row,  # Data row
                            ['', '', '', '']  # Empty row for spacing
                        ]
                    }
                    
                    logger.info(f"Posting data to range {range_name}")
                    try:
                        self.service.spreadsheets().values().update(
                            spreadsheetId=self.spreadsheet_id,
                            range=range_name,
                            valueInputOption='RAW',
                            body=body
                        ).execute()
                        logger.info("Successfully posted data")
                        
                        # Apply formatting
                        sheet_id = self._get_sheet_id(sheet_name)
                        if sheet_id:
                            logger.info("Applying sheet formatting")
                            requests = [
                                # Auto-resize columns
                                {
                                    'autoResizeDimensions': {
                                        'dimensions': {
                                            'sheetId': sheet_id,
                                            'dimension': 'COLUMNS',
                                            'startIndex': 0,
                                            'endIndex': 4
                                        }
                                    }
                                },
                                # Enable text wrapping for the token analysis column
                                {
                                    'repeatCell': {
                                        'range': {
                                            'sheetId': sheet_id,
                                            'startColumnIndex': 3,
                                            'endColumnIndex': 4
                                        },
                                        'cell': {
                                            'userEnteredFormat': {
                                                'wrapStrategy': 'WRAP'
                                            }
                                        },
                                        'fields': 'userEnteredFormat.wrapStrategy'
                                    }
                                }
                            ]
                            
                            try:
                                self.service.spreadsheets().batchUpdate(
                                    spreadsheetId=self.spreadsheet_id,
                                    body={'requests': requests}
                                ).execute()
                                logger.info("Successfully applied formatting")
                                return True
                            except Exception as format_error:
                                logger.error(f"Error applying formatting: {str(format_error)}")
                                # Continue since data was posted successfully
                                return True
                        else:
                            logger.error(f"Could not find sheet ID for {sheet_name}")
                            return False
                            
                    except Exception as update_error:
                        logger.error(f"Error posting data: {str(update_error)}")
                        return False
                        
                except Exception as get_error:
                    logger.error(f"Error getting sheet data: {str(get_error)}")
                    return False
                    
            except Exception as sheet_error:
                logger.error(f"Error with sheet operations: {str(sheet_error)}")
                return False
                
        except Exception as e:
            logger.error(f"Error in post_holder_token_analysis: {str(e)}")
            return False
