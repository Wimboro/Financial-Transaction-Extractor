#!/usr/bin/env python3

import os
import json
import base64
from html.parser import HTMLParser
from datetime import datetime
from http.server import BaseHTTPRequestHandler

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import Telegram notification module
try:
    import sys
    sys.path.append('.')
    from telegram_notifier import send_telegram_notification, send_batch_notification
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

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

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
MODEL_NAME = 'gemini-2.0-flash'
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '')
SHEET_RANGE = 'Sheet1!A1'
GMAIL_SEARCH_QUERY = os.environ.get('GMAIL_SEARCH_QUERY', 
                                  "subject:(Transfer OR Pembayaran OR Transaksi OR payment OR transaction) is:unread newer_than:1d")

# HTML Parser to extract text from HTML content
class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    
    def handle_data(self, data):
        self.text.append(data)
    
    def get_text(self):
        return ' '.join(self.text)

def get_credentials_from_env():
    """
    Get OAuth credentials from environment variables for serverless deployment
    """
    try:
        # For Vercel deployment, credentials should be stored as environment variables
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            creds_info = json.loads(creds_json)
            return Credentials.from_authorized_user_info(creds_info, SCOPES)
        
        # Fallback: try individual credential components
        token = os.environ.get('GOOGLE_ACCESS_TOKEN')
        refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        
        if all([token, refresh_token, client_id, client_secret]):
            creds_info = {
                'token': token,
                'refresh_token': refresh_token,
                'client_id': client_id,
                'client_secret': client_secret,
                'token_uri': 'https://oauth2.googleapis.com/token'
            }
            return Credentials.from_authorized_user_info(creds_info, SCOPES)
        
        return None
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None

def initialize_gemini_client(api_key, model_name):
    """Initialize the Gemini API client"""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)

def get_emails(gmail_service, search_query):
    """Retrieve emails based on search query"""
    try:
        results = gmail_service.users().messages().list(
            userId='me', q=search_query).execute()
        messages = results.get('messages', [])
        
        if not messages:
            return []
        
        emails = []
        for message in messages:
            msg = gmail_service.users().messages().get(
                userId='me', id=message['id']).execute()
            emails.append(msg)
        
        return emails
    except Exception as e:
        print(f"Error retrieving emails: {e}")
        return []

def extract_email_body(message_payload):
    """Extract the text or HTML body from an email message"""
    if 'parts' in message_payload:
        for part in message_payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif part.get('mimeType') == 'text/html':
                data = part['body'].get('data', '')
                if data:
                    html_content = base64.urlsafe_b64decode(data).decode('utf-8')
                    parser = HTMLTextExtractor()
                    parser.feed(html_content)
                    return parser.get_text()
            elif 'parts' in part:
                body = extract_email_body(part)
                if body:
                    return body
    else:
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

def parse_email_with_gemini(gemini_model_instance, email_text):
    """Parse email content using Gemini to extract financial transaction data"""
    if not email_text:
        return None
    
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        
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
        
        For category, try to identify specific categories like:
        - Income categories: "Gaji", "Bonus", "Investasi", "Hadiah", "Penjualan", "Bisnis"
        - Expense categories: "Makanan", "Transportasi", "Belanja", "Hiburan", "Tagihan", "Kesehatan", "Pendidikan"
        
        If any field is unclear, set it to null.
        """
        
        response = gemini_model_instance.generate_content(prompt)
        response_text = response.text
        
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        parsed_data = json.loads(response_text)
        
        if parsed_data.get('amount') is not None:
            amount = abs(float(parsed_data.get('amount')))
            if parsed_data.get('transaction_type') == 'expense':
                amount = -amount
            else:
                amount = abs(amount)
            parsed_data['amount'] = amount
        
        return parsed_data
    
    except Exception as e:
        print(f"Error parsing email with Gemini: {e}")
        return None

def process_emails():
    """Main function to process emails"""
    try:
        # Get credentials
        creds = get_credentials_from_env()
        if not creds:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Authentication credentials not found'})
            }
        
        # Build service objects
        gmail_service = build('gmail', 'v1', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        # Initialize Gemini client
        if not GEMINI_API_KEY:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Gemini API key not configured'})
            }
        
        gemini_model_instance = initialize_gemini_client(GEMINI_API_KEY, MODEL_NAME)
        
        # Get emails
        emails = get_emails(gmail_service, GMAIL_SEARCH_QUERY)
        
        if not emails:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No emails found', 'processed': 0})
            }
        
        # Process emails
        processed_count = 0
        processed_transactions = []
        
        for email in emails:
            message_id = email['id']
            payload = email['payload']
            
            email_body = extract_email_body(payload)
            
            if email_body:
                parsed_data = parse_email_with_gemini(gemini_model_instance, email_body)
                
                if parsed_data:
                    # Format data for Google Sheets
                    data_row = [
                        parsed_data.get('date', datetime.now().strftime("%Y-%m-%d")),
                        parsed_data.get('amount', 0),
                        parsed_data.get('category', 'Lainnya'),
                        parsed_data.get('description', ''),
                        os.environ.get('PROCESSOR_USER_ID', 'email-processor'),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ]
                    
                    # Append to sheet
                    try:
                        body = {'values': [data_row]}
                        sheets_service.spreadsheets().values().append(
                            spreadsheetId=SPREADSHEET_ID,
                            range=SHEET_RANGE,
                            valueInputOption='USER_ENTERED',
                            insertDataOption='INSERT_ROWS',
                            body=body
                        ).execute()
                        
                        processed_count += 1
                        processed_transactions.append(parsed_data)
                        
                        # Mark email as processed
                        gmail_service.users().messages().modify(
                            userId='me',
                            id=message_id,
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                        
                    except Exception as e:
                        print(f"Error appending to sheet: {e}")
        
        # Send notifications
        if TELEGRAM_AVAILABLE and processed_count > 0:
            if processed_count > 5:
                send_batch_notification(processed_count, 'vercel')
            else:
                for transaction in processed_transactions:
                    send_telegram_notification(transaction, 'vercel')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {processed_count} transactions',
                'processed': processed_count
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = process_emails()
        
        self.send_response(result['statusCode'])
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        self.wfile.write(result['body'].encode())
    
    def do_POST(self):
        # Handle POST requests (for webhooks or manual triggers)
        result = process_emails()
        
        self.send_response(result['statusCode'])
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        self.wfile.write(result['body'].encode()) 