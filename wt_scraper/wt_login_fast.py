# wt_login_fast.py (FIXED version)
import os
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.browser_helper import get_chrome_binary_path, get_chromedriver_path


class WTAutoLoginFast:
    def __init__(self, headless=False):
        load_dotenv()

        self.gtu = os.getenv("WT_GTU")
        self.email = os.getenv("WT_EMAIL")
        self.password = os.getenv("WT_PASSWORD")

        if not all([self.gtu, self.email, self.password]):
            raise ValueError("❌ Missing WT_GTU, WT_EMAIL or WT_PASSWORD in .env")

        options = uc.ChromeOptions()
        options.add_argument("--lang=tr-TR")
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
        else:
            options.add_argument("--start-maximized")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        chrome_path = get_chrome_binary_path()
        driver_path = get_chromedriver_path()
        if chrome_path:
            options.binary_location = chrome_path

        self.driver = uc.Chrome(
            options=options,
            driver_executable_path=driver_path
        )

        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': """Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"""
        })

    def login(self):
        try:
            print("🌐 Opening login page...")
            self.driver.get("https://wtdriver.world-transfer.com/login")

            # Wait for GTU input
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input#ion-input-0'))
            ).send_keys(self.gtu)

            self.driver.find_element(By.CSS_SELECTOR, 'input#ion-input-1').send_keys(self.email)
            self.driver.find_element(By.CSS_SELECTOR, 'input#ion-input-2').send_keys(self.password)

            WebDriverWait(self.driver, 10).until(
                lambda d: d.find_element(By.CSS_SELECTOR, 'ion-button[type="submit"]').get_attribute("disabled") is None
            )
            self.driver.find_element(By.CSS_SELECTOR, 'ion-button[type="submit"]').click()

            # 🧭 Wait for sidebar to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ion-menu'))
            )

            # 🧾 Click Bookings via JS
            bookings_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//ion-label[contains(.,"Bookings")]/ancestor::ion-item'))
            )
            self.driver.execute_script("arguments[0].click();", bookings_button)

            # ✅ Wait for the booking page to confirm success
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'app-booking-master'))
            )

            print("✅ Login + Navigation to Bookings succeeded.")
            return True

        except Exception as e:
            print(f"❌ Login failed: {e}")
            self.driver.save_screenshot("login_error.png")
            return False

    def get_driver(self):
        return self.driver

    def close(self):
        try:
            self.driver.quit()
        except:
            pass
