# elife_login_fast.py
import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.browser_helper import get_chrome_binary_path, get_chromedriver_path

class ElifeAutoLoginFast:
    def __init__(self, headless=True):
        load_dotenv()

        self.username = os.getenv("ELIFE_USERNAME")
        self.password = os.getenv("ELIFE_PASSWORD")
        if not self.username or not self.password:
            raise ValueError("❌ ELIFE_USERNAME or ELIFE_PASSWORD missing in .env")

        options = webdriver.ChromeOptions()
        options.add_argument("--lang=tr-TR")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--start-maximized")
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")

        # 👇 Add these outside the headless block so they apply always
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        chrome_path = get_chrome_binary_path()
        driver_path = get_chromedriver_path()
        if chrome_path:
            options.binary_location = chrome_path

        self.driver = webdriver.Chrome(service=Service(driver_path), options=options)

    def login(self):
        try:
            print("🌐 Opening Elife login page...")
            self.driver.get("https://elifelimo.com/fleet/")

            email = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[ref="emailInput"]'))
            )
            email.send_keys(self.username)
            self.driver.find_element(By.CSS_SELECTOR, 'input[ref="passwordInput"]').send_keys(self.password)
            self.driver.find_element(By.CSS_SELECTOR, 'div[ref="submitBtn"]').click()
            print("🔐 Login form submitted")

            time.sleep(10)  # 🔴 wait for agreement to show

            # ✅ Click agreement button
            buttons = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.--bg-gradient-to-tr.--from-\\[\\#FF993C\\].--to-\\[\\#FE7A1F\\]"
            )
            if buttons:
                agreement_button = buttons[-1]
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", agreement_button)
                time.sleep(1)
                agreement_button.click()
                print("✅ Agreement button clicked")
                time.sleep(5)

            self.close_all_popups()
            time.sleep(3)
            self.final_popup_check()
            print("✅ Login successful")
            return True

        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

    def close_all_popups(self):
        selectors = [
            'section.--min-h-\\[4rem\\] i.i-close',
            'section.modal-wrap i.i-close',
            'div.notification, div.alert, div.toast i.i-close, button.close'
        ]
        for sel in selectors:
            try:
                close_btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
                close_btn.click()
                time.sleep(1)
            except:
                continue

    def final_popup_check(self):
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(1)
        except:
            pass

    def get_driver(self):
        return self.driver

    def close(self):
        try:
            self.driver.quit()
        except:
            pass
