import os
from dotenv import load_dotenv

# .env.client_city dosyasını yükle
load_dotenv(dotenv_path="../.env.client_city")

# CLIENT_BASE doğrudan .env.client_city içinde
client_base = os.getenv("CLIENT_BASE", "BULUNAMADI")

# ANALYSIS_CRITERIA_FILE varsa dosyadan oku, yoksa ANALYSIS_CRITERIA string'ini al
criteria_file = os.getenv("ANALYSIS_CRITERIA_FILE")
if criteria_file and os.path.exists(criteria_file):
    with open(criteria_file, encoding="utf-8") as f:
        criteria_text = f.read()
else:
    criteria_text = os.getenv("ANALYSIS_CRITERIA", "❌ Analiz kriteri bulunamadı.")

# Çıktı verelim
print(f"\n📍 Müşteri Lokasyonu: {client_base}")
print("\n🎯 Analiz Kriterleri (Satır Satır):")
for i, line in enumerate(criteria_text.strip().splitlines(), start=1):
    print(f"{i}. {line.strip()}")
