import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını yükle

def get_mongo_collection(collection_name):
    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "city_agent")
    client = MongoClient(uri)
    return client[db_name][collection_name]
