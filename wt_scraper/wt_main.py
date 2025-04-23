# wt_main.py - Debug-enhanced + REACTIVATION support for REMOVED rides

import time
import traceback
from datetime import datetime, timedelta
from collections import Counter
from wt_login import WTAutoLogin
from wt_scraper import WTScraperZoomScroll
from utils.mongodb_utils import get_mongo_collection


class PersistentSession:
    def __init__(self):
        self.session = None
        self.driver = None

    def ensure_login(self):
        if not self.session:
            self.session = WTAutoLogin(headless=True)
            if not self.session.login():
                self.session = None
                raise Exception("🔐 Giriş başarısız")
            self.driver = self.session.get_driver()
        return self.driver

    def reset_session(self):
        if self.session:
            try:
                self.session.close()
            except:
                pass
        self.session = None
        self.driver = None


persistent = PersistentSession()


def get_mongo_status_summary():
    collection = get_mongo_collection("wt_rides")
    status_counts = Counter()
    for doc in collection.find({"Source": "wt"}):
        status = doc.get("Status", "UNKNOWN")
        status_counts[status] += 1
    return status_counts


def save_to_mongodb(df):
    try:
        collection = get_mongo_collection("wt_rides")
        now = datetime.now()
        all_ids = set(df["ID"])

        print(f"🧮 Gelen {len(df)} kaydın ID'leri: {list(all_ids)[:5]} ...")

        new_count = 0
        updated_count = 0
        reactivated_count = 0

        for _, row in df.iterrows():
            row_dict = row.to_dict()
            ride_id = row_dict["ID"]
            existing = collection.find_one({"ID": ride_id})

            if existing:
                if existing.get("Status") == "REMOVED":
                    row_dict["FirstSeen"] = now
                    row_dict["LastSeen"] = now
                    row_dict["Status"] = "NEW"
                    row_dict["Source"] = "wt"
                    collection.update_one({"ID": ride_id}, {"$set": row_dict})
                    reactivated_count += 1
                    print(f"♻️ [REACTIVATED] {ride_id} (was REMOVED)")
                    continue

                updates = {}
                first_seen = existing.get("FirstSeen")
                if isinstance(first_seen, str):
                    first_seen = datetime.fromisoformat(first_seen)
                age_minutes = (now - first_seen).total_seconds() / 60
                if existing.get("Status") in ["NEW", "UPDATED"] and age_minutes > 10:
                    updates["Status"] = "ACTIVE"
                updates.update({
                    "LastSeen": now,
                    "Vehicle": row_dict.get("Vehicle"),
                    "Pickup": row_dict.get("Pickup"),
                    "Dropoff": row_dict.get("Dropoff"),
                    "Time": row_dict.get("Time"),
                    "ride_datetime": row_dict.get("ride_datetime"),
                    "Price": row_dict.get("Price"),
                    "IsNewBadge": row_dict.get("IsNewBadge"),
                    "Source": "wt"
                })
                collection.update_one({"ID": ride_id}, {"$set": updates})
                updated_count += 1
            else:
                row_dict["FirstSeen"] = now
                row_dict["LastSeen"] = now
                row_dict["Status"] = "NEW"
                row_dict["Source"] = "wt"
                collection.insert_one(row_dict)
                new_count += 1
                print(f"➕ [INSERT] {ride_id} → {row_dict.get('Pickup')} → {row_dict.get('Dropoff')}")

        removed_count = 0
        for doc in collection.find({"Source": "wt"}):
            if doc["ID"] not in all_ids and doc["Status"] != "REMOVED":
                collection.update_one({"ID": doc["ID"]}, {"$set": {"Status": "REMOVED", "LastSeen": now}})
                removed_count += 1

        print(f"✅ MongoDB: {len(df)} kayıt işlendi → NEW: {new_count}, REACTIVATED: {reactivated_count}, UPDATED: {updated_count}, REMOVED: {removed_count}")

    except Exception as e:
        print(f"❌ MongoDB kayıt hatası: {e}")
        traceback.print_exc()


def remove_old_removed_entries():
    try:
        collection = get_mongo_collection("wt_rides")
        cutoff_time = datetime.now() - timedelta(days=1)
        result = collection.delete_many({
            "Status": "REMOVED",
            "LastSeen": {"$lt": cutoff_time}
        })
        if result.deleted_count:
            print(f"🗑️ {result.deleted_count} eski REMOVED kayıt silindi.")
    except Exception as e:
        print(f"⚠️ REMOVED kayıt silme hatası: {e}")


def log_mongo_status(label):
    summary = get_mongo_status_summary()
    print(f"\n📊 MongoDB Durumu ({label}):")
    for key in ["NEW", "ACTIVE", "UPDATED", "REMOVED"]:
        print(f"  - {key}: {summary.get(key, 0)}")


def run_scraper_loop(interval=60):
    login_attempts = 0
    while True:
        try:
            print(f"\n=== WT Scraper Başlatılıyor: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            log_mongo_status("🟡 Öncesi")

            driver = persistent.ensure_login()
            scraper = WTScraperZoomScroll(driver=driver, csv_path=None)
            df, raw_card_count, parsed_count = scraper.run_scraping_cycle()

            if parsed_count == 0:
                print("⚠️ No rides parsed. Trying one more time in 5 seconds...")
                time.sleep(5)
                df, raw_card_count, parsed_count = scraper.run_scraping_cycle()

            if df is not None and not df.empty:
                print(f"📥 Scraped DataFrame ({len(df)} rows):")
                print(df[["ID", "Pickup", "Dropoff", "Time"]].head(5).to_string(index=False))

                save_to_mongodb(df)
                remove_old_removed_entries()
            else:
                print("⚠️ No data frame created after retry.")

            log_mongo_status("🟢 Sonrası")

            login_attempts = 0
            print(f"⏱️ {interval} saniye sonra tekrar çalışacak...")
            time.sleep(interval)

        except Exception as e:
            print(f"\n[ERROR] Scraper çalışırken hata oluştu: {e}")
            traceback.print_exc()
            persistent.reset_session()
            login_attempts += 1
            if login_attempts >= 3:
                print("❌ 3 kez üst üste hata alındı. Döngü durduruluyor.")
                break
            else:
                print("🔁 Oturum yenileniyor, 30 sn sonra tekrar deneniyor...")
                time.sleep(30)


if __name__ == "__main__":
    run_scraper_loop()