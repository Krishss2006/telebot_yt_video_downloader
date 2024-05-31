# File: telebot_youtube_downloader.py
api = "5883942283:AAHBjRNN6enzueo4ffFOx8BxLrvySG26QYM"
# File: telebot_youtube_downloader.py
# File: telebot_youtube_downloader.py

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytube import YouTube
import os
import re
import logging
import json
import time

API_TOKEN = api
USER_DATA_FILE = 'user_data.json'
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

bot = telebot.TeleBot(API_TOKEN)

# Load user data
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, 'r') as file:
        user_data = json.load(file)
else:
    user_data = {}

def save_user_data():
    with open(USER_DATA_FILE, 'w') as file:
        json.dump(user_data, file)

def add_user(user_id, username):
    if user_id not in user_data:
        user_data[user_id] = username
        save_user_data()

# Handler for the /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    add_user(user_id, username)
    
    logger.info(f"User {user_id} ({username}) started the bot.")
    bot.reply_to(message, f"Welcome, {username}! Send me a YouTube link to get started. Use /help for more information.")

# Handler for the /help command
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "Here's how you can use this bot:\n"
        "1. Send a YouTube link to download the video.\n"
        "2. Choose the video quality from the provided options.\n"
        "3. The bot will download and send the video to you.\n"
        "4. You can greet the bot with 'Hi' or 'Hello'."
    )
    bot.reply_to(message, help_text)

# Handler for text messages
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    text = message.text.lower()
    user_id = message.from_user.id
    username = message.from_user.first_name
    add_user(user_id, username)

    # Greeting messages
    if text in ['hi', 'hello']:
        logger.info(f"Greeting message received from user {user_id} ({username}).")
        bot.reply_to(message, f"Hello, {username}! How can I help you today? Send me a YouTube link to download a video.")
        return

    # Check for YouTube link
    yt_link = message.text
    if not re.search(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/', yt_link):
        logger.warning(f"Invalid YouTube link received from user {user_id} ({username}): {yt_link}")
        bot.reply_to(message, "Please send a valid YouTube link.")
        return

    try:
        yt = YouTube(yt_link)
        streams = yt.streams.filter(progressive=True)
        
        if not streams:
            logger.warning(f"No downloadable streams found for link {yt_link} from user {user_id} ({username}).")
            bot.reply_to(message, "No downloadable video streams found.")
            return
        
        markup = InlineKeyboardMarkup()
        for stream in streams:
            btn_text = f"{stream.resolution} - {round(stream.filesize / (1024 * 1024), 2)} MB"
            markup.add(InlineKeyboardButton(btn_text, callback_data=f"{yt_link}|{stream.itag}|{message.message_id}"))
        
        logger.info(f"Video quality options sent to user {user_id} ({username}) for link {yt_link}.")
        bot.send_message(message.chat.id, "Select the quality:", reply_markup=markup)
    
    except Exception as e:
        logger.error(f"Error processing link {yt_link} from user {user_id} ({username}): {str(e)}")
        bot.reply_to(message, f"Error: {str(e)}")

# Handler for quality selection
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    yt_link, itag, select_quality_msg_id = call.data.split('|')
    user_id = call.message.chat.id
    username = user_data.get(str(user_id), "User")

    def download_video():
        yt = YouTube(yt_link)
        stream = yt.streams.get_by_itag(itag)

        if not stream:
            logger.warning(f"Invalid stream selection by user {user_id} ({username}) for link {yt_link}.")
            bot.send_message(call.message.chat.id, "Invalid selection.")
            return
        
        # Delete the "select quality" message
##        bot.delete_message(call.message.chat.id, int(select_quality_msg_id))

        # Download video with retries
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Attempt {attempt}: Downloading video for user {user_id} ({username}) from link {yt_link} with itag {itag}.")
                msg = bot.send_message(call.message.chat.id, f"Downloading video... (Attempt {attempt}/{MAX_RETRIES})")
                stream.download()
                video_file = stream.default_filename
                
                with open(video_file, 'rb') as video:
                    bot.send_video(call.message.chat.id, video)
                
                os.remove(video_file)
                logger.info(f"Video successfully sent to user {user_id} ({username}) from link {yt_link}.")
                
                # Delete the "downloading video" message
                bot.delete_message(call.message.chat.id, msg.message_id)
                return

            except Exception as e:
                logger.error(f"Error during download attempt {attempt} for user {user_id} ({username}): {str(e)}")
                if attempt < MAX_RETRIES:
                    bot.send_message(call.message.chat.id, f"Retrying... (Attempt {attempt}/{MAX_RETRIES})")
                    time.sleep(RETRY_DELAY)
                else:
                    bot.send_message(call.message.chat.id, f"Failed to download the video after {MAX_RETRIES} attempts. Please try again later.")
                    return
    
    try:
        download_video()
    
    except Exception as e:
        logger.error(f"Error during callback handling for user {user_id} ({username}): {str(e)}")
        bot.send_message(call.message.chat.id, f"Error: {str(e)}")

bot.polling()
