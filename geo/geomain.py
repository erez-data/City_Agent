from geocoder import MongoGeoCoder
from distance_calculator import MongoDistanceCalculator
from utils.mongodb_utils import get_mongo_collection
from datetime import datetime
import time
import pandas as pd
import traceback
import os

def is_allowed_region(pickup, dropoff, allowed_regions):
    for region in allowed_regions:
        if region.lower() in (pickup or "").lower() or region.lower() in (dropoff or "").lower():
            return True
    return False

def is_malformed(row):
    return (
        not row.get("Pickup") or
        not row.get("Dropoff") or
        pd.isna(row.get("ride_datetime")) or
        row.get("ride_datetime") == "" or
        row.get("ID", "").strip() == ""
    )

class MainGeoProcessor:
    def __init__(self):
        self.geo = MongoGeoCoder()
        self.dist = MongoDistanceCalculator()
        self.rides_collection = get_mongo_collection("enriched_rides")
        self.calendar_collection = get_mongo_collection("calendar_tasks")
        self.log_collection = get_mongo_collection("geo_logs")

    def fetch_records_to_enrich(self, source_name):
        collection = get_mongo_collection(f"{source_name}_rides") if source_name != "calendar" else get_mongo_collection("calendar_tasks")
        query = {
            "$or": [
                {"GeoStatus": {"$exists": False}},
                {"GeoStatus": ""},
                {"DistanceStatus": {"$exists": False}},
                {"DistanceStatus": ""}
            ]
        }
        return list(collection.find(query)), collection

    def update_flags(self, record):
        geo_status = "Done"
        if record.get('Pickup_lat') is None:
            geo_status = "Pickup Failed"
        elif record.get('Dropoff_lat') is None:
            geo_status = "Dropoff Failed"

        distance_status = "Done" if record.get("Distance_meters") else "Failed"
        return geo_status, distance_status

    def log_event(self, level, message, data=None):
        entry = {
            "timestamp": datetime.utcnow(),
            "level": level,
            "message": message,
            "data": data or {}
        }
        print(f"[{entry['timestamp'].strftime('%H:%M:%S')}] [{level.upper()}] {message} | {entry['data']}")

        if level.lower() in ["error", "critical"]:
            self.log_collection.insert_one(entry)

    def fetch_dataframe_from_mongo(self, collection, query):
        docs = list(collection.find(query))
        return pd.DataFrame(docs) if docs else pd.DataFrame()

    def sanitize_dataframe(self, df):
        df = df.copy()
        # Replace NaT in datetime columns
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].apply(lambda x: x if pd.notnull(x) else None)
        return df

    def update_enriched_rides(self):
        elife_df = self.fetch_dataframe_from_mongo(get_mongo_collection("elife_rides"), {})
        wt_df = self.fetch_dataframe_from_mongo(get_mongo_collection("wt_rides"), {})

        enriched_df = pd.concat([elife_df, wt_df], ignore_index=True)
        enriched_df = enriched_df.dropna(subset=["ID"])
        enriched_df = enriched_df[enriched_df["ID"] != ""]

        # Drop malformed rows entirely
        before_clean = len(enriched_df)
        enriched_df = enriched_df[~enriched_df.apply(is_malformed, axis=1)]
        after_clean = len(enriched_df)
        self.log_event("info", "🧹 Dropped malformed rows", {"dropped": before_clean - after_clean})

        client_name = os.getenv("CLIENT_ID")
        client_config = get_mongo_collection("clients").find_one({"client_name": client_name})

        if client_config and client_config.get("filter", False):
            allowed_regions = client_config.get("filter_regions", [])
            before_count = len(enriched_df)
            enriched_df = enriched_df[
                enriched_df.apply(
                    lambda row: is_allowed_region(row.get("Pickup", ""), row.get("Dropoff", ""), allowed_regions),
                    axis=1
                )
            ]
            after_count = len(enriched_df)
            self.log_event("info", f"🚧 Region filter applied: {before_count - after_count} rides excluded", {
                "total_before": before_count,
                "total_after": after_count,
                "allowed_regions": allowed_regions
            })

        new_df = enriched_df.copy()
        new_df.set_index("ID", inplace=True)

        existing_df = self.fetch_dataframe_from_mongo(self.rides_collection, {})
        if not existing_df.empty:
            existing_df.set_index("ID", inplace=True)

        to_update = new_df.loc[new_df.index.intersection(existing_df.index)]
        to_add = new_df.loc[~new_df.index.isin(existing_df.index)]
        to_remove = existing_df.loc[~existing_df.index.isin(new_df.index)]

        for doc_id, row in to_update.iterrows():
            row_dict = row.to_dict()
            row_dict.pop("_id", None)
            self.rides_collection.update_one({"ID": doc_id}, {"$set": row_dict})

        if not to_add.empty:
            clean_df = self.sanitize_dataframe(to_add.reset_index())
            self.rides_collection.insert_many(clean_df.to_dict(orient="records"))

        for doc_id in to_remove.index:
            self.rides_collection.delete_one({"ID": doc_id})

        self.log_event("info", "🔁 Enriched rides collection synchronized", {
            "added": len(to_add),
            "updated": len(to_update),
            "removed": len(to_remove)
        })

    def run_enrichment_loop(self, interval=30):
        self.log_event("info", "🌍 Enrichment loop started", {"interval_seconds": interval})
        while True:
            try:
                for source in ["elife", "wt", "calendar"]:
                    records, collection = self.fetch_records_to_enrich(source)
                    self.log_event("info", f"🔍 Found {len(records)} to enrich for {source}")
                    for rec in records:
                        try:
                            rec = self.geo.process_address_fields(rec, source=source)
                            rec = self.dist.enrich_record(rec, source=source)
                            rec["GeoStatus"], rec["DistanceStatus"] = self.update_flags(rec)
                            rec.pop("_id", None)
                            collection.update_one({"ID": rec["ID"]}, {"$set": rec})
                            self.log_event("info", f"✅ Enriched {source} ID: {rec['ID']}", {
                                "GeoStatus": rec["GeoStatus"],
                                "DistanceStatus": rec["DistanceStatus"]
                            })
                        except Exception as e:
                            self.log_event("error", f"❌ Failed for {source} ID: {rec.get('ID', 'UNKNOWN')}", {"error": str(e)})

                self.update_enriched_rides()
                time.sleep(interval)

            except Exception as loop_error:
                self.log_event("critical", "🔥 Enrichment loop crashed", {
                    "error": str(loop_error),
                    "trace": traceback.format_exc()
                })
                time.sleep(interval)

if __name__ == "__main__":
    processor = MainGeoProcessor()
    processor.run_enrichment_loop(interval=15)
