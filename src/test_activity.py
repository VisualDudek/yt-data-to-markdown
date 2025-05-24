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

# --- Configuration ---
API_KEY = os.getenv("API_KEY2")
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

def get_last_videos(channel_id, api_key, max_results=10):
    """
    Fetches the most recent videos from the specified YouTube channel.
    Returns a list of dicts with 'title', 'video_id', 'published_at', 'url', and 'duration'.
    """
    # Build the YouTube API service object
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=api_key)

    # First, get the list of videos using search().list()
    activities = youtube.activities().list(
        channelId=channel_id,
        part='snippet',
        # order='date',
        maxResults=max_results,
        # type='video'
    )
    search_response = activities.execute()

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


# --- Main Execution ---
if __name__ == '__main__':
    get_last_videos("UCVhQ2NnY5Rskt6UjCUkJ_DA", API_KEY)
