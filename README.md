# Universal Telegram Escrow Bot

## Project Overview

The Universal Telegram Escrow Bot is designed to facilitate secure and trustworthy transactions between users on Telegram. It acts as a neutral third-party, holding funds in escrow until both the buyer and seller have fulfilled their agreed-upon obligations. This system is built to prevent fraud, ensure fair exchanges, and provide a reliable platform for peer-to-peer transactions within the Telegram ecosystem.

## Key Features

*   **Secure Escrow System:** Funds are held securely by the bot until all trade conditions are met by both parties.
*   **Detailed Trade Flows:** Comprehensive step-by-step processes for both buying and selling various types of items, including digital assets, cryptocurrencies, services, and physical goods.
*   **Unique Trade Identification:** Each trade is assigned a unique Trade ID for easy tracking, communication, and management.
*   **Shareable Trade Links:** Buyers can generate and share unique links with sellers to initiate and confirm trades.
*   **Flexible Payment Methods:** Support for various payment methods, including bank transfers and cryptocurrency (USDT, USDC, BTC, ETH, other ERC20/BEP20 tokens).
*   **Admin Verification & Dispute Resolution:** An administrative dashboard and process for verifying payments, resolving disputes, and ensuring fair outcomes.
*   **Automated Reminders & Deadlines:** The bot sends automated reminders for payment and delivery deadlines, with auto-cancellation features for unfulfilled obligations.
*   **Nigeria Time Zone (WAT):** All time-sensitive operations, including deadlines and reminders, are managed according to the West African Time (WAT) zone.
*   **Transparent Fee Structure:** A clear, tiered fee structure is applied, with fees typically borne by the seller.
*   **Admin Force Release Option:** Administrators can force the release of an asset if a seller is unresponsive or refusing to release after payment, ensuring trade progression.
*   **Manual Refund Process:** A structured `/refund` command for buyers, involving admin verification and careful collection of original payment details to ensure secure and accurate refunds.
*   **Admin User Identification:** The bot identifies administrators via `ADMIN_IDS` environment variable, granting them access to privileged commands and features.
*   **Comprehensive Admin Dashboard:** A `/dashboard` command providing daily summaries (WAT) and on-demand full trade history (`/view`), including total trades, pending trades, open disputes, refunds issued, and escrow volume by currency.

## How it Works (High-Level Flow)

1.  **Initiate Trade:** A user (buyer or seller) starts a trade using the `/trade` command.
2.  **Specify Item & Details:** Users provide details about the item/service, price, currency, payment method, and deadline.
3.  **Review & Share:** The bot summarizes the trade details, calculates fees (seller sees net amount), generates a unique Trade ID, and provides a shareable link for the counterparty.
4.  **Counterparty Approval:** The other party reviews and approves the trade.
5.  **Buyer Pays:** The buyer sends payment to the bot (escrow) and provides proof.
6.  **Admin Verification:** An admin verifies the payment. If rejected, the admin provides a reason to the buyer.
7.  **Seller Releases Asset:** Upon payment verification, the seller releases the asset/service to the buyer.
8.  **Buyer Confirms Receipt:** The buyer confirms receipt, and funds are released to the seller (minus fees).
9.  **Dispute/Refund (if applicable):** If issues arise, a dispute can be raised, or a manual refund process initiated by the buyer (requiring admin approval and verification of original payment details).

## Deployment

This bot is designed for deployment on platforms like Koyeb. A detailed deployment guide is available:

*   [Koyeb Deployment Guide](koyeb_deployment_guide.md)

## Getting Started (Development)

To run this bot locally for development or testing:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ekenegodwins22-eng/telegram-escrow-bot.git
    cd telegram-escrow-bot
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set up environment variables:**
    Create a `.env` file based on `.env.example` and replace `YOUR_BOT_TOKEN` with your actual Telegram Bot Token and `ADMIN_IDS` with the Telegram user IDs of your administrators.
    ```
    TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
    MONGODB_URI=mongodb://localhost:27017/
    ADMIN_IDS=123456789,987654321
    ```
4.  **Run the bot:**
    ```bash
    python3.11 main.py
    ```

## State Machine Diagram

The core logic of the trade flow is managed by a state machine, ensuring robust and predictable transitions between trade statuses. A visual representation of this state machine is provided below:

![Trade State Machine](state_machine.png)

## Contributing

Contributions are welcome! Please feel free to fork the repository, make your changes, and submit a pull request.
