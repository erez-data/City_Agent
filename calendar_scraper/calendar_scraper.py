import os
import pickle
import re
from datetime import datetime, timedelta
import pandas as pd
from dateutil import parser
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from utils.mongodb_utils import get_mongo_collection

SCOPES = ['https://www.googleapis.com/auth/tasks.readonly']
ADDRESS_CONVERSION = {
    'DALAMAN': 'Dalaman Airport,Muğla',
    'FETHİYE': 'Fethiye,Muğla',
    'MARMARİS': 'Marmaris,Muğla',
    'ÖLÜDENİZ': 'Ölüdeniz,Fethiye,Muğla',
    'ÇALIŞ': 'Çalış,Fethiye,Muğla',
    'ÇİFTLİK': 'Çiftlik,Fethiye,Muğla',
    'SARIGERME': 'Sarıgerme,Muğla',
    'GÖCEK': 'Göcek,Fethiye,Muğla',
    'DALYAN': 'Dalyan,Muğla',
    'LYKİA': 'Lykia,Fethiye,Muğla',
    'OVACIK': 'Ovacık,Fethiye,Muğla',
    'KALKAN': 'Kalkan,Antalya',
    'KAŞ': 'Kaş,Antalya',
    'YANIKLAR': 'Yanıklar,Fethiye,Muğla',
    'ADAKÖY': 'Adaköy,Marmaris,Muğla',
    'DALAMAN DALAMAN': 'Dalaman Airport,Muğla',
    'ÇİFTLİK,FETHİYE': 'Çiftlik,Fethiye,Muğla',
    'D MARIS': 'Marmaris,Muğla'
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(SCRIPT_DIR, 'token.pickle')

class CalendarScraper:
    def __init__(self):
        self.collection = get_mongo_collection("calendar_tasks")
        self.service = self.authenticate_google()

    def authenticate_google(self):
        creds = None
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_PATH, 'wb') as token:
                pickle.dump(creds, token)

        return build('tasks', 'v1', credentials=creds)

    def fetch_all_tasks(self):
        tasks = []
        next_page_token = None
        while True:
            result = self.service.tasks().list(
                tasklist='@default',
                pageToken=next_page_token,
                showCompleted=True,
                showHidden=True
            ).execute()
            tasks.extend(result.get('items', []))
            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break
        return tasks

    def convert_address(self, address):
        if not address:
            return None
        address = address.strip().upper()
        return ADDRESS_CONVERSION.get(address, f"{address},Muğla")

    def convert_date(self, date_str):
        try:
            return parser.isoparse(date_str)
        except:
            return None

    def extract_transfer_info(self, title, due_dt):
        if not title or not due_dt:
            return None, None, None, None
        match = re.match(r"(\d{1,2}:\d{2})\s+([^\s]+)\s+(.+)", title)
        if match:
            time_str = match.group(1)
            start = match.group(2)
            end = match.group(3)
            try:
                full = pd.to_datetime(f"{due_dt.date()} {time_str}")
                return full, time_str, start, end
            except:
                return None, time_str, start, end
        return None, None, None, None

    def run_scraping_cycle(self):
        print("\n📅 Calendar scraping cycle started...")
        now = datetime.now()
        task_data = []
        tasks = self.fetch_all_tasks()
        scraped_ids = set()

        for task in tasks:
            task_id = task.get("id")
            title = task.get("title", "")
            notes = task.get("notes", "")
            due_dt = self.convert_date(task.get("due"))
            updated_dt = self.convert_date(task.get("updated"))
            api_status = task.get("status", "needsAction")

            dt, ttime, pickup, dropoff = self.extract_transfer_info(title, due_dt)
            pickup = self.convert_address(pickup)
            dropoff = self.convert_address(dropoff)

            row = {
                "ID": f"TASK_{task_id}",
                "Status": "NEW",
                "API_Status": api_status,
                "Title": title,
                "Notes": notes,
                "Transfer_Datetime": dt,
                "Transfer_Time": ttime,
                "Pickup": pickup,
                "Dropoff": dropoff,
                "Due": due_dt,
                "Updated": updated_dt,
                "FirstSeen": now,
                "LastSeen": now,
                "Task_ID": task_id,
                "Source": "calendar"
            }

            scraped_ids.add(row["ID"])

            existing = self.collection.find_one({"ID": row["ID"]})
            if existing:
                row["FirstSeen"] = existing.get("FirstSeen", now)
                age_min = (now - row["FirstSeen"]).total_seconds() / 60
                row["Status"] = "ACTIVE" if age_min > 10 else existing.get("Status", "NEW")
                self.collection.update_one({"ID": row["ID"]}, {"$set": row})
            else:
                self.collection.insert_one(row)

        print(f"✅ Processed {len(scraped_ids)} calendar tasks")

        for doc in self.collection.find({"Source": "calendar"}):
            if doc["ID"] not in scraped_ids and doc.get("Status") != "REMOVED":
                self.collection.update_one({"ID": doc["ID"]}, {"$set": {"Status": "REMOVED", "LastSeen": now}})
                print(f"🗑️ Marked as REMOVED: {doc['ID']}")

        return scraped_ids
