import random
import datetime
import gspread
import matplotlib
matplotlib.use('Agg')  # Set the backend to non-interactive

import matplotlib.pyplot as plt
import io,re
from oauth2client.service_account import ServiceAccountCredentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

import pytesseract
from PIL import Image
import cachetools
from telegram import InputFile
import telegram

# Telegram API key
bot_token = '5843343029:AAHkVvTbI_zsue_LL8wYoW85BzTARNSDcag'

# Google Sheets credentials
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
client = gspread.authorize(creds)
sheet = client.open('orders').sheet1

# Dictionary to store order count
order_count = {}

# Initialize a cache with a maximum size of 100 items
cache = cachetools.LRUCache(maxsize=100)

# Generate a unique token number
def generate_token():
    min_token = 1000  # Minimum token number
    max_token = 9999  # Maximum token number
    token_number = random.randint(min_token, max_token)
    return token_number

# Start function
def start(update, context):
    user = update.message.chat.first_name
    message = f"Hello {user}, welcome to our restaurant! How can I assist you today?"
    menu_keyboard = [[InlineKeyboardButton("🍔 Menu", callback_data='menu'),
                      InlineKeyboardButton("🍟 Snacks", callback_data='snacks')],
                     [InlineKeyboardButton("📊 Most Ordered", callback_data='most_ordered')],
                     [InlineKeyboardButton("📦 My Orders", callback_data='my_orders')]]
    reply_markup = InlineKeyboardMarkup(menu_keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)


# Menu function
def menu(update, context):
    query = update.callback_query  
    menu_keyboard = [[InlineKeyboardButton("🌱 Veg", callback_data='veg'),
                      InlineKeyboardButton("🥩 Non-veg", callback_data='non_veg')],
                     [InlineKeyboardButton("🔙 Back", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(menu_keyboard)
    query.answer()
    query.edit_message_text(text="Please select a category:", reply_markup=reply_markup)

# Veg function
def veg(update, context):
    query = update.callback_query
    veg_keyboard = [[InlineKeyboardButton("🍝 Veg Noodles - Rs 50", callback_data='Veg Noodles'),
                     InlineKeyboardButton("🍛 Veg Fried Rice - Rs 50", callback_data='Veg Fried Rice')],
                    [InlineKeyboardButton("🔙 Back", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(veg_keyboard)
    query.answer()
    query.edit_message_text(text="Please select a dish:", reply_markup=reply_markup)

# Non-veg function
def non_veg(update, context):
    query = update.callback_query
    non_veg_keyboard = [[InlineKeyboardButton("🍝 Non-Veg Noodles - Rs 60", callback_data='Non-Veg Noodles'),
                         InlineKeyboardButton("🍛 Non-Veg Fried Rice - Rs 60", callback_data='Non-Veg Fried Rice')],
                        [InlineKeyboardButton("🔙 Back", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(non_veg_keyboard)
    query.answer()
    query.edit_message_text(text="Please select a dish:", reply_markup=reply_markup)

# Snacks function
def snacks(update, context):
    query = update.callback_query
    snacks_keyboard = [[InlineKeyboardButton("🍟 Samosa - Rs 10", callback_data='Samosa'),
                        InlineKeyboardButton("🥪 Egg Puff - Rs 15", callback_data='Egg Puff')],
                       [InlineKeyboardButton("🔙 Back", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(snacks_keyboard)
    query.answer()
    query.edit_message_text(text="Please select a dish:", reply_markup=reply_markup)

# Most Ordered function
def most_ordered(update, context):
    query = update.callback_query
    query.answer()

    # Check if the data is already cached
    if "most_ordered_data" in cache:
        cached_data = cache["most_ordered_data"]
    else:
        # Fetch the most ordered items from the spreadsheet
        try:
            records = sheet.get_all_records()
            items_count = {}
            for record in records:
                item = str(record['Item'])  # Convert the item value to a string
                if item.strip():  # Filter out empty item names
                    if item in items_count:
                        items_count[item] += 1
                    else:
                        items_count[item] = 1

            # Sort the items by the order count in descending order
            sorted_items = sorted(items_count.items(), key=lambda x: x[1], reverse=True)

            # Prepare the message with the most ordered items
            message = "Most Ordered Items:\n"
            for item, count in sorted_items:
                message += f"{item}: {count} orders\n"

            # Create a bar graph of the most ordered items
            items = [item for item, _ in sorted_items]
            counts = [count for _, count in sorted_items]
            plt.bar(items, counts)
            plt.xlabel('Items')
            plt.ylabel('Order Count')
            plt.title('Most Ordered Items')
            plt.xticks(rotation=90)

            # Display the number of items on the graph
            for i in range(len(items)):
                plt.text(i, counts[i], str(counts[i]), ha='center', va='bottom')

            plt.tight_layout()

            # Save the graph image to a BytesIO object
            image_stream = io.BytesIO()
            plt.savefig(image_stream, format='png')
            image_stream.seek(0)

            cached_data = (message, image_stream)
            cache["most_ordered_data"] = cached_data

        except Exception as e:
            print("Error fetching most ordered items:", str(e))

    # Send the cached data to the user
    message, image_stream = cached_data
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_stream)

# My Orders function
def my_orders(update, context):
    query = update.callback_query
    user = query.from_user

    # Fetch the user's orders from the spreadsheet
    try:
        records = sheet.get_all_records()
        user_orders = []
        for record in records:
            if str(record['User Id']) == str(user.id):
                order_details = f"Item: {record['Item']}\n"
                order_details += f"Token : {record['Token']}\n"
                order_details += f"Payment Type: {record['Payment Type']}\n"
                order_details += f"Transaction Id: {record['Transaction Id']}\n"
                user_orders.append(order_details)

        if user_orders:
            # Split orders into separate messages if necessary
            max_message_length = 4096
            current_message = ""
            for order in user_orders:
                if len(current_message) + len(order) <= max_message_length:
                    current_message += order
                else:
                    context.bot.send_message(chat_id=update.effective_chat.id, text=current_message)
                    current_message = order
            if current_message:
                context.bot.send_message(chat_id=update.effective_chat.id, text=current_message)
        else:
            message = "You haven't placed any orders yet."
            context.bot.send_message(chat_id=update.effective_chat.id, text=message)

    except Exception as e:
        print("Error fetching user orders:", str(e))




# Payment methods function
def payment_methods(update, context):
    query = update.callback_query
    payment_keyboard = [[InlineKeyboardButton("💳 Online Payment", callback_data='online_payment')],
                        [InlineKeyboardButton("💵 Offline Payment", callback_data='offline_payment')]]
    reply_markup = InlineKeyboardMarkup(payment_keyboard)
    query.answer()
    query.edit_message_text(text="Please select a payment method:", reply_markup=reply_markup)

# Online payment function
def online_payment(update, context):
    query = update.callback_query
    user = query.from_user
    if user.id in order_count:
        order_count[user.id]['payment_method'] = 'Online'
        quantity = order_count[user.id].get('quantity')
        item = order_count[user.id].get('item')
        total_amount = order_count[user.id].get('total_amount')

        # Send the QR code image to the user
        qr_code_image_path = 'qr_code.png'  # Replace with the actual path to your QR code image
        with open(qr_code_image_path, 'rb') as qr_code_file:
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(qr_code_file), caption=f"Scan the QR code to complete the payment for:\n\nItem: {item}\nQuantity: {quantity}\nTotal Amount: {total_amount} RS")

        query.answer()
        query.edit_message_text(text="Please send a screenshot of the transaction details.")


# Offline payment function
def offline_payment(update, context):
    query = update.callback_query
    user = query.from_user
    if user.id in order_count:
        order_count[user.id]['payment_method'] = 'Offline'
        quantity = order_count[user.id].get('quantity')
        item = order_count[user.id].get('item')
        token_number = generate_token()
        order_count[user.id]['token_number'] = token_number
        query.answer()
        query.edit_message_text(text=f"Your order has been placed successfully!\nPlease make the payment within 15 minutes.\n\nItem: {item}\nQuantity: {quantity}\nToken number: {token_number}")
        
        # Update the spreadsheet with the token number
        try:
            transaction_id = ''  # Since it's an offline payment, there won't be a Transaction Id
        except Exception as e:
            print("Error inserting row:", str(e))


# Online Feedback function
def online_feedback(update, context):
    query = update.callback_query
    query.answer()

    # Ask the user to provide online feedback
    query.message.reply_text("Please provide your online feedback:")

# Offline Feedback function
def offline_feedback(update, context):
    query = update.callback_query
    query.answer()

    # Ask the user to provide offline feedback
    query.message.reply_text("Please provide your offline feedback:")

# Process Online Feedback
def process_online_feedback(update, context):
    user = update.message.from_user
    feedback = update.message.text
    query = update.callback_query

    # Store online feedback in the Google Sheets spreadsheet
    try:
        payment_method = order_count[user.id].get('payment_method')  # Get payment method from order_count
        sheet = client.open('orders').sheet1  # Change 'feedback' to your actual spreadsheet name
        transaction_id = order_count[user.id].get('transaction_id')  # Get transaction ID from order_count
        item = order_count[user.id].get('item')
        quantity = order_count[user.id].get('quantity')
        token_number = order_count[user.id].get('token_number')
        row_data = [user.id, user.username,telegram.phone_number, item, quantity, token_number, str(datetime.datetime.now().replace(microsecond=0)), payment_method, transaction_id, feedback]
        sheet.insert_row(row_data, 2)

        update.message.reply_text("Thank you for your online feedback!")

    except Exception as e:
        print("Error inserting online feedback:", str(e))
        update.message.reply_text("Oops! Something went wrong. Please try again later.")


# Process Offline Feedback
def process_offline_feedback(update, context):
    user = update.message.from_user
    feedback = update.message.text
    query = update.callback_query

    # Store offline feedback in the Google Sheets spreadsheet
    try:
        payment_method = order_count[user.id].get('payment_method')  # Get payment method from order_count
        sheet = client.open('orders').sheet1  # Change 'feedback' to your actual spreadsheet name
        transaction_id = ''
        item = order_count[user.id].get('item')
        quantity = order_count[user.id].get('quantity')
        token_number = order_count[user.id].get('token_number')
        row_data = [user.id, user.username,telegram.phone_number, item, quantity, token_number, str(datetime.datetime.now().replace(microsecond=0)), 'Offline', transaction_id, feedback]
        sheet.insert_row(row_data, 2)

        update.message.reply_text("Thank you for your offline feedback!")

    except Exception as e:
        print("Error inserting offline feedback:", str(e))
        update.message.reply_text("Oops! Something went wrong. Please try again later.")




#UPI Transaction Id
def extract_text_from_screenshot(image_path):
    try:
        image = Image.open(image_path)

        # Convert the image to grayscale for better OCR results
        image = image.convert('L')

        # Perform OCR using Tesseract
        extracted_text = pytesseract.image_to_string(image)

        pattern = r"UPI transaction ID\s+(\d+)"

        # Search for the UPI transaction ID in the text
        match = re.search(pattern, extracted_text)

        # Extract the UPI transaction ID if a match is found
        if match:
            upi_id = match.group(1)
            print("UPI transaction ID:", upi_id)
            return upi_id
        else:
            print("UPI transaction ID not found.")
            return None

    except Exception as e:
        print("Error extracting text from screenshot:", str(e))
        return None


    
# Screenshot handler for online payment
def process_screenshot(update, context):
    user = update.message.from_user

    if update.message.photo:
        screenshot = update.message.photo[-1].get_file()
        screenshot_path = f"screenshot_{user.id}.jpg"

        try:
            screenshot.download(screenshot_path)
            extracted_text = extract_text_from_screenshot(screenshot_path)

            if extracted_text:
                transaction_id = extracted_text.strip()
                if user.id not in order_count:
                    return  # Ignore invalid transaction ID

                order_count[user.id]['transaction_id'] = transaction_id  # Store transaction ID

                item = order_count[user.id].get('item')
                quantity = order_count[user.id].get('quantity')
                payment_method = order_count[user.id].get('payment_method')
                quantity = order_count[user.id].get('quantity')

                if item and quantity and payment_method == 'Online':
                    token_number = generate_token()
                    order_count[user.id]['token_number'] = token_number
                    

                    try:
                        
                        message = f"Your order for {item} has been placed successfully!\nToken number: {token_number}"
                        context.bot.send_message(chat_id=update.effective_chat.id, text=message)
                    except Exception as e:
                        print("Error inserting row:", str(e))
            else:
                context.bot.send_message(chat_id=update.effective_chat.id, text="Unable to extract transaction ID from the screenshot. Please try again.")

        except Exception as e:
            print("Error processing screenshot:", str(e))
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No screenshot found. Please send a screenshot of the transaction details.")

# Callback query handler
# Callback query handler
def button(update, context):
    query = update.callback_query
    user = query.from_user

    if query.data == 'menu':
        menu(update, context)
    elif query.data == 'snacks':
        snacks(update, context)
    elif query.data == 'most_ordered':
        most_ordered(update, context)
    elif query.data == 'my_orders':
        my_orders(update, context)
    elif query.data == 'veg':
        veg(update, context)
    elif query.data == 'non_veg':
        non_veg(update, context)
    elif query.data == 'back':
        start(update, context)
    elif query.data in ['Veg Noodles', 'Veg Fried Rice', 'Non-Veg Noodles', 'Non-Veg Fried Rice', 'Samosa', 'Egg Puff']:
        if user.id not in order_count:
            order_count[user.id] = {}
        order_count[user.id]['item'] = query.data

        # Ask for quantity selection
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("1", callback_data='quantity_1'),
             InlineKeyboardButton("2", callback_data='quantity_2'),
             InlineKeyboardButton("3", callback_data='quantity_3')],
            [InlineKeyboardButton("Back", callback_data='back')]
        ])
        query.message.reply_text("Select quantity:", reply_markup=reply_markup)
    elif query.data in ['quantity_1', 'quantity_2', 'quantity_3']:
        quantity = int(query.data.split('_')[1])
        if user.id in order_count:
            order_count[user.id]['quantity'] = quantity

            # Calculate the total amount
            item = order_count[user.id].get('item')
            item_price = {
                'Veg Noodles': 50,
                'Veg Fried Rice': 50,
                'Non-Veg Noodles': 60,
                'Non-Veg Fried Rice': 60,
                'Samosa': 15,
                'Egg Puff': 20
            }
            price = item_price.get(item)
            if price is not None:
                total_amount = price * quantity
                order_count[user.id]['total_amount'] = total_amount

                # Ask the user to pay
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Online Payment", callback_data='online_payment')],
                    [InlineKeyboardButton("Offline Payment", callback_data='offline_payment')],
                    [InlineKeyboardButton("Back", callback_data='back')]
                ])
                query.message.reply_text(f"Total Amount: {total_amount} RS\nSelect a payment method:", reply_markup=reply_markup)
            else:
                query.message.reply_text("Failed to calculate the total amount. Please try again.")
    elif query.data == 'online_payment':
        online_payment(update, context)
    elif query.data == 'offline_payment':
        offline_payment(update, context)
    elif query.data == 'online_feedback':
        online_feedback(update, context)
    elif query.data == 'offline_feedback':
        offline_feedback(update, context)




# Error handler
def error(update, context):
    print(f"Update {update} caused error {context.error}")

# Main function
def main():
    updater = Updater(token=bot_token, use_context=True)
    dp = updater.dispatcher

    # Add handlers
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.photo, process_screenshot))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, process_online_feedback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, process_offline_feedback))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
