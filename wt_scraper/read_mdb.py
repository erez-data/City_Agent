import os
from dotenv import load_dotenv
from pymongo import MongoClient
import pandas as pd

load_dotenv()

def test_read_from_mongo():
    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "city_agent")

    client = MongoClient(uri)
    collection = client[db_name]["wt_rides"]

    print(f"Connected to MongoDB → Database: {db_name}, Collection: wt_rides")
    print("Fetching all records...\n")

    # Get all documents from the collection
    cursor = collection.find().sort("LastSeen", -1)
    data = list(cursor)

    if not data:
        print("❌ No records found.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Optional: Reorder columns if needed
    columns_order = ['ID', 'Vehicle', 'Pickup', 'Dropoff', 'Time', 'Status', 'FirstSeen', 'LastSeen']
    df = df[[col for col in columns_order if col in df.columns]]

    # Print tabular format
    print(df.to_markdown(tablefmt="grid", index=False))

    print(df.to_markdown(tablefmt="grid", index=False))


if __name__ == "__main__":
    test_read_from_mongo()
