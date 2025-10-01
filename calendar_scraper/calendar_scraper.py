import os
import pickle
import re
from datetime import datetime, timedelta, timezone
import pandas as pd
from dateutil import parser
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pymongo import UpdateOne, ASCENDING
from pymongo.errors import BulkWriteError
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
    def __init__(self, use_incremental=False, incremental_window_hours=24):
        """
        use_incremental=True: Google Tasks'ı updatedMin ile (son N saat) çek.
        Incremental modda REMOVED işaretleme atlanır (tam evren görünmez).
        """
        self.collection = get_mongo_collection("calendar_tasks")
        self.service = self.authenticate_google()
        self.ensure_indexes()
        self.use_incremental = use_incremental
        self.incremental_window_hours = incremental_window_hours

    # --- Infrastructure ---

    def ensure_indexes(self):
        info = self.collection.index_information()

        def has_index(keys, unique=None):
            key_tuple = tuple(keys)
            for _, spec in info.items():
                spec_keys = tuple(spec.get('key', []))
                if spec_keys == key_tuple:
                    if unique is None:
                        return True
                    return bool(spec.get('unique', False)) == bool(unique)
            return False

        id_keys = [("ID", ASCENDING)]
        if has_index(id_keys, unique=True):
            print("ℹ️ ID unique index mevcut.")
        elif has_index(id_keys, unique=False):
            print("⚠️ ID üzerinde unique OLMAYAN index mevcut; otomatik dönüştürmüyorum.")
        else:
            try:
                self.collection.create_index(id_keys, name="idx_unique_id", unique=True)
                print("✅ ID için unique index oluşturuldu.")
            except Exception as e:
                print(f"⚠️ ID unique index oluşturulamadı: {e}")

        for name, keys in [
            ("idx_source_id", [("Source", ASCENDING), ("ID", ASCENDING)]),
            ("idx_source_status", [("Source", ASCENDING), ("Status", ASCENDING)]),
            ("idx_updated", [("Updated", ASCENDING)]),
            ("idx_lastseen", [("LastSeen", ASCENDING)]),
        ]:
            if not has_index(keys):
                try:
                    self.collection.create_index(keys, name=name)
                    print(f"✅ {name} oluşturuldu.")
                except Exception as e:
                    print(f"⚠️ {name} oluşturulamadı: {e}")
            else:
                print(f"ℹ️ {name} zaten var.")

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

    # --- Google Tasks ---

    def fetch_all_tasks(self, updated_min_iso: str | None = None):
        tasks = []
        next_page_token = None
        total_pages = 0

        if updated_min_iso:
            print(f"🔎 Incremental aktif: updatedMin={updated_min_iso}")

        while True:
            try:
                req = self.service.tasks().list(
                    tasklist='@default',
                    pageToken=next_page_token,
                    showCompleted=True,
                    showHidden=True,
                    maxResults=100,
                    updatedMin=updated_min_iso  # None ise client bunu atar
                )
            except TypeError:
                req = self.service.tasks().list(
                    tasklist='@default',
                    pageToken=next_page_token,
                    showCompleted=True,
                    showHidden=True,
                    maxResults=100
                )

            try:
                result = req.execute()
            except HttpError as e:
                if updated_min_iso and e.resp.status in (400, 404):
                    print(f"⚠️ updatedMin kabul edilmedi ({e}). Tam fetch'e düşüyorum.")
                    updated_min_iso = None
                    next_page_token = None
                    tasks.clear()
                    total_pages = 0
                    continue
                raise

            tasks.extend(result.get('items', []))
            next_page_token = result.get('nextPageToken')
            total_pages += 1
            if not next_page_token:
                break

        print(f"🗂️ Google Tasks: {len(tasks)} kayıt, {total_pages} sayfa alındı.")
        return tasks

    # --- Helpers ---

    @staticmethod
    def _to_utc_naive(dt):
        """Any tz-aware/naive dt'yi UTC-naive'e çevirir (Mongo kıyasları için)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # naive -> naive (varsayım: zaten UTC)
            return dt
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    def convert_address(self, address):
        if not address:
            return None
        address = address.strip().upper()
        return ADDRESS_CONVERSION.get(address, f"{address},Muğla")

    def convert_date(self, date_str):
        try:
            raw = parser.isoparse(date_str) if date_str else None
            return self._to_utc_naive(raw)
        except Exception:
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
                full = pd.to_datetime(f"{due_dt.date()} {time_str}")  # pandas UTC-naive üretir
                return full, time_str, start, end
            except Exception:
                return None, time_str, start, end
        return None, None, None, None

    # --- Core scraping cycle ---

    def run_scraping_cycle(self):
        print("\n📅 Calendar scraping cycle started.")
        now_utc = datetime.utcnow()  # UTC-naive

        updated_min_iso = None
        if self.use_incremental:
            updated_min_iso = (now_utc - timedelta(hours=self.incremental_window_hours)).replace(tzinfo=timezone.utc).isoformat()

        tasks = self.fetch_all_tasks(updated_min_iso)

        rows = []
        scraped_ids = []
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
                "API_Status": api_status,
                "Title": title,
                "Notes": notes,
                "Transfer_Datetime": dt,
                "Transfer_Time": ttime,
                "Pickup": pickup,
                "Dropoff": dropoff,
                "Due": due_dt,
                "Updated": updated_dt,
                "FirstSeen": now_utc,
                "LastSeen": now_utc,
                "Task_ID": task_id,
                "Source": "calendar"
            }
            rows.append(row)
            scraped_ids.append(row["ID"])

        print(f"🧰 Hazırlanan satır sayısı: {len(rows)}")

        # Mevcutları getir
        existing_map = {}
        if scraped_ids:
            cursor = self.collection.find(
                {"ID": {"$in": scraped_ids}, "Source": "calendar"},
                {
                    "_id": 0,
                    "ID": 1, "Status": 1, "API_Status": 1, "Title": 1, "Notes": 1,
                    "Transfer_Datetime": 1, "Transfer_Time": 1, "Pickup": 1, "Dropoff": 1,
                    "Due": 1, "Updated": 1, "FirstSeen": 1, "LastSeen": 1, "Task_ID": 1, "Source": 1
                }
            )
            for doc in cursor:
                existing_map[doc["ID"]] = doc
        print(f"📬 DB'den alınan mevcut kayıt sayısı: {len(existing_map)}")

        # Diff + bulk
        ops = []
        changed_count = 0
        unchanged_count = 0
        inserted_like_count = 0

        skip_keys = {"ID", "Source", "FirstSeen", "LastSeen"}

        for row in rows:
            _id = row["ID"]
            existing = existing_map.get(_id)

            set_doc = {}
            set_on_insert = {
                "ID": _id,
                "Source": "calendar",
                "FirstSeen": row["FirstSeen"],
                "Status": "NEW"  # yalnızca insert'te
            }

            if existing is None:
                for k, v in row.items():
                    if k in {"ID", "Source", "FirstSeen", "LastSeen"}:
                        continue
                    set_doc[k] = v
                ops.append(
                    UpdateOne(
                        {"ID": _id},
                        {
                            "$set": set_doc,
                            "$setOnInsert": set_on_insert,
                            "$currentDate": {"LastSeen": True}
                        },
                        upsert=True
                    )
                )
                inserted_like_count += 1
            else:
                has_change = False
                for k, v in row.items():
                    if k in skip_keys:
                        continue
                    prev = existing.get(k)
                    if prev != v:
                        set_doc[k] = v
                        has_change = True

                update_body = {"$currentDate": {"LastSeen": True}}
                if has_change:
                    set_doc["Status"] = "UPDATED"
                    update_body["$set"] = set_doc
                    changed_count += 1
                else:
                    if set_doc:
                        update_body["$set"] = set_doc
                    else:
                        unchanged_count += 1

                ops.append(
                    UpdateOne(
                        {"ID": _id, "Source": "calendar"},
                        update_body,
                        upsert=True
                    )
                )

        if ops:
            try:
                bulk_result = self.collection.bulk_write(ops, ordered=False)
                print(
                    "📦 bulk_write sonucu -> "
                    f"matched: {bulk_result.matched_count}, "
                    f"modified: {bulk_result.modified_count}, "
                    f"upserted: {bulk_result.upserted_count}"
                )
            except BulkWriteError as bwe:
                print(f"❌ Bulk write hatası: {bwe.details}")
            except Exception as e:
                print(f"❌ Bulk write beklenmeyen hata: {e}")

        print(
            f"✅ Diff özeti -> inserted_like:{inserted_like_count}, "
            f"changed:{changed_count}, unchanged:{unchanged_count}"
        )

        if not self.use_incremental:
            removed_res = self.mark_removed(scraped_ids)
            if removed_res:
                print(f"🗑️ REMOVED yapılan kayıt: {removed_res.modified_count}")
        else:
            print("↷ Incremental mod: 'REMOVED' işaretleme atlandı.")

        print(f"🏁 Cycle tamam: görülen {len(scraped_ids)} kayıt.")
        return set(scraped_ids)

    def mark_removed(self, seen_ids):
        if not isinstance(seen_ids, list):
            seen_ids = list(seen_ids)
        try:
            res = self.collection.update_many(
                {
                    "Source": "calendar",
                    "ID": {"$nin": seen_ids},
                    "Status": {"$ne": "REMOVED"}
                },
                {
                    "$set": {"Status": "REMOVED"},
                    "$currentDate": {"LastSeen": True}
                }
            )
            return res
        except Exception as e:
            print(f"⚠️ REMOVED güncellemesi sırasında hata: {e}")
            return None
