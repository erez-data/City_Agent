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
from selenium.webdriver.common.action_chains import ActionChains
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

        # always-on switches
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        chrome_path = get_chrome_binary_path()
        driver_path = get_chromedriver_path()
        if chrome_path:
            options.binary_location = chrome_path

        self.driver = webdriver.Chrome(service=Service(driver_path), options=options)

    # --- helpers ---
    def _set_input_with_events(self, web_el, value: str):
        """Custom <input is="..."> alanlarında framework state'ini güncellemek için input/change event tetikle."""
        self.driver.execute_script(
            """
            const el = arguments[0];
            const val = arguments[1];
            el.focus();
            el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.blur();
            """,
            web_el,
            value,
        )

    def _click_via_js(self, el):
        """Normal click olmazsa JS ile tıkla."""
        self.driver.execute_script("arguments[0].click();", el)

    def _focus_for_keys(self, el):
        """Klavye olaylarını alabilmesi için elemana tabindex verip focusla."""
        try:
            self.driver.execute_script(
                "arguments[0].setAttribute('tabindex','-1'); arguments[0].focus();", el
            )
            return True
        except Exception:
            return False

    def _element_at_viewport_center(self):
        """Viewport merkezindeki elementi döndür (elementFromPoint)."""
        try:
            el = self.driver.execute_script(
                "return document.elementFromPoint(Math.floor(window.innerWidth/2), Math.floor(window.innerHeight/2));"
            )
            return el
        except Exception:
            return None

    def _activate_center_and_send_end(self, end_repeats=7, pause=0.10):
        """
        1) Viewport merkezindeki elementi bul (elementFromPoint)
        2) Actions ile tıkla (gerçek kullanıcı tıklaması)
        3) focus ver (tabindex + focus)
        4) END tuşlarını gönder (hedefe + body'ye)
        """
        target = self._element_at_viewport_center()

        # Yedek: pageContainer1 ya da body
        if target is None:
            try:
                target = self.driver.find_element(By.CSS_SELECTOR, "div.pageContainer.pageContainer1")
            except Exception:
                try:
                    target = self.driver.find_element(By.CSS_SELECTOR, "canvas.canvasImg1")
                except Exception:
                    target = self.driver.find_element(By.TAG_NAME, "body")

        # >>> ACTIVATE MID-PAGE & SEND END <<<
        try:
            ActionChains(self.driver).move_to_element(target).pause(0.05).click().perform()
        except Exception:
            try:
                self._click_via_js(target)
            except Exception:
                pass

        self._focus_for_keys(target)

        # hedef elemana END gönder
        for _ in range(end_repeats):
            try:
                target.send_keys(Keys.END)
            except Exception:
                break
            time.sleep(pause)

        # body'ye de END gönder (garanti)
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            for _ in range(max(2, end_repeats // 2)):
                body.send_keys(Keys.END)
                time.sleep(pause)
        except Exception:
            # son çare global ActionChains
            try:
                actions = ActionChains(self.driver)
                for _ in range(2):
                    actions.send_keys(Keys.END).pause(pause)
                actions.perform()
            except Exception:
                pass

    # --- Popup kapatma yardımcıları ---
    def close_all_popups(self, max_rounds=10, per_click_wait=0.5):
        """
        Popupları i-close ikonlarına tıklayarak kapat.
        Özellikle: <i ref="iconRef" class="... i-close cursor-pointer"> ... </i>
        """
        wait_short = WebDriverWait(self.driver, 3)

        def visible_icons():
            selectors = [
                'i.i-close',
                '[ref="iconRef"].i-close',
                'i.i-close.cursor-pointer',
                '.modal-wrap i.i-close',
                'section.--min-h-\\[4rem\\] i.i-close',
                'div.notification i.i-close',
                'div.alert i.i-close',
                'div.toast i.i-close',
            ]
            uniq = {}
            for sel in selectors:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in els:
                        try:
                            if e.is_displayed():
                                uniq[e._id] = e
                        except Exception:
                            continue
                except Exception:
                    continue
            return list(uniq.values())

        for _ in range(max_rounds):
            icons = visible_icons()
            if not icons:
                break

            clicked_any = False
            for icon in icons:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", icon)
                except Exception:
                    pass

                # TIKLA
                try:
                    icon.click()
                except Exception:
                    try:
                        self._click_via_js(icon)
                    except Exception:
                        continue

                clicked_any = True

                # KAPANDI MI? (staleness veya invisibility)
                try:
                    wait_short.until(EC.staleness_of(icon))
                except Exception:
                    try:
                        wait_short.until(lambda d: not icon.is_displayed())
                    except Exception:
                        pass

                time.sleep(per_click_wait)

            if not clicked_any:
                break

        # En sonda bir ESC
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except Exception:
            pass

    def final_popup_check(self):
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except Exception:
            pass

    # --- AGREEMENT (2s pre-scroll -> mid-page click+END -> 7s -> click -> 5s post-click) ---
    def _accept_supplier_agreement(self, wait_timeout=45):
        """
        Akış:
        1) Agreement görünür olsun
        2) **2 sn bekle** (tam yükleme için)
        3) sayfanın ortasını aktive et + **END** gönder
        4) **7 sn bekle** (buton enable kuralı)
        5) 'Read and accepted the agreement' butonuna tıkla
        6) **5 sn bekle** (sonraki sayfa/popup'ların yüklenmesi için)
        """
        wait = WebDriverWait(self.driver, wait_timeout)

        # 1) Agreement sinyali (başlık veya buton metni)
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(., 'Supplier Agreement') or contains(., 'Read and accepted the agreement')]")
                )
            )
        except Exception:
            pass

        # 2) **SCROLL ÖNCESİ**: 2 saniye bekle (agreement tamamen yüklensin)
        time.sleep(4)

        # 3) ortayı aktive et ve END gönder
        self._activate_center_and_send_end(end_repeats=7, pause=0.10)

        # 4) buton için 7 saniye bekle (enable olması için)
        time.sleep(7)

        # 5) Butonu tıklanabilir olana kadar bekle ve tıkla
        button_xpath = "(//div[contains(@class,'bg-gradient-to-tr') and contains(., 'Read and accepted the agreement')])[last()]"
        try:
            clickable_btn = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
        except Exception:
            # sınıf bazlı yedek (tailwind)
            button_css = (
                "div.bg-gradient-to-tr.from-\\[\\#FF993C\\].to-\\[\\#FE7A1F\\]"
                ".shadow-\\[0px_4px_6px_0px_\\#FE7A1F33\\].py-2.text-center.text-sm"
                ".font-semibold.text-white.rounded-lg.px-6"
            )
            clickable_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, button_css)))

        # görünür alana getir (opsiyonel)
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", clickable_btn)
            time.sleep(0.2)
        except Exception:
            pass

        # >>> AGREEMENT CLICK <<<
        try:
            clickable_btn.click()
        except Exception:
            self._click_via_js(clickable_btn)

        print("✅ Supplier agreement accepted (clicked).")

        # 6) **SCROLL SONRASI**: 5 saniye bekle (sonraki sayfa/popup'lar gelsin)
        time.sleep(10)

    # --- NEW: Ride Pool ikonuna tıkla ---
    def _open_ride_pool(self, wait_timeout=20):
        """
        Popuplar kapandıktan sonra Ride listesine geçmek için
        <i class="icon relative i-tb-ride-pool" ...> ikonuna tıklarız.
        """
        wait = WebDriverWait(self.driver, wait_timeout)

        # Birden fazla olabilir; görünenleri topla
        def find_visible_icons():
            icons = []
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, "i.i-tb-ride-pool")
                for e in els:
                    try:
                        if e.is_displayed():
                            icons.append(e)
                    except Exception:
                        continue
            except Exception:
                pass
            return icons

        icons = wait.until(lambda d: find_visible_icons())
        icon = icons[-1]  # en son görünen (genelde toolbar'daki)

        # Görünür alana getir
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", icon)
            time.sleep(0.1)
        except Exception:
            pass

        # Tıkla (normal -> JS fallback)
        try:
            icon.click()
        except Exception:
            self._click_via_js(icon)

        print("🚕 'Ride Pool' ikonuna tıklandı.")
        # Yüklenme payı
        time.sleep(1)

    def login(self):
        try:
            print("🌐 Opening Elife login page.")
            self.driver.get("https://elifelimo.com/fleet/")

            wait = WebDriverWait(self.driver, 25)

            # Email formu hazır
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[ref="emailForm"]')))

            # --- Email ---
            email = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[ref="emailInput"]')))
            email.click()
            try:
                email.clear()
            except Exception:
                pass
            email.send_keys(self.username)
            self._set_input_with_events(email, self.username)

            # --- Password ---
            pwd = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[ref="passwordInput"]')))
            pwd.click()
            try:
                pwd.clear()
            except Exception:
                pass
            pwd.send_keys(self.password)

            # Submit
            btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[ref="submitBtn"]')))
            btn.click()
            print("🔐 Login form submitted")

            # --- AGREEMENT: 2s -> mid-page click+END -> 7s -> click -> 5s ---
            try:
                self._accept_supplier_agreement(wait_timeout=45)
            except Exception as agr_err:
                print(f"ℹ️ Agreement flow: {agr_err} (devam ediliyor)")

            # Popupları KAPAT
            self.close_all_popups()
            self.final_popup_check()

            # --- NEW STEP: Ride Pool ikonuna tıkla ---
            try:
                self._open_ride_pool(wait_timeout=20)
            except Exception as e:
                print(f"ℹ️ Ride Pool ikonuna tıklanamadı: {e}")

            print("✅ Login successful")
            return True

        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

    def get_driver(self):
        return self.driver

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass
