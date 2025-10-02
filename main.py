
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime, timedelta
import pytz
import uuid

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

# Get bot token, MongoDB URI, and Admin IDs from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(uid.strip()) for uid in ADMIN_IDS_STR.split(",") if uid.strip()]

# Timezone setup
WAT = pytz.timezone("Africa/Lagos")

# MongoDB setup
client = None
db = None
users_collection = None
trades_collection = None
payments_collection = None

try:
    client = MongoClient(MONGODB_URI)
    db = client.escrow_bot
    users_collection = db.users
    trades_collection = db.trades
    payments_collection = db.payments
    # The ismaster command is cheap and does not require auth. 
    client.admin.command('ismaster')
    logger.info("Successfully connected to MongoDB.")
except ConnectionFailure as e:
    logger.error(f"Could not connect to MongoDB: {e}")
    # Exit or handle gracefully if DB connection is critical
    exit(1)

# Trade states for ConversationHandler
ITEM_CATEGORY, ITEM_DESCRIPTION, PRICE, CURRENCY, PAYMENT_METHOD, DEADLINE, COUNTERPARTY_ID, CONFIRMATION = range(8)
REFUND_REASON = 8

def get_current_time():
    return datetime.now(WAT)

def is_admin(user_id: int) -> bool:
    """Checks if a user ID belongs to an administrator."""
    if not users_collection:
        logger.error("MongoDB users_collection not initialized.")
        return False
    if user_id in ADMIN_IDS:
        return True
    try:
        user = users_collection.find_one({"telegram_id": user_id, "is_admin": True})
        return user is not None
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed while checking admin status for user {user_id}: {e}")
        return False

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
        welcome_message += "\n\n(Admin: You have access to admin commands like /dashboard and /view)"

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
            f"*Buyer*: {context.user_data["buyer_username"] or context.user_data["buyer_id"]}\n"
            f"*Category*: {context.user_data["item_category"]}\n"
            f"*Description*: {context.user_data["item_description"]}\n"
            f"*Price*: {context.user_data["price"]:.2f} {context.user_data["currency"]}\n"
            f"*Escrow Fee*: {context.user_data["fee_amount"]:.2f} {context.user_data["currency"]}\n"
            f"*Total Buyer Pays*: {(context.user_data["price"] + context.user_data["fee_amount"]):.2f} {context.user_data["currency"]}\n"
            f"*Payment Method*: {context.user_data["payment_method"]}\n"
            f"*Deadline*: {context.user_data["deadline"].strftime('%Y-%m-%d %H:%M %Z')}\n"
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

    if not trades_collection or not payments_collection:
        logger.error("MongoDB collections not initialized.")
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
                f"*Item*: {context.user_data["item_description"]} ({context.user_data["item_category"]})\n"
                f"*Price*: {context.user_data["price"]:.2f} {context.user_data["currency"]}\n"
                f"*Escrow Fee*: {context.user_data["fee_amount"]:.2f} {context.user_data["currency"]}\n"
                f"*Total to Pay*: {(context.user_data["price"] + context.user_data["fee_amount"]):.2f} {context.user_data["currency"]}\n"
                f"*Payment Method*: {context.user_data["payment_method"]}\n"
                f"*Deadline*: {context.user_data["deadline"].strftime('%Y-%m-%d %H:%M %Z')}\n\n"
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
    except Exception as e:
        logger.error(f"An unexpected error occurred during trade confirmation: {e}")
        await query.edit_message_text("An unexpected error occurred. Please try again later.")
        return ConversationHandler.END

async def cancel_trade(update: Update, context: CallbackContext) -> int:
    """Cancels the trade conversation."""
    await update.message.reply_text("Trade creation canceled.")
    return ConversationHandler.END

async def handle_buyer_approval(update: Update, context: CallbackContext) -> None:
    """Handles buyer's approval or rejection of a trade."""
    query = update.callback_query
    await query.answer()
    action_type, _, trade_id = query.data.partition("trade_")
    action = action_type.rstrip("_")
    buyer_id = query.from_user.id

    if not trades_collection:
        logger.error("MongoDB trades_collection not initialized.")
        await query.edit_message_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    try:
        trade_doc = trades_collection.find_one({"trade_id": trade_id, "buyer_id": buyer_id})

        if not trade_doc:
            await query.edit_message_text("Trade not found or you are not the designated buyer.")
            return

        if trade_doc["status"] != "pending_buyer_approval":
            await query.edit_message_text(f"This trade is already in status: {trade_doc['status']}.")
            return

        seller_id = trade_doc["seller_id"]

        if action == "approve":
            trades_collection.update_one(
                {"trade_id": trade_id},
                {"$set": {"status": "pending_payment", "updated_at": get_current_time()}}
            )
            await query.edit_message_text(f"You have approved trade `{trade_id}`. Please proceed with payment using the agreed method: {trade_doc['payment_method']}. Once paid, use /upload_payment_proof {trade_id} to submit proof.", parse_mode='Markdown')
            await context.bot.send_message(chat_id=seller_id, text=f"Good news! Your trade `{trade_id}` has been approved by the buyer. It is now `pending_payment`.", parse_mode='Markdown')
            logger.info(f"Buyer {buyer_id} approved trade {trade_id}")
        elif action == "reject":
            trades_collection.update_one(
                {"trade_id": trade_id},
                {"$set": {"status": "cancelled", "updated_at": get_current_time()}}
            )
            await query.edit_message_text(f"You have rejected trade `{trade_id}`. The trade has been cancelled.", parse_mode='Markdown')
            await context.bot.send_message(chat_id=seller_id, text=f"Bad news. Your trade `{trade_id}` has been rejected by the buyer and is now `cancelled`.", parse_mode='Markdown')
            logger.info(f"Buyer {buyer_id} rejected trade {trade_id}")
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during buyer approval for trade {trade_id}: {e}")
        await query.edit_message_text("A database error occurred. Please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during buyer approval for trade {trade_id}: {e}")
        await query.edit_message_text("An unexpected error occurred. Please try again later.")

# Admin Commands
async def admin_dashboard(update: Update, context: CallbackContext) -> None:
    """Displays a daily dashboard with trade statistics for admins."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not trades_collection:
        logger.error("MongoDB trades_collection not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    try:
        today = get_current_time().date()
        start_of_day = WAT.localize(datetime(today.year, today.month, today.day))
        end_of_day = start_of_day + timedelta(days=1)

        total_trades_today = trades_collection.count_documents({"created_at": {"$gte": start_of_day, "$lt": end_of_day}})
        pending_payments_today = trades_collection.count_documents({"status": "payment_awaiting_verification", "updated_at": {"$gte": start_of_day, "$lt": end_of_day}})
        completed_trades_today = trades_collection.count_documents({"status": "completed", "updated_at": {"$gte": start_of_day, "$lt": end_of_day}})
        disputes_today = trades_collection.count_documents({"dispute_status": {"$ne": "none"}, "updated_at": {"$gte": start_of_day, "$lt": end_of_day}})

        dashboard_message = (
            f"*Admin Dashboard - {today.strftime('%Y-%m-%d')}*\n\n"
            f"*Total Trades Initiated Today*: {total_trades_today}\n"
            f"*Pending Payments Verification Today*: {pending_payments_today}\n"
            f"*Completed Trades Today*: {completed_trades_today}\n"
            f"*Disputes Opened Today*: {disputes_today}\n\n"
            f"Use /trade_history to view all trades."
        )
        await update.message.reply_text(dashboard_message, parse_mode='Markdown')
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during admin dashboard generation: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during admin dashboard generation: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")

async def trade_history(update: Update, context: CallbackContext) -> None:
    """Displays full trade history, with optional status filter, for admins."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not trades_collection:
        logger.error("MongoDB trades_collection not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    try:
        filter_status = None
        if context.args:
            filter_status = context.args[0].lower()

        query = {}
        if filter_status:
            query["status"] = filter_status

        trades = trades_collection.find(query).sort("created_at", -1).limit(20) # Limit to 20 for brevity

        if not trades:
            await update.message.reply_text("No trades found.")
            return

        history_message = "*Trade History*\n\n"
        for trade_doc in trades:
            history_message += (
                f"*ID*: `{trade_doc['trade_id']}`\n"
                f"*Status*: {trade_doc['status']}\n"
                f"*Seller*: {trade_doc['seller_id']}\n"
                f"*Buyer*: {trade_doc['buyer_id']}\n"
                f"*Item*: {trade_doc['item_description']}\n"
                f"*Price*: {trade_doc['price']:.2f} {trade_doc['currency']}\n"
                f"*Created*: {trade_doc['created_at'].strftime('%Y-%m-%d %H:%M %Z')}\n"
                f"---\n"
            )
        await update.message.reply_text(history_message, parse_mode='Markdown')
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during trade history retrieval: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during trade history retrieval: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")

async def verify_payment(update: Update, context: CallbackContext) -> None:
    """Admin command to verify a payment for a given trade ID."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /verify_payment <trade_id>")
        return

    if not trades_collection or not payments_collection:
        logger.error("MongoDB collections not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    trade_id = context.args[0]
    try:
        trade_doc = trades_collection.find_one({"trade_id": trade_id})

        if not trade_doc:
            await update.message.reply_text(f"Trade `{trade_id}` not found.")
            return

        if trade_doc["status"] != "payment_awaiting_verification":
            await update.message.reply_text(f"Trade `{trade_id}` is not awaiting payment verification. Current status: {trade_doc['status']}.")
            return

        # In a real scenario, admin would view payment_proof_url here
        # For now, we'll just proceed with verification
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "payment_verified", "updated_at": get_current_time()}}
        )
        # Also record payment in payments_collection
        payments_collection.insert_one({
            "trade_id": trade_doc["_id"],
            "payer_id": trade_doc["buyer_id"],
            "amount": trade_doc["price"] + trade_doc["fee_amount"],
            "currency": trade_doc["currency"],
            "type": "trade_payment",
            "status": "verified",
            "transaction_details": {"note": "Verified by admin"}, # Placeholder
            "verified_by": update.effective_user.id,
            "verified_at": get_current_time(),
            "created_at": get_current_time(),
            "updated_at": get_current_time()
        })

        await update.message.reply_text(f"Payment for trade `{trade_id}` has been verified. Status updated to `payment_verified`.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade_doc["seller_id"], text=f"Good news! Payment for your trade `{trade_id}` has been verified. You can now release the asset.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade_doc["buyer_id"], text=f"Your payment for trade `{trade_id}` has been verified. The seller will now release the asset.", parse_mode='Markdown')
        logger.info(f"Admin {update.effective_user.id} verified payment for trade {trade_id}")
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during payment verification for trade {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during payment verification for trade {trade_id}: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")

async def force_release(update: Update, context: CallbackContext) -> None:
    """Admin command to force release an asset for a given trade ID."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /force_release <trade_id>")
        return

    if not trades_collection:
        logger.error("MongoDB trades_collection not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    trade_id = context.args[0]
    try:
        trade_doc = trades_collection.find_one({"trade_id": trade_id})

        if not trade_doc:
            await update.message.reply_text(f"Trade `{trade_id}` not found.")
            return

        if trade_doc["status"] != "payment_verified":
            await update.message.reply_text(f"Trade `{trade_id}` is not in `payment_verified` status. Current status: {trade_doc['status']}. Cannot force release.")
            return

        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "completed", "updated_at": get_current_time()}}
        )
        await update.message.reply_text(f"Asset for trade `{trade_id}` has been force-released. Status updated to `completed`.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade_doc["seller_id"], text=f"Your trade `{trade_id}` has been force-released by an admin and is now `completed`.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade_doc["buyer_id"], text=f"Your trade `{trade_id}` has been force-released by an admin and is now `completed`.", parse_mode='Markdown')
        logger.info(f"Admin {update.effective_user.id} force-released asset for trade {trade_id}")
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during force release for trade {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during force release for trade {trade_id}: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")

async def resolve_dispute(update: Update, context: CallbackContext) -> None:
    """Admin command to resolve a dispute for a given trade ID."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /resolve_dispute <trade_id>")
        return

    if not trades_collection:
        logger.error("MongoDB trades_collection not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    trade_id = context.args[0]
    try:
        trade_doc = trades_collection.find_one({"trade_id": trade_id})

        if not trade_doc:
            await update.message.reply_text(f"Trade `{trade_id}` not found.")
            return

        if trade_doc["dispute_status"] == "none":
            await update.message.reply_text(f"Trade `{trade_id}` does not have an active dispute.")
            return

        # In a real scenario, this would lead to a conversation or interface for dispute resolution options
        # For now, we'll just mark it as resolved.
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"dispute_status": "resolved", "status": "dispute_resolved", "updated_at": get_current_time()}}
        )
        await update.message.reply_text(f"Dispute for trade `{trade_id}` has been marked as resolved.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade_doc["seller_id"], text=f"The dispute for your trade `{trade_id}` has been resolved by an admin.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade_doc["buyer_id"], text=f"The dispute for your trade `{trade_id}` has been resolved by an admin.", parse_mode='Markdown')
        logger.info(f"Admin {update.effective_user.id} resolved dispute for trade {trade_id}")
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during dispute resolution for trade {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during dispute resolution for trade {trade_id}: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")

# Refund Process
async def refund_command(update: Update, context: CallbackContext) -> int:
    """Initiates the refund process."""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /refund <trade_id>\n\nPlease provide the Trade ID for which you want to request a refund.")
        return ConversationHandler.END

    if not trades_collection or not payments_collection:
        logger.error("MongoDB collections not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return ConversationHandler.END

    trade_id = context.args[0]
    try:
        trade_doc = trades_collection.find_one({"trade_id": trade_id})

        if not trade_doc:
            await update.message.reply_text(f"Trade `{trade_id}` not found.")
            return ConversationHandler.END

        if trade_doc["buyer_id"] != update.effective_user.id and trade_doc["seller_id"] != update.effective_user.id:
            await update.message.reply_text("You can only request a refund for trades you are part of.")
            return ConversationHandler.END

        if trade_doc["status"] not in ["payment_verified", "dispute_resolved"]:
            await update.message.reply_text(f"Refunds can only be requested for trades that are `payment_verified` or `dispute_resolved`. Current status: {trade_doc['status']}.")
            return ConversationHandler.END

        context.user_data["refund_trade_id"] = trade_id
        await update.message.reply_text(f"You are requesting a refund for trade `{trade_id}`. Please provide the reason for the refund.")
        return REFUND_REASON
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during refund command for trade {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"An unexpected error occurred during refund command for trade {trade_id}: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")
        return ConversationHandler.END

async def refund_reason(update: Update, context: CallbackContext) -> int:
    """Stores the refund reason and creates a refund request."""
    trade_id = context.user_data["refund_trade_id"]
    reason = update.message.text
    user_id = update.effective_user.id

    if not trades_collection or not payments_collection:
        logger.error("MongoDB collections not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return ConversationHandler.END

    try:
        # Create a payment record for the refund request
        # This assumes the original payment details are available in the trade_doc or linked payment
        trade_doc_for_refund = trades_collection.find_one({"trade_id": trade_id})
        if not trade_doc_for_refund:
            await update.message.reply_text("Trade not found for refund processing.")
            return ConversationHandler.END

        original_payment = payments_collection.find_one({"trade_id": trade_doc_for_refund["_id"], "type": "trade_payment", "status": "verified"})

        if not original_payment:
            await update.message.reply_text("Could not find original payment details for this trade. Please contact support.")
            return ConversationHandler.END

        refund_amount = original_payment["amount"]
        refund_currency = original_payment["currency"]

        payments_collection.insert_one({
            "trade_id": original_payment["trade_id"],
            "payer_id": user_id, # The one requesting refund
            "amount": refund_amount,
            "currency": refund_currency,
            "type": "refund",
            "status": "pending",
            "transaction_details": {"reason": reason, "original_payment_id": original_payment["_id"]},
            "created_at": get_current_time(),
            "updated_at": get_current_time()
        })

        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "refund_initiated", "updated_at": get_current_time()}}
        )

        await update.message.reply_text(f"Refund request for trade `{trade_id}` submitted with reason: '{reason}'. An admin will review your request shortly.")
        logger.info(f"User {user_id} requested refund for trade {trade_id} with reason: {reason}")

        # Notify admins
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=f"*New Refund Request!*\n\nTrade ID: `{trade_id}`\nRequested by: {update.effective_user.first_name} (@{update.effective_user.username or 'N/A'})\nReason: {reason}\n\nUse /verify_refund {trade_id} to review.", parse_mode='Markdown')

        return ConversationHandler.END
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during refund reason processing for trade {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"An unexpected error occurred during refund reason processing for trade {trade_id}: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")
        return ConversationHandler.END

async def verify_refund(update: Update, context: CallbackContext) -> None:
    """Admin command to verify a refund request."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /verify_refund <trade_id>")
        return

    if not trades_collection or not payments_collection:
        logger.error("MongoDB collections not initialized.")
        await update.message.reply_text("Bot is experiencing technical difficulties. Please try again later.")
        return

    trade_id = context.args[0]
    try:
        trade_doc = trades_collection.find_one({"trade_id": trade_id})

        if not trade_doc:
            await update.message.reply_text(f"Trade `{trade_id}` not found.")
            return

        if trade_doc["status"] != "refund_initiated":
            await update.message.reply_text(f"Trade `{trade_id}` is not in `refund_initiated` status. Current status: {trade_doc['status']}.")
            return

        refund_payment = payments_collection.find_one({"trade_id": trade_doc["_id"], "type": "refund", "status": "pending"})

        if not refund_payment:
            await update.message.reply_text(f"No pending refund request found for trade `{trade_id}`.")
            return

        # Admin confirms refund (in a real scenario, they would perform the actual refund outside the bot)
        payments_collection.update_one(
            {"_id": refund_payment["_id"]},
            {"$set": {"status": "refunded", "verified_by": update.effective_user.id, "verified_at": get_current_time(), "updated_at": get_current_time()}}
        )
        trades_collection.update_one(
            {"trade_id": trade_id},
            {"$set": {"status": "refunded", "updated_at": get_current_time()}}
        )

        await update.message.reply_text(f"Refund for trade `{trade_id}` has been verified and marked as `refunded`.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade_doc["buyer_id"], text=f"Good news! Your refund request for trade `{trade_id}` has been verified by an admin and processed.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=trade_doc["seller_id"], text=f"An admin has verified and processed the refund for trade `{trade_id}`.", parse_mode='Markdown')
        logger.info(f"Admin {update.effective_user.id} verified refund for trade {trade_id}")
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during refund verification for trade {trade_id}: {e}")
        await update.message.reply_text("A database error occurred. Please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during refund verification for trade {trade_id}: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Log the error and send a user-friendly message."""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred while processing your request. Please try again later.")
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}")

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TOKEN).build()

    # Conversation handler for /trade command
    trade_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("trade", trade)],
        states={
            ITEM_CATEGORY: [CallbackQueryHandler(item_category, pattern='^category_')],
            ITEM_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, item_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_input)],
            CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, currency_input)],
            PAYMENT_METHOD: [CallbackQueryHandler(payment_method, pattern='^pm_')],
            DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, deadline_input)],
            COUNTERPARTY_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, counterparty_id)],
            CONFIRMATION: [CallbackQueryHandler(confirmation_handler, pattern='^(confirm_trade|cancel_trade)$')],
        },
        fallbacks=[CommandHandler("cancel", cancel_trade)],
    )

    # Conversation handler for /refund command
    refund_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("refund", refund_command)],
        states={
            REFUND_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, refund_reason)],
        },
        fallbacks=[CommandHandler("cancel", cancel_trade)], # Using the same cancel for now
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(trade_conv_handler)
    application.add_handler(refund_conv_handler)
    application.add_handler(CallbackQueryHandler(handle_buyer_approval, pattern='^(approve_trade|reject_trade)_trade_'))

    # Admin Command Handlers
    application.add_handler(CommandHandler("dashboard", admin_dashboard))
    application.add_handler(CommandHandler("trade_history", trade_history))
    application.add_handler(CommandHandler("verify_payment", verify_payment))
    application.add_handler(CommandHandler("force_release", force_release))
    application.add_handler(CommandHandler("resolve_dispute", resolve_dispute))
    application.add_handler(CommandHandler("verify_refund", verify_refund))

    # Error handler
    application.add_error_handler(error_handler)

    logger.info("Bot started polling...")
    application.run_polling()

if __name__ == "__main__":
    main()


