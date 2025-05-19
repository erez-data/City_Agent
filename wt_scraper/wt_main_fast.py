# wt_main_fast.py
import time
import traceback
from datetime import datetime, timedelta
from collections import Counter
from wt_login_fast import WTAutoLoginFast
from wt_scv2_fast import WTScraperZoomScrollFast
from utils.mongodb_utils import get_mongo_collection
from send_TG_message import send_telegram_message_with_metadata


class WTSession:
    def __init__(self):
        self.driver = None
        self.session = None
        self.last_login = None

    def login(self):
        self.close()  # clean before starting fresh
        self.session = WTAutoLoginFast(headless=True)
        if not self.session.login():
            raise Exception("❌ WT Login failed")
        self.driver = self.session.get_driver()
        self.last_login = datetime.now()
        print("✅ WT Login completed.")
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


def notify_ride(row):
    dt = row.get("ride_datetime")
    pickup = row.get("Pickup", "-")
    dropoff = row.get("Dropoff", "-")
    vehicle = row.get("Vehicle", "-")
    price = row.get("Price", "-")

    msg = (
        f"**🟢 Yeni WT Ride Tespit Edildi**\n"
        f"📅 <b>{dt}</b>\n"
        f"🚗 <b>{vehicle}</b>\n"
        f"📍 <b>{pickup}</b>\n"
        f"🎯 <b>{dropoff}</b>\n"
        f"💰 <b>{price}</b>"
    )
    send_telegram_message_with_metadata(msg)


def save_to_mongodb(df):
    collection = get_mongo_collection("wt_rides")
    now = datetime.now()

    # Load all existing rides into memory
    existing_docs = {doc["ID"]: doc for doc in collection.find({"Source": "wt"})}
    seen_ids = set()

    new_count = 0

    for _, row in df.iterrows():
        ride_id = row["ID"]
        seen_ids.add(ride_id)

        doc = existing_docs.get(ride_id)
        row_dict = row.to_dict()

        if doc is None:
            # New ride
            row_dict.update({
                "FirstSeen": now,
                "LastSeen": now,
                "Status": "NEW",
                "Source": "wt"
            })
            collection.insert_one(row_dict)
            notify_ride(row_dict)
            new_count += 1
        else:
            # Existing ride → update core fields
            row_dict.update({
                "LastSeen": now,
                "Source": "wt"
            })

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

            # Update status only if it qualifies
            first_seen = doc.get("FirstSeen", now)
            if isinstance(first_seen, str):
                first_seen = datetime.fromisoformat(first_seen)

            age_minutes = (now - first_seen).total_seconds() / 60
            if doc.get("Status") in ["NEW", "UPDATED", "REACTIVATED"] and age_minutes > 10:
                updates["Status"] = "ACTIVE"

            collection.update_one({"ID": ride_id}, {"$set": updates})

    # Mark old entries as REMOVED
    for ride_id, doc in existing_docs.items():
        if ride_id not in seen_ids and doc.get("Status") != "REMOVED":
            collection.update_one({"ID": ride_id}, {"$set": {"Status": "REMOVED", "LastSeen": now}})
            print(f"🗑️ Removed: {ride_id}")

    if new_count:
        print(f"✅ {new_count} yeni kayıt MongoDB'ye eklendi.")
    # else:  # no output if nothing new
    #     print("⏳ Yeni kayıt bulunamadı.")


def run_loop():
    session = WTSession()
    cycle_start = datetime.now()

    while True:
        try:
            # Restart browser every 15 minutes
            if session.should_relogin():
                print("♻️ 15 dakika doldu. Oturum yenileniyor...")
                session.login()
                cycle_start = datetime.now()

            scraper = WTScraperZoomScrollFast(driver=session.driver)
            df, _, parsed = scraper.run_scraping_cycle()

            if not df.empty:
                save_to_mongodb(df)

            time.sleep(5)

        except Exception as e:
            print(f"[ERROR] {e}")
            traceback.print_exc()
            session.close()
            time.sleep(10)


if __name__ == "__main__":
    run_loop()
