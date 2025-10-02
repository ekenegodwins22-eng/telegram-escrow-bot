# Fixing Koyeb Deployment for Universal Telegram Escrow Bot

This guide provides detailed instructions to resolve the `bash: line 1: python3.11: command not found` error encountered during the deployment of your Universal Telegram Escrow Bot on Koyeb. It includes updates to your repository, instructions for modifying Koyeb settings, troubleshooting tips, and verification steps.

## Summary of Changes Made to Your Repository

To address the deployment issue, the following changes have been made to your `telegram-escrow-bot` repository:

1.  **`koyeb_deployment_guide.md`**: The run command in the deployment guide has been updated from `python3.11 main.py` to `python3 main.py`. This ensures compatibility with Koyeb's default Python 3 interpreter, which is typically aliased as `python3`.
2.  **`main.py`**: No changes were required for `main.py` as the code appears to be compatible with standard Python 3 environments.
3.  **`requirements.txt`**: The `requirements.txt` file has been updated to explicitly include `pytz` and specify a version for `python-telegram-bot` for better dependency management and to prevent potential issues with future incompatible updates. The updated `requirements.txt` now contains:
    ```
    python-telegram-bot==20.7
    pymongo==4.6.0
    pytz==2024.1
    ```

## Updated Koyeb Deployment Steps

Follow these revised steps to deploy your Universal Telegram Escrow Bot on Koyeb:

### 1. Set up MongoDB Atlas (No Change)

1.  **Create a MongoDB Atlas Account**: If you don't have one, sign up for a free account on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2.  **Create a New Cluster**: Follow the on-screen instructions to create a new free-tier (M0) cluster. Choose a cloud provider and region that offers low latency to your target user base.
3.  **Configure Network Access**: In your Atlas project, navigate to **Network Access** and add your application's IP addresses (or temporarily allow access from anywhere for initial testing, then restrict later) to the IP Access List.
4.  **Create a Database User**: In your Atlas project, navigate to **Database Access** and create a new database user with a strong password.
5.  **Retrieve Connection String**: Go to **Databases** -> **Connect** for your cluster. Choose **Connect your application** and copy the connection string. It will look something like `mongodb+srv://<username>:<password>@<cluster-name>.mongodb.net/<database-name>?retryWrites=true&w=majority`.

### 2. Deploy to Koyeb (Revised)

1.  **Log in to Koyeb**: Go to [koyeb.com](https://www.koyeb.com/) and log in to your account.
2.  **Create a New Service**: Navigate to the **Services** page and click **Create Service**.
3.  **Connect to GitHub**: Select **GitHub** as the deployment method. If you haven't already, connect your GitHub account and authorize Koyeb to access your `telegram-escrow-bot` repository.
4.  **Configure Deployment Settings**:
    *   **Repository**: Select `ekenegodwins22-eng/telegram-escrow-bot`.
    *   **Branch**: Choose the branch you want to deploy (e.g., `main`).
    *   **Build Command**: Koyeb typically handles Python dependencies automatically by installing `requirements.txt`. For this project, the default should work.
    *   **Run Command**: **IMPORTANT CHANGE** Specify the command to start your bot as:
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

## How to Update Your Existing Koyeb Deployment Settings

If you have an existing service on Koyeb, you can update its settings without creating a new service:

1.  **Log in to Koyeb**: Go to [koyeb.com](https://www.koyeb.com/) and log in to your account.
2.  **Navigate to Your Service**: From the dashboard, select your `telegram-escrow-bot` service.
3.  **Access Settings**: Go to the **Settings** tab for your service.
4.  **Update Run Command**: Locate the **Run Command** field. Change its value from `python3.11 main.py` to `python3 main.py`.
5.  **Verify Environment Variables**: Ensure all necessary environment variables (`TELEGRAM_BOT_TOKEN`, `MONGODB_URI`, `ADMIN_IDS`, `TZ`) are correctly set.
6.  **Redeploy**: Save your changes. Koyeb will automatically trigger a redeployment of your service with the updated configuration.

## Troubleshooting Steps if the Error Persists

If the `command not found` error or other deployment issues persist after making these changes, consider the following:

1.  **Check Build Logs Carefully**: In the Koyeb dashboard, review the build logs for any errors during the dependency installation phase. Ensure `requirements.txt` is being processed correctly.
2.  **Specify Python Version (Advanced)**: Although `python3` should work, if Koyeb's environment has a specific Python version requirement or if you want to ensure a particular version, you can add a `.python-version` file to the root of your repository with the desired version (e.g., `3.11` or `3.10`). Koyeb supports Python versions 3.9, 3.10, 3.11, 3.12, and 3.13 [1].
3.  **Verify `requirements.txt` Path**: Ensure `requirements.txt` is in the root directory of your repository. If it's in a subdirectory, you might need to specify a custom build command to install dependencies from that location.
4.  **Koyeb Support**: If all else fails, reach out to Koyeb support with your deployment logs. They can provide insights into the specific build environment and potential conflicts.

## How to Verify the Bot is Running Correctly

Once your bot is deployed and shows a 
