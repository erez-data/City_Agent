from datetime import datetime
from tomtom_testv2 import calculate_route, format_duration, format_distance
from utils.mongodb_utils import get_mongo_collection

class MongoDistanceCalculator:
    def __init__(self):
        self.collection = get_mongo_collection("distance_cache")

    def is_cached_or_failed(self, start_lat, start_lon, end_lat, end_lon, source):
        key = {
            'StartLat': start_lat,
            'StartLon': start_lon,
            'EndLat': end_lat,
            'EndLon': end_lon,
            'Source': source
        }
        cached = self.collection.find_one(key)
        if cached:
            if cached.get("Distance_meters") is None:
                return True, None  # failed entry, skip retry
            return True, cached
        return False, None

    def calculate_and_cache(self, start_lat, start_lon, end_lat, end_lon, source):
        if any(x is None for x in [start_lat, start_lon, end_lat, end_lon]):
            return None, None, None, None

        exists, cached_data = self.is_cached_or_failed(start_lat, start_lon, end_lat, end_lon, source)
        if exists:
            if cached_data:
                return (
                    cached_data['Distance_meters'],
                    cached_data['Duration_seconds'],
                    cached_data['Distance_display'],
                    cached_data['Duration_display']
                )
            return None, None, None, None

        print(f"\n🧭 Calculating {source} route between ({start_lat},{start_lon}) → ({end_lat},{end_lon})")
        result = calculate_route(f"{start_lat},{start_lon}", f"{end_lat},{end_lon}")

        new_entry = {
            'StartLat': start_lat,
            'StartLon': start_lon,
            'EndLat': end_lat,
            'EndLon': end_lon,
            'LastUpdated': datetime.now(),
            'Source': source
        }

        if result:
            distance, duration = result
            new_entry.update({
                'Distance_meters': distance,
                'Duration_seconds': duration,
                'Distance_display': format_distance(distance),
                'Duration_display': format_duration(duration)
            })
        else:
            new_entry.update({
                'Distance_meters': None,
                'Duration_seconds': None,
                'Distance_display': None,
                'Duration_display': None
            })

        self.collection.insert_one(new_entry)
        return (
            new_entry['Distance_meters'],
            new_entry['Duration_seconds'],
            new_entry['Distance_display'],
            new_entry['Duration_display']
        )

    def enrich_record(self, record, source):
        if not all(k in record for k in ['Pickup_lat', 'Pickup_lon', 'Dropoff_lat', 'Dropoff_lon']):
            return record

        if record.get('Distance_meters') and record.get('Duration_seconds'):
            return record  # already enriched

        dist, dur, dist_disp, dur_disp = self.calculate_and_cache(
            record['Pickup_lat'], record['Pickup_lon'],
            record['Dropoff_lat'], record['Dropoff_lon'],
            source
        )
        record['Distance_meters'] = dist
        record['Duration_seconds'] = dur
        record['Distance'] = dist_disp
        record['Duration'] = dur_disp
        return record

    def process_bulk(self, records, source):
        enriched = []
        for rec in records:
            enriched.append(self.enrich_record(rec, source))
        return enriched
