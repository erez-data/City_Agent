import time
import traceback
from datetime import datetime, timedelta
from calendar_scraper import CalendarScraper
from utils.mongodb_utils import get_mongo_collection
from collections import Counter

def get_mongo_status_summary():
    collection = get_mongo_collection("calendar_tasks")
    status_counts = Counter()
    for doc in collection.find({"Source": "calendar"}):
        status = doc.get("Status", "UNKNOWN")
        status_counts[status] += 1
    return status_counts

def remove_old_removed_entries():
    try:
        collection = get_mongo_collection("calendar_tasks")
        cutoff = datetime.now() - timedelta(days=1)
        result = collection.delete_many({"Status": "REMOVED", "LastSeen": {"$lt": cutoff}})
        if result.deleted_count:
            print(f"🗑️ {result.deleted_count} eski REMOVED kayıt silindi.")
    except Exception as e:
        print(f"⚠️ Silme hatası: {e}")

def log_status_summary(label):
    summary = get_mongo_status_summary()
    print(f"\n📊 MongoDB Durumu ({label}):")
    for key in ["NEW", "UPDATED", "ACTIVE", "REMOVED"]:
        print(f"  - {key}: {summary.get(key, 0)}")

def run_calendar_loop(interval=60):
    print("\n=== Calendar Scraper Başlatıldı ===")
    scraper = CalendarScraper()

    while True:
        try:
            log_status_summary("🟡 Öncesi")

            now = datetime.now()
            scraped_ids = scraper.run_scraping_cycle()

            # Status güncellemesi: UPDATED
            collection = get_mongo_collection("calendar_tasks")
            for doc in collection.find({"Source": "calendar"}):
                if doc["ID"] in scraped_ids:
                    if doc.get("Status") == "ACTIVE":
                        age_min = (now - datetime.fromisoformat(str(doc.get("Updated")))).total_seconds() / 60
                        if age_min < 2:
                            collection.update_one({"ID": doc["ID"]}, {"$set": {"Status": "UPDATED"}})

            remove_old_removed_entries()
            log_status_summary("🟢 Sonrası")

            print(f"⏱️ {interval} saniye sonra tekrar çalışacak...\n")
            time.sleep(interval)

        except KeyboardInterrupt:
            print("🛑 Kullanıcı tarafından durduruldu.")
            break
        except Exception as e:
            print(f"[ERROR] Scraper hata verdi: {e}")
            traceback.print_exc()
            time.sleep(30)

if __name__ == "__main__":
    run_calendar_loop()
