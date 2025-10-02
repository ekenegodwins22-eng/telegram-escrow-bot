# Koyeb Deployment Guide for Universal Telegram Escrow Bot

This guide provides step-by-step instructions for deploying the Universal Telegram Escrow Bot to Koyeb, a serverless platform that allows you to deploy applications quickly and efficiently.

## Prerequisites

Before you begin, ensure you have the following:

*   A GitHub account with the bot's repository (`telegram-escrow-bot`).
*   A Koyeb account (sign up at [koyeb.com](https://www.koyeb.com/)).
*   Your Telegram Bot Token obtained from BotFather.

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
*   **Build Command:** Koyeb typically handles Python dependencies automatically by installing `requirements.txt`. If you have a custom build process, specify it here. For this project, the default should work.
*   **Run Command:** Specify the command to start your bot. For this project, it will be:
    ```bash
    python3.11 main.py
    ```

### 4. Set Environment Variables

This is a crucial step. Your bot requires the `TELEGRAM_BOT_TOKEN` and `ADMIN_IDS` to function. No other Telegram API keys are needed.

1.  In the Koyeb service configuration, navigate to the **Environment Variables** section.
2.  Add the following environment variables:
    *   **Key:** `TELEGRAM_BOT_TOKEN`
    *   **Value:** Your actual Telegram Bot Token (e.g., `123456:ABC-DEF1234ghIkl-789_jklmnoPQRSTUV`)
    *   **Key:** `ADMIN_IDS`
    *   **Value:** A comma-separated list of Telegram user IDs for your bot administrators (e.g., `123456789,987654321`)

    **Important:** Never hardcode your bot token or admin IDs directly into your code. Always use environment variables for sensitive information.

### 5. Deploy the Service

1.  Review all your settings.
2.  Click **Deploy** to start the deployment process.

Koyeb will now fetch your code from GitHub, install dependencies, and run your bot. You can monitor the deployment logs in the Koyeb dashboard.

## Post-Deployment

Once your bot is deployed and running, it will be accessible via Telegram. Ensure your bot is set up to receive updates (webhook or long polling). The provided `main.py` uses long polling, which should work out-of-the-box with Koyeb.

## Troubleshooting

*   **Bot not responding:** Check the Koyeb deployment logs for any errors during startup or runtime. Ensure `TELEGRAM_BOT_TOKEN` is correctly set.
*   **Dependencies not installed:** Verify that `requirements.txt` is correctly formatted and contains all necessary packages.

For further assistance, refer to the [Koyeb Documentation](https://www.koyeb.com/docs).
