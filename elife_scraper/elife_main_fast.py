# elife_main_fast.py
import time
import traceback
from datetime import datetime, timedelta
from elife_login_fast import ElifeAutoLoginFast
from elife_scraper_fast import ElifeScraperFast
from send_TG_message import send_telegram_message_with_metadata
from utils.mongodb_utils import get_mongo_collection

class ElifeSession:
    def __init__(self):
        self.driver = None
        self.session = None
        self.last_login = None

    def login(self):
        self.close()
        self.session = ElifeAutoLoginFast(headless=True)
        if not self.session.login():
            raise Exception("❌ Elife login failed")
        self.driver = self.session.get_driver()
        self.last_login = datetime.now()
        print("✅ Elife login successful")
        return self.driver

    def should_relogin(self):
        return not self.last_login or (datetime.now() - self.last_login) > timedelta(minutes=15)

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass
        self.driver = None
        self.session = None


def notify_elife_ride(ride):
    msg = (
        f"**🟦 Elife VIP Transfer Tespit Edildi** ✈️🚗\n"
        f"- 📍 Rota: <b>{ride.get('Pickup')} → {ride.get('Dropoff')}</b>\n"
        f"- ⏰ Zaman: <b>{ride.get('ride_datetime')}</b>\n"
        f"- 💰 Ücret: <b>{ride.get('Price')}</b>\n"
        f"- 🚗 Araç: <b>{ride.get('Vehicle')}</b>"
    )
    send_telegram_message_with_metadata(msg)


def update_elife_ride_statuses(seen_ids):
    collection = get_mongo_collection("elife_rides")
    now = datetime.now()

    for doc in collection.find({"Source": "elife"}):
        ride_id = doc["ID"]
        if ride_id not in seen_ids and doc.get("Status") != "REMOVED":
            collection.update_one(
                {"ID": ride_id},
                {"$set": {"Status": "REMOVED", "LastSeen": now}}
            )
            print(f"🗑️ REMOVED: {ride_id}")


def run_loop():
    session = ElifeSession()
    last_scrape = datetime.now() - timedelta(seconds=30)

    while True:
        try:
            if session.should_relogin():
                print("♻️ 15 dakika doldu, tekrar login olunuyor...version fast 1.0")
                session.login()

            if (datetime.now() - last_scrape).total_seconds() >= 20:
                scraper = ElifeScraperFast(session.driver)
                all_seen_ids, new_rides = scraper.run_scraping_cycle()

                for ride in new_rides:
                    if ride.get("Status") == "NEW":
                        notify_elife_ride(ride)

                update_elife_ride_statuses(all_seen_ids)
                last_scrape = datetime.now()

            time.sleep(1)

        except Exception as e:
            print(f"[ERROR] {e}")
            traceback.print_exc()
            session.close()
            time.sleep(10)


if __name__ == "__main__":
    run_loop()
