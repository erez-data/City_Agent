
import os
import time
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.driver_utils import focus_driver
from utils.browser_helper import get_chrome_binary_path, get_chromedriver_path

class WTAutoLogin:
    def __init__(self, headless=False):
        load_dotenv()

        self.gtu = os.getenv("WT_GTU")
        self.email = os.getenv("WT_EMAIL")
        self.password = os.getenv("WT_PASSWORD")

        if not all([self.gtu, self.email, self.password]):
            raise ValueError("❌ .env file missing WT_GTU, WT_EMAIL or WT_PASSWORD")

        options = uc.ChromeOptions()
        # ✅ Zorunlu dil ayarı
        options.add_argument("--lang=tr-TR")
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
        else:
            options.add_argument("--start-maximized")

        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-infobars")

        chrome_path = get_chrome_binary_path()
        driver_path = get_chromedriver_path()

        if chrome_path:
            options.binary_location = chrome_path

        self.driver = uc.Chrome(
            options=options,
            driver_executable_path=driver_path
        )


        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

    def login(self):
        try:
            print("🌐 Navigating to login page...")
            self.driver.get("https://wtdriver.world-transfer.com/login")
            time.sleep(3)

            print("🧾 Filling form...")
            gtu_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input#ion-input-0'))
            )
            gtu_input.clear()
            gtu_input.send_keys(self.gtu)

            email_input = self.driver.find_element(By.CSS_SELECTOR, 'input#ion-input-1')
            email_input.clear()
            email_input.send_keys(self.email)

            password_input = self.driver.find_element(By.CSS_SELECTOR, 'input#ion-input-2')
            password_input.clear()
            password_input.send_keys(self.password)

            print("🔒 Submitting login...")
            WebDriverWait(self.driver, 10).until(
                lambda d: d.find_element(
                    By.CSS_SELECTOR, 'ion-button[type="submit"]'
                ).get_attribute("disabled") is None
            )
            login_button = self.driver.find_element(By.CSS_SELECTOR, 'ion-button[type="submit"]')
            self.driver.execute_script("arguments[0].click();", login_button)

            print("⏳ Verifying login success...")
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ion-menu-button'))
            )
            time.sleep(2)
            return self.click_bookings()

        except Exception as e:
            print(f"❌ Login error: {e}")
            self.driver.save_screenshot("error.png")
            return False

    def click_bookings(self):
        """Clicks the Bookings menu item after successful login"""
        try:
            # Wait for menu to be present
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ion-menu'))
            )

            # Find Bookings item by its text
            bookings_xpath = '//ion-label[contains(., "Bookings")]/ancestor::ion-item'
            bookings_item = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, bookings_xpath))
            )

            # Click using JavaScript
            self.driver.execute_script("arguments[0].click();", bookings_item)
            time.sleep(2)  # Wait for page load

            # Verify we're on Bookings page
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'app-booking-master')))

            print("Successfully navigated to Bookings page")
            return True

        except Exception as e:
            print(f"Error navigating to Bookings: {str(e)}")
            self.driver.save_screenshot("bookings_error.png")
            return False

    def get_driver(self):
        return self.driver

    def close(self):
        if hasattr(self, 'driver') and self.driver:
            self.driver.quit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Optional standalone test
if __name__ == "__main__":
    with WTAutoLogin(headless=False) as bot:
        if bot.login():
            print("✅ WT Login and navigation success.")
        else:
            print("❌ WT Login failed.")
