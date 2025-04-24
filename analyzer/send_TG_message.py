from dotenv import load_dotenv
import os
import requests
from datetime import datetime
import pandas as pd
from utils.path_helper import get_data_path

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID_LIST = os.getenv("TELEGRAM_CHAT_IDS", "").split(",")
ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "false").lower() == "true"

def send_telegram_message_with_metadata(message):
    if not ENABLE_TELEGRAM:
        print("🚫 Telegram disabled via .env (ENABLE_TELEGRAM=false)")
        return {
            "telegram_sent": False,
            "analysis": message
        }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    success = False

    for chat_id in CHAT_ID_LIST:
        try:
            response = requests.post(url, data={"chat_id": chat_id.strip(), "text": message})
            if response.status_code == 200:
                print(f"✅ Message sent to chat ID {chat_id}")
                success = True
                log_message(chat_id, message)
            else:
                print(f"❌ Failed: {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")

    return {
        "telegram_sent": success,
        "analysis": message
    }

def log_message(chat_id, message):
    log_path = get_data_path("logs/msg_log.csv")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_entry = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ChatID": chat_id,
        "Message": message
    }

    if not os.path.exists(log_path):
        pd.DataFrame([log_entry]).to_csv(log_path, index=False)
    else:
        df = pd.read_csv(log_path)
        df = pd.concat([df, pd.DataFrame([log_entry])], ignore_index=True)
        df.to_csv(log_path, index=False)
