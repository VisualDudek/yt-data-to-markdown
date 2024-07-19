import yaml
import logging
import logging.config
import os

from helper import parse_yaml_to_model
from dotenv import load_dotenv
from googleapiclient.discovery import build
from yt_viewer.data_model import PlaylistItemListResponse
from mdutils.mdutils import MdUtils
from typing import Dict


YT_CONFIG = "yt_config.yaml"
LOGGING_CONFIG = "logging_config.yaml"

# Load the config file
with open(LOGGING_CONFIG, 'rt') as f:
    config = yaml.safe_load(f.read())

# Configure the logging module with the config file
logging.config.dictConfig(config)

# Get a logger object
logger = logging.getLogger(__name__)


def convert_channelid_to_playlistid(channel_id: str) -> str:
    """
    Converts a YouTube channel ID to a playlist ID.

    Args:
        channel_id (str): The YouTube channel ID.

    Returns:
        str: The converted playlist ID.
    """
    return f"UU{channel_id[2:]}"


def generate_md_file(data: Dict[str, PlaylistItemListResponse]) -> None:
    md_file = MdUtils(file_name='yt_videos', title='Youtube Videos')

    for name, items in data.items():
        md_file.new_header(level=1, title=f"Channel: {name}")

        for item in items.items:
            md_file.new_line(
                f" - {item.snippet.title}  " +
                md_file.new_inline_link(link=f"https://youtu.be/{item.snippet.resourceId.videoId}", text="Watch")
                )

    md_file.create_md_file()


def main():
    # Get API key from .env file
    logger.info('Getting API key from .env file')
    load_dotenv()
    API_KEY_YT = os.getenv('API_KEY_YT')

    # Build the youtube object
    youtube = build('youtube', 'v3', developerKey=API_KEY_YT)

    # Create a dictionary to store the data
    data: Dict[str, PlaylistItemListResponse] = {}

    # Loop through the channels and call the API
    for name, id in config_model.channels.items():

        # Create a request object to call the API
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=convert_channelid_to_playlistid(id),  # Very importatnt and easy to miss
            maxResults=config_model.results
        ) 

        # Call the API
        logger.info(f"Calling the API for channel: {name}")
        response = request.execute()

        # Parse the response into a model
        try:
            playlist_response = PlaylistItemListResponse(**response)
        except Exception as e:
            logger.error(f"Failed to parse response into model. {e}")
            return
        
        # Traverse the response object and log the titles
        for item in playlist_response.items:
            logger.debug(f"Title: {item.snippet.title}")

        # Store data in dictionary
        data[name] = playlist_response

    # Generate a markdown file
    generate_md_file(data)


# Example usage
if __name__ == "__main__":
    yaml_file_path = YT_CONFIG
    logger.info(f"Reading YAML file: {yaml_file_path}")
    config_model = parse_yaml_to_model(yaml_file_path)
    
    if config_model:
        logger.debug(config_model)
    else:
        logger.error("Failed to parse YAML file into model.")

    main()
