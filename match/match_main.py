import time
from datetime import datetime
from pymongo import UpdateOne
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

    rides = list(rides_col.find(ride_filter))
    calendar = list(calendar_col.find(calendar_filter))
    return rides, calendar


def save_match_data(matches):
    match_col = get_mongo_collection("match_data")
    if matches:
        match_col.insert_many(matches)
        print(f"✅ Inserted {len(matches)} new matches.")


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
        rides, calendar = fetch_unmatched_records()

        if not rides and not calendar:
            print("📭 No new rides or calendar tasks to analyze. Sleeping...")
            time.sleep(30)
            continue

        calendar_pairs = fetch_calendar_pairs()

        match_results = matcher.find_matches(rides, calendar)
        flat_results = matcher.flatten_results(match_results)

        for item in flat_results:
            if item["Match_Source"] == "Calendar" and item["Matched_ID"] in calendar_pairs:
                item["CalendarMatchPair"] = calendar_pairs[item["Matched_ID"]]

        ride_ids = [r['ID'] for r in rides]
        matcher.mark_old_matches_outdated(ride_ids)

        save_match_data(flat_results)
        task_ids = [c['ID'] for c in calendar]
        update_processed_flags(ride_ids, task_ids)

        print("🔁 Cycle complete. Sleeping 30s...\n")
        time.sleep(30)


if __name__ == '__main__':
    build_match_runner()
