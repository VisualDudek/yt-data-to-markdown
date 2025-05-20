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
YT_CONFIG = './yt_config.yaml'

# --- Configuration ---
API_KEY = os.getenv("API_KEY")
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

# --- MongoDB Configuration ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DATABASE_NAME = "youtube_data" # Or your preferred database name
MONGO_COLLECTION_NAME = "videos"     # Or your preferred collection name


def load_yaml(file_path: str) -> dict:
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def get_last_videos(channel_id, api_key, max_results=10):
    """
    Fetches the most recent videos from the specified YouTube channel.
    Returns a list of dicts with 'title', 'video_id', 'published_at', 'url', and 'duration'.
    """
    # Build the YouTube API service object
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=api_key)

    # First, get the list of videos using search().list()
    search_request = youtube.search().list(
        channelId=channel_id,
        part='snippet',
        order='date',
        maxResults=max_results,
        type='video'
    )
    search_response = search_request.execute()

    print(f"\n--- Video list ---")

    # Extract video IDs for the second API call
    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    
    # If no videos found, return empty list
    if not video_ids:
        print("No videos found for this channel.")
        return []
        
    # Second API call to get video details including duration
    # For duration, we need the 'contentDetails' part
    # For URL construction, we already have the video IDs
    videos_request = youtube.videos().list(
        part='snippet,contentDetails,statistics',
        id=','.join(video_ids)
    )
    videos_response = videos_request.execute()

    videos = []
    for item in videos_response.get('items', []):
        video_id = item['id']
        video_title = item['snippet']['title']
        published_at_str = item['snippet']['publishedAt']
        channel_id = item['snippet']['channelId']
        channel_title = item['snippet']['channelTitle']
        
        # Extract duration in ISO 8601 format (e.g., "PT5M30S" for 5 minutes and 30 seconds)
        duration_iso = item['contentDetails']['duration']
        
        # Construct URL
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        published_at_dt = None
        try:
            # YouTube API returns ISO 8601 format (e.g., "2023-10-26T14:30:00Z")
            # .replace('Z', '+00:00') is robust for Python versions < 3.11 with fromisoformat
            if published_at_str.endswith('Z'):
                published_at_dt = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
            else:
                published_at_dt = datetime.fromisoformat(published_at_str)
        except ValueError:
            print(f"Warning: Could not parse date '{published_at_str}' for video ID '{video_id}'. Storing as string.")
            published_at_dt = published_at_str # Fallback

        videos.append({
            'title': video_title,
            'video_id': video_id,
            'published_at': published_at_dt,
            'channel_id': channel_id,
            'channel_title': channel_title,
            'url': video_url,
            'duration': duration_iso,
            'view_count': item['statistics'].get('viewCount', '0')
        })
        print(f"Title: {video_title}, URL: {video_url}, Duration: {duration_iso}, Views: {item['statistics'].get('viewCount', '0')}")

    return videos


def save_videos_to_mongodb(collection, videos_data):
    """
    Saves a list of video data to MongoDB, avoiding duplicates based on 'video_id'.
    A unique index on 'video_id' must exist in the collection.
    """
    if not videos_data:
        print("No video data provided to save.")
        return

    saved_count = 0
    duplicate_count = 0
    error_count = 0

    for video in videos_data:
        try:
            # Ensure 'video_id' exists, as it's crucial for the unique index
            if 'video_id' not in video or not video['video_id']:
                print(f"Skipping video due to missing video_id: {video.get('title', 'N/A')}")
                error_count +=1
                continue
            
            # The unique index on 'video_id' will prevent duplicates
            collection.insert_one(video)
            print(f"Successfully saved video to MongoDB: {video['title']} (ID: {video['video_id']})")
            saved_count += 1
        except DuplicateKeyError:
            print(f"Video already exists in MongoDB (ID: {video['video_id']}). Skipping.")
            duplicate_count += 1
        except Exception as e:
            print(f"An error occurred while saving video {video.get('title', 'N/A')} to MongoDB: {e}")
            error_count += 1
    
    print(f"\n--- MongoDB Save Summary ---")
    print(f"Successfully saved {saved_count} new videos.")
    print(f"Found {duplicate_count} duplicates (skipped).")
    if error_count > 0:
        print(f"Encountered {error_count} errors during save.")

# --- Main Execution ---
if __name__ == '__main__':

    # --- MongoDB Setup ---

    mongo_client = None
    video_collection = None
    try:
        print(f"Connecting to MongoDB at {MONGO_URI}...")
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, server_api= ServerApi('1')) # Timeout for connection
        # Ping to confirm connection
        mongo_client.admin.command('ping') 
        print("Successfully connected to MongoDB.")
        
        db = mongo_client[MONGO_DATABASE_NAME]
        video_collection = db[MONGO_COLLECTION_NAME]

        # Create a unique index on 'video_id' to prevent duplicates.
        # This is idempotent (safe to run multiple times).
        index_name = video_collection.create_index("video_id", unique=True)
        print(f"Ensured unique index '{index_name}' on 'video_id' in collection '{MONGO_COLLECTION_NAME}'.")

    except Exception as e:
        print(f"Error: Could not connect to MongoDB or set up collection: {e}")
        print("Please ensure MongoDB is running and accessible, and MONGO_URI is correct.")
        exit(1) # Exit if DB connection fails, as storing data is a key goal.

    # --- Main Logic ---

    # Load the YAML configuration file
    config = load_yaml(YT_CONFIG)
    print(f"Loaded configuration from {YT_CONFIG}.")

    # Iterate through each channel in the config
    for channel_name, channel_id in config['channels'].items():
        print(f"Channel Name: {channel_name}, Channel ID: {channel_id}")

        # Fetch the latest videos from the channel
        latest_videos = get_last_videos(channel_id, API_KEY, max_results=config['results'])

        if latest_videos:
            print(f"\nFetched {len(latest_videos)} videos. Attempting to save to MongoDB...")
            # Save the videos to MongoDB
            save_videos_to_mongodb(video_collection, latest_videos)
        else:
            print("No videos fetched from the channel, nothing to save to MongoDB.")


    # Close MongoDB connection when done
    if mongo_client:
        mongo_client.close()
        print("\nMongoDB connection closed.")