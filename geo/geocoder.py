
from datetime import datetime
from tomtom_testv2 import get_coordinates, format_address_for_search
from utils.mongodb_utils import get_mongo_collection

class MongoGeoCoder:
    def __init__(self):
        self.collection = get_mongo_collection("geo_addresses")

    def is_address_geocoded(self, formatted_address):
        result = self.collection.find_one({"FormattedAddress": formatted_address})
        return result is not None

    def geocode_address(self, address, source='unknown'):
        formatted_address = format_address_for_search(address)
        existing = self.collection.find_one({"FormattedAddress": formatted_address})

        if existing:
            if existing.get("GeocodeStatus") == "FAILED":
                return None, None
            return existing.get("Latitude"), existing.get("Longitude")

        print(f"\n🔍 Geocoding new address from {source}: {address}")
        result = get_coordinates(address, "TR")

        new_entry = {
            'OriginalAddress': address,
            'FormattedAddress': formatted_address,
            'LastUpdated': datetime.now(),
            'Source': source
        }

        if result:
            lat, lon = result
            new_entry.update({
                'Latitude': lat,
                'Longitude': lon,
                'MatchedAddress': address,
                'GeocodeStatus': 'EXACT'
            })
        else:
            new_entry.update({
                'Latitude': None,
                'Longitude': None,
                'GeocodeStatus': 'FAILED'
            })

        self.collection.insert_one(new_entry)
        return new_entry['Latitude'], new_entry['Longitude']

    def process_address_fields(self, record, source='unknown'):
        for field in ['Pickup', 'Dropoff']:
            lat_key = f"{field}_lat"
            lon_key = f"{field}_lon"

            if record.get(field) and (record.get(lat_key) is None or record.get(lon_key) is None):
                lat, lon = self.geocode_address(record[field], source)
                record[lat_key] = lat
                record[lon_key] = lon
        return record

    def process_bulk(self, records, source='unknown'):
        updated = []
        for rec in records:
            updated.append(self.process_address_fields(rec, source))
        return updated
