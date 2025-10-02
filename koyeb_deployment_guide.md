# Koyeb Deployment Guide for Universal Telegram Escrow Bot

This guide provides step-by-step instructions for deploying the Universal Telegram Escrow Bot to Koyeb, a serverless platform that allows you to deploy applications quickly and efficiently.

## Prerequisites

Before you begin, ensure you have the following:

*   A GitHub account with the bot's repository (`telegram-escrow-bot`).
*   A Koyeb account (sign up at [koyeb.com](https://www.koyeb.com/)).
*   Your Telegram Bot Token obtained from BotFather.
*   A MongoDB Atlas account (sign up at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)).

## Deployment Steps

Follow these steps to deploy your Universal Telegram Escrow Bot on Koyeb:

### 1. Set up MongoDB Atlas

1.  **Create a MongoDB Atlas Account**: If you don't have one, sign up for a free account on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2.  **Create a New Cluster**: Follow the on-screen instructions to create a new free-tier (M0) cluster. Choose a cloud provider and region that offers low latency to your target user base (e.g., a region close to Nigeria for WAT timezone operations).
3.  **Configure Network Access**: In your Atlas project, navigate to **Network Access** and add your application's IP addresses (or temporarily allow access from anywhere for initial testing, then restrict later) to the IP Access List. This allows your Koyeb application to connect to the database.
4.  **Create a Database User**: In your Atlas project, navigate to **Database Access** and create a new database user with a strong password. This user will be used by the bot to connect to the database.
5.  **Retrieve Connection String**: Go to **Databases** -> **Connect** for your cluster. Choose **Connect your application** and copy the connection string. It will look something like `mongodb+srv://<username>:<password>@<cluster-name>.mongodb.net/<database-name>?retryWrites=true&w=majority`.

### 2. Deploy to Koyeb

1.  **Log in to Koyeb**: Go to [koyeb.com](https://www.koyeb.com/) and log in to your account.
2.  **Create a New Service**: Navigate to the **Services** page and click **Create Service**.
3.  **Connect to GitHub**: Select **GitHub** as the deployment method. If you haven't already, connect your GitHub account and authorize Koyeb to access your `telegram-escrow-bot` repository.
4.  **Configure Deployment Settings**:
    *   **Repository**: Select `ekenegodwins22-eng/telegram-escrow-bot`.
    *   **Branch**: Choose the branch you want to deploy (e.g., `main`).
    *   **Build Command**: Koyeb typically handles Python dependencies automatically by installing `requirements.txt`. For this project, the default should work.
    *   **Run Command**: Specify the command to start your bot:
        ```bash
        python3 main.py
        ```
5.  **Set Environment Variables**:
    In the Koyeb service configuration, navigate to the **Environment Variables** section and add the following:
    *   **Key:** `TELEGRAM_BOT_TOKEN`
    *   **Value:** Your actual Telegram Bot Token obtained from BotFather.
    *   **Key:** `MONGODB_URI`
    *   **Value:** The connection string you retrieved from MongoDB Atlas.
    *   **Key:** `ADMIN_IDS`
    *   **Value:** A comma-separated list of Telegram user IDs for your bot administrators (e.g., `123456789,987654321`).
    *   **Key:** `TZ`
    *   **Value:** `Africa/Lagos` (This ensures all time-related operations adhere to the Nigeria Time Zone (WAT)).

    **Important:** Always use environment variables for sensitive information and configuration. Never hardcode these values directly into your code.

6.  **Deploy the Service**: Review all your settings and click **Deploy** to initiate the deployment process. Monitor the build and deployment logs in the Koyeb dashboard for any issues.

## Post-Deployment

Once your bot is deployed and running, it will be accessible via Telegram. Ensure your bot is set up to receive updates (webhook or long polling). The provided `main.py` uses long polling, which should work out-of-the-box with Koyeb.

## Troubleshooting

*   **Bot not responding:** Check the Koyeb deployment logs for any errors during startup or runtime. Ensure `TELEGRAM_BOT_TOKEN` is correctly set.
*   **Dependencies not installed:** Verify that `requirements.txt` is correctly formatted and contains all necessary packages.

For further assistance, refer to the [Koyeb Documentation](https://www.koyeb.com/docs).
