from utils.mongodb_utils import get_mongo_collection
from pymongo import UpdateMany

def reset_match_analyzed_flags():
    rides_col = get_mongo_collection("enriched_rides")
    calendar_col = get_mongo_collection("calendar_tasks")

    # Reset enriched rides
    ride_result = rides_col.update_many(
        {"MatchAnalyzed": True},
        {"$set": {"MatchAnalyzed": False}}
    )

    # Reset calendar tasks
    calendar_result = calendar_col.update_many(
        {"MatchAnalyzed": True},
        {"$set": {"MatchAnalyzed": False}}
    )

    print(f"✅ Reset MatchAnalyzed in {ride_result.modified_count} enriched_rides")
    print(f"✅ Reset MatchAnalyzed in {calendar_result.modified_count} calendar_tasks")

if __name__ == "__main__":
    reset_match_analyzed_flags()
