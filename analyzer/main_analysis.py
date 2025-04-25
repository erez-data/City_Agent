import time
from pymongo import UpdateOne
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from utils.mongodb_utils import get_mongo_collection
from ride_analyzerv2 import RideAnalyzer

load_dotenv()


def fetch_analysis_candidates():
    rides_col = get_mongo_collection("enriched_rides")
    calendar_col = get_mongo_collection("calendar_tasks")
    match_col = get_mongo_collection("match_data")

    ride_filter = {
        "Analyzed": {"$ne": True},
        "MatchAnalyzed": True,
        "Status": {"$ne": "REMOVED"},
        "GeoStatus": {"$ne": None},
        "DistanceStatus": {"$ne": None},
    }

    calendar_filter = {
        "Analyzed": {"$ne": True},
        "MatchAnalyzed": True,
        "API_Status": {"$in": ["needsAction", None]},
        "Status": {"$ne": "REMOVED"},
        "GeoStatus": {"$ne": None},
        "DistanceStatus": {"$ne": None},
    }

    print("\n🔍 Fetching rides data...")
    rides = list(rides_col.find(ride_filter))
    print(f"📊 Found {len(rides)} rides")
    if rides:
        print("First ride ID:", rides[0].get('ID', 'N/A'))

    print("\n📅 Fetching calendar data...")
    calendar = list(calendar_col.find(calendar_filter))
    print(f"📊 Found {len(calendar)} calendar entries")
    if calendar:
        print("First calendar ID:", calendar[0].get('ID', calendar[0].get('ID', 'N/A')))

    print("\n🔄 Fetching match data...")
    matches = list(match_col.find({}))
    print(f"📊 Found {len(matches)} matches")

    return rides, calendar, matches


def update_analysis_flags(rides, calendar, ride_results, calendar_results):
    rides_col = get_mongo_collection("enriched_rides")
    calendar_col = get_mongo_collection("calendar_tasks")

    now = datetime.utcnow()
    ride_ops = []
    calendar_ops = []

    # Debug info
    print(f"\n📝 Preparing to update {len(ride_results)} rides and {len(calendar_results)} calendar entries")

    # Rides updates
    for result in ride_results:
        if not result.get('ID'):
            print(f"⚠️ Missing ID in ride result: {result}")
            continue

        ride_ops.append(UpdateOne(
            {"ID": result["ID"]},
            {"$set": {
                "Analyzed": True,
                "AnalysisDatetime": now,
                "AnalysisResponse": result.get("analysis", ""),
                "TelegramSent": result.get("telegram_sent", False)
            }}
        ))
        print(f"  🚗 Ride update prepared - ID: {result['ID']}")

    # Calendar updates
    for result in calendar_results:
        task_id = result.get("ID", result.get("ID"))
        if not task_id:
            print(f"⚠️ Missing Task_ID/ID in calendar result: {result}")
            continue

        calendar_ops.append(UpdateOne(
            {"$or": [{"ID": task_id}, {"ID": task_id}]},
            {"$set": {
                "Analyzed": True,
                "AnalysisDatetime": now,
                "AnalysisResponse": result.get("analysis", ""),
                "TelegramSent": result.get("telegram_sent", False)
            }}
        ))
        print(f"  📅 Calendar update prepared - ID: {task_id}")

    # Execute updates
    try:
        if ride_ops:
            ride_result = rides_col.bulk_write(ride_ops, ordered=False)
            print(
                f"✅ Rides update result - Matched: {ride_result.matched_count}, Modified: {ride_result.modified_count}")
        else:
            print("ℹ️ No ride updates to perform")

        if calendar_ops:
            calendar_result = calendar_col.bulk_write(calendar_ops, ordered=False)
            print(
                f"✅ Calendar update result - Matched: {calendar_result.matched_count}, Modified: {calendar_result.modified_count}")
        else:
            print("ℹ️ No calendar updates to perform")

    except Exception as e:
        print(f"❌ Database update failed: {str(e)}")
        raise


def run_analysis_cycle():
    print("\n" + "=" * 50)
    print(f"🔁 New analysis cycle started at {datetime.now().isoformat()}")
    print("=" * 50)

    try:
        rides, calendar, matches = fetch_analysis_candidates()

        if not rides and not calendar:
            print("📭 No unanalyzed rides or calendar tasks found")
            time.sleep(30)
            return

        # Create DataFrames with additional checks
        rides_df = pd.DataFrame(rides) if rides else pd.DataFrame()
        calendar_df = pd.DataFrame(calendar) if calendar else pd.DataFrame()
        match_df = pd.DataFrame(matches) if matches else pd.DataFrame()

        if not rides_df.empty:
            print("\n🔍 First ride details:")
            print(f"ID: {rides_df.iloc[0]['ID']}")
            print(f"Pickup: {rides_df.iloc[0]['Pickup']}")
            print(f"Status: {rides_df.iloc[0].get('Status', 'N/A')}")

        analyzer = RideAnalyzer(rides_df, calendar_df, match_df)
        ride_results, calendar_results = analyzer.run_analysis_cycle(return_metadata=True)

        if not ride_results and not calendar_results:
            print("⚠️ No analysis results returned from analyzer")
            return

        update_analysis_flags(rides, calendar, ride_results, calendar_results)

    except Exception as e:
        print(f"\n❌ Critical error in analysis cycle: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔄 Cycle completed. Sleeping for 30 seconds...")
        time.sleep(30)


if __name__ == "__main__":
    while True:
        run_analysis_cycle()