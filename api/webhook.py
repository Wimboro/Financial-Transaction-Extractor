#!/usr/bin/env python3

import os
import json
import base64
from http.server import BaseHTTPRequestHandler
from datetime import datetime

# Import the main processing function
try:
    import sys
    sys.path.append('.')
    from api.process import process_emails
except ImportError:
    # Fallback if import fails
    def process_emails():
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Processing function not available'})
        }

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests - return status"""
        response = {
            'message': 'Gmail to Sheets Webhook Endpoint',
            'status': 'active',
            'timestamp': datetime.now().isoformat()
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        self.wfile.write(json.dumps(response).encode())
    
    def do_POST(self):
        """Handle POST requests - Gmail push notifications"""
        try:
            # Get the request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Parse the Gmail push notification
            try:
                notification_data = json.loads(post_data.decode('utf-8'))
                print(f"Received Gmail notification: {notification_data}")
                
                # Extract the Pub/Sub message
                if 'message' in notification_data:
                    message = notification_data['message']
                    
                    # Decode the data if it's base64 encoded
                    if 'data' in message:
                        try:
                            decoded_data = base64.b64decode(message['data']).decode('utf-8')
                            gmail_data = json.loads(decoded_data)
                            print(f"Gmail push data: {gmail_data}")
                        except Exception as e:
                            print(f"Error decoding Gmail data: {e}")
                            gmail_data = {}
                    else:
                        gmail_data = {}
                    
                    # Check if this is a relevant email notification
                    # Gmail sends notifications for various events, we want to process new emails
                    if gmail_data.get('historyId'):
                        print("Processing emails due to Gmail notification...")
                        
                        # Process emails
                        result = process_emails()
                        
                        self.send_response(result['statusCode'])
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        
                        self.wfile.write(result['body'].encode())
                        return
            
            except json.JSONDecodeError:
                print("Invalid JSON in webhook payload")
            
            # If we reach here, it's not a valid Gmail notification or no processing needed
            response = {
                'message': 'Webhook received but no processing required',
                'timestamp': datetime.now().isoformat()
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error processing webhook: {e}")
            
            error_response = {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(error_response).encode())
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers() 