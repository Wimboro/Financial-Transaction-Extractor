#!/usr/bin/env python3

import os
import json
import base64
import time
from html.parser import HTMLParser
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Environment variables loaded from .env file")
except ImportError:
    print("python-dotenv not installed. Using environment variables directly.")

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
          'https://www.googleapis.com/auth/spreadsheets.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')  # From environment variable
MODEL_NAME = 'gemini-2.0-flash'  # Adjust based on available models
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '')  # From environment variable
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

def authenticate_google_services():
    """
    Authenticate with Google services using OAuth 2.0
    Returns credentials for Gmail API
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_info(
            json.load(open(TOKEN_FILE)), SCOPES)
    
    # If credentials are invalid or don't exist, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for future use
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def initialize_gemini_client(api_key, model_name):
    """
    Initialize the Gemini API client
    """
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)

def get_email_details(gmail_service, message_id):
    """
    Get detailed information about a specific email
    """
    try:
        message = gmail_service.users().messages().get(
            userId='me', id=message_id).execute()
        
        # Extract headers
        headers = {}
        for header in message['payload']['headers']:
            headers[header['name'].lower()] = header['value']
        
        # Get internal date (timestamp) and convert to human-readable format
        timestamp = int(message['internalDate']) / 1000
        date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        return {
            'id': message['id'],
            'subject': headers.get('subject', 'No Subject'),
            'from': headers.get('from', 'Unknown'),
            'date': date_str,
            'snippet': message.get('snippet', ''),
            'payload': message['payload']
        }
    except Exception as e:
        print(f"Error retrieving email details: {e}")
        return None

def extract_email_body(message_payload):
    """
    Extract the text or HTML body from an email message
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

def parse_email_with_gemini(gemini_model_instance, email_text, debug=True):
    """
    Parse email content using Gemini to extract financial transaction data
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
                
        If any field is unclear, set it to null.
        """
        
        if debug:
            print("\n--- Sending prompt to Gemini ---")
            print(f"Prompt length: {len(prompt)} characters")
            print("Waiting for Gemini response...")
            start_time = time.time()
        
        # Send request to Gemini
        response = gemini_model_instance.generate_content(prompt)
        
        if debug:
            elapsed_time = time.time() - start_time
            print(f"Gemini response received in {elapsed_time:.2f} seconds")
        
        # Extract and parse JSON response
        response_text = response.text
        
        if debug:
            print("\n--- Raw Gemini Response ---")
            print(response_text[:500] + "..." if len(response_text) > 500 else response_text)
        
        # Clean the response in case it contains markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # Parse the JSON response
        parsed_data = json.loads(response_text)
        
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
        
        if debug:
            print("\n--- Parsed JSON Data ---")
            print(json.dumps(parsed_data, indent=2))
        
        return parsed_data
    
    except Exception as e:
        print(f"Error parsing email with Gemini: {e}")
        return None

def get_recent_emails(gmail_service, time_range="1d", max_results=10, filter_financial=False):
    """
    Retrieve recent emails based on time range
    Args:
        gmail_service: Authenticated Gmail service
        time_range: Time range for emails (e.g., "1d" for 1 day)
        max_results: Maximum number of emails to retrieve
        filter_financial: Whether to filter for financial emails
    """
    try:
        if filter_financial:
            # Add financial transaction-related filters
            search_query = f"newer_than:{time_range} subject:(receipt OR invoice OR payment OR transaction OR order OR purchase OR subscription)"
        else:
            search_query = f"newer_than:{time_range}"
            
        print(f"Using search query: {search_query}")
        
        results = gmail_service.users().messages().list(
            userId='me', q=search_query, maxResults=max_results).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            print("No messages found in the specified time range.")
            return []
        
        print(f"Found {len(messages)} emails newer than {time_range}")
        
        email_list = []
        for message in messages:
            email_details = get_email_details(gmail_service, message['id'])
            if email_details:
                email_list.append(email_details)
        
        return email_list
    
    except Exception as e:
        print(f"Error retrieving recent emails: {e}")
        return []

def display_email_list(emails):
    """
    Display a numbered list of emails with key information
    """
    print("\n=== Recent Emails ===")
    print(f"{'#':3} {'Date':<20} {'From':<30} {'Subject':<50}")
    print("-" * 103)
    
    for i, email in enumerate(emails, 1):
        from_truncated = email['from'][:30]
        subject_truncated = email['subject'][:50]
        print(f"{i:3} {email['date']:<20} {from_truncated:<30} {subject_truncated:<50}")

def save_extracted_data_to_json(data, email_id):
    """
    Save the extracted data to a JSON file for debugging
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"extracted_data_{timestamp}_{email_id[:6]}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Data saved to {filename}")
        return filename
    except Exception as e:
        print(f"Error saving data to file: {e}")
        return None

def get_existing_data(sheets_service, spreadsheet_id, sheet_range):
    """
    Retrieve existing data from Google Sheet to check for duplicates
    """
    try:
        if not spreadsheet_id:
            print("No spreadsheet ID provided, skipping duplicate check")
            return []
            
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_range
        ).execute()
        
        values = result.get('values', [])
        
        if not values or len(values) <= 1:  # Empty or only header row
            return []
        
        # Assume first row is header
        headers = ["vendor_name", "transaction_date", "total_amount", "currency", "description", "transaction_type"]
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
    """
    if not existing_entries:
        return False
        
    # Define fields that uniquely identify a transaction
    key_fields = ["vendor_name", "transaction_date", "total_amount", "currency"]
    
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

def mark_email_as_read(gmail_service, message_id):
    """
    Mark an email as read
    Args:
        gmail_service: Authenticated Gmail service
        message_id: ID of the email to mark as read
    """
    try:
        gmail_service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"Email {message_id} marked as read")
        return True
    except Exception as e:
        print(f"Error marking email as read: {e}")
        return False

def main():
    # Get API key (in production, use environment variables or secure storage)
    global GEMINI_API_KEY, SPREADSHEET_ID
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY is not set. Please set it as an environment variable or in the script.")
        GEMINI_API_KEY = input("Enter your Gemini API Key: ")
    
    # Authenticate Google services
    creds = authenticate_google_services()
    
    # Build Gmail service
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    # Build Sheets service if spreadsheet ID is provided
    sheets_service = None
    existing_data = []
    if SPREADSHEET_ID:
        sheets_service = build('sheets', 'v4', credentials=creds)
        # Get existing data for duplicate checking
        sheet_range_all = "Sheet1!A:F"  # Adjust based on your actual sheet structure
        existing_data = get_existing_data(sheets_service, SPREADSHEET_ID, sheet_range_all)
    else:
        print("No SPREADSHEET_ID provided. Duplicate checking will be disabled.")
        print("Set SPREADSHEET_ID in the script or as an environment variable to enable it.")
    
    # Initialize Gemini client
    gemini_model_instance = initialize_gemini_client(GEMINI_API_KEY, MODEL_NAME)
    
    while True:
        print("\n=== Gmail Debug Menu ===")
        print("1. List recent emails (default: 1 day)")
        print("2. Change time range")
        print("3. List recent financial emails only")
        print("4. Select and analyze an email")
        print("5. Check for duplicates in Google Sheet")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            time_range = "1d"  # Default time range: 1 day
            max_results = 10   # Default maximum results
            
            emails = get_recent_emails(gmail_service, time_range, max_results, filter_financial=False)
            
            if emails:
                display_email_list(emails)
        
        elif choice == '2':
            print("\nTime Range Options:")
            print("- Xh: X hours (e.g., 12h)")
            print("- Xd: X days (e.g., 3d)")
            print("- Xw: X weeks (e.g., 1w)")
            print("- Xm: X months (e.g., 1m)")
            
            time_range = input("\nEnter time range (default: 1d): ") or "1d"
            max_results = input("Maximum number of emails to retrieve (default: 10): ") or "10"
            
            try:
                max_results = int(max_results)
            except ValueError:
                print("Invalid number, using default: 10")
                max_results = 10
            
            emails = get_recent_emails(gmail_service, time_range, max_results, filter_financial=False)
            
            if emails:
                display_email_list(emails)
        
        elif choice == '3':
            time_range = input("\nEnter time range (default: 1d): ") or "1d"
            max_results = input("Maximum number of emails to retrieve (default: 10): ") or "10"
            
            try:
                max_results = int(max_results)
            except ValueError:
                print("Invalid number, using default: 10")
                max_results = 10
            
            emails = get_recent_emails(gmail_service, time_range, max_results, filter_financial=True)
            
            if emails:
                display_email_list(emails)
        
        elif choice == '4':
            if not 'emails' in locals() or not emails:
                print("No emails loaded. Please list emails first (option 1).")
                continue
            
            email_index = input("\nEnter the number of the email to analyze: ")
            
            try:
                email_index = int(email_index)
                if email_index < 1 or email_index > len(emails):
                    print(f"Invalid selection. Please enter a number between 1 and {len(emails)}.")
                    continue
                
                selected_email = emails[email_index - 1]
                
                print("\n=== Selected Email Details ===")
                print(f"From: {selected_email['from']}")
                print(f"Subject: {selected_email['subject']}")
                print(f"Date: {selected_email['date']}")
                print(f"ID: {selected_email['id']}")
                
                # Extract email body
                email_body = extract_email_body(selected_email['payload'])
                
                if email_body:
                    print("\n--- Email Content Preview (first 300 chars) ---")
                    print(email_body[:300] + "..." if len(email_body) > 300 else email_body)
                    
                    process = input("\nProcess this email with Gemini? (y/n): ").lower()
                    
                    if process == 'y':
                        print("\nProcessing email with Gemini AI...")
                        parsed_data = parse_email_with_gemini(gemini_model_instance, email_body)
                        
                        if parsed_data:
                            print("\n=== Extracted Financial Data ===")
                            print(f"Date: {parsed_data.get('date', 'Not found')}")
                            print(f"Amount: Rp {abs(float(parsed_data.get('amount', 0))):,.0f}")
                            print(f"Type: {'Pemasukan' if parsed_data.get('amount', 0) >= 0 else 'Pengeluaran'}")
                            print(f"Category: {parsed_data.get('category', 'Not found')}")
                            print(f"Description: {parsed_data.get('description', 'Not found')}")
                            
                            # Check if the transaction would be a duplicate
                            if sheets_service and existing_data:
                                if is_duplicate(parsed_data, existing_data):
                                    print("\n⚠️ WARNING: This transaction is a DUPLICATE of an existing entry in the sheet.")
                                else:
                                    print("\n✅ This transaction is NEW and not a duplicate.")
                            
                            save_option = input("\nSave extracted data to JSON file? (y/n): ").lower()
                            if save_option == 'y':
                                saved_file = save_extracted_data_to_json(parsed_data, selected_email['id'])
                                if saved_file:
                                    print(f"Data saved to {saved_file}")
                            
                            mark_option = input("\nMark email as read? (y/n): ").lower()
                            if mark_option == 'y':
                                mark_email_as_read(gmail_service, selected_email['id'])
                else:
                    print("Could not extract email body content.")
            
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        elif choice == '5':
            if not SPREADSHEET_ID or not sheets_service:
                print("Please provide a SPREADSHEET_ID to use this feature.")
                spreadsheet_id = input("Enter your Google Sheet ID: ")
                if spreadsheet_id:
                    SPREADSHEET_ID = spreadsheet_id
                    sheets_service = build('sheets', 'v4', credentials=creds)
                else:
                    continue
            
            sheet_range_all = "Sheet1!A:F"  # Adjust based on your actual sheet structure
            existing_data = get_existing_data(sheets_service, SPREADSHEET_ID, sheet_range_all)
            
            if not existing_data:
                print("No existing data found in the sheet or unable to access the sheet.")
                continue
                
            print("\n=== Duplicate Checking ===")
            print("Use this to check if a transaction would be considered a duplicate.")
            
            # Get transaction details from user
            vendor = input("Enter vendor name: ")
            date = input("Enter transaction date (YYYY-MM-DD): ")
            amount = input("Enter amount: ")
            currency = input("Enter currency: ")
            
            test_transaction = {
                "vendor_name": vendor,
                "transaction_date": date,
                "total_amount": amount,
                "currency": currency
            }
            
            if is_duplicate(test_transaction, existing_data):
                print("This transaction would be considered a DUPLICATE.")
            else:
                print("This transaction would be considered NEW (not a duplicate).")
                
        elif choice == '6':
            print("Exiting the debug tool.")
            break
        
        else:
            print("Invalid choice. Please enter a number between 1 and 6.")

if __name__ == "__main__":
    main() 