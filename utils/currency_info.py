import requests
import xml.etree.ElementTree as ET

def get_eur_try():
    try:
        response = requests.get("https://www.tcmb.gov.tr/kurlar/today.xml", timeout=5)
        root = ET.fromstring(response.content)
        for currency in root.findall("Currency"):
            if currency.get("Kod") == "EUR":
                rate = currency.find("BanknoteSelling").text
                return round(float(rate), 2)
    except Exception as e:
        print(f"⚠️ Döviz kuru alınamadı: {e}")
        return None
