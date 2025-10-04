
import logging
import os
import threading
from flask import Flask
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
    client.admin.command("ismaster")
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
    await query.edit_message_text(f"Selected category: {context.user_data['item_category']}.\n\nPlease provide a detailed description of the item you are trading.")
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
    await query.edit_message_text(f"Selected payment method: {context.user_data['payment_method']}.\n\nPlease provide the trade deadline (e.g., YYYY-MM-DD HH:MM). All times are in WAT.")
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

# Flask app for health checks
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Add a conversation handler for the /trade command
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("trade", trade)],
        states={
            ITEM_CATEGORY: [CallbackQueryHandler(item_category, pattern='^category_.*$')],
            ITEM_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, item_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_input)],
            CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, currency_input)],
            PAYMENT_METHOD: [CallbackQueryHandler(payment_method, pattern='^pm_.*$')],
            DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, deadline_input)],
            COUNTERPARTY_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, counterparty_id)],
            CONFIRMATION: [CallbackQueryHandler(confirmation_handler, pattern='^(confirm|cancel)_trade$')]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    # Run the bot in a separate thread
    bot_thread = threading.Thread(target=application.run_polling)
    bot_thread.start()

    # Run Flask app in the main thread
    run_flask()

if __name__ == "__main__":
    main()

