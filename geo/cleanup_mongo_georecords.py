from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "city_agent")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def clean_geo_pipeline_data():
    for name in ["geo_addresses", "distance_cache", "enriched_rides"]:
        result = db[name].delete_many({})
        print(f"🧹 Cleared {result.deleted_count} documents from {name}")

if __name__ == "__main__":
    clean_geo_pipeline_data()
