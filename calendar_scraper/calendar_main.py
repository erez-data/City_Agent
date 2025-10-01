import os
import time
import traceback
from datetime import datetime, timedelta
from calendar_scraper import CalendarScraper
from utils.mongodb_utils import get_mongo_collection
from collections import Counter

USE_INCREMENTAL = bool(int(os.getenv("TASKS_INCREMENTAL", "0")))  # 1 ise incremental
INCREMENTAL_WINDOW_HOURS = int(os.getenv("TASKS_INCREMENTAL_WINDOW_H", "24"))  # varsayılan 24h

def get_mongo_status_summary():
    collection = get_mongo_collection("calendar_tasks")
    status_counts = Counter()
    for doc in collection.find({"Source": "calendar"}, {"_id": 0, "Status": 1}):
        status = doc.get("Status", "UNKNOWN")
        status_counts[status] += 1
    return status_counts


def remove_old_removed_entries():
    try:
        collection = get_mongo_collection("calendar_tasks")
        cutoff = datetime.utcnow() - timedelta(days=1)  # UTC-naive
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
    scraper = CalendarScraper(use_incremental=USE_INCREMENTAL, incremental_window_hours=INCREMENTAL_WINDOW_HOURS)
    collection = get_mongo_collection("calendar_tasks")

    while True:
        try:
            log_status_summary("🟡 Öncesi")

            now_utc = datetime.utcnow()  # UTC-naive
            scraped_ids = scraper.run_scraping_cycle()

            # Son 2 dk'da Google Updated olan görülenleri UPDATED yap (UTC)
            try:
                recent_cut = now_utc - timedelta(minutes=2)
                if scraped_ids:
                    res = collection.update_many(
                        {
                            "Source": "calendar",
                            "ID": {"$in": list(scraped_ids)},
                            "Updated": {"$gt": recent_cut},
                            "Status": {"$ne": "REMOVED"}
                        },
                        {"$set": {"Status": "UPDATED"}}
                    )
                    if res.modified_count:
                        print(f"✨ UPDATED (Updated<2dk): {res.modified_count} kayıt işaretlendi.")
            except Exception as e:
                print(f"⚠️ UPDATED toplu işaretleme hatası: {e}")

            # NEW/UPDATED → ACTIVE (10 dk sonra) — UTC'ye göre
            try:
                ten_min_cut = now_utc - timedelta(minutes=10)
                res_active = collection.update_many(
                    {
                        "Source": "calendar",
                        "Status": {"$in": ["NEW", "UPDATED"]},
                        "FirstSeen": {"$lt": ten_min_cut}
                    },
                    {"$set": {"Status": "ACTIVE"}}
                )
                if res_active.modified_count:
                    print(f"🔁 NEW/UPDATED → ACTIVE: {res_active.modified_count} kayıt güncellendi.")
            except Exception as e:
                print(f"⚠️ ACTIVE güncellemesi hatası: {e}")

            remove_old_removed_entries()
            log_status_summary("🟢 Sonrası")

            print(f"⏱️ {interval} saniye sonra tekrar çalışacak.\n")
            time.sleep(interval)

        except KeyboardInterrupt:
            print("🛑 Kullanıcı tarafından durduruldu.")
            break
        except Exception as e:
            print(f"[ERROR] Scraper hata verdi: {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    run_calendar_loop()
