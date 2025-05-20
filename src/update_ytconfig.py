import yaml
import re
import os

from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.prompt import Prompt
from rich.console import Console
from rich.pretty import Pretty
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone

# Load environment variables from .env file
load_dotenv()  

# --- YT channel config ---
YT_CONFIG = './src/yt_config.yaml'

# --- Configuration ---
API_KEY = os.getenv("API_KEY")
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'



def load_yaml(file_path: str) -> dict:
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def get_video_id_from_url(url):
    """
    Extracts the YouTube video ID from various URL formats.
    Handles:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    """
    if not url:
        return None

    # Parse the URL
    parsed_url = urlparse(url)
    
    # Check for standard youtube.com/watch URLs
    if parsed_url.hostname in ('www.youtube.com', 'm.youtube.com', 'music.youtube.com') and parsed_url.path == '/watch':
        query_params = parse_qs(parsed_url.query)
        return query_params.get('v', [None])[0]
    
    # Check for youtu.be short URLs
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]  # Remove the leading '/'
        
    # Check for youtube.com/embed URLs
    if parsed_url.hostname in ('www.youtube.com', 'm.youtube.com') and parsed_url.path.startswith('/embed/'):
        return parsed_url.path.split('/embed/')[1].split('?')[0] # Get part after /embed/ and before any query params

    # Regex for more robust matching if the above simple parsing fails for some edge cases
    # This regex tries to find common patterns for video IDs.
    regex_patterns = [
        r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    ]
    for pattern in regex_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
            
    print(f"Could not extract video ID from URL: {url}")
    return None

def get_channel_id_from_video_url(api_key, video_url):
    """
    Fetches the YouTube Channel ID for a given video URL.
    """

    video_id = get_video_id_from_url(video_url)
    if not video_id:
        return None

    try:
        # Build the YouTube API service object
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=api_key)

        # Call the videos.list method to retrieve video info
        request = youtube.videos().list(
            part="snippet",  # 'snippet' contains channelId, title, description, etc.
            id=video_id      # ID of the video to retrieve
        )
        response = request.execute()

        if response.get("items"):
            # Extract the channel ID from the first item in the response
            channel_id = response["items"][0]["snippet"]["channelId"]
            channel_title = response["items"][0]["snippet"]["channelTitle"]
            video_title = response["items"][0]["snippet"]["title"]
            
            print(f"\n--- Video Details ---")
            print(f"Video Title: {video_title}")
            print(f"Channel Title: {channel_title}")
            print(f"Channel ID: {channel_id}")
            return (channel_id, channel_title)
        else:
            print(f"No video found with ID: {video_id}. The video might be private, deleted, or the ID is incorrect.")
            return None

    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content.decode()}")
        if e.resp.status == 403:
            print("This might be due to an incorrect API key, exceeded quota, or the API not being enabled.")
        elif e.resp.status == 404:
             print(f"Video with ID '{video_id}' not found.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


# --- Main Execution ---
if __name__ == '__main__':

    console = Console()

    # --- Main Logic ---
    sample_video_url = Prompt.ask("Enter a YouTube video URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID): ", default="https://youtu.be/Coot4TFTkN4?si=MTxHahttsNC07ymW")
    if not sample_video_url:
        print("No URL provided. Exiting.")
        exit(1)

    print(f"Attempting to fetch Channel ID for video URL: {sample_video_url}")

    channel_id, channel_title = get_channel_id_from_video_url(API_KEY, sample_video_url)

    if channel_id:
        print(f"\nSuccessfully retrieved Channel ID: {channel_id}")
    else:
        print("\nFailed to retrieve Channel ID.")

    # Load the YAML configuration file
    config = load_yaml(YT_CONFIG)
    print(f"Loaded configuration from {YT_CONFIG}.")

    # Check if the config.channels has retrieved channel ID
    if channel_id in config['channels'].values():
        console.print(f"Channel ID {channel_id} [bold magenta]{channel_title}[/bold magenta] already exists in the configuration.")
    else:
        # Add the new channel ID to the config
        config['channels'][channel_title] = channel_id
        # Sort the channels alphabetically
        config['channels'] = dict(sorted(config['channels'].items(), key=lambda item: item[0].lower()))
        # Save the updated config back to the YAML file
        with open(YT_CONFIG, 'w') as file:
            yaml.dump(config, file, sort_keys=False)
        console.print(f"Added new channel: [bold magenta]{channel_title}[/bold magenta] with ID: {channel_id}")

    # Iterate through each channel in the config
    # for channel_name, channel_id in config['channels'].items():
        # print(f"Channel Name: {channel_name}, Channel ID: {channel_id}")

