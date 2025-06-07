#!/usr/bin/env python3

import os
import json
import base64
import sys
from html.parser import HTMLParser
from email.mime.text import MIMEText
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Environment variables loaded from .env file")
except ImportError:
    print("python-dotenv not installed. Using environment variables directly.")

# Import Telegram notification module
try:
    from telegram_notifier import send_telegram_notification, send_batch_notification
    TELEGRAM_AVAILABLE = True
    print("Telegram notification module loaded")
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Telegram notification module not available")

# Google API imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Gemini AI API
import google.generativeai as genai

# Constants & Configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
          'https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE_TEMPLATE = 'token_{}.json'  # Template for token files with account identifier
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')  # From environment variable
MODEL_NAME = 'gemini-2.0-flash'  # Adjust based on available models
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '')  # From environment variable
SHEET_RANGE = 'Sheet1!A1'  # Starting cell for appending data
GMAIL_SEARCH_QUERY = os.environ.get('GMAIL_SEARCH_QUERY', 
                                  "subject:(Transfer OR Pembayaran OR Transaksi OR payment OR transaction) is:unread newer_than:1d")

# Get Gmail accounts to process from environment variable or command line
GMAIL_ACCOUNTS = os.environ.get('GMAIL_ACCOUNTS', '').split(',')
if not GMAIL_ACCOUNTS or GMAIL_ACCOUNTS == ['']:
    # If no accounts specified in env, check command line args
    if len(sys.argv) > 1:
        GMAIL_ACCOUNTS = sys.argv[1].split(',')
    else:
        # Default to a single account with default token file
        GMAIL_ACCOUNTS = ['default']

# HTML Parser to extract text from HTML content
class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    
    def handle_data(self, data):
        self.text.append(data)
    
    def get_text(self):
        return ' '.join(self.text)

def authenticate_google_services(account_id='default'):
    """
    Authenticate with Google services using OAuth 2.0 for a specific account
    Args:
        account_id: Identifier for the account (used in token filename)
    Returns:
        credentials for Gmail and Sheets APIs
    """
    token_file = TOKEN_FILE_TEMPLATE.format(account_id)
    creds = None
    
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_info(
            json.load(open(token_file)), SCOPES)
    
    # If credentials are invalid or don't exist, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
            # Save account information in token file
            creds_dict = json.loads(creds.to_json())
            creds_dict['account_id'] = account_id
            
            # Save credentials for future use
            with open(token_file, 'w') as token:
                json.dump(creds_dict, token)
    
    return creds

def initialize_gemini_client(api_key, model_name):
    """
    Initialize the Gemini API client
    Args:
        api_key: The API key for Gemini
        model_name: The model to use for generation
    Returns:
        A GenerativeModel instance
    """
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)

def get_emails(gmail_service, search_query):
    """
    Retrieve emails based on search query
    Args:
        gmail_service: Authenticated Gmail service
        search_query: Query to filter emails (e.g., 'label:inbox is:unread subject:receipt')
    Returns:
        List of email messages
    """
    try:
        results = gmail_service.users().messages().list(
            userId='me', q=search_query).execute()
        messages = results.get('messages', [])
        
        if not messages:
            print("No messages found matching the criteria.")
            return []
        
        emails = []
        for message in messages:
            msg = gmail_service.users().messages().get(
                userId='me', id=message['id']).execute()
            emails.append(msg)
            print(f"Retrieved email with ID: {message['id']}")
        
        return emails
    
    except Exception as e:
        print(f"Error retrieving emails: {e}")
        return []

def extract_email_body(message_payload):
    """
    Extract the text or HTML body from an email message
    Args:
        message_payload: The payload part of the email
    Returns:
        Extracted text content
    """
    if 'parts' in message_payload:
        for part in message_payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            
            # If no plain text, try to get HTML content
            elif part.get('mimeType') == 'text/html':
                data = part['body'].get('data', '')
                if data:
                    html_content = base64.urlsafe_b64decode(data).decode('utf-8')
                    parser = HTMLTextExtractor()
                    parser.feed(html_content)
                    return parser.get_text()
            
            # Recursively check for nested parts
            elif 'parts' in part:
                body = extract_email_body(part)
                if body:
                    return body
    else:
        # For messages without parts, try to get data directly
        data = message_payload.get('body', {}).get('data', '')
        if data:
            if message_payload.get('mimeType') == 'text/html':
                html_content = base64.urlsafe_b64decode(data).decode('utf-8')
                parser = HTMLTextExtractor()
                parser.feed(html_content)
                return parser.get_text()
            else:
                return base64.urlsafe_b64decode(data).decode('utf-8')
    
    return None

def mark_email_processed(gmail_service, message_id, label_name="Processed-Financial", mark_as_read=True):
    """
    Mark an email as processed by adding a label and optionally marking it as read
    Args:
        gmail_service: Authenticated Gmail service
        message_id: ID of the email to mark
        label_name: Name of the label to apply
        mark_as_read: Whether to mark the email as read
    """
    try:
        # Check if label exists, create if not
        results = gmail_service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        
        label_id = None
        for label in labels:
            if label['name'] == label_name:
                label_id = label['id']
                break
        
        if not label_id:
            # Create new label
            label_object = {'name': label_name, 'labelListVisibility': 'labelShow', 
                            'messageListVisibility': 'show'}
            created_label = gmail_service.users().labels().create(
                userId='me', body=label_object).execute()
            label_id = created_label['id']
        
        # Modify the message
        modify_request = {'addLabelIds': [label_id]}
        
        # If marking as read, remove the UNREAD label
        if mark_as_read:
            modify_request['removeLabelIds'] = ['UNREAD']
        
        gmail_service.users().messages().modify(
            userId='me', 
            id=message_id, 
            body=modify_request
        ).execute()
        
        action_text = "marked as processed" + (" and read" if mark_as_read else "")
        print(f"Email {message_id} {action_text}")
    
    except Exception as e:
        print(f"Error processing email: {e}")

def parse_email_with_gemini(gemini_model_instance, email_text):
    """
    Parse email content using Gemini to extract financial transaction data
    Args:
        gemini_model_instance: Initialized Gemini model
        email_text: Email content to parse
    Returns:
        Dictionary containing extracted fields or None if parsing failed
    """
    if not email_text:
        print("No email text to parse.")
        return None
    
    try:
        # Get current date for reference
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Create a detailed prompt for Gemini - matching the main.py format
        prompt = f"""
        Extract financial information from this Indonesian text: "{email_text}"
        Today's date is {current_date}.
        
        Return a JSON object with these fields:
        - amount: the monetary amount (numeric value only, without currency symbols)
        - category: the spending/income category
        - description: brief description of the transaction
        - transaction_type: "income" if this is money received, or "expense" if this is money spent
        - date: the date of the transaction in YYYY-MM-DD format
        
        For the date field, if no specific date is mentioned, use today's date ({current_date}).
        
        For transaction_type, analyze the context carefully:
        - INCOME indicators (set to "income"): "terima", "dapat", "pemasukan", "masuk", "diterima", "gaji", "bonus", etc.
        - EXPENSE indicators (set to "expense"): "beli", "bayar", "belanja", "pengeluaran", "keluar", "dibayar", etc.
        
        If transaction_type is "income", amount should be positive. If "expense", amount should be negative.
                
        If still unclear, default to "expense".
    
    For category, try to identify specific categories like:
    - Income categories: "Gaji", "Bonus", "Investasi", "Hadiah", "Penjualan", "Bisnis"
    - Expense categories: "Makanan", "Transportasi", "Belanja", "Hiburan", "Tagihan", "Kesehatan", "Pendidikan"
    
        If any field is unclear, set it to null.
        """
        
        # Send request to Gemini
        response = gemini_model_instance.generate_content(prompt)
        
        # Extract and parse JSON response
        response_text = response.text
        
        # Clean the response in case it contains markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # Parse the JSON response
        parsed_data = json.loads(response_text)
        print("Successfully parsed email data with Gemini")
        
        # Process the amount based on transaction type to ensure correct sign
        if parsed_data.get('amount') is not None:
            # Convert amount to float and ensure proper sign
            amount = abs(float(parsed_data.get('amount')))
            
            # Apply sign based on transaction type
            if parsed_data.get('transaction_type') == 'expense':
                amount = -amount
            else:
                amount = abs(amount)
                
            parsed_data['amount'] = amount
        
        return parsed_data
    
    except Exception as e:
        print(f"Error parsing email with Gemini: {e}")
        return None

def append_to_sheet(sheets_service, spreadsheet_id, sheet_range, data_rows, skip_header=False):
    """
    Append data rows to a Google Sheet
    Args:
        sheets_service: Authenticated Sheets service
        spreadsheet_id: ID of the target spreadsheet
        sheet_range: Range where data should be appended (e.g., 'Sheet1!A1')
        data_rows: List of rows to append
        skip_header: Whether to skip the first row (header) when appending
    """
    try:
        # Skip header row if requested
        rows_to_append = data_rows[1:] if skip_header and len(data_rows) > 1 else data_rows
        
        if not rows_to_append:
            print("No rows to append after skipping header.")
            return
            
        body = {
            'values': rows_to_append
        }
        
        result = sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=sheet_range,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        print(f"Appended {result.get('updates').get('updatedRows')} rows to the sheet")
    
    except Exception as e:
        print(f"Error appending to sheet: {e}")

def get_existing_data(sheets_service, spreadsheet_id, sheet_range):
    """
    Retrieve existing data from Google Sheet to check for duplicates
    Args:
        sheets_service: Authenticated Sheets service
        spreadsheet_id: ID of the target spreadsheet
        sheet_range: Range to retrieve data from (e.g., 'Sheet1!A:F')
    Returns:
        List of existing rows as dictionaries with keys matching our data fields
    """
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_range
        ).execute()
        
        values = result.get('values', [])
        
        if not values or len(values) <= 1:  # Empty or only header row
            return []
        
        # Match the column structure from main.py
        headers = ["date", "amount", "category", "description", "user_id", "timestamp"]
        existing_data = []
        
        # Skip header row
        for row in values[1:]:
            # Handle case where row might be shorter than headers
            padded_row = row + [''] * (len(headers) - len(row))
            entry = {headers[i]: padded_row[i] for i in range(len(headers))}
            existing_data.append(entry)
            
        print(f"Retrieved {len(existing_data)} existing entries from the sheet")
        return existing_data
    
    except Exception as e:
        print(f"Error retrieving existing data from sheet: {e}")
        return []

def is_duplicate(new_entry, existing_entries):
    """
    Check if a new entry already exists in the sheet
    Args:
        new_entry: Dictionary containing the new transaction data
        existing_entries: List of dictionaries containing existing data
    Returns:
        Boolean indicating whether the entry is a duplicate
    """
    # Define fields that uniquely identify a transaction
    key_fields = ["date", "amount", "category", "description"]
    
    for existing in existing_entries:
        # Check if all key fields match (case insensitive)
        match = True
        for field in key_fields:
            new_val = str(new_entry.get(field, "")).lower()
            existing_val = str(existing.get(field, "")).lower()
            
            if new_val != existing_val:
                match = False
                break
        
        if match:
            return True
    
    return False

def process_gmail_account(account_id):
    """
    Process a single Gmail account
    Args:
        account_id: Identifier for the account
    """
    print(f"\n{'='*50}")
    print(f"Processing Gmail account: {account_id}")
    print(f"{'='*50}")
    
    try:
        # Authenticate Google services for this account
        creds = authenticate_google_services(account_id)
        
        # Build service objects
        gmail_service = build('gmail', 'v1', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        # Initialize Gemini client
        gemini_model_instance = initialize_gemini_client(GEMINI_API_KEY, MODEL_NAME)
        
        # Get emails
        emails = get_emails(gmail_service, GMAIL_SEARCH_QUERY)
        
        if not emails:
            print(f"No emails found for account {account_id}")
            return
            
        # Retrieve existing data from sheet to check for duplicates
        sheet_range_all = "Sheet1!A:F"  # Match the main.py column structure
        existing_data = get_existing_data(sheets_service, SPREADSHEET_ID, sheet_range_all)
        
        # Process emails and extract data
        all_data_rows = []
        duplicate_count = 0
        processed_transactions = []  # Store processed transactions for notifications
        
        # Add header row matching main.py
        header_row = ["Date", "Amount", "Category", "Description", "User ID", "Timestamp"]
        all_data_rows.append(header_row)
        
        # Get a user ID for the email processor (to match main.py schema)
        # Include account ID to differentiate between accounts
        email_processor_user_id = os.environ.get('PROCESSOR_USER_ID', f'email-processor-{account_id}')
        
        for email in emails:
            message_id = email['id']
            payload = email['payload']
            
            # Extract email body
            email_body = extract_email_body(payload)
            
            if email_body:
                # Parse email with Gemini
                parsed_data = parse_email_with_gemini(gemini_model_instance, email_body)
                
                if parsed_data:
                    # Create entry for duplicate checking
                    entry = {
                        'date': parsed_data.get('date', datetime.now().strftime("%Y-%m-%d")),
                        'amount': parsed_data.get('amount', 0),
                        'category': parsed_data.get('category', 'Lainnya'),
                        'description': parsed_data.get('description', '')
                    }
                    
                    # Check if this transaction is already in the sheet
                    if is_duplicate(entry, existing_data):
                        print(f"Skipping duplicate transaction from {entry.get('description')} on {entry.get('date')}")
                        duplicate_count += 1
                        
                        # Still mark email as processed even if it's a duplicate
                        mark_email_processed(gmail_service, message_id, mark_as_read=True)
                        continue
                    
                    # Format data for Google Sheets - matching main.py structure
                    data_row = [
                        entry['date'],
                        entry['amount'],
                        entry['category'],
                        entry['description'],
                        email_processor_user_id,  # User ID for the email processor
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Timestamp
                    ]
                    
                    all_data_rows.append(data_row)
                    processed_transactions.append(entry)  # Store for notification
                    
                    # Mark email as processed
                    mark_email_processed(gmail_service, message_id, mark_as_read=True)
        
        # Append data to Google Sheet if we have data rows beyond the header
        if len(all_data_rows) > 1:
            # Check if sheet is empty - only add header row if sheet is empty
            should_skip_header = len(existing_data) > 0
            
            append_to_sheet(sheets_service, SPREADSHEET_ID, SHEET_RANGE, all_data_rows, skip_header=should_skip_header)
            
            transactions_count = len(all_data_rows) - 1  # Subtract header row
            print(f"Processed {transactions_count} new transactions and added them to the sheet.")
            
            # Send notifications for processed transactions
            if TELEGRAM_AVAILABLE and transactions_count > 0:
                # If there are many transactions, send a batch notification
                if transactions_count > 5:
                    send_batch_notification(transactions_count, account_id)
                else:
                    # For a small number of transactions, send individual notifications
                    for transaction in processed_transactions:
                        send_telegram_notification(transaction, account_id)
            
            if duplicate_count > 0:
                print(f"Skipped {duplicate_count} duplicate transactions.")
        else:
            print("No new transaction data was extracted.")
            if duplicate_count > 0:
                print(f"Found {duplicate_count} duplicate transactions that were already in the sheet.")
                
    except Exception as e:
        print(f"Error processing account {account_id}: {e}")

if __name__ == "__main__":
    # Get API key (in production, use environment variables or secure storage)
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY is not set. Please set it as an environment variable or in the script.")
        GEMINI_API_KEY = input("Enter your Gemini API Key: ")
    
    # Process each Gmail account
    for account_id in GMAIL_ACCOUNTS:
        if account_id.strip():  # Skip empty account IDs
            process_gmail_account(account_id.strip())
    
    print("\nAll accounts processed.") 