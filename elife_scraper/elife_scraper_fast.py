# elife_scraper_fast.py
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.time_utils import standardize_ride_time
from utils.mongodb_utils import get_mongo_collection


class ElifeScraperFast:
    def __init__(self, driver):
        self.driver = driver
        self.collection = get_mongo_collection("elife_rides")

    # ------------------------------
    # Overlay / modal temizliği
    # ------------------------------
    def _wait_overlay_gone(self, timeout=6):
        end = time.time() + timeout
        while time.time() < end:
            try:
                fullscreens = self.driver.find_elements(
                    By.XPATH,
                    "//*[contains(@class,'fixed') and contains(@class,'top-0') and contains(@class,'left-0') "
                    "and (contains(@class,'w-full') or contains(@class,'w-screen') or contains(@class,'w\\-full') or contains(@class,'w\\-screen')) "
                    "and (contains(@class,'h-full') or contains(@class,'h-screen') or contains(@class,'h\\-full') or contains(@class,'h\\-screen'))]"
                )
            except Exception:
                fullscreens = []

            visible = False
            for fs in fullscreens:
                try:
                    if fs.is_displayed():
                        cls = (fs.get_attribute("class") or "")
                        style = (fs.get_attribute("style") or "")
                        if "pointer-events-none" in cls or "opacity-0" in cls or "opacity: 0" in style:
                            continue
                        visible = True
                        break
                except Exception:
                    continue

            if not visible:
                return

            for sel in ["i.i-close", "i.i-close-1", "[ref='iconRef'].i-close"]:
                try:
                    for icon in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        if icon.is_displayed():
                            try:
                                icon.click()
                            except Exception:
                                try:
                                    self.driver.execute_script("arguments[0].click();", icon)
                                except Exception:
                                    pass
                except Exception:
                    pass

            try:
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
                pass

            time.sleep(0.2)

    # ------------------------------
    # Refresh (i.i-reload)
    # ------------------------------
    def refresh_rides(self):
        try:
            self._wait_overlay_gone(timeout=4)
            wait = WebDriverWait(self.driver, 6)
            try:
                reload_icon = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "i.i-reload")))
            except Exception:
                print("ℹ️ reload icon not found – continue without refresh")
                return

            try:
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "i.i-reload"))).click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", reload_icon)

            print("🔄 Rides refreshed")
            time.sleep(0.8)
        except Exception as e:
            print(f"⚠️ Error refreshing rides: {str(e)}")

    # ------------------------------
    # Yardımcılar
    # ------------------------------
    def _first_displayed(self, css_selector):
        try:
            for e in self.driver.find_elements(By.CSS_SELECTOR, css_selector):
                try:
                    if e.is_displayed():
                        return e
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _focus_element(self, el):
        try:
            self.driver.execute_script(
                "arguments[0].setAttribute('tabindex','0'); arguments[0].focus();",
                el
            )
        except Exception:
            pass

    # ------------------------------
    # Aktivasyon: bilgi satırı + list container
    # ------------------------------
    def _activate_list_area(self):
        """
        1) 'This list is visible to many fleets' satırına tıkla (güvenli alan)
        2) List container'ı (div.flex-1.overflow-auto.p-3) focus'la
        """
        wait = WebDriverWait(self.driver, 8)

        info_xpath = (
            "//*[contains(@class,'text-sm') and contains(@class,'text') "
            "and contains(normalize-space(.), 'This list is visible')]"
        )
        info_div = None
        try:
            info_div = wait.until(EC.presence_of_element_located((By.XPATH, info_xpath)))
        except Exception:
            pass

        if info_div:
            try:
                ActionChains(self.driver).move_to_element(info_div).pause(0.05).click().perform()
            except Exception:
                self.driver.execute_script("arguments[0].click();", info_div)

        container = self._first_displayed("div.flex-1.overflow-auto.p-3") \
            or self._first_displayed("div.--flex-1.--overflow-auto.--p-3")

        if container:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", container)
            except Exception:
                pass
            self._focus_element(container)
            try:
                ActionChains(self.driver).move_to_element(container).pause(0.05).perform()
            except Exception:
                pass

        return container

    # ------------------------------
    # SCROLL: sadece konteynere END gönder (No more items şart!)
    # ------------------------------
    def scroll_to_load_all_rides(self, start_delay=0.0):
        """
        - (ops.) kısa bekleme
        - aktivasyon -> sadece KONTEYNERE END gönder
        - 'No more items' METNİ görülmeden bottom kabul ETME
        - tail sweep max 3; yine metin yoksa stabil dibine geldiysek dur ama REMOVED atla
        """
        if start_delay > 0:
            time.sleep(start_delay)

        bottom_text = False
        try:
            self._wait_overlay_gone(timeout=5)
            container = self._activate_list_area()
            if not container:
                print("❌ List container not found; abort scrolling.")
                return False

            def at_bottom_text():
                """3 kanaldan kontrol: (1) container içinde XPATH (2) container.innerText (3) body.innerText"""
                try:
                    # (1) XPATH (container scope)
                    nodes = container.find_elements(
                        By.XPATH,
                        ".//*[normalize-space(text())='No more items' or "
                        "translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='no more']"
                    )
                    if any(n.is_displayed() for n in nodes):
                        return True
                except Exception:
                    pass
                try:
                    # (2) container.innerText
                    txt = self.driver.execute_script("return (arguments[0].innerText||'').toLowerCase();", container)
                    if "no more items" in txt or "\nno more items" in txt or " no more items" in txt:
                        return True
                    if txt.strip().endswith("no more"):
                        return True
                except Exception:
                    pass
                try:
                    # (3) body.innerText (yedek)
                    btxt = (self.driver.execute_script("return (document.body.innerText||'').toLowerCase();") or "")
                    if "no more items" in btxt or "\nno more items" in btxt:
                        return True
                except Exception:
                    pass
                return False

            def metrics():
                try:
                    top = int(self.driver.execute_script("return arguments[0].scrollTop||0;", container) or 0)
                    sh  = int(self.driver.execute_script("return arguments[0].scrollHeight||0;", container) or 0)
                    ch  = int(self.driver.execute_script("return arguments[0].clientHeight||0;", container) or 0)
                except Exception:
                    top, sh, ch = 0, 0, 0
                try:
                    cc = len(self.driver.find_elements(
                        By.CSS_SELECTOR, "div.p-4.bg-white.rounded-lg, div.--p-4.--bg-white"
                    ))
                except Exception:
                    cc = 0
                return top, sh, ch, cc

            print("⬇️ Container-focused END scrolling started...")
            last_sh = -1
            last_cc = -1
            stable_rounds = 0
            tail_sweep_runs = 0
            max_batches = 240

            for i in range(1, max_batches + 1):
                # sadece container'a END gönder
                try:
                    container.send_keys(Keys.END)
                    container.send_keys(Keys.END)
                except Exception:
                    self._focus_element(container)
                    try:
                        container.send_keys(Keys.END)
                    except Exception:
                        pass

                # her END sonrası 0.5s bekle
                time.sleep(0.5)

                # metin ile doğrula
                if at_bottom_text():
                    print(f"✅ Bottom confirmed by text after {i} END batches.")
                    bottom_text = True
                    break

                # ilerleme / yüklenme takibi
                top, sh, ch, cc = metrics()

                grew = (sh > last_sh) or (cc > last_cc)
                if grew:
                    stable_rounds = 0
                else:
                    stable_rounds += 1
                last_sh = max(last_sh, sh)
                last_cc = max(last_cc, cc)

                # near-bottom + büyüme yoksa tail sweep
                near_bottom = (sh > 0 and ch > 0 and (sh - (top + ch)) <= 6)
                if near_bottom and not grew:
                    if tail_sweep_runs < 3:
                        print("🛡️ Safety tail sweep initiating...")
                        tail_sweep_runs += 1
                        for _ in range(10):
                            try:
                                container.send_keys(Keys.END)
                            except Exception:
                                self._focus_element(container)
                            time.sleep(0.5)
                            if at_bottom_text():
                                print("✅ Bottom confirmed by text during tail sweep.")
                                bottom_text = True
                                break
                        if bottom_text:
                            break
                    else:
                        # tail sweep limiti aşıldı; stabil dibe gelinmiş gibi davran ama REMOVED atlama
                        if stable_rounds >= 8:
                            print("ℹ️ Tail sweep exhausted; stable bottom reached without text — stopping (no REMOVED).")
                            break

            if not bottom_text:
                print("ℹ️ Bottom text not found; stopping scroll without REMOVED marking.")
            print("✅ Scrolling complete.")
        except Exception as e:
            print(f"❌ Error during scrolling: {str(e)}")

        return bottom_text  # YALNIZCA metin görülürse True döner

    # ------------------------------
    # Ride kartlarını oku
    # ------------------------------
    def scrape_rides(self):
        all_seen_ids = []
        new_rides = []
        now = datetime.now()

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "div.p-4.bg-white.rounded-lg, div.--p-4.--bg-white"
                ))
            )
            time.sleep(0.5)

            cards = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.p-4.bg-white.rounded-lg, div.--p-4.--bg-white"
            )
            print(f"🔍 Found {len(cards)} rides to process")

            for card in cards:
                try:
                    # Vehicle
                    vehicle = None
                    for sel in [
                        ".flex.items-baseline.gap-3 .text-sm.font-bold",
                        "div.--flex.--items-baseline.--gap-3 div.--text-sm.--font-bold",
                        ".text-sm.font-bold",
                    ]:
                        try:
                            vehicle = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                            if vehicle:
                                break
                        except Exception:
                            continue
                    vehicle = vehicle or "N/A"

                    # Time
                    raw_time_text = None
                    for sel in [
                        ".shrink-0 .text-sm.font-bold",
                        "div.--shrink-0 div.--text-sm.--font-bold",
                    ]:
                        try:
                            raw_time_text = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                            if raw_time_text:
                                break
                        except Exception:
                            continue
                    raw_time_text = raw_time_text or "N/A"
                    ride_datetime = standardize_ride_time(raw_time_text)

                    # Pickup & Dropoff
                    locs = card.find_elements(
                        By.CSS_SELECTOR,
                        ".line-clamp-1.flex-1.text-sm, .--line-clamp-1.--flex-1.--text-sm.--text-\\[\\#333\\]"
                    )
                    pickup = locs[0].text if len(locs) > 0 else "N/A"
                    dropoff = locs[1].text if len(locs) > 1 else "N/A"

                    # Price
                    price = None
                    for sel in [
                        ".text-base.text-primary",
                        "div.--text-base.--text-primary"
                    ]:
                        try:
                            price = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                            if price:
                                break
                        except Exception:
                            continue
                    price = price or "N/A"

                    # NEW badge
                    is_new = len(card.find_elements(
                        By.CSS_SELECTOR,
                        ".absolute.left-0.top-0, div.--absolute.--left-0.--top-0"
                    )) > 0

                    ride_id = f"elife_{vehicle}_{raw_time_text}_{pickup[:10]}_{dropoff[:10]}".replace(" ", "_")
                    all_seen_ids.append(ride_id)

                    ride_doc = {
                        "ID": ride_id,
                        "Vehicle": vehicle,
                        "Time": raw_time_text,
                        "ride_datetime": ride_datetime,
                        "Pickup": pickup,
                        "Dropoff": dropoff,
                        "Price": price,
                        "IsNewBadge": is_new,
                        "Source": "elife",
                        "LastSeen": now,
                    }

                    existing = self.collection.find_one({"ID": ride_id})
                    is_newish = False

                    if existing:
                        first_seen = existing.get("FirstSeen", now)
                        ride_doc["FirstSeen"] = first_seen

                        if existing.get("Status") == "REMOVED":
                            ride_doc["Status"] = "REACTIVATED"
                            is_newish = True
                        else:
                            age_minutes = (now - first_seen).total_seconds() / 60
                            if existing.get("Status") in ["NEW", "UPDATED", "REACTIVATED"] and age_minutes > 10:
                                ride_doc["Status"] = "ACTIVE"
                            else:
                                ride_doc["Status"] = existing.get("Status", "ACTIVE")

                        self.collection.update_one({"ID": ride_id}, {"$set": ride_doc})
                    else:
                        ride_doc["FirstSeen"] = now
                        ride_doc["Status"] = "NEW"
                        self.collection.insert_one(ride_doc)
                        is_newish = True

                    if is_newish:
                        new_rides.append(ride_doc)

                except Exception as e:
                    print(f"⚠️ Ride parse error: {str(e)[:120]}...")

            print(f"✅ Processed {len(new_rides)} new/reactivated rides")

        except Exception as e:
            print(f"❌ Ride list load error: {str(e)[:160]}...")

        return all_seen_ids, new_rides

    # ------------------------------
    # Tek tur
    # ------------------------------
    def run_scraping_cycle(self):
        print("\n▶ Elife Scraping Cycle Started")
        all_ids, new_ids = [], []
        bottom_confirmed = False
        try:
            self.refresh_rides()
            bottom_confirmed = self.scroll_to_load_all_rides(start_delay=2.0)
            all_ids, new_ids = self.scrape_rides()
        except Exception as e:
            print(f"❌ run_scraping_cycle error: {e}")

        # REMOVED sadece 'No more items' metni doğrulanmışsa
        try:
            if bottom_confirmed and all_ids:
                now = datetime.now()
                for doc in self.collection.find({"Source": "elife"}):
                    if doc["ID"] not in all_ids and doc.get("Status") != "REMOVED":
                        self.collection.update_one(
                            {"ID": doc["ID"]},
                            {"$set": {"Status": "REMOVED", "LastSeen": now}}
                        )
                        print(f"🗑️ Marked as REMOVED: {doc['ID']}")
            else:
                print("⏭️ Bottom not confirmed by text — skipping REMOVED marking.")
        except Exception as e:
            print(f"⚠️ post-process error: {e}")

        return all_ids, new_ids
