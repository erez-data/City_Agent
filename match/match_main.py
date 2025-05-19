import time
from datetime import datetime
from pymongo import UpdateOne, InsertOne
from utils.mongodb_utils import get_mongo_collection
from distance_calculator import MongoDistanceCalculator
from match_finder import MatchFinder
from calendar_self_matcher import fetch_calendar_pairs


def fetch_unmatched_records():
    rides_col = get_mongo_collection("enriched_rides")
    calendar_col = get_mongo_collection("calendar_tasks")

    ride_filter = {
        "MatchAnalyzed": {"$ne": True},
        "Status": {"$ne": "REMOVED"},
        "GeoStatus": {"$ne": None},
        "DistanceStatus": {"$ne": None}
    }
    calendar_filter = {
        "MatchAnalyzed": {"$ne": True},
        "API_Status": "needsAction",
        "Status": {"$ne": "REMOVED"},
        "GeoStatus": {"$ne": None},
        "DistanceStatus": {"$ne": None}
    }

    new_rides = list(rides_col.find(ride_filter))
    new_calendar = list(calendar_col.find(calendar_filter))
    return new_rides, new_calendar


def fetch_active_records():
    rides_col = get_mongo_collection("enriched_rides")
    calendar_col = get_mongo_collection("calendar_tasks")

    ride_filter = {
        "Status": {"$ne": "REMOVED"},
        "GeoStatus": {"$ne": None},
        "DistanceStatus": {"$ne": None}
    }
    calendar_filter = {
        "API_Status": "needsAction",
        "Status": {"$ne": "REMOVED"},
        "GeoStatus": {"$ne": None},
        "DistanceStatus": {"$ne": None}
    }

    active_rides = list(rides_col.find(ride_filter))
    active_calendar = list(calendar_col.find(calendar_filter))
    return active_rides, active_calendar


def incremental_save_match_data(new_matches):
    match_col = get_mongo_collection("match_data")
    now = datetime.now()

    ride_ids = list(set(m['Ride_ID'] for m in new_matches))
    existing_matches = list(match_col.find({
        "Ride_ID": {"$in": ride_ids},
        "MatchStatus": "Active"
    }))

    existing_index = {(m["Ride_ID"], m["Matched_ID"], m["Match_Source"]): m for m in existing_matches}

    operations = []
    existing_matched_keys = set(existing_index.keys())
    new_matched_keys = set()

    for match in new_matches:
        key = (match["Ride_ID"], match["Matched_ID"], match["Match_Source"])
        new_matched_keys.add(key)

        if key in existing_index:
            operations.append(UpdateOne(
                {"_id": existing_index[key]["_id"]},
                {"$set": {"last_updated": now}}
            ))
        else:
            operations.append(InsertOne(match))

    to_outdate = existing_matched_keys - new_matched_keys
    if to_outdate:
        for key in to_outdate:
            ride_id, matched_id, match_source = key
            operations.append(UpdateOne(
                {
                    "Ride_ID": ride_id,
                    "Matched_ID": matched_id,
                    "Match_Source": match_source,
                    "MatchStatus": "Active"
                },
                {"$set": {"MatchStatus": "Outdated", "outdated_at": now}}
            ))

    if operations:
        result = match_col.bulk_write(operations)
        print(f"✅ Incremental match update complete: {result.bulk_api_result}")
    else:
        print("ℹ️ No match changes detected.")


def update_processed_flags(ride_ids, task_ids):
    rides_col = get_mongo_collection("enriched_rides")
    calendar_col = get_mongo_collection("calendar_tasks")

    if ride_ids:
        rides_col.bulk_write([UpdateOne({"ID": _id}, {"$set": {"MatchAnalyzed": True}}) for _id in ride_ids])
    if task_ids:
        calendar_col.bulk_write([UpdateOne({"ID": _id}, {"$set": {"MatchAnalyzed": True}}) for _id in task_ids])


def build_match_runner():
    distance_calc = MongoDistanceCalculator()
    matcher = MatchFinder(distance_service=distance_calc)

    while True:
        print(f"\n⏱️ Match cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        new_rides, new_calendar = fetch_unmatched_records()

        if not new_rides and not new_calendar:
            print("📭 No new unmatched records found. Sleeping...")
            time.sleep(30)
            continue

        active_rides, active_calendar = fetch_active_records()
        calendar_pairs = fetch_calendar_pairs()

        # Ana eşleşme burada: aktif rides ve aktif calendar arasında
        match_results = matcher.find_matches(active_rides, active_calendar)

        flat_results = matcher.flatten_results(match_results)

        for item in flat_results:
            if item["Match_Source"] == "Calendar" and item.get("Matched_ID") in calendar_pairs:
                item["CalendarMatchPair"] = calendar_pairs[item["Matched_ID"]]

        incremental_save_match_data(flat_results)

        ride_ids = [r['ID'] for r in new_rides]
        task_ids = [c['ID'] for c in new_calendar]
        update_processed_flags(ride_ids, task_ids)

        print("🔁 Match cycle complete. Sleeping 30s...\n")
        time.sleep(10)


if __name__ == '__main__':
    build_match_runner()