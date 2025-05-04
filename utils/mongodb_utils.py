import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()  # .env.client_usetravel.client_city dosyasını yükle

def get_mongo_collection(collection_name):
    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGODB_DB_NAME")
    client = MongoClient(uri)
    return client[db_name][collection_name]
