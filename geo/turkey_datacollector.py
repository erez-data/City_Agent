import requests
import pandas as pd
import os
import time
from utils.mongodb_utils import get_mongo_collection

# Geonames API Configuration
GEONAMES_USERNAME = 'eyupcity'
BASE_URL = 'http://api.geonames.org/searchJSON'
CITIES = ['Muğla', 'Antalya', 'Aydın', 'İzmir', 'Denizli', 'Burdur']


def fetch_data(city_name, feature_class=None, feature_code=None, start_row=0):
    params = {
        'q': city_name,
        'country': 'TR',
        'maxRows': 1000,
        'startRow': start_row,
        'username': GEONAMES_USERNAME,
        'style': 'full'
    }

    if feature_class:
        params['featureClass'] = feature_class
    if feature_code:
        params['featureCode'] = feature_code

    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        return response.json().get('geonames', [])
    except Exception as e:
        print(f"❌ Error fetching {city_name}: {str(e)}")
        return []


def get_all_records(city_name):
    all_records = []

    for fetch_mode in [('P', None), (None, 'AIRP')]:
        start_row = 0
        while True:
            records = fetch_data(city_name, feature_class=fetch_mode[0], feature_code=fetch_mode[1], start_row=start_row)
            all_records.extend(records)
            if len(records) < 1000:
                break
            start_row += 1000
            time.sleep(1)

    return all_records


def process_and_upload():
    print("\n📍 Starting Turkey location collection and MongoDB upload...")
    mongo_collection = get_mongo_collection("turkey_locations")
    mongo_collection.delete_many({})  # Clear old records (optional)
    total_inserted = 0

    for city in CITIES:
        print(f"🌆 Processing: {city}...")
        locations = get_all_records(city)
        structured = []

        for loc in locations:
            structured.append({
                'name': loc.get('name'),
                'ascii_name': loc.get('asciiName'),
                'latitude': loc.get('lat'),
                'longitude': loc.get('lng'),
                'feature_class': loc.get('fcl'),
                'feature_code': loc.get('fcode'),
                'admin1': loc.get('adminName1'),
                'admin2': loc.get('adminName2'),
                'admin3': loc.get('adminName3'),
                'population': loc.get('population'),
                'elevation': loc.get('elevation'),
                'timezone': loc.get('timezone'),
                'original_city_search': city,
                'record_type': 'airport' if loc.get('fcode') == 'AIRP' else 'populated_place'
            })

        if structured:
            mongo_collection.insert_many(structured)
            print(f"✅ Inserted {len(structured)} records for {city}")
            total_inserted += len(structured)

    print(f"\n✅ Done. Total inserted: {total_inserted} records")


if __name__ == "__main__":
    process_and_upload()
