# wt_main.py - FINAL manual clean integrated version

import time
import traceback
import psutil  # ✅ Eksik olan import tamamlandı
from datetime import datetime, timedelta
from collections import Counter
from wt_login import WTAutoLogin
from wt_scv2 import WTScraperZoomScroll
from utils.mongodb_utils import get_mongo_collection
from utils.process_helperv2 import ChromeCleaner  # ✅ Cleaner import
import atexit

class PersistentSession:
    def __init__(self):
        self.session = None
        self.driver = None
        self.cleaner = None
        atexit.register(self.cleanup_on_exit)

    def ensure_login(self):
        if not self.session:
            self.session = WTAutoLogin(headless=True)
            if not self.session.login():
                self.session = None
                raise Exception("🔐 Giriş başarısız")
            self.driver = self.session.get_driver()

            if not self.cleaner:
                self.cleaner = ChromeCleaner(active_driver=self.driver)
            else:
                self.cleaner.active_driver = self.driver

        return self.driver

    def reset_session(self):
        if self.session:
            try:
                self.session.close()
            except:
                pass
        self.session = None
        self.driver = None

    def cleanup_on_exit(self):
        if self.session:
            print("🛑 [EXIT] Browser kapatılıyor...")
            try:
                self.session.close()
            except Exception as e:
                print(f"⚠️ [EXIT] Driver kapatılırken hata oluştu: {e}")
        else:
            print("ℹ️ [EXIT] Oturum zaten kapalı.")

persistent = PersistentSession()
scraper_cycle_counter = 0  # ✅ Full clean kontrolü için sayaç

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

        new_count = 0
        updated_count = 0
        reactivated_count = 0

        for _, row in df.iterrows():
            row_dict = row.to_dict()
            ride_id = row_dict["ID"]
            existing = collection.find_one({"ID": ride_id})

            if existing:
                if existing.get("Status") == "REMOVED":
                    row_dict.update({"FirstSeen": now, "LastSeen": now, "Status": "NEW", "Source": "wt"})
                    collection.update_one({"ID": ride_id}, {"$set": row_dict})
                    reactivated_count += 1
                    continue

                updates = {
                    "LastSeen": now,
                    "Vehicle": row_dict.get("Vehicle"),
                    "Pickup": row_dict.get("Pickup"),
                    "Dropoff": row_dict.get("Dropoff"),
                    "Time": row_dict.get("Time"),
                    "ride_datetime": row_dict.get("ride_datetime"),
                    "Price": row_dict.get("Price"),
                    "IsNewBadge": row_dict.get("IsNewBadge"),
                    "Source": "wt"
                }
                first_seen = existing.get("FirstSeen")
                if isinstance(first_seen, str):
                    first_seen = datetime.fromisoformat(first_seen)
                age_minutes = (now - first_seen).total_seconds() / 60
                if existing.get("Status") in ["NEW", "UPDATED"] and age_minutes > 10:
                    updates["Status"] = "ACTIVE"
                collection.update_one({"ID": ride_id}, {"$set": updates})
                updated_count += 1
            else:
                row_dict.update({"FirstSeen": now, "LastSeen": now, "Status": "NEW", "Source": "wt"})
                collection.insert_one(row_dict)
                new_count += 1

        removed_count = 0
        for doc in collection.find({"Source": "wt"}):
            if doc["ID"] not in all_ids and doc["Status"] != "REMOVED":
                collection.update_one({"ID": doc["ID"]}, {"$set": {"Status": "REMOVED", "LastSeen": now}})
                removed_count += 1

        print(f"✅ MongoDB kayıtları: NEW {new_count}, REACTIVATED {reactivated_count}, UPDATED {updated_count}, REMOVED {removed_count}")

    except Exception as e:
        print(f"❌ MongoDB kayıt hatası: {e}")
        traceback.print_exc()

def remove_old_removed_entries():
    try:
        collection = get_mongo_collection("wt_rides")
        cutoff_time = datetime.now() - timedelta(days=1)
        result = collection.delete_many({"Status": "REMOVED", "LastSeen": {"$lt": cutoff_time}})
        if result.deleted_count:
            print(f"🗑️ {result.deleted_count} eski REMOVED kayıt silindi.")
    except Exception as e:
        print(f"⚠️ REMOVED kayıt silme hatası: {e}")

def show_active_chrome_processes(context=""):
    print(f"\n🛠️ Active Chrome Processes {context}:")
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            if proc.info['name'] and ('chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower()):
                mem_mb = (proc.info['memory_info'].rss / 1024 / 1024) if proc.info['memory_info'] else 0
                print(f"  PID {proc.pid} - {proc.info['name']} - {mem_mb:.1f} MB")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def run_scraper_loop(interval=60):
    global scraper_cycle_counter
    login_attempts = 0

    while True:
        try:
            print(f"\n=== WT Scraper Başlatılıyor: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

            driver = persistent.ensure_login()

            show_active_chrome_processes("(before scraping)")

            scraper = WTScraperZoomScroll(driver=driver, csv_path=None)
            df, raw_card_count, parsed_count = scraper.run_scraping_cycle()

            if parsed_count == 0:
                print("⚠️ No rides parsed. Trying again in 5 seconds...")
                time.sleep(5)
                df, raw_card_count, parsed_count = scraper.run_scraping_cycle()

            if df is not None and not df.empty:
                save_to_mongodb(df)
                remove_old_removed_entries()

            show_active_chrome_processes("(after scraping)")

            # ✅ Scraping ve DB kayıt işlemi bitince manuel temizleme
            if persistent.cleaner:
                persistent.cleaner.manual_clean(force_full_clean=False)

            scraper_cycle_counter += 1
            if scraper_cycle_counter >= 5:
                print("\n💥 5 scraping sonrası FULL CLEAN yapılıyor...")

                # ✅ Önce tüm Chrome PID'leri öldür
                if persistent.cleaner:
                    persistent.cleaner.manual_clean(force_full_clean=True)

                # ✅ Sonra driverı resetle ve yeniden login yap
                print("♻️ FULL CLEAN sonrası yeni oturum açılıyor...")
                persistent.reset_session()
                persistent.ensure_login()

                scraper_cycle_counter = 0

            print(f"⏱️ {interval} saniye sonra tekrar çalışacak...")
            time.sleep(interval)

        except Exception as e:
            print(f"\n[ERROR] Scraper çalışırken hata oluştu: {e}")
            traceback.print_exc()
            persistent.reset_session()
            login_attempts += 1
            if login_attempts >= 3:
                print("❌ 3 kez üst üste hata. Döngü duruyor.")
                break
            else:
                print("🔁 30 sn sonra yeni login deneniyor...")
                time.sleep(30)

if __name__ == "__main__":
    run_scraper_loop()