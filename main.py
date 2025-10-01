
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

# Get bot token from environment variable
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")

# Trade states
ITEM, PRICE, CURRENCY, CONFIRMATION = range(4)


def start(update: Update, context: CallbackContext) -> None:
    """Sends a welcome message when the /start command is issued."""
    update.message.reply_text(
        "Welcome to the Universal Telegram Escrow Bot!\n\n" 
        "To start a new trade, use the /trade command."
    )

def trade(update: Update, context: CallbackContext) -> int:
    """Starts a new trade."""
    update.message.reply_text("You have initiated a new trade. Please provide the item you are trading.")
    return ITEM

def item(update: Update, context: CallbackContext) -> int:
    """Stores the item and asks for the price."""
    context.user_data["item"] = update.message.text
    update.message.reply_text(f"Item: {context.user_data["item"]}\n\nWhat is the price of the item?")
    return PRICE

def price(update: Update, context: CallbackContext) -> int:
    """Stores the price and asks for the currency."""
    context.user_data["price"] = update.message.text
    update.message.reply_text(f"Price: {context.user_data["price"]}\n\nWhat is the currency?")
    return CURRENCY

def currency(update: Update, context: CallbackContext) -> int:
    """Stores the currency and asks for confirmation."""
    context.user_data["currency"] = update.message.text
    trade_details = (
        f"Item: {context.user_data["item"]}\n"
        f"Price: {context.user_data["price"]} {context.user_data["currency"]}"
    )
    update.message.reply_text(f"Please confirm the trade details:\n\n{trade_details}")
    keyboard = [
        [InlineKeyboardButton("Confirm", callback_data="confirm"),
         InlineKeyboardButton("Cancel", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Do you want to proceed?", reply_markup=reply_markup)
    return CONFIRMATION

def confirmation(update: Update, context: CallbackContext) -> int:
    """Handles the confirmation of the trade."""
    query = update.callback_query
    query.answer()
    if query.data == "confirm":
        query.edit_message_text(text="Trade confirmed. The other party will be notified.")
        # Here you would add the logic to notify the other user and store the trade
    else:
        query.edit_message_text(text="Trade canceled.")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels the trade."""
    update.message.reply_text("Trade canceled.")
    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Add a conversation handler for the /trade command
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("trade", trade)],
        states={
            ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, item)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price)],
            CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, currency)],
            CONFIRMATION: [CallbackQueryHandler(confirmation)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()

