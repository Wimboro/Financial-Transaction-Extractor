# Deploying Gmail to Sheets Project to Vercel

This guide will help you deploy your Gmail to Google Sheets automation project to Vercel as serverless functions.

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **Vercel CLI**: Install globally with `npm install -g vercel`
3. **Google Cloud Project**: Set up with Gmail API and Sheets API enabled
4. **OAuth Credentials**: Obtained from Google Cloud Console
5. **Gemini API Key**: From Google AI Studio

## Step 1: Prepare Your OAuth Credentials

Since Vercel doesn't support the interactive OAuth flow, you need to get your OAuth tokens locally first:

1. Run your original script locally once to authenticate:
   ```bash
   python gmail_to_sheets.py
   ```

2. After authentication, find your token file (e.g., `token_default.json` or `token_wgppra.json`)

3. Extract the credentials from the token file. You'll need:
   - `token` (access token)
   - `refresh_token`
   - `client_id`
   - `client_secret`

## Step 2: Set Up Environment Variables in Vercel

### Option A: Using Vercel CLI

```bash
# Navigate to your project directory
cd /path/to/your/project

# Login to Vercel
vercel login

# Set environment variables
vercel env add GEMINI_API_KEY
vercel env add SPREADSHEET_ID
vercel env add GOOGLE_ACCESS_TOKEN
vercel env add GOOGLE_REFRESH_TOKEN
vercel env add GOOGLE_CLIENT_ID
vercel env add GOOGLE_CLIENT_SECRET

# Optional: Telegram settings
vercel env add TELEGRAM_ENABLED
vercel env add TELEGRAM_BOT_TOKEN
vercel env add TELEGRAM_CHAT_IDS

# Optional: Other settings
vercel env add PROCESSOR_USER_ID
vercel env add GMAIL_SEARCH_QUERY
```

### Option B: Using Vercel Dashboard

1. Go to your project in the Vercel dashboard
2. Navigate to Settings → Environment Variables
3. Add the following variables:

**Required Variables:**
- `GEMINI_API_KEY`: Your Gemini API key
- `SPREADSHEET_ID`: Your Google Sheets ID
- `GOOGLE_ACCESS_TOKEN`: From your token file
- `GOOGLE_REFRESH_TOKEN`: From your token file
- `GOOGLE_CLIENT_ID`: From your OAuth credentials
- `GOOGLE_CLIENT_SECRET`: From your OAuth credentials

**Optional Variables:**
- `TELEGRAM_ENABLED`: `true` or `false`
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_IDS`: Comma-separated chat IDs
- `PROCESSOR_USER_ID`: Custom user ID (default: `email-processor`)
- `GMAIL_SEARCH_QUERY`: Custom search query

## Step 3: Deploy to Vercel

### Option A: Using Vercel CLI

```bash
# Deploy to production
vercel --prod

# Or deploy for testing first
vercel
```

### Option B: Using Git Integration

1. Push your code to GitHub/GitLab/Bitbucket
2. Connect your repository to Vercel
3. Vercel will automatically deploy on every push

## Step 4: Test Your Deployment

After deployment, you'll get URLs like:
- `https://your-project.vercel.app/api/process` - Main processing endpoint
- `https://your-project.vercel.app/api/webhook` - Webhook endpoint

### Test the Processing Endpoint

```bash
# Test with GET request
curl https://your-project.vercel.app/api/process

# Test with POST request
curl -X POST https://your-project.vercel.app/api/process
```

### Test the Webhook Endpoint

```bash
# Test webhook status
curl https://your-project.vercel.app/api/webhook
```

## Step 5: Set Up Automated Processing

### Option A: Using Vercel Cron Jobs (Pro Plan Required)

Add to your `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/process",
      "schedule": "0 * * * *"
    }
  ]
}
```

### Option B: Using External Cron Services

Use services like:
- **Cron-job.org**: Free cron service
- **EasyCron**: Reliable cron service
- **GitHub Actions**: If your code is on GitHub

Example GitHub Action (`.github/workflows/process-emails.yml`):

```yaml
name: Process Gmail Emails
on:
  schedule:
    - cron: '0 * * * *'  # Every hour
  workflow_dispatch:  # Manual trigger

jobs:
  process:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Vercel Function
        run: |
          curl -X POST https://your-project.vercel.app/api/process
```

## Step 6: Set Up Gmail Push Notifications (Optional)

For real-time processing, set up Gmail push notifications:

1. **Create a Pub/Sub Topic** in Google Cloud Console
2. **Create a Subscription** pointing to your webhook URL:
   ```
   https://your-project.vercel.app/api/webhook
   ```
3. **Set up Gmail Watch** using the Gmail API:
   ```bash
   curl -X POST \
     'https://gmail.googleapis.com/gmail/v1/users/me/watch' \
     -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
     -H 'Content-Type: application/json' \
     -d '{
       "topicName": "projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME",
       "labelIds": ["INBOX"]
     }'
   ```

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Ensure all OAuth credentials are correctly set
   - Check that tokens haven't expired
   - Verify scopes are correct

2. **Function Timeout**:
   - Vercel has a 10-second timeout on Hobby plan
   - Consider upgrading to Pro for 60-second timeout
   - Optimize your code to process fewer emails per run

3. **Import Errors**:
   - Ensure all dependencies are in `requirements.txt`
   - Check Python version compatibility (Vercel supports 3.9)

4. **Environment Variables Not Loading**:
   - Verify variables are set in Vercel dashboard
   - Check variable names match exactly
   - Redeploy after adding new variables

### Debugging

1. **Check Vercel Function Logs**:
   ```bash
   vercel logs
   ```

2. **Test Locally**:
   ```bash
   vercel dev
   ```

3. **Monitor Function Performance**:
   - Use Vercel dashboard analytics
   - Check function execution time
   - Monitor error rates

## Security Considerations

1. **Environment Variables**: Never commit sensitive data to your repository
2. **OAuth Tokens**: Regularly refresh tokens and monitor for unauthorized access
3. **API Keys**: Use least-privilege principles for all API keys
4. **Webhook Security**: Consider adding webhook signature verification

## Cost Considerations

- **Vercel Hobby Plan**: 100GB-hours of function execution per month (free)
- **Vercel Pro Plan**: 1000GB-hours per month ($20/month)
- **Google API Costs**: Gmail API and Sheets API have generous free tiers
- **Gemini API Costs**: Pay per request based on usage

## Monitoring and Maintenance

1. **Set up monitoring** for function failures
2. **Monitor API quotas** for Google services
3. **Regularly check logs** for errors
4. **Update dependencies** periodically
5. **Monitor costs** if using paid plans

## Next Steps

After successful deployment:
1. Test with real emails
2. Monitor for a few days to ensure stability
3. Set up alerting for failures
4. Consider adding more features like email filtering or custom categories
5. Document your specific configuration for team members 