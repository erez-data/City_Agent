# elife_main.py - FINAL manual clean integrated version

import time
import traceback
import psutil  # ✅ Yeni: Chrome proseslerini kontrol için
from datetime import datetime, timedelta
from collections import Counter
from login import ElifeAutoLogin
from elife_scraper import ElifeScraper
from utils.mongodb_utils import get_mongo_collection
from utils.process_helperv2 import ChromeCleaner  # ✅ Yeni: Cleaner import
import atexit

class PersistentSession:
    def __init__(self):
        self.session = None
        self.driver = None
        self.cleaner = None
        atexit.register(self.cleanup_on_exit)

    def ensure_login(self):
        if not self.session:
            self.session = ElifeAutoLogin(headless=True)
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
    collection = get_mongo_collection("elife_rides")
    status_counts = Counter()
    for doc in collection.find({"Source": "elife"}):
        status = doc.get("Status", "UNKNOWN")
        status_counts[status] += 1
    return status_counts

def remove_old_removed_entries():
    try:
        collection = get_mongo_collection("elife_rides")
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
    for key in ["NEW", "ACTIVE", "UPDATED", "REMOVED", "REACTIVATED"]:
        print(f"  - {key}: {summary.get(key, 0)}")

def show_active_chrome_processes(context=""):
    #print(f"\n🛠️ Active Chrome Processes {context}:")
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            if proc.info['name'] and ('chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower()):
                mem_mb = (proc.info['memory_info'].rss / 1024 / 1024) if proc.info['memory_info'] else 0
                print(f"  PID {proc.pid} - {proc.info['name']} - {mem_mb:.1f} MB")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def run_scraper_loop(interval=30):
    global scraper_cycle_counter
    login_attempts = 0

    while True:
        try:
            print(f"\n=== Elife Scraper Başlatılıyor: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

            driver = persistent.ensure_login()

            show_active_chrome_processes("(before scraping)")

            scraper = ElifeScraper(driver)
            scraped_ids = scraper.run_scraping_cycle()

            remove_old_removed_entries()
            log_mongo_status("🟢 Sonrası")

            show_active_chrome_processes("(after scraping)")

            if persistent.cleaner:
                persistent.cleaner.manual_clean(force_full_clean=False)

            scraper_cycle_counter += 1
            if scraper_cycle_counter >= 5:
                print("\n💥 5 scraping sonrası FULL CLEAN yapılıyor...")

                if persistent.cleaner:
                    persistent.cleaner.manual_clean(force_full_clean=True)

                print("♻️ FULL CLEAN sonrası yeni oturum açılıyor...")
                persistent.reset_session()
                persistent.ensure_login()

                scraper_cycle_counter = 0

            login_attempts = 0
            print(f"⏱️ {interval} saniye sonra tekrar çalışacak...")
            time.sleep(interval)

        except KeyboardInterrupt:
            print("🛑 Kullanıcı tarafından durduruldu.")
            break
        except Exception as e:
            print(f"\n[ERROR] Scraper çalışırken hata oluştu: {e}")
            traceback.print_exc()
            persistent.reset_session()
            login_attempts += 1
            if login_attempts >= 3:
                print("❌ 3 kez üst üste hata alındı. Döngü durduruluyor.")
                break
            else:
                print("🔁 30 sn sonra yeni login deneniyor...")
                time.sleep(10)

if __name__ == "__main__":
    run_scraper_loop()
