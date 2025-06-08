<!-- GitAds-Verify: 6G765HGS8TACYKYZLJBUW31E4E2OC1LL -->
# Gmail to Google Sheets Financial Transaction Extractor

This Python script automates the extraction of financial transaction data from Gmail emails, parses this data using Google's Gemini AI model, and records the structured data into a Google Sheet.

## Features

- Extracts financial transaction data from Gmail emails matching search criteria
- Uses Google's Gemini AI model to parse email content into structured data
- Records extracted data into a Google Sheet
- Marks processed emails with a custom label
- Supports multiple Gmail accounts
- Sends notifications to Telegram when new transactions are recorded

## Requirements

- Python 3.7+
- Google account with Gmail and Google Sheets
- Gemini API key from Google AI Studio

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up Google API credentials:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Gmail API and Google Sheets API
   - Create OAuth 2.0 credentials
   - Download the credentials JSON file and save it as `credentials.json` in the project directory

3. Get a Gemini API key:
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key

4. Configure environment variables:
   - Copy the `env_sample` file to `.env`
   - Set your Gemini API key and Google Sheet ID in the `.env` file
   ```
   cp env_sample .env
   # Edit .env with your API key and Sheet ID
   ```
   - Alternatively, set them as environment variables:
   ```
   export GEMINI_API_KEY="your-api-key"
   export SPREADSHEET_ID="your-spreadsheet-id"
   ```

5. Configure the script (optional):
   - Adjust other settings in the `.env` file if needed
   - Customizable options include:
     - `PROCESSOR_USER_ID`: Identifier for transactions added by the email processor
     - `GMAIL_SEARCH_QUERY`: Custom query to filter which emails to process
     - `GMAIL_ACCOUNTS`: Comma-separated list of Gmail accounts to process

6. Set up Telegram notifications (optional):
   - Create a Telegram bot using [BotFather](https://t.me/botfather) and get your bot token
   - Get your chat ID by sending a message to your bot and visiting: `https://api.telegram.org/bot<YourBOTToken>/getUpdates`
   - Configure Telegram settings in your `.env` file:
     ```
     TELEGRAM_ENABLED=true
     TELEGRAM_BOT_TOKEN=your_telegram_bot_token
     TELEGRAM_CHAT_IDS=id1,id2,id3
     ```
   - For multiple recipients, add all chat IDs as a comma-separated list
   - Chat IDs can be:
     - Individual users: The user must first send a message to your bot
     - Groups: Add your bot to a group and get the group chat ID
     - Channels: Add your bot as an administrator to your channel

## Usage

Run the script:

```
python gmail_to_sheets.py
```

The first time you run the script, it will open a browser window to authenticate with your Google account. After authentication, a token will be saved for future use.

### Using Multiple Gmail Accounts

The script supports processing multiple Gmail accounts:

1. Configure accounts in the `.env` file:
   ```
   GMAIL_ACCOUNTS=personal,work,finance
   ```

2. Or specify accounts as a command-line argument:
   ```
   python gmail_to_sheets.py personal,work,finance
   ```

3. For each account, the script will:
   - Use a separate token file (e.g., `token_personal.json`, `token_work.json`)
   - Prompt for authentication if needed
   - Process emails independently
   - Mark transactions with account-specific user IDs

When you first run the script with multiple accounts, it will prompt you to authenticate each account separately.

### Automatic Scheduling

To run the script automatically at regular intervals:

#### On Linux/Mac (using cron):

1. Open your crontab file:
   ```
   crontab -e
   ```

2. Add a line to run the script hourly (adjust the timing as needed):
   ```
   0 * * * * cd /path/to/script/directory && python gmail_to_sheets.py >> gmail_log.txt 2>&1
   ```

#### On Windows (using Task Scheduler):

1. Open Task Scheduler
2. Create a new Basic Task
3. Set the trigger (e.g., Daily or Hourly)
4. Set the action to start a program: `python.exe`
5. Add arguments: `/path/to/gmail_to_sheets.py`
6. Set the start in directory: `/path/to/script/directory`

The script is designed to:
- Process only new emails (received within the last day)
- Avoid adding duplicate header rows to the spreadsheet
- Skip transactions that have already been added to the spreadsheet
- Automatically mark processed emails as read and add a "Processed-Financial" label

## How It Works

1. The script authenticates with Google services using OAuth 2.0
2. It searches Gmail for **new emails** (received within the last day) matching the specified criteria
3. For each email, it extracts the message body
4. The Gemini AI model analyzes the email content and extracts financial transaction data
5. The extracted data is appended to the specified Google Sheet
6. Processed emails are marked as read and labeled with "Processed-Financial"

## Customization

- Modify the search query to filter different types of financial emails or change the time window (default is 1 day)
- Adjust the Gemini prompt to extract different data fields
- Change the output format in the Google Sheet 
