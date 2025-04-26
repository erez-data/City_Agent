import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.time_utils import standardize_ride_time
from utils.mongodb_utils import get_mongo_collection

class ElifeScraper:
    def __init__(self, driver):
        self.driver = driver
        self.collection = get_mongo_collection("elife_rides")

    def refresh_rides(self):
        try:
            refresh_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'i.i-reload')))
            refresh_btn.click()
            time.sleep(2)
            print("🔄 Rides refreshed successfully")
        except Exception as e:
            print(f"⚠️ Error refreshing rides: {str(e)}")

    def scroll_to_load_all_rides(self):
        try:
            scroll_div = self.driver.find_element(By.CSS_SELECTOR, "div.--flex-1.--overflow-auto.--p-3")
            max_scrolls = 20
            print("⬇️ Smart scrolling initiated...")
            self.driver.execute_script("window.focus();")

            for i in range(max_scrolls):
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_div)
                print(f"  ↳ Scroll {i+1}/{max_scrolls}")
                time.sleep(0.3)
                try:
                    no_more_element = self.driver.find_element(By.XPATH, "//div[text()='No more']")
                    if no_more_element.is_displayed():
                        print(f"✅ 'No more' detected after {i + 1} scrolls.")
                        break
                except:
                    continue

            print("✅ Scrolling complete.")
        except Exception as e:
            print(f"❌ Error during scrolling: {str(e)}")

    def scrape_rides(self):
        rides = []
        now = datetime.now()

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.--p-4.--bg-white')))

            ride_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div.--p-4.--bg-white')
            print(f"🔍 Found {len(ride_elements)} rides to process")

            for ride in ride_elements:
                try:
                    vehicle = ride.find_element(
                        By.CSS_SELECTOR,
                        'div.--flex.--items-baseline.--gap-3 div.--text-sm.--font-bold'
                    ).text

                    time_element = ride.find_element(
                        By.CSS_SELECTOR,
                        'div.--shrink-0 div.--text-sm.--font-bold'
                    )
                    raw_time_text = time_element.text.strip()
                    ride_datetime = standardize_ride_time(raw_time_text)

                    locations = ride.find_elements(
                        By.CSS_SELECTOR,
                        'div.--line-clamp-1.--flex-1.--text-sm.--text-\[\#333\]'
                    )
                    pickup = locations[0].text if len(locations) > 0 else "N/A"
                    dropoff = locations[1].text if len(locations) > 1 else "N/A"

                    price = ride.find_element(
                        By.CSS_SELECTOR,
                        'div.--text-base.--text-primary'
                    ).text.strip()

                    is_new = len(ride.find_elements(
                        By.CSS_SELECTOR,
                        'div.--absolute.--left-0.--top-0'
                    )) > 0

                    ride_id = f"elife_{vehicle}_{raw_time_text}_{pickup[:10]}_{dropoff[:10]}".replace(" ", "_")

                    ride_data = {
                        'ID': ride_id,
                        'Vehicle': vehicle,
                        'Time': raw_time_text,
                        'ride_datetime': ride_datetime,
                        'Pickup': pickup,
                        'Dropoff': dropoff,
                        'Price': price,
                        'IsNewBadge': is_new,
                        'Source': 'elife',
                        'LastSeen': now
                    }

                    existing = self.collection.find_one({"ID": ride_id})
                    if existing:
                        update_data = ride_data.copy()
                        update_data["FirstSeen"] = existing.get("FirstSeen", now)

                        age_minutes = (now - update_data["FirstSeen"]).total_seconds() / 60
                        if existing.get("Status") in ["NEW", "UPDATED"] and age_minutes > 10:
                            update_data["Status"] = "ACTIVE"
                        else:
                            update_data["Status"] = existing.get("Status", "NEW")

                        self.collection.update_one({"ID": ride_id}, {"$set": update_data})
                    else:
                        ride_data["FirstSeen"] = now
                        ride_data["Status"] = "NEW"
                        self.collection.insert_one(ride_data)

                    rides.append(ride_id)

                except Exception as e:
                    print(f"⚠️ Ride parse error: {str(e)[:100]}...")

            print(f"✅ Successfully processed {len(rides)} rides")

        except Exception as e:
            print(f"❌ Ride list load error: {str(e)[:100]}...")

        return rides

    def run_scraping_cycle(self):
        print("\n▶ Elife Scraping Cycle Started")
        self.refresh_rides()
        self.scroll_to_load_all_rides()
        scraped_ids = self.scrape_rides()

        now = datetime.now()
        if scraped_ids:
            for doc in self.collection.find({"Source": "elife"}):
                if doc["ID"] not in scraped_ids and doc.get("Status") != "REMOVED":
                    self.collection.update_one({"ID": doc["ID"]}, {"$set": {"Status": "REMOVED", "LastSeen": now}})
                    print(f"🗑️ Marked as REMOVED: {doc['ID']}")
        return scraped_ids