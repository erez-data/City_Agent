from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB URI and DB name from .env.client_city or fallback
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGODB_DB_NAME", "city_agent")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def show_collection_counts():
    print(f"📦 Collections in database '{DB_NAME}':\n")
    for name in db.list_collection_names():
        count = db[name].count_documents({})
        print(f"📁 {name:<25} → {count} records")

if __name__ == "__main__":
    show_collection_counts()
