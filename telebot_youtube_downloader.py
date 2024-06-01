# File: telebot_youtube_downloader.py
api = "5883942283:AAHBjRNN6enzueo4ffFOx8BxLrvySG26QYM"
# File: telebot_youtube_downloader.py
# api = "6118338235:AAGy64uITXMbc3h_KmLeKQVYxlIjDu1YX5o"
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytube import YouTube
from pytube.cli import on_progress
import os
import re
import logging
import json
import requests
from keep_alive import keep_alive

keep_alive()

API_TOKEN = api
USER_DATA_FILE = 'user_data.json'

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

bot = telebot.TeleBot(API_TOKEN)

# Delete webhook
bot.remove_webhook()

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


def upload_to_fileio(file_path):
    with open(file_path, 'rb') as f:
        response = requests.post('https://file.io/', files={'file': f})
    response_data = response.json()
    if response.status_code == 200 and response_data.get('success'):
        return response_data['link']
    else:
        raise Exception("Failed to upload file to file.io")


# Handler for the /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    add_user(user_id, username)

    logger.info(f"User {user_id} ({username}) started the bot.")
    bot.reply_to(
        message,
        f"Welcome, {username}! Send me a YouTube link to get started. Use /help for more information."
    )


# Handler for the /help command
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "Here's how you can use this bot:\n"
        "1. Send a YouTube link to download the video.\n"
        "2. Choose the video quality from the provided options.\n"
        "3. The bot will upload the video and send you a download link.\n"
        "4. You can greet the bot with 'Hi' or 'Hello'.")
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
        logger.info(
            f"Greeting message received from user {user_id} ({username}).")
        bot.reply_to(
            message,
            f"Hello, {username}! How can I help you today? Send me a YouTube link to download a video."
        )
        return

    # Check for YouTube link
    yt_link = message.text
    if not re.search(
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
            yt_link):
        logger.warning(
            f"Invalid YouTube link received from user {user_id} ({username}): {yt_link}"
        )
        bot.reply_to(message, "Please send a valid YouTube link.")
        return

    try:
        yt = YouTube(yt_link)
        streams = yt.streams.filter(progressive=True)

        if not streams:
            logger.warning(
                f"No downloadable streams found for link {yt_link} from user {user_id} ({username})."
            )
            bot.reply_to(message, "No downloadable video streams found.")
            return

        markup = InlineKeyboardMarkup()
        for stream in streams:
            btn_text = f"{stream.resolution} - {round(stream.filesize / (1024 * 1024), 2)} MB"
            markup.add(
                InlineKeyboardButton(btn_text,
                                     callback_data=f"{yt_link}|{stream.itag}"))

        logger.info(
            f"Video quality options sent to user {user_id} ({username}) for link {yt_link}."
        )
        bot.send_message(message.chat.id,
                         "Select the quality:",
                         reply_markup=markup)

    except Exception as e:
        logger.error(
            f"Error processing link {yt_link} from user {user_id} ({username}): {str(e)}"
        )
        bot.reply_to(message, f"Error: {str(e)}")


# Download progress callback
def progress_callback(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage_of_completion = bytes_downloaded / total_size * 100
    if percentage_of_completion % 10 == 0:  # Update every 10%
        bot.send_message(
            chat_id, f"Download progress: {percentage_of_completion:.2f}%")


# Handler for quality selection
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global chat_id
    chat_id = call.message.chat.id
    try:
        yt_link, itag = call.data.split('|')
        yt = YouTube(yt_link, on_progress_callback=progress_callback)
        stream = yt.streams.get_by_itag(itag)
        user_id = call.message.chat.id
        username = user_data.get(str(user_id), "User")

        if not stream:
            logger.warning(
                f"Invalid stream selection by user {user_id} ({username}) for link {yt_link}."
            )
            bot.send_message(call.message.chat.id, "Invalid selection.")
            return

        # Download video
        logger.info(
            f"Downloading video for user {user_id} ({username}) from link {yt_link} with itag {itag}."
        )
        bot.send_message(call.message.chat.id, "Downloading video...")
        stream.download()
        video_file = stream.default_filename

        # Upload to file.io and get the link
        download_link = upload_to_fileio(video_file)

        bot.send_message(
            call.message.chat.id,
            f"Video downloaded successfully! [Download it here]({download_link})."
        )
        logger.info(
            f"Video successfully uploaded and link sent to user {user_id} ({username}) from link {yt_link}."
        )

        os.remove(video_file)

    except Exception as e:
        logger.error(
            f"Error during callback handling for user {user_id} ({username}): {str(e)}"
        )
        bot.send_message(call.message.chat.id, f"Error: {str(e)}")


bot.polling()
