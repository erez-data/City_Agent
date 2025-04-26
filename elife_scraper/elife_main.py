import time
from datetime import datetime, timedelta
from login import ElifeAutoLogin
from elife_scraper import ElifeScraper
from utils.mongodb_utils import get_mongo_collection
from collections import Counter
import traceback
import atexit  # ✨ NEW: atexit import edildi, shutdown kontrolü için

class PersistentSession:
    def __init__(self):
        self.session = None
        self.driver = None
        atexit.register(self.cleanup_on_exit)  # ✨ NEW: atexit ile cleanup_on_exit kaydedildi

    def ensure_login(self):
        if not self.session:
            self.session = ElifeAutoLogin(headless=True)
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

    def cleanup_on_exit(self):  # ✨ NEW: Program kapanırken driver'ı güvenli kapatan method
        if self.session:
            print("🛑 [EXIT] Browser kapatılıyor...")
            try:
                self.session.close()
            except Exception as e:
                print(f"⚠️ [EXIT] Driver kapatılırken hata oluştu: {e}")
        else:
            print("ℹ️ [EXIT] Oturum zaten kapalı.")

persistent = PersistentSession()


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
    for key in ["NEW", "ACTIVE", "UPDATED", "REMOVED"]:
        print(f"  - {key}: {summary.get(key, 0)}")

def run_scraper_loop(interval=60):
    print("\n=== Elife Scraper Başlatılıyor ===")
    login_attempts = 0

    while True:
        try:
            log_mongo_status("🟡 Öncesi")

            driver = persistent.ensure_login()
            scraper = ElifeScraper(driver)
            scraped_ids = scraper.run_scraping_cycle()

            remove_old_removed_entries()
            log_mongo_status("🟢 Sonrası")

            login_attempts = 0
            print(f"⏱️ {interval} saniye sonra tekrar denenecek...")
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
                print("🔁 Oturum yenileniyor, 30 sn sonra tekrar deneniyor...")
                time.sleep(30)

if __name__ == "__main__":
    run_scraper_loop()
