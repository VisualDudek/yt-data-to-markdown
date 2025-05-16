import re
import os
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from rich.prompt import Prompt
from rich.console import Console
from rich.pretty import Pretty
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone

load_dotenv()  # Load environment variables from .env file
# --- Configuration ---
API_KEY = os.getenv("API_KEY")
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

# --- MongoDB Configuration ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DATABASE_NAME = "youtube_data" # Or your preferred database name
MONGO_COLLECTION_NAME = "videos"     # Or your preferred collection name

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
    if api_key == 'YOUR_API_KEY':
        print("Error: Please replace 'YOUR_API_KEY' with your actual API key in the script.")
        return None

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
            return channel_id
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


if __name__ == '__main__':
    # --- Test with a sample YouTube video URL ---
    # TODO: Replace with the YouTube video URL you want to test
    # sample_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Example: Rick Astley
    # sample_video_url = "https://youtu.be/3JZ_D3ELwOQ" # Example: Google I/O Keynote
    # sample_video_url = "https://www.youtube.com/embed/rokGy0huYEA" # Example: NASA Live Stream


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

    sample_video_url = Prompt.ask("Enter a YouTube video URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID): ", default="https://youtu.be/Coot4TFTkN4?si=MTxHahttsNC07ymW")
    if not sample_video_url:
        print("No URL provided. Exiting.")
        exit(1)

    print(f"Attempting to fetch Channel ID for video URL: {sample_video_url}")
    
    retrieved_channel_id = get_channel_id_from_video_url(API_KEY, sample_video_url)

    if retrieved_channel_id:
        print(f"\nSuccessfully retrieved Channel ID: {retrieved_channel_id}")

        # Fetch the latest videos from the channel
        latest_videos = get_last_videos(retrieved_channel_id, API_KEY)


        if latest_videos:
            print(f"\nFetched {len(latest_videos)} videos. Attempting to save to MongoDB...")
            save_videos_to_mongodb(video_collection, latest_videos)
        else:
            print("No videos fetched from the channel, nothing to save to MongoDB.")

    else:
        print("\nFailed to retrieve Channel ID.")


    # --- Featch data from MongoDB View ---
    print("\n--- Fetching data from MongoDB View ---")
    for doc in db.abc.find():
        # Pretty print the document using rich console
        console = Console()
        console.print(Pretty(doc))
        print("\n") 


    # Close MongoDB connection when done
    if mongo_client:
        mongo_client.close()
        print("\nMongoDB connection closed.")