# wt_scraper.py - Final Version: Includes zoom out, tab switching, scroll, and page source parsing

import os
import re
import time
import pandas as pd
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

def clean_price_text(label_text):
    return re.sub(r"\s*\(.*?\)", "", label_text.replace("\xa0", " ")).strip()

class WTScraperZoomScroll:
    def __init__(self, driver, csv_path=None):
        self.driver = driver
        self.csv_path = csv_path
        self.data_dir = "cache"
        self.cache_file = os.path.join(self.data_dir, "page_source.txt")
        os.makedirs(self.data_dir, exist_ok=True)

    def wait_for_cards(self):
        print("\n⏳ Waiting for booking cards to appear...")
        WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "app-booking-master ion-card"))
        )
        time.sleep(2)

    def apply_zoom_out(self):
        print("🔍 Applying maximum browser zoom-out...")
        self.driver.execute_script("document.body.style.zoom='0.3'")
        time.sleep(1)

    def tab_and_switch_focus(self):
        print("🔀 Switching to 'Transfer Documents' tab and back to refresh UI...")
        try:
            transfer_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//ion-item[@routerlink='/transfer-documents']"))
            )
            transfer_button.click()
            time.sleep(2)

            booking_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//ion-item[@routerlink='/booking-master']"))
            )
            booking_button.click()
            time.sleep(12)

            print("🧩 Sending 25 TABs to focus booking list...")
            for _ in range(40):
                ActionChains(self.driver).send_keys(Keys.TAB).perform()
                time.sleep(0.1)
        except Exception as e:
            print(f"[WARN] Tab switching failed: {e}")

    def scroll_to_bottom(self, max_scrolls=200):
        print("⬇️ Scrolling to bottom using ARROW_DOWN...")
        for i in range(max_scrolls):
            ActionChains(self.driver).send_keys(Keys.ARROW_DOWN).perform()
            time.sleep(0.03)

    def cache_page_source(self):
        print("💾 Caching page source...")
        html = self.driver.page_source
        with open(self.cache_file, "w", encoding="utf-8") as f:
            f.write(html)

    def cleanup_cache(self):
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)

    def parse_cached_page(self):
        print("🔍 Parsing cached page source...")
        with open(self.cache_file, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("ion-card")
        print(f"🔎 Found {len(cards)} cards in cached HTML")

        parsed = []
        for card in cards:
            try:
                bolds = card.find_all("b")
                bold_texts = [b.get_text(strip=True) for b in bolds if b.get_text(strip=True)]
                date_pattern = r"(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})"
                time_pattern = r"(\d{1,2}:\d{2}(?:\s?[APap][Mm])?)"

                date = next((t for t in bold_texts if re.match(date_pattern, t)), None)
                time_ = next((t for t in bold_texts if re.match(time_pattern, t)), None)
                others = [t for t in bold_texts if t not in [date, time_]]
                pickup = others[0] if len(others) > 0 else ""
                dropoff = others[1] if len(others) > 1 else ""

                vehicle = "Unknown"
                price = ""

                for icon in card.select("ion-icon"):
                    try:
                        icon_src = icon.get("src") or ""
                        label = icon.find_next("ion-label")
                        label_text = label.get_text(strip=True)
                        if "car-side" in icon_src:
                            vehicle = label_text
                        elif "money" in icon_src and "€" in label_text:
                            price = clean_price_text(label_text)
                    except:
                        continue

                if not (date and time_ and pickup and dropoff and vehicle and price):
                    continue

                ride_dt = datetime.strptime(f"{date} {time_}", "%d.%m.%Y %H:%M")
                ride_id = (
                    f"wt_{vehicle}_{ride_dt.strftime('%Y-%m-%d_%H:%M:%S')}_{pickup[:10]}_{dropoff[:10]}"
                ).replace(" ", "_")

                parsed.append({
                    "ID": ride_id,
                    "Vehicle": vehicle,
                    "Time": ride_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "ride_datetime": ride_dt,
                    "Pickup": pickup,
                    "Dropoff": dropoff,
                    "Price": price,
                    "IsNewBadge": False,
                    "FirstSeen": datetime.now(),
                    "LastSeen": datetime.now(),
                    "Status": "NEW",
                    "Source": "wt"
                })
            except Exception as e:
                print(f"[WARN] Failed to parse a card: {e}")

        return parsed

    def run_scraping_cycle(self):
        print("\n▶ WT Scraping Cycle Started")
        self.wait_for_cards()
        self.apply_zoom_out()
        self.tab_and_switch_focus()
        self.scroll_to_bottom()
        self.cache_page_source()
        rides = self.parse_cached_page()
        self.cleanup_cache()

        df = pd.DataFrame(rides)
        return df, len(rides), len(rides)
