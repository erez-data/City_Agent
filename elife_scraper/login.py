# login.py - Integrated with full working logic using undetected-chromedriver and popup handling

import os
import time
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from browser_helper import get_chrome_binary_path, get_chromedriver_path

class ElifeAutoLogin:
    def __init__(self, headless=True):
        load_dotenv()
        self.username = os.getenv("ELIFE_USERNAME")
        self.password = os.getenv("ELIFE_PASSWORD")

        if not self.username or not self.password:
            raise ValueError("❌ ELIFE_USERNAME veya ELIFE_PASSWORD .env dosyasında tanımlı değil!")

        options = uc.ChromeOptions()
        options.add_argument("--lang=tr-TR")
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        else:
            options.add_argument("--start-maximized")
            options.add_argument("--disable-notifications")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")

        chrome_path = get_chrome_binary_path()
        driver_path = get_chromedriver_path()

        if chrome_path:
            options.binary_location = chrome_path

        self.driver = uc.Chrome(
            options=options,
            driver_executable_path=driver_path
        )

    def login(self):
        try:
            self.driver.get("https://elifelimo.com/fleet/")
            print("🌐 Siteye erişildi, input alanları bekleniyor...")

            email = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[ref="emailInput"]'))
            )
            email.send_keys(self.username)
            print("📩 Kullanıcı adı girildi")

            password = self.driver.find_element(By.CSS_SELECTOR, 'input[ref="passwordInput"]')
            password.send_keys(self.password)
            print("🔑 Şifre girildi")

            self.driver.find_element(By.CSS_SELECTOR, 'input[ref="agrPolCheckbox"]').click()
            self.driver.find_element(By.CSS_SELECTOR, 'div[ref="submitBtn"]').click()

            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.--p-4.--bg-white'))
            )
            time.sleep(3)
            self.close_all_popups()
            self.final_popup_check()
            print("✅ Giriş başarılı")
            return True

        except Exception as e:
            print(f"❌ Giriş hatası: {e}")
            return False

    def close_all_popups(self):
        try:
            close_btn = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'section.--min-h-\\[4rem\\] i.i-close'))
            )
            close_btn.click()
            print("🛑 Yeni özellik pop-up kapatıldı")
            time.sleep(1)
        except:
            pass

        try:
            close_btn = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'section.modal-wrap i.i-close'))
            )
            close_btn.click()
            print("🛑 Ana ekrana ekle pop-up kapatıldı")
            time.sleep(1)
        except:
            pass

        try:
            notification_close = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.notification, div.alert, div.toast i.i-close, button.close'))
            )
            notification_close.click()
            print("🛑 Bildirim pop-up kapatıldı")
            time.sleep(1)
        except:
            pass

    def final_popup_check(self):
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(1)
        except:
            pass

    def get_driver(self):
        return self.driver

    def close(self):
        if hasattr(self, 'driver') and self.driver:
            self.driver.quit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
