# Service Account Setup for Google Sheets Access

This project now uses **Service Account credentials** for Google Sheets access instead of OAuth credentials. This provides better security and automation capabilities.

## Why Service Account?

- **No manual authorization**: Service accounts don't require manual OAuth flow
- **Better for automation**: Perfect for scheduled scripts and CI/CD pipelines
- **Separate permissions**: Gmail access uses OAuth, Sheets access uses Service Account
- **Enhanced security**: Different credential types for different services

## Setup Instructions

### 1. Create Service Account in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Sheets API** for your project:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click on it and press "Enable"

### 2. Create Service Account

1. Go to "IAM & Admin" > "Service Accounts"
2. Click "Create Service Account"
3. Enter details:
   - **Name**: `gmail-sheets-processor` (or any descriptive name)
   - **Description**: `Service account for Gmail to Sheets automation`
4. Click "Create and Continue"

### 3. Set Permissions

Grant one of these roles:
- **Recommended**: "Editor" role (simple but broad)
- **Advanced**: Create custom role with specific permissions:
  - `sheets.spreadsheets.batchGet`
  - `sheets.spreadsheets.batchUpdate`
  - `sheets.spreadsheets.get`
  - `sheets.spreadsheets.values.append`
  - `sheets.spreadsheets.values.batchGet`
  - `sheets.spreadsheets.values.batchUpdate`
  - `sheets.spreadsheets.values.get`
  - `sheets.spreadsheets.values.update`

Click "Done" to create the service account.

### 4. Generate Credentials File

1. Click on the newly created service account
2. Go to the "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose "JSON" format
5. Download the file
6. **Rename it to `sa-credentials.json`**
7. **Place it in the same directory as your Python script**

### 5. Share Spreadsheet with Service Account

**This is crucial!** The service account needs access to your spreadsheet:

1. Open your Google Spreadsheet
2. Click the "Share" button
3. Add the **service account email** (found in the `client_email` field of your `sa-credentials.json`)
4. Give it "Editor" permissions
5. Click "Send"

## File Structure

Your project directory should look like this:

```
your-project/
├── gmail_to_sheets.py
├── sa-credentials.json          # ← Service account credentials
├── credentials.json             # ← OAuth credentials (for Gmail)
├── token_default.json           # ← Generated OAuth tokens
├── sa-credentials.json.template # ← Template file (optional)
└── .env                         # ← Environment variables
```

## Verification

When you run the script, you should see:

```
Service account email: your-service-account@your-project.iam.gserviceaccount.com
Remember to share your Google Spreadsheet with this email address!
Successfully authenticated with Google Sheets using service account
```

## Troubleshooting

### Error: "Service account credentials file not found"
- Make sure `sa-credentials.json` is in the same directory as your script
- Check the filename is exactly `sa-credentials.json`

### Error: "Permission denied" or "The caller does not have permission"
- Share your Google Spreadsheet with the service account email
- Make sure you gave "Editor" permissions
- Verify Google Sheets API is enabled in your project

### Error: "Invalid JSON"
- Re-download the credentials file from Google Cloud Console
- Make sure the file wasn't corrupted during download/transfer

### Error: "Service account file is missing required fields"
- Make sure you downloaded the correct JSON file (not a different type)
- The file should have `type: "service_account"`

## Security Notes

- **Never commit `sa-credentials.json` to version control**
- Add it to your `.gitignore` file
- Store it securely in production environments
- Rotate credentials periodically for enhanced security

## Environment Variables

Update your `.env` file:

```env
# Gmail OAuth (still needed for Gmail access)
GMAIL_ACCOUNTS=your-gmail@gmail.com

# Google Sheets
SPREADSHEET_ID=your-spreadsheet-id-here

# Other settings
GEMINI_API_KEY=your-gemini-api-key
GMAIL_SEARCH_QUERY=subject:(Transfer OR payment) is:unread newer_than:1d
PROCESSOR_USER_ID=email-processor-main
```

The script will now:
- Use **OAuth** for Gmail access (requires `credentials.json`)
- Use **Service Account** for Sheets access (requires `sa-credentials.json`) 