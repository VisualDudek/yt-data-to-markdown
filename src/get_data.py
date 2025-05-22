import os
import pickle

from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Load environment variables from .env file
load_dotenv()  

# --- MongoDB Configuration ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DATABASE_NAME = "youtube_data"
MONGO_COLLECTION_NAME = "videos"     


print(f"Connecting to MongoDB at {MONGO_URI}...")
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, server_api= ServerApi('1')) # Timeout for connection
# Ping to confirm connection
mongo_client.admin.command('ping') 
print("Successfully connected to MongoDB.")

db = mongo_client[MONGO_DATABASE_NAME]
video_collection = db[MONGO_COLLECTION_NAME]

data = list(db.latest_ten.find())

# Pickle to file
with open("data.pkl", "wb") as f:
    pickle.dump(data, f)

# Load Pickled Data
with open("data.pkl", "rb") as f:
    loaded_data = pickle.load(f)

print(loaded_data)