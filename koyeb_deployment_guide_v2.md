# Koyeb Deployment Guide for Universal Telegram Escrow Bot (v2)

This guide provides updated step-by-step instructions for deploying the Universal Telegram Escrow Bot to Koyeb, a serverless platform. This version of the guide is tailored for the enhanced bot functionality and refined codebase (`main_v2.py`).

## Prerequisites

Before you begin, ensure you have the following:

*   A GitHub account with the bot's repository (`telegram-escrow-bot`).
*   A Koyeb account (sign up at [koyeb.com](https://www.koyeb.com/)).
*   Your Telegram Bot Token obtained from BotFather.
*   A MongoDB Atlas account and connection string (`MONGODB_URI`).

## Deployment Steps

Follow these steps to deploy your Telegram Escrow Bot on Koyeb:

### 1. Create a New Koyeb Service

1.  Log in to your Koyeb account.
2.  Navigate to the **Services** page and click **Create Service**.
3.  Select **GitHub** as the deployment method.

### 2. Connect to GitHub

1.  If you haven't already, connect your GitHub account to Koyeb. You might need to authorize Koyeb to access your repositories.
2.  Select the `telegram-escrow-bot` repository from your list of repositories.

### 3. Configure Deployment

Koyeb will automatically detect that it's a Python application. You may need to adjust some settings:

*   **Branch:** Choose the branch you want to deploy (e.g., `master` or `main`).
*   **Runtime:** Select **Python 3.10**.
*   **Build Command:** `pip install -r requirements_v2.txt`
*   **Run Command:** `python3 main_v2.py`

### 4. Set Environment Variables

This is a crucial step. Your bot requires the following environment variables to function:

1.  In the Koyeb service configuration, navigate to the **Environment Variables** section.
2.  Add the following environment variables:
    *   **Key:** `TELEGRAM_BOT_TOKEN`
    *   **Value:** Your actual Telegram Bot Token (e.g., `123456:ABC-DEF1234ghIkl-789_jklmnoPQRSTUV`)
    *   **Key:** `MONGODB_URI`
    *   **Value:** Your MongoDB Atlas connection string.
    *   **Key:** `ADMIN_IDS`
    *   **Value:** A comma-separated list of Telegram user IDs for your bot administrators (e.g., `123456789,987654321`)
    *   **Key:** `PORT`
    *   **Value:** `8080` (This is the port your Flask app listens on for health checks)

    **Important:** Never hardcode your bot token, MongoDB URI, or admin IDs directly into your code. Always use environment variables for sensitive information.

### 5. Configure Health Checks

To ensure your application remains active and responsive on Koyeb, configure a health check:

1.  In the Koyeb service configuration, navigate to the **Health Checks** section.
2.  Add a new HTTP health check:
    *   **Path:** `/`
    *   **Port:** `8080` (Matches the port your Flask app is running on)
    *   **Interval:** `30s` (Recommended interval, adjust as needed)
    *   **Timeout:** `10s` (Recommended timeout, adjust as needed)

This health check will periodically ping your Flask application's root endpoint (`/`). As long as the Flask app responds with a 200 OK status, Koyeb will consider your service healthy and keep it running.

### 6. Deploy the Service

1.  Review all your settings.
2.  Click **Deploy** to start the deployment process.

Koyeb will now fetch your code from GitHub, install dependencies using `requirements_v2.txt`, and run your bot using `main_v2.py`. The integrated Flask web server will keep the application alive and respond to Koyeb's health checks.

## Post-Deployment

Once your bot is deployed and running, it will be accessible via Telegram. The bot uses long polling, which will run in a separate thread, while the Flask web server handles health checks.

## Troubleshooting

*   **Bot not responding:** Check the Koyeb deployment logs for any errors during startup or runtime. Ensure all environment variables are correctly set.
*   **Dependencies not installed:** Verify that `requirements_v2.txt` is correctly formatted and contains all necessary packages.
*   **MongoDB Connection Issues:** Ensure your MongoDB Atlas cluster is accessible and the `MONGODB_URI` is correct.
*   **Health Check Failures:** Double-check the health check configuration (path and port) in Koyeb to match your Flask application.

For further assistance, refer to the [Koyeb Documentation](https://www.koyeb.com/docs).
