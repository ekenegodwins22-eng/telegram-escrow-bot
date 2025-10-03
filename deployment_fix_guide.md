# Deployment Fix Guide for Universal Telegram Escrow Bot

## Updated Koyeb Deployment Steps

1. Log in to your Koyeb account at [koyeb.com](https://www.koyeb.com/)
2. Create a new service or select your existing escrow bot service
3. Set the following configuration:
   - Runtime: Python 3.10
   - Build Command: `pip install -r requirements.txt`
   - Run Command: `python3 main.py` (This command starts both the Telegram bot and a Flask web server for Koyeb health checks.)
4. Set all required environment variables:
   - TELEGRAM_BOT_TOKEN
   - MONGODB_URI
   - ADMIN_IDS (comma-separated list of admin Telegram IDs)
5. Deploy the service

## How to Update Your Existing Koyeb Deployment

1. Navigate to your service in the Koyeb dashboard
2. Click on "Settings" tab
3. Update the Run Command to `python3 main.py`
4. Under "Runtime" section, select Python 3.10
5. Save changes and redeploy

## Troubleshooting Steps

If you encounter further issues:
1. Check the logs in Koyeb dashboard for specific error messages
2. Verify that all environment variables are correctly set
3. Ensure MongoDB connection is working properly
4. Try restarting the service

## Verifying Bot Operation

1. After successful deployment, send `/start` to your bot on Telegram
2. The bot should respond with a welcome message
3. Test the `/trade` command to ensure core functionality works
4. Monitor the logs in Koyeb dashboard for any errors

