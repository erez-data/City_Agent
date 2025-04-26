from datetime import datetime, timedelta
from geopy.distance import geodesic
import logging
from utils.mongodb_utils import get_mongo_collection

class MatchFinder:
    def __init__(self, distance_service):
        self.distance_service = distance_service
        self.match_col = get_mongo_collection("match_data")
        self.HOME_BASE_COORDS = (36.7659, 28.8028)  # Dalaman
        self.MAX_DISTANCE_KM = 20
        self.MAX_TIME_DIFF_MIN = 240
        self.HOME_RADIUS_KM = 10
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.logged_invalid_rides = set()  # 🆕 invalid kayıtları sadece bir kez logla
        self.logged_invalid_candidates = set()

    def is_near_home(self, coords):
        return geodesic(self.HOME_BASE_COORDS, coords).km <= self.HOME_RADIUS_KM

    def calculate_arrival(self, start_time, duration_seconds):
        if not duration_seconds:
            return start_time
        try:
            return start_time + timedelta(seconds=float(duration_seconds))
        except (TypeError, ValueError):
            return start_time

    def get_real_distance(self, start_coords, end_coords):
        try:
            cached = self.distance_service.is_cached_or_failed(*start_coords, *end_coords, source="match_finder")
            if cached[0]:
                data = cached[1]
                if data:
                    return data['Distance_meters'] / 1000, data['Duration_seconds'] / 60

            result = self.distance_service.calculate_and_cache(*start_coords, *end_coords, source="match_finder")
            if result[0] is None:
                raise ValueError("Distance calculation failed")
            return result[0] / 1000, result[1] / 60
        except Exception:
            return geodesic(start_coords, end_coords).km, 0

    def is_double_utilized(self, arrival_time, next_departure_time, dropoff_coords, next_pickup_coords):
        wait_time = (next_departure_time - arrival_time).total_seconds() / 60
        distance_km = geodesic(dropoff_coords, next_pickup_coords).km
        return 0 <= wait_time <= 90 and distance_km <= self.MAX_DISTANCE_KM

    def determine_direction(self, ride, match, match_source):
        try:
            match_time = match['ride_datetime'] if match_source == 'Rides' else match['Transfer_Datetime']
            match_dropoff = (match['Dropoff_lat'], match['Dropoff_lon'])

            ride_time = ride['ride_datetime']
            ride_pickup = (ride['Pickup_lat'], ride['Pickup_lon'])
            ride_dropoff = (ride['Dropoff_lat'], ride['Dropoff_lon'])

            if not self.is_valid_coords(*ride_pickup) or not self.is_valid_coords(*match_dropoff):
                return "Unknown"

            if self.is_near_home(match_dropoff):
                if geodesic(ride_pickup, match_dropoff).km <= self.MAX_DISTANCE_KM and match_time > ride_time:
                    return "Home Return"
            if not self.is_near_home(ride_pickup) and not self.is_near_home(match_dropoff):
                return "Away Return"
            return "Unknown"
        except Exception:
            return "Unknown"

    def mark_old_matches_outdated(self, ride_ids):
        result = self.match_col.update_many(
            {"Ride_ID": {"$in": ride_ids}, "MatchStatus": "Active"},
            {"$set": {"MatchStatus": "Outdated", "outdated_at": datetime.utcnow()}}
        )
        print(f"🧹 Marked {result.modified_count} old matches as Outdated.")

    def find_matches(self, rides, calendar):
        results = []

        for ride in rides:
            ride_arrival = self.calculate_arrival(ride['ride_datetime'], ride.get("Duration_seconds", 0))
            ride_dropoff_coords = (ride['Dropoff_lat'], ride['Dropoff_lon'])

            if not self.is_valid_coords(*ride_dropoff_coords):
                if ride['ID'] not in self.logged_invalid_rides:
                    print(f"⚠️ [Invalid Ride Dropoff] Ride ID {ride['ID']} atlanıyor.")
                    self.logged_invalid_rides.add(ride['ID'])
                continue

            matches = []

            for candidate in rides:
                if ride['ID'] == candidate['ID']:
                    continue

                candidate_pickup = (candidate['Pickup_lat'], candidate['Pickup_lon'])

                if not self.is_valid_coords(*candidate_pickup):
                    if candidate['ID'] not in self.logged_invalid_candidates:
                        print(f"⚠️ [Invalid Candidate Pickup] Ride ID {candidate['ID']} atlanıyor.")
                        self.logged_invalid_candidates.add(candidate['ID'])
                    continue

                candidate_departure = candidate['ride_datetime']
                candidate_arrival = self.calculate_arrival(candidate_departure, candidate.get("Duration_seconds", 0))
                if candidate_departure < ride_arrival:
                    continue

                dist_km = geodesic(ride_dropoff_coords, candidate_pickup).km
                if dist_km > self.MAX_DISTANCE_KM:
                    continue
                time_diff = (candidate_departure - ride_arrival).total_seconds() / 60
                if time_diff > self.MAX_TIME_DIFF_MIN:
                    continue

                real_dist_km, real_dur_min = self.get_real_distance(ride_dropoff_coords, candidate_pickup)

                matches.append({
                    "Match Source": "Rides",
                    "Matched ID": candidate["ID"],
                    "Match Time": candidate_departure,
                    "Match Arrival": candidate_arrival,
                    "Ride Arrival": ride_arrival,
                    "Match Direction": self.determine_direction(ride, candidate, "Rides"),
                    "Time Difference (min)": round(time_diff),
                    "Geo Distance (km)": round(dist_km, 2),
                    "Real Distance (km)": round(real_dist_km, 2),
                    "Real Duration (min)": round(real_dur_min),
                    "Matched Pickup": candidate["Pickup"],
                    "Matched Dropoff": candidate["Dropoff"],
                    "DoubleUtilized": self.is_double_utilized(
                        ride_arrival, candidate_departure,
                        ride_dropoff_coords, candidate_pickup
                    )
                })

            for task in calendar:
                task_pickup = (task['Pickup_lat'], task['Pickup_lon'])

                if not self.is_valid_coords(*task_pickup):
                    if task['ID'] not in self.logged_invalid_candidates:
                        print(f"⚠️ [Invalid Calendar Pickup] Task ID {task['ID']} atlanıyor.")
                        self.logged_invalid_candidates.add(task['ID'])
                    continue

                task_departure = task['Transfer_Datetime']
                task_arrival = self.calculate_arrival(task_departure, task.get("Duration_seconds", 0))
                if task_departure < ride_arrival:
                    continue

                dist_km = geodesic(ride_dropoff_coords, task_pickup).km
                if dist_km > self.MAX_DISTANCE_KM:
                    continue
                time_diff = (task_departure - ride_arrival).total_seconds() / 60
                if time_diff > self.MAX_TIME_DIFF_MIN:
                    continue

                real_dist_km, real_dur_min = self.get_real_distance(ride_dropoff_coords, task_pickup)

                matches.append({
                    "Match Source": "Calendar",
                    "Matched ID": task["ID"],
                    "Match Time": task_departure,
                    "Match Arrival": task_arrival,
                    "Ride Arrival": ride_arrival,
                    "Match Direction": self.determine_direction(ride, task, "Calendar"),
                    "Time Difference (min)": round(time_diff),
                    "Geo Distance (km)": round(dist_km, 2),
                    "Real Distance (km)": round(real_dist_km, 2),
                    "Real Duration (min)": round(real_dur_min),
                    "Matched Pickup": task["Pickup"],
                    "Matched Dropoff": task["Dropoff"],
                    "DoubleUtilized": self.is_double_utilized(
                        ride_arrival, task_departure,
                        ride_dropoff_coords, task_pickup
                    )
                })

            results.append({
                "Ride ID": ride["ID"],
                "Ride Time": ride["ride_datetime"],
                "Pickup": ride["Pickup"],
                "Dropoff": ride["Dropoff"],
                "Ride Arrival": ride_arrival,
                "Matches": matches
            })

        return results

    @staticmethod
    def is_valid_coords(lat, lon):
        try:
            return (
                lat is not None and lon is not None and
                isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and
                not (lat != lat or lon != lon)  # NaN kontrolü
            )
        except Exception:
            return False

    def flatten_results(self, results):
        output = []
        now = datetime.now()
        for result in results:
            for match in result["Matches"]:
                output.append({
                    "Ride_ID": result["Ride ID"],
                    "Ride_Time": result["Ride Time"],
                    "Ride_Arrival": result["Ride Arrival"],
                    "Pickup": result["Pickup"],
                    "Dropoff": result["Dropoff"],
                    "Match_Source": match["Match Source"],
                    "Matched_ID": match["Matched ID"],
                    "Match_Time": match["Match Time"],
                    "Match_Arrival": match["Match Arrival"],
                    "Match_Direction": match["Match Direction"],
                    "Time_Difference_min": match["Time Difference (min)"],
                    "Geo_Distance_km": match["Geo Distance (km)"],
                    "Real_Distance_km": match["Real Distance (km)"],
                    "Real_Duration_min": match["Real Duration (min)"],
                    "Matched_Pickup": match["Matched Pickup"],
                    "Matched_Dropoff": match["Matched Dropoff"],
                    "DoubleUtilized": match["DoubleUtilized"],
                    "last_updated": now,
                    "MatchStatus": "Active"
                })
        return output
