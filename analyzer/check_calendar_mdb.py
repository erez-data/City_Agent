from utils.mongodb_utils import get_mongo_collection

# calendar_tasks koleksiyonunu al
calendar_collection = get_mongo_collection("calendar_tasks")

# ID alanı olmayan veya boş olan kayıtları getir
missing_id_docs = list(calendar_collection.find({
    "$or": [
        {"ID": {"$exists": False}},
        {"ID": None},
        {"ID": ""}
    ]
}))

# Sonuçları yazdır
print(f"🚨 Found {len(missing_id_docs)} records in calendar_tasks without a valid ID.\n")
for doc in missing_id_docs:
    print(doc)
