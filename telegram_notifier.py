#!/usr/bin/env python3

import os
import requests
import json
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using environment variables directly.")

# Telegram API configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
# Support multiple chat IDs (comma-separated)
TELEGRAM_CHAT_IDS = [chat_id.strip() for chat_id in os.environ.get('TELEGRAM_CHAT_IDS', '').split(',') if chat_id.strip()]
# For backward compatibility
if not TELEGRAM_CHAT_IDS:
    single_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if single_chat_id:
        TELEGRAM_CHAT_IDS = [single_chat_id]
        
TELEGRAM_ENABLED = os.environ.get('TELEGRAM_ENABLED', 'false').lower() == 'true'

def format_amount(amount):
    """Format amount with currency symbol and thousands separator"""
    try:
        amount_float = float(amount)
        # Add Rp prefix and format with thousands separator
        if amount_float >= 0:
            return f"Rp {amount_float:,.0f}"
        else:
            return f"-Rp {abs(amount_float):,.0f}"
    except (ValueError, TypeError):
        return str(amount)

def send_message_to_chat(chat_id, message):
    """
    Send a message to a specific chat ID
    
    Args:
        chat_id: Telegram chat ID to send the message to
        message: The formatted message text
        
    Returns:
        Boolean indicating success/failure
    """
    if not TELEGRAM_BOT_TOKEN:
        return False
        
    try:
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(api_url, json=payload)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('ok'):
            print(f"Telegram notification sent to chat ID {chat_id}")
            return True
        else:
            print(f"Failed to send notification to chat ID {chat_id}: {response_data}")
            return False
    
    except Exception as e:
        print(f"Error sending message to chat ID {chat_id}: {e}")
        return False

def send_telegram_notification(transaction_data, account_id='default'):
    """
    Send a notification to all configured Telegram chat IDs about a new transaction
    
    Args:
        transaction_data: Dictionary containing transaction data
        account_id: The Gmail account ID that processed this transaction
    
    Returns:
        Boolean indicating whether the notification was sent successfully to at least one chat
    """
    if not TELEGRAM_ENABLED:
        print("Telegram notifications disabled.")
        return False
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        print("Telegram bot token or chat IDs not configured.")
        return False
    
    try:
        # Format the date if available
        date = transaction_data.get('date', '')
        try:
            # Convert YYYY-MM-DD to DD/MM/YYYY for display
            if date and len(date) == 10:  # Assuming YYYY-MM-DD format
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                date = date_obj.strftime("%d/%m/%Y")
        except Exception:
            # If date conversion fails, use the original date
            pass
        
        # Determine transaction type based on amount
        amount = transaction_data.get('amount', 0)
        try:
            amount_float = float(amount)
            transaction_type = "➕ Pemasukan" if amount_float >= 0 else "➖ Pengeluaran"
        except (ValueError, TypeError):
            transaction_type = "Transaksi"
        
        # Format the message
        message = f"*Ada {transaction_type} baru nih*\n\n"
        message += f"📅 Tanggal: {date}\n"
        message += f"💰 Jumlah: {format_amount(amount)}\n"
        message += f"🏷️ Kategori: {transaction_data.get('category', 'Not specified')}\n"
        
        # Add description if available
        description = transaction_data.get('description', '')
        if description:
            message += f"📝 Deskripsi: {description}\n"
        
        # Add source information
        message += f"\n📧 Sumber: Email dari {account_id}"
        
        # Send to all chat IDs
        success_count = 0
        for chat_id in TELEGRAM_CHAT_IDS:
            if send_message_to_chat(chat_id, message):
                success_count += 1
        
        print(f"Sent notification to {success_count} of {len(TELEGRAM_CHAT_IDS)} chat IDs")
        return success_count > 0
            
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")
        return False

def send_batch_notification(transaction_count, account_id='default'):
    """
    Send a summary notification for multiple transactions to all configured chat IDs
    
    Args:
        transaction_count: Number of transactions processed
        account_id: The Gmail account ID that processed these transactions
    
    Returns:
        Boolean indicating whether the notification was sent successfully to at least one chat
    """
    if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        return False
    
    try:
        # Current timestamp
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # Format the message
        message = f"*📊 Update Transaksi Massal*\n\n"
        message += f"✅ {transaction_count} transaksi baru telah ditambahkan ke spreadsheet\n"
        message += f"🕒 Waktu: {timestamp}\n"
        message += f"📧 Sumber: Email dari {account_id}"
        
        # Send to all chat IDs
        success_count = 0
        for chat_id in TELEGRAM_CHAT_IDS:
            if send_message_to_chat(chat_id, message):
                success_count += 1
        
        print(f"Sent batch notification to {success_count} of {len(TELEGRAM_CHAT_IDS)} chat IDs")
        return success_count > 0
            
    except Exception as e:
        print(f"Error sending batch notification: {e}")
        return False

if __name__ == "__main__":
    # Test the notification
    test_transaction = {
        "date": "2023-11-15",
        "amount": -50000,
        "category": "Food",
        "description": "Lunch at Restaurant"
    }
    
    success = send_telegram_notification(test_transaction, "test_account")
    print(f"Test notification {'sent successfully' if success else 'failed'}")
    
    # Test batch notification
    batch_success = send_batch_notification(5, "test_account")
    print(f"Test batch notification {'sent successfully' if batch_success else 'failed'}") 