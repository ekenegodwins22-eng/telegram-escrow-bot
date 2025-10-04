

'''
Universal Telegram Escrow Bot - Comprehensive Implementation

This script implements a Telegram Escrow Bot with the following features:
- Secure trade initiation and management
- Buyer and seller approval flow
- Admin verification and dispute resolution
- MongoDB for data persistence
- Flask for health checks on Koyeb
- Timezone handling for WAT (West Africa Time)
'''

import logging
import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
)
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime, timedelta
import pytz
import uuid

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment Variables & Configuration ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set. Exiting.")
    exit(1)

MONGODB_URI = os.environ.get("MONGODB_URI")
if not MONGODB_URI:
    logger.error("MONGODB_URI environment variable not set. Exiting.")
    exit(1)

ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(uid.strip()) for uid in ADMIN_IDS_STR.split(",") if uid.strip()]

# --- Timezone Setup ---
WAT = pytz.timezone("Africa/Lagos")

# --- MongoDB Connection ---
client = None
db = None
users_collection = None
trades_collection = None

try:
    client = MongoClient(MONGODB_URI)
    db = client.escrow_bot
    users_collection = db.users
    trades_collection = db.trades
    client.admin.command("ismaster")
    logger.info("Successfully connected to MongoDB.")
except ConnectionFailure as e:
    logger.error(f"Could not connect to MongoDB: {e}")
    exit(1)

# --- Conversation Handler States ---
(
    ITEM_CATEGORY,
    ITEM_DESCRIPTION,
    PRICE,
    CURRENCY,
    PAYMENT_METHOD,
    DEADLINE,
    COUNTERPARTY_ID,
    CONFIRMATION,
) = range(8)

SUBMIT_PAYMENT_PROOF = 0
REFUND_REASON = 0

# --- Helper Functions ---
def get_current_time():
    '''Returns the current time in WAT.'''
    return datetime.now(WAT)

def is_admin(user_id: int) -> bool:
    '''Checks if a user ID belongs to an administrator.'''
    return user_id in ADMIN_IDS



async def register_user(user_id: int, username: str, first_name: str, last_name: str = None):
    """Registers a user in the database if they don't exist."""
    if not users_collection:
        logger.error("MongoDB users_collection not initialized.")
        return
    try:
        user = users_collection.find_one({"telegram_id": user_id})
        if not user:
            users_collection.insert_one({
                "telegram_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "is_admin": user_id in ADMIN_IDS, # Set admin status based on env var initially
                "created_at": get_current_time(),
                "updated_at": get_current_time()
            })
            logger.info(f"New user registered: {username} ({user_id})")
        else:
            # Update existing user info if necessary
            users_collection.update_one(
                {"telegram_id": user_id},
                {"$set": {
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "updated_at": get_current_time()
                }}
            )
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed while registering/updating user {user_id}: {e}")

async def start(update: Update, context: CallbackContext) -> None:
    """Sends a welcome message when the /start command is issued and registers the user."""
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name, user.last_name)

    welcome_message = "Welcome to the Universal Telegram Escrow Bot!\n\n" \
                      "To start a new trade, use the /trade command."
    
    if is_admin(user.id):
        welcome_message += "\n\n(Admin: You have access to admin commands like /dashboard and /view_trade)"

    await update.message.reply_text(welcome_message)



async def trade(update: Update, context: CallbackContext) -> int:
    """Starts a new trade conversation."""
    context.user_data["trade_initiator_id"] = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("Digital Assets", callback_data="category_Digital Assets")],
        [InlineKeyboardButton("Crypto & Tokens", callback_data="category_Crypto & Tokens")],
        [InlineKeyboardButton("Services", callback_data="category_Services")],
        [InlineKeyboardButton("Physical Goods", callback_data="category_Physical Goods")],
        [InlineKeyboardButton("Other", callback_data="category_Other")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("You have initiated a new trade. Please select the item category:", reply_markup=reply_markup)
    return ITEM_CATEGORY

async def item_category(update: Update, context: CallbackContext) -> int:
    """Stores the item category and asks for item description."""
    query = update.callback_query
    await query.answer()
    context.user_data["item_category"] = query.data.split("_")[1]
    await query.edit_message_text(f"Selected category: {context.user_data["item_category"]}.\n\nPlease provide a detailed description of the item you are trading.")
    return ITEM_DESCRIPTION

async def item_description(update: Update, context: CallbackContext) -> int:
    """Stores the item description and asks for the price."""
    context.user_data["item_description"] = update.message.text
    await update.message.reply_text("What is the price of the item? (e.g., 100.00)")
    return PRICE

async def price_input(update: Update, context: CallbackContext) -> int:
    """Stores the price and asks for the currency."""
    try:
        price_val = float(update.message.text)
        if price_val <= 0:
            await update.message.reply_text("Price must be a positive number. Please enter a valid price.")
            return PRICE
        context.user_data["price"] = price_val
        await update.message.reply_text("What is the currency? (e.g., USD, NGN)")
        return CURRENCY
    except ValueError:
        await update.message.reply_text("Invalid price format. Please enter a number (e.g., 100.00).")
        return PRICE

async def currency_input(update: Update, context: CallbackContext) -> int:
    """Stores the currency and asks for the payment method."""
    context.user_data["currency"] = update.message.text.upper()
    keyboard = [
        [InlineKeyboardButton("Bank Transfer", callback_data="pm_Bank Transfer")],
        [InlineKeyboardButton("Crypto Wallet", callback_data="pm_Crypto Wallet")],
        [InlineKeyboardButton("Other", callback_data="pm_Other")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("What is the preferred payment method?", reply_markup=reply_markup)
    return PAYMENT_METHOD

async def payment_method(update: Update, context: CallbackContext) -> int:
    """Stores the payment method and asks for the deadline."""
    query = update.callback_query
    await query.answer()
    context.user_data["payment_method"] = query.data.split("_")[1]
    await query.edit_message_text(f"Selected payment method: {context.user_data["payment_method"]}.\n\nPlease provide the trade deadline (e.g., YYYY-MM-DD HH:MM). All times are in WAT.")
    return DEADLINE

async def deadline_input(update: Update, context: CallbackContext) -> int:
    """Stores the deadline and asks for the counterparty's Telegram ID/username."""
    try:
        deadline_str = update.message.text
        deadline_dt = WAT.localize(datetime.strptime(deadline_str, "%Y-%m-%d %H:%M"))
        if deadline_dt <= get_current_time():
            await update.message.reply_text("Deadline must be in the future. Please enter a valid date and time.")
            return DEADLINE
        context.user_data["deadline"] = deadline_dt
        await update.message.reply_text("Please provide the Telegram ID or username of the counterparty (buyer).")
        return COUNTERPARTY_ID
    except ValueError:
        await update.message.reply_text("Invalid date/time format. Please use YYYY-MM-DD HH:MM (e.g., 2025-12-31 18:00).")
        return DEADLINE

async def counterparty_id(update: Update, context: CallbackContext) -> int:
    """Stores counterparty ID/username and presents trade summary for confirmation."""
    counterparty_input = update.message.text.strip()
    buyer_id = None
    buyer_username = None

    if not users_collection:
        logger.error("MongoDB users_collection not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return ConversationHandler.END

    try:
        if counterparty_input.isdigit():
            buyer_id = int(counterparty_input)
            buyer_user = users_collection.find_one({"telegram_id": buyer_id})
            if buyer_user:
                buyer_username = buyer_user.get("username")
        elif counterparty_input.startswith("@"):
            buyer_username = counterparty_input[1:]
            buyer_user = users_collection.find_one({"username": buyer_username})
            if buyer_user:
                buyer_id = buyer_user.get("telegram_id")
        else:
            buyer_username = counterparty_input
            buyer_user = users_collection.find_one({"username": buyer_username})
            if buyer_user:
                buyer_id = buyer_user.get("telegram_id")

        if not buyer_id:
            await update.message.reply_text("Could not find the counterparty. Please ensure they have interacted with the bot before or provide a valid Telegram ID/username.")
            return COUNTERPARTY_ID
        
        if buyer_id == context.user_data["trade_initiator_id"]:
            await update.message.reply_text("You cannot trade with yourself. Please provide a different counterparty.")
            return COUNTERPARTY_ID

        context.user_data["buyer_id"] = buyer_id
        context.user_data["buyer_username"] = buyer_username

        # Fee calculation (simple example, needs tiered system)
        price_val = context.user_data["price"]
        fee_percentage = 0.025 # 2.5% flat fee for now
        fee_amount = round(price_val * fee_percentage, 2)
        context.user_data["fee_amount"] = fee_amount

        trade_summary = (
            f"*Trade Summary*\n\n"
            f"*Seller*: {update.effective_user.first_name} (@{update.effective_user.username or 'N/A'})\n"
            f"*Buyer*: {context.user_data['buyer_username'] or context.user_data['buyer_id']}\n"
            f"*Category*: {context.user_data['item_category']}\n"
            f"*Description*: {context.user_data['item_description']}\n"
            f"*Price*: {context.user_data['price']:.2f} {context.user_data['currency']}\n"
            f"*Escrow Fee*: {context.user_data['fee_amount']:.2f} {context.user_data['currency']}\n"
            f"*Total Buyer Pays*: {(context.user_data['price'] + context.user_data['fee_amount']):.2f} {context.user_data['currency']}\n"
            f"*Payment Method*: {context.user_data['payment_method']}\n"
            f"*Deadline*: {context.user_data['deadline'].strftime('%Y-%m-%d %H:%M %Z')}\n"
        )

        keyboard = [
            [InlineKeyboardButton("Confirm Trade", callback_data="confirm_trade"),
             InlineKeyboardButton("Cancel", callback_data="cancel_trade")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(trade_summary, parse_mode='Markdown', reply_markup=reply_markup)
        return CONFIRMATION
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed while finding counterparty {counterparty_input}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
        return ConversationHandler.END

async def confirmation_handler(update: Update, context: CallbackContext) -> int:
    """Handles the final confirmation of the trade details."""
    query = update.callback_query
    await query.answer()

    if not trades_collection:
        logger.error("MongoDB trades_collection not initialized.")
        await query.edit_message_text("Bot is experiencing technical difficulties. Please try again later.")
        return ConversationHandler.END

    try:
        if query.data == "confirm_trade":
            seller_id = context.user_data["trade_initiator_id"]
            buyer_id = context.user_data["buyer_id"]

            # Generate a unique Trade ID
            trade_id_prefix = "TEB-"
            count = trades_collection.count_documents({}) + 1
            unique_trade_id = f"{trade_id_prefix}{count:05d}"

            trade_data = {
                "trade_id": unique_trade_id,
                "seller_id": seller_id,
                "buyer_id": buyer_id,
                "item_category": context.user_data["item_category"],
                "item_description": context.user_data["item_description"],
                "price": context.user_data["price"],
                "currency": context.user_data["currency"],
                "payment_method": context.user_data["payment_method"],
                "deadline": context.user_data["deadline"],
                "status": "pending_buyer_approval",
                "fee_amount": context.user_data["fee_amount"],
                "fee_currency": context.user_data["currency"],
                "payment_proof_url": None,
                "dispute_status": "none",
                "created_at": get_current_time(),
                "updated_at": get_current_time()
            }
            trades_collection.insert_one(trade_data)

            share_link = f"https://t.me/{context.bot.username}?start=trade_{unique_trade_id}"
            await query.edit_message_text(
                text=f"Trade confirmed! Your Trade ID is `{unique_trade_id}`. "
                     f"Share this link with the buyer to get their approval: {share_link}",
                parse_mode='Markdown'
            )
            logger.info(f"Trade {unique_trade_id} initiated by {seller_id} with buyer {buyer_id}")

            # Notify buyer
            buyer_message = (
                f"You have been invited to a new escrow trade (ID: `{unique_trade_id}`).\n\n"
                f"*Seller*: {query.from_user.first_name} (@{query.from_user.username or 'N/A'})\n"
                f"*Item*: {context.user_data['item_description']} ({context.user_data['item_category']})\n"
                f"*Price*: {context.user_data['price']:.2f} {context.user_data['currency']}\n"
                f"*Escrow Fee*: {context.user_data['fee_amount']:.2f} {context.user_data['currency']}\n"
                f"*Total to Pay*: {(context.user_data['price'] + context.user_data['fee_amount']):.2f} {context.user_data['currency']}\n"
                f"*Payment Method*: {context.user_data['payment_method']}\n"
                f"*Deadline*: {context.user_data['deadline'].strftime('%Y-%m-%d %H:%M %Z')}\n\n"
                f"Do you approve this trade?"
            )
            buyer_keyboard = [
                [InlineKeyboardButton("Approve", callback_data=f"approve_trade_{unique_trade_id}"),
                 InlineKeyboardButton("Reject", callback_data=f"reject_trade_{unique_trade_id}")]
            ]
            buyer_reply_markup = InlineKeyboardMarkup(buyer_keyboard)
            await context.bot.send_message(chat_id=buyer_id, text=buyer_message, parse_mode='Markdown', reply_markup=buyer_reply_markup)

        else:
            await query.edit_message_text(text="Trade creation canceled.")
        return ConversationHandler.END
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during trade confirmation: {e}")
        await query.edit_message_text("A database error occurred. Please try again later.")
        return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels the trade conversation."""
    await update.message.reply_text("Trade creation canceled.")
    return ConversationHandler.END



async def approve_trade(update: Update, context: CallbackContext) -> None:
    """Handles buyer approval of a trade."""
    query = update.callback_query
    await query.answer()
    trade_id = query.data.split("_")[2]

    if not trades_collection:
        logger.error("MongoDB trades_collection not initialized.")
        await query.edit_message_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    try:
        trade = trades_collection.find_one({"trade_id": trade_id})
        if not trade:
            await query.edit_message_text(f"Trade `{trade_id}` not found.")
            return

        if trade["buyer_id"] != query.from_user.id:
            await query.edit_message_text("You are not the buyer for this trade.")
            return

        if trade["status"] != "pending_buyer_approval":
            await query.edit_message_text(f"Trade `{trade_id}` is not awaiting your approval (current status: {trade["status"]}).")
            return

        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "approved", "updated_at": get_current_time()}}
        )
        await query.edit_message_text(f"You have approved trade `{trade_id}`. The seller has been notified.\n\n" \
                                      f"Please make the payment of `{(trade["price"] + trade["fee_amount"]):.2f} {trade["currency"]}` to the seller using the agreed method: `{trade["payment_method"]}`.\n\n" \
                                      f"Once paid, use the /submit_payment_proof `{trade_id}` command to upload proof of payment.")
        logger.info(f"Buyer {query.from_user.id} approved trade {trade_id}")

        # Notify seller
        seller_message = f"Your trade `{trade_id}` has been approved by the buyer!\n\n" \
                         f"The buyer has been instructed to make payment. Please await payment and then confirm receipt.\n\n" \
                         f"Once you receive payment, you can use the /confirm_payment `{trade_id}` command to verify it."
        await context.bot.send_message(chat_id=trade["seller_id"], text=seller_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during trade approval for {trade_id}: {e}")
        await query.edit_message_text("A database error occurred. Please try again later.")

async def reject_trade(update: Update, context: CallbackContext) -> None:
    """Handles buyer rejection of a trade."""
    query = update.callback_query
    await query.answer()
    trade_id = query.data.split("_")[2]

    if not trades_collection:
        logger.error("MongoDB trades_collection not initialized.")
        await query.edit_message_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    try:
        trade = trades_collection.find_one({"trade_id": trade_id})
        if not trade:
            await query.edit_message_text(f"Trade `{trade_id}` not found.")
            return

        if trade["buyer_id"] != query.from_user.id:
            await query.edit_message_text("You are not the buyer for this trade.")
            return

        if trade["status"] != "pending_buyer_approval":
            await query.edit_message_text(f"Trade `{trade_id}` is not awaiting your approval (current status: {trade["status"]}).")
            return

        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "rejected", "updated_at": get_current_time()}}
        )
        await query.edit_message_text(f"You have rejected trade `{trade_id}`. The seller has been notified.")
        logger.info(f"Buyer {query.from_user.id} rejected trade {trade_id}")

        # Notify seller
        seller_message = f"Your trade `{trade_id}` has been rejected by the buyer.\n\n" \
                         f"Status: Canceled."
        await context.bot.send_message(chat_id=trade["seller_id"], text=seller_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during trade rejection for {trade_id}: {e}")
        await query.edit_message_text("A database error occurred. Please try again later.")



# --- Payment Proof Submission ---
async def submit_payment_proof_command(update: Update, context: CallbackContext) -> int:
    """Initiates the payment proof submission process."""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /submit_payment_proof <trade_id>")
        return ConversationHandler.END

    trade_id = context.args[0]
    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return ConversationHandler.END

    if trade["buyer_id"] != update.effective_user.id:
        await update.message.reply_text("You are not the buyer for this trade.")
        return ConversationHandler.END

    if trade["status"] != "approved":
        await update.message.reply_text(f"Payment proof can only be submitted for trades with status 'approved'. Current status: {trade["status"]}.")
        return ConversationHandler.END

    context.user_data["current_trade_id"] = trade_id
    await update.message.reply_text("Please send the payment proof as an image or a URL.")
    return SUBMIT_PAYMENT_PROOF

async def receive_payment_proof(update: Update, context: CallbackContext) -> int:
    """Receives the payment proof (image or URL) from the buyer."""
    trade_id = context.user_data.get("current_trade_id")
    if not trade_id:
        await update.message.reply_text("No active payment proof submission. Please start again with /submit_payment_proof.")
        return ConversationHandler.END

    payment_proof_url = None
    if update.message.photo:
        # Get the file_id of the largest photo
        file_id = update.message.photo[-1].file_id
        # In a real scenario, you'd download this and upload to a persistent storage (e.g., S3)
        # For this example, we'll just use the file_id as a placeholder URL
        payment_proof_url = f"telegram_photo_id:{file_id}"
        await update.message.reply_text("Received your payment proof image. Admins will review it shortly.")
    elif update.message.text and (update.message.text.startswith("http://") or update.message.text.startswith("https://")):
        payment_proof_url = update.message.text
        await update.message.reply_text("Received your payment proof URL. Admins will review it shortly.")
    else:
        await update.message.reply_text("Please send a valid image or a URL for the payment proof.")
        return SUBMIT_PAYMENT_PROOF

    try:
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {
                "payment_proof_url": payment_proof_url,
                "status": "payment_pending",
                "updated_at": get_current_time()
            }}
        )
        await update.message.reply_text(f"Payment proof for trade `{trade_id}` submitted successfully. Admins have been notified for verification.")
        logger.info(f"Payment proof for trade {trade_id} submitted by buyer {update.effective_user.id}")

        # Notify admins
        admin_message = f"🚨 *New Payment Proof Submitted!* 🚨\n\n" \
                        f"Trade ID: `{trade_id}`\n" \
                        f"Buyer: {update.effective_user.first_name} (@{update.effective_user.username or 'N/A'})\n" \
                        f"Proof: {payment_proof_url}\n\n" \
                        f"Please verify payment using /verify_payment <trade_id>"
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during payment proof submission for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")

    return ConversationHandler.END



# --- Admin Features ---
async def admin_only(update: Update, context: CallbackContext) -> bool:
    """Decorator-like function to check if the user is an admin."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return False
    return True

async def verify_payment(update: Update, context: CallbackContext) -> None:
    """Admin command to verify a payment for a trade."""
    if not await admin_only(update, context): return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /verify_payment <trade_id>")
        return

    trade_id = context.args[0]
    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return

    if trade["status"] != "payment_pending":
        await update.message.reply_text(f"Trade `{trade_id}` is not in 'payment_pending' status. Current status: {trade["status"]}.")
        return

    if not trade.get("payment_proof_url"):
        await update.message.reply_text(f"No payment proof submitted for trade `{trade_id}`.")
        return

    try:
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "payment_verified", "updated_at": get_current_time()}}
        )
        await update.message.reply_text(f"Payment for trade `{trade_id}` verified. Seller has been notified to release assets.")
        logger.info(f"Admin {update.effective_user.id} verified payment for trade {trade_id}")

        # Notify seller
        seller_message = f"Good news! Payment for your trade `{trade_id}` has been *verified* by an admin!\n\n" \
                         f"Please proceed to release the asset to the buyer.\n\n" \
                         f"Once the asset is released, use the /release_asset `{trade_id}` command."
        await context.bot.send_message(chat_id=trade["seller_id"], text=seller_message, parse_mode=\'Markdown\')

        # Notify buyer
        buyer_message = f"Great news! Payment for your trade `{trade_id}` has been *verified* by an admin!\n\n" \
                        f"The seller has been notified to release the asset. Please confirm receipt once you receive it using /confirm_receipt `{trade_id}`."
        await context.bot.send_message(chat_id=trade["buyer_id"], text=buyer_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during payment verification for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")

async def reject_payment(update: Update, context: CallbackContext) -> None:
    """Admin command to reject a payment for a trade."""
    if not await admin_only(update, context): return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /reject_payment <trade_id>")
        return

    trade_id = context.args[0]
    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return

    if trade["status"] != "payment_pending":
        await update.message.reply_text(f"Trade `{trade_id}` is not in 'payment_pending' status. Current status: {trade["status"]}.")
        return

    try:
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "payment_failed", "updated_at": get_current_time()}}
        )
        await update.message.reply_text(f"Payment for trade `{trade_id}` rejected. Trade status set to 'payment_failed'.")
        logger.info(f"Admin {update.effective_user.id} rejected payment for trade {trade_id}")

        # Notify buyer
        buyer_message = f"Your payment for trade `{trade_id}` could not be verified by an admin.\n\n" \
                        f"The trade status has been updated to 'payment_failed'. Please contact the seller or admin for more details."
        await context.bot.send_message(chat_id=trade["buyer_id"], text=buyer_message, parse_mode=\'Markdown\')

        # Notify seller
        seller_message = f"Payment for your trade `{trade_id}` was rejected by an admin.\n\n" \
                         f"The trade status has been updated to 'payment_failed'."
        await context.bot.send_message(chat_id=trade["seller_id"], text=seller_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during payment rejection for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")

async def force_release(update: Update, context: CallbackContext) -> None:
    """Admin command to force release assets for an unresponsive seller."""
    if not await admin_only(update, context): return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /force_release <trade_id>")
        return

    trade_id = context.args[0]
    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return

    if trade["status"] != "payment_verified":
        await update.message.reply_text(f"Assets can only be force-released for trades in 'payment_verified' status. Current status: {trade["status"]}.")
        return

    try:
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "asset_released", "updated_at": get_current_time()}}
        )
        await update.message.reply_text(f"Assets for trade `{trade_id}` have been force-released. Buyer and seller notified.")
        logger.info(f"Admin {update.effective_user.id} force-released assets for trade {trade_id}")

        # Notify buyer
        buyer_message = f"Important: Assets for your trade `{trade_id}` have been *force-released* by an admin due to seller unresponsiveness.\n\n" \
                        f"Please confirm receipt using /confirm_receipt `{trade_id}`."
        await context.bot.send_message(chat_id=trade["buyer_id"], text=buyer_message, parse_mode=\'Markdown\')

        # Notify seller
        seller_message = f"Notice: Assets for your trade `{trade_id}` were *force-released* by an admin due to unresponsiveness.\n\n" \
                         f"Please contact support if you believe this was an error."
        await context.bot.send_message(chat_id=trade["seller_id"], text=seller_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during force release for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")

async def resolve_dispute(update: Update, context: CallbackContext) -> None:
    """Admin command to resolve a dispute and set trade to completed or refunded."""
    if not await admin_only(update, context): return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /resolve_dispute <trade_id> <resolution_status> [reason]")
        await update.message.reply_text("Resolution status can be 'completed' or 'refunded'.")
        return

    trade_id = context.args[0]
    resolution_status = context.args[1].lower()
    resolution_reason = " ".join(context.args[2:]) if len(context.args) > 2 else "No specific reason provided."

    if resolution_status not in ["completed", "refunded"]:
        await update.message.reply_text("Invalid resolution status. Must be 'completed' or 'refunded'.")
        return

    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return

    if trade["dispute_status"] != "raised":
        await update.message.reply_text(f"Trade `{trade_id}` is not currently in a 'dispute_raised' status. Current dispute status: {trade["dispute_status"]}.")
        return

    try:
        new_trade_status = "completed" if resolution_status == "completed" else "refund_initiated"
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {
                "status": new_trade_status,
                "dispute_status": "resolved",
                "resolution_reason": resolution_reason,
                "updated_at": get_current_time()
            }}
        )
        await update.message.reply_text(f"Dispute for trade `{trade_id}` resolved as '{resolution_status}'. Trade status set to '{new_trade_status}'.")
        logger.info(f"Admin {update.effective_user.id} resolved dispute for trade {trade_id} as {resolution_status}")

        # Notify buyer and seller
        message_to_users = f"Admin decision for trade `{trade_id}`:\n\n" \
                           f"*Resolution*: {resolution_status.capitalize()}\n" \
                           f"*Reason*: {resolution_reason}\n\n" \
                           f"Trade status updated to: {new_trade_status.replace("_", " ").capitalize()}"
        await context.bot.send_message(chat_id=trade["buyer_id"], text=message_to_users, parse_mode=\'Markdown\')
        await context.bot.send_message(chat_id=trade["seller_id"], text=message_to_users, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during dispute resolution for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")

async def dashboard(update: Update, context: CallbackContext) -> None:
    """Admin command to view a daily dashboard of trade statistics."""
    if not await admin_only(update, context): return

    try:
        today = get_current_time().date()
        start_of_day = WAT.localize(datetime(today.year, today.month, today.day, 0, 0, 0))
        end_of_day = WAT.localize(datetime(today.year, today.month, today.day, 23, 59, 59))

        total_trades_today = trades_collection.count_documents({"created_at": {"$gte": start_of_day, "$lte": end_of_day}})
        completed_trades_today = trades_collection.count_documents({"created_at": {"$gte": start_of_day, "$lte": end_of_day}, "status": "completed"})
        pending_trades_today = trades_collection.count_documents({"created_at": {"$gte": start_of_day, "$lte": end_of_day}, "status": {"$nin": ["completed", "canceled", "rejected", "payment_failed"]}})
        disputed_trades_today = trades_collection.count_documents({"created_at": {"$gte": start_of_day, "$lte": end_of_day}, "dispute_status": "raised"})

        dashboard_message = (
            f"*Daily Trade Dashboard ({today.strftime('%Y-%m-%d')})*\n\n"
            f"*Total Trades Initiated*: {total_trades_today}\n"
            f"*Completed Trades*: {completed_trades_today}\n"
            f"*Pending Trades*: {pending_trades_today}\n"
            f"*Disputed Trades*: {disputed_trades_today}\n"
        )
        await update.message.reply_text(dashboard_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during dashboard generation: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")

async def view_trade(update: Update, context: CallbackContext) -> None:
    """Admin command to view details of a specific trade or all trades."""
    if not await admin_only(update, context): return

    if len(context.args) == 1:
        trade_id = context.args[0]
        trade = trades_collection.find_one({"trade_id": trade_id})
        if trade:
            seller_user = users_collection.find_one({"telegram_id": trade["seller_id"]})
            buyer_user = users_collection.find_one({"telegram_id": trade["buyer_id"]})

            seller_info = f"{seller_user.get('first_name', 'N/A')} (@{seller_user.get('username', 'N/A')}) (ID: {trade['seller_id']})"
            buyer_info = f"{buyer_user.get('first_name', 'N/A')} (@{buyer_user.get('username', 'N/A')}) (ID: {trade['buyer_id']})"

            trade_details = (
                f"*Trade Details for `{trade_id}`*\n\n"
                f"*Seller*: {seller_info}\n"
                f"*Buyer*: {buyer_info}\n"
                f"*Category*: {trade['item_category']}\n"
                f"*Description*: {trade['item_description']}\n"
                f"*Price*: {trade['price']:.2f} {trade['currency']}\n"
                f"*Escrow Fee*: {trade['fee_amount']:.2f} {trade['fee_currency']}\n"
                f"*Total Buyer Pays*: {(trade['price'] + trade['fee_amount']):.2f} {trade['currency']}\n"
                f"*Payment Method*: {trade['payment_method']}\n"
                f"*Deadline*: {trade['deadline'].strftime('%Y-%m-%d %H:%M %Z')}\n"
                f"*Status*: {trade['status'].replace('_', ' ').capitalize()}\n"
                f"*Dispute Status*: {trade['dispute_status'].capitalize()}\n"
                f"*Payment Proof*: {trade.get('payment_proof_url', 'N/A')}\n"
                f"*Created At*: {trade['created_at'].strftime('%Y-%m-%d %H:%M %Z')}\n"
                f"*Last Updated*: {trade['updated_at'].strftime('%Y-%m-%d %H:%M %Z')}\n"
            )
            await update.message.reply_text(trade_details, parse_mode=\'Markdown\')
        else:
            await update.message.reply_text(f"Trade `{trade_id}` not found.")
    elif len(context.args) == 0:
        # View all trades (or a paginated list)
        trades = trades_collection.find().sort("created_at", -1).limit(10) # Show last 10 trades
        if trades:
            response_message = "*Recent Trades:*\n\n"
            for trade in trades:
                response_message += (
                    f"- ID: `{trade['trade_id']}` | Status: {trade['status'].replace('_', ' ').capitalize()} | "
                    f"Seller: {trade['seller_id']} | Buyer: {trade['buyer_id']} | "
                    f"Item: {trade['item_description']} | Price: {trade['price']:.2f} {trade['currency']}\n"
                )
            await update.message.reply_text(response_message, parse_mode=\'Markdown\')
        else:
            await update.message.reply_text("No trades found.")
    else:
        await update.message.reply_text("Usage: /view_trade [trade_id]")




# --- Asset Release and Buyer Confirmation ---
async def release_asset(update: Update, context: CallbackContext) -> None:
    """Seller command to confirm asset release."""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /release_asset <trade_id>")
        return

    trade_id = context.args[0]
    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return

    if trade["seller_id"] != update.effective_user.id:
        await update.message.reply_text("You are not the seller for this trade.")
        return

    if trade["status"] != "payment_verified":
        await update.message.reply_text(f"Assets can only be released for trades with status 'payment_verified'. Current status: {trade["status"]}.")
        return

    try:
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "asset_released", "updated_at": get_current_time()}}
        )
        await update.message.reply_text(f"You have confirmed asset release for trade `{trade_id}`. The buyer has been notified to confirm receipt.")
        logger.info(f"Seller {update.effective_user.id} released asset for trade {trade_id}")

        # Notify buyer
        buyer_message = f"Great news! The seller has confirmed asset release for your trade `{trade_id}`.\n\n" \
                        f"Please confirm receipt of the asset using /confirm_receipt `{trade_id}`."
        await context.bot.send_message(chat_id=trade["buyer_id"], text=buyer_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during asset release for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")

async def confirm_receipt(update: Update, context: CallbackContext) -> None:
    """Buyer command to confirm receipt of assets."""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /confirm_receipt <trade_id>")
        return

    trade_id = context.args[0]
    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return

    if trade["buyer_id"] != update.effective_user.id:
        await update.message.reply_text("You are not the buyer for this trade.")
        return

    if trade["status"] != "asset_released":
        await update.message.reply_text(f"Receipt can only be confirmed for trades with status 'asset_released'. Current status: {trade["status"]}.")
        return

    try:
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "completed", "updated_at": get_current_time()}}
        )
        await update.message.reply_text(f"You have confirmed receipt for trade `{trade_id}`. Trade completed successfully!")
        logger.info(f"Buyer {update.effective_user.id} confirmed receipt for trade {trade_id}")

        # Notify seller
        seller_message = f"Congratulations! The buyer has confirmed receipt for your trade `{trade_id}`.\n\n" \
                         f"Trade status: *Completed*."
        await context.bot.send_message(chat_id=trade["seller_id"], text=seller_message, parse_mode=\'Markdown\')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during receipt confirmation for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")



# --- Refund Process ---
async def refund_command(update: Update, context: CallbackContext) -> int:
    """Initiates a refund request for a trade."""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /refund <trade_id>")
        return ConversationHandler.END

    trade_id = context.args[0]
    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return ConversationHandler.END

    if trade["buyer_id"] != update.effective_user.id and trade["seller_id"] != update.effective_user.id:
        await update.message.reply_text("You are not a participant in this trade.")
        return ConversationHandler.END

    if trade["status"] not in ["payment_pending", "payment_verified", "asset_released", "dispute_raised"]:
        await update.message.reply_text(f"Refund can only be requested for trades in 'payment_pending', 'payment_verified', 'asset_released', or 'dispute_raised' status. Current status: {trade["status"]}.")
        return ConversationHandler.END

    context.user_data["current_trade_id"] = trade_id
    await update.message.reply_text("Please provide a reason for the refund request.")
    return REFUND_REASON

async def refund_reason_input(update: Update, context: CallbackContext) -> int:
    """Stores the refund reason and notifies admins."""
    trade_id = context.user_data.get("current_trade_id")
    if not trade_id:
        await update.message.reply_text("No active refund request. Please start again with /refund.")
        return ConversationHandler.END

    refund_reason = update.message.text

    try:
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {
                "status": "refund_initiated",
                "refund_reason": refund_reason,
                "updated_at": get_current_time()
            }}
        )
        await update.message.reply_text(f"Refund request for trade `{trade_id}` submitted successfully. Admins have been notified.")
        logger.info(f"Refund request for trade {trade_id} submitted by {update.effective_user.id}")

        # Notify admins
        admin_message = f"🚨 *New Refund Request!* 🚨\n\n" \
                        f"Trade ID: `{trade_id}`\n" \
                        f"Requested by: {update.effective_user.first_name} (@{update.effective_user.username or 'N/A'})\n" \
                        f"Reason: {refund_reason}\n\n" \
                        f"Please process the refund using /process_refund <trade_id>"
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode='Markdown')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during refund request for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")

    return ConversationHandler.END

async def process_refund(update: Update, context: CallbackContext) -> None:
    """Admin command to process a refund for a trade."""
    if not await admin_only(update, context): return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /process_refund <trade_id>")
        return

    trade_id = context.args[0]
    trade = trades_collection.find_one({"trade_id": trade_id})

    if not trade:
        await update.message.reply_text(f"Trade `{trade_id}` not found.")
        return

    if trade["status"] != "refund_initiated":
        await update.message.reply_text(f"Trade `{trade_id}` is not in 'refund_initiated' status. Current status: {trade["status"]}.")
        return

    try:
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "refund_processed", "updated_at": get_current_time()}}
        )
        await update.message.reply_text(f"Refund for trade `{trade_id}` processed. Buyer and seller notified.")
        logger.info(f"Admin {update.effective_user.id} processed refund for trade {trade_id}")

        # Notify buyer and seller
        message_to_users = f"Refund for trade `{trade_id}` has been *processed* by an admin.\n\n" \
                           f"Reason: {trade.get('refund_reason', 'N/A')}\n\n" \
                           f"Trade status updated to: Refund Processed."
        await context.bot.send_message(chat_id=trade["buyer_id"], text=message_to_users, parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade["seller_id"], text=message_to_users, parse_mode='Markdown')

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during refund processing for {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")



# --- Flask App for Health Checks ---
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is running!"

def run_flask():
    """Runs the Flask app in a separate thread."""
    app.run(host="0.0.0.0", port=os.environ.get("PORT", 8080))

# --- Main Bot Function ---
def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TOKEN).build()

    # Conversation handler for /trade command
    trade_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("trade", trade)],
        states={
            ITEM_CATEGORY: [CallbackQueryHandler(item_category, pattern="^category_.*$")],
            ITEM_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, item_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_input)],
            CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, currency_input)],
            PAYMENT_METHOD: [CallbackQueryHandler(payment_method, pattern="^pm_.*$")],
            DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, deadline_input)],
            COUNTERPARTY_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, counterparty_id)],
            CONFIRMATION: [CallbackQueryHandler(confirmation_handler, pattern="^(confirm|cancel)_trade$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler for /submit_payment_proof command
    payment_proof_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("submit_payment_proof", submit_payment_proof_command)],
        states={
            SUBMIT_PAYMENT_PROOF: [
                MessageHandler(filters.PHOTO | (filters.TEXT & filters.Regex("^(http|https)://.*$")), receive_payment_proof)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler for /refund command
    refund_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("refund", refund_command)],
        states={
            REFUND_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, refund_reason_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(trade_conv_handler)
    application.add_handler(payment_proof_conv_handler)
    application.add_handler(refund_conv_handler)

    # CallbackQueryHandlers for trade approval/rejection
    application.add_handler(CallbackQueryHandler(approve_trade, pattern="^approve_trade_.*$"))
    application.add_handler(CallbackQueryHandler(reject_trade, pattern="^reject_trade_.*$"))

    # CommandHandlers for asset release and receipt confirmation
    application.add_handler(CommandHandler("release_asset", release_asset))
    application.add_handler(CommandHandler("confirm_receipt", confirm_receipt))

    # Admin CommandHandlers
    application.add_handler(CommandHandler("verify_payment", verify_payment))
    application.add_handler(CommandHandler("reject_payment", reject_payment))
    application.add_handler(CommandHandler("force_release", force_release))
    application.add_handler(CommandHandler("resolve_dispute", resolve_dispute))
    application.add_handler(CommandHandler("dashboard", dashboard))
    application.add_handler(CommandHandler("view_trade", view_trade))
    application.add_handler(CommandHandler("process_refund", process_refund))

    # Run the bot in a separate thread
    bot_thread = threading.Thread(target=application.run_polling, daemon=True)
    bot_thread.start()

    # Run Flask app in the main thread
    run_flask()

if __name__ == "__main__":
    main()

