from utils.mongodb_utils import get_mongo_collection
from datetime import datetime
from geopy.distance import geodesic
from datetime import timedelta


MAX_DISTANCE_KM = 20
MAX_TIME_DIFF_MIN = 240

def fetch_calendar_pairs():
    col = get_mongo_collection("calendar_tasks")
    tasks = list(col.find({
        "API_Status": "needsAction",
        "Status": {"$ne": "REMOVED"},
        "GeoStatus": {"$ne": None},
        "DistanceStatus": {"$ne": None}
    }))

    pairs = {}
    for i, t1 in enumerate(tasks):
        for t2 in tasks[i + 1:]:
            if t1["ID"] == t2["ID"]:
                continue

            dist = geodesic((t1["Dropoff_lat"], t1["Dropoff_lon"]),
                            (t2["Pickup_lat"], t2["Pickup_lon"])).km
            if dist > MAX_DISTANCE_KM:
                continue

            t1_arrival = t1["Transfer_Datetime"] + timedelta(seconds=t1.get("Duration_seconds", 0))
            wait = (t2["Transfer_Datetime"] - t1_arrival).total_seconds() / 60
            if 0 <= wait <= MAX_TIME_DIFF_MIN:
                pairs[t1["ID"]] = t2["Title"]
                break

    return pairs
