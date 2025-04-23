import requests
import urllib.parse
import re
from math import radians, sin, cos, sqrt, atan2
from fuzzywuzzy import fuzz
from utils.mongodb_utils import get_mongo_collection
from dotenv import load_dotenv
import os
load_dotenv()

API_KEY = os.getenv("TOMTOM_API_KEY")
BASE_URL = 'https://api.tomtom.com'
SEARCH_API_VERSION = '2'
ROUTING_API_VERSION = '1'

# MongoDB'den Turkey location verisini al
locations_collection = get_mongo_collection("turkey_locations")
locations_cursor = locations_collection.find()
locations_data = list(locations_cursor)

# Preprocess lookup
all_place_names = set()
location_index = []

for loc in locations_data:
    for key in ['name', 'ascii_name', 'original_city_search']:
        val = loc.get(key)
        if val:
            lowered = val.lower()
            all_place_names.add(lowered)
            location_index.append((lowered, loc))

COUNTRY_VARIANTS = ['turkey', 'türkiye', 'turkiye', 'turecko', 'turkei', 'turquie', 'turchia', 'tr', 'турция']

def format_address_for_search(address):
    address = str(address).strip()
    address = re.sub(r'\s+', ' ', address)
    keep_chars = ',./()-'
    address = ''.join(c for c in address if c.isalnum() or c in keep_chars or c.isspace())
    return urllib.parse.quote(address)

def extract_address_context(address):
    address_lower = address.lower()
    parts = [p.strip() for p in re.split(r'[\,\n]', address) if p.strip()]

    country = None
    for variant in COUNTRY_VARIANTS:
        if variant in address_lower:
            country = "TR"
            break

    poi_match = re.match(r'^(.*?)(?:,|\()', address)
    poi = poi_match.group(1).strip() if poi_match else None

    town, city = None, None
    for text in parts[::-1]:
        text_lower = text.lower()
        match = next((row for row in all_place_names if row in text_lower), None)
        if match:
            matching = [entry for entry in location_index if entry[0] == match]
            if matching:
                match_row = matching[0][1]
                town = match_row.get('ascii_name')
                city = match_row.get('original_city_search')
                break

    return {'poi': poi, 'country': country, 'city': city, 'town': town}

def extract_location_context(address):
    parts = [p.strip() for p in address.split(',') if p.strip()]
    location_parts = parts[-2:] if len(parts) >= 2 else parts
    return [''.join(c for c in part.lower() if c.isalnum() or c.isspace()) for part in location_parts]

def search_address(address, country_set=None):
    print(f"\n🔎 Original address: {address}")
    cleaned_address = re.sub(r'/', ' ', address)
    formatted_address = format_address_for_search(cleaned_address)
    print(f"🌐 Cleaned & encoded address: {formatted_address}")

    endpoint = f"{BASE_URL}/search/{SEARCH_API_VERSION}/search/{formatted_address}.json"
    ctx = extract_address_context(cleaned_address)

    params = {
        'key': API_KEY,
        'limit': 5,
        'typeahead': True,
        'language': 'en-US',
        'view': 'Unified'
    }
    if ctx['country']:
        params['countrySet'] = ctx['country']

    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        results = response.json().get('results', [])
        if results:
            return results
        if ',' in cleaned_address:
            simplified = ','.join(cleaned_address.split(',')[1:]).strip()
            print(f"🔁 Retrying without POI: {simplified}")
            endpoint = f"{BASE_URL}/search/{SEARCH_API_VERSION}/search/{format_address_for_search(simplified)}.json"
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            return response.json().get('results', [])
        return []
    except requests.exceptions.RequestException as e:
        print(f"⚠️ API Error: {e}")
        return []

def calculate_location_match(input_terms, result_address, result_municipality):
    test_strings = [result_address.lower(), result_municipality.lower()]
    best_score = 0
    for term in input_terms:
        for target in test_strings:
            score = fuzz.token_set_ratio(term, target)
            best_score = max(best_score, score)
    return best_score

def select_best_match(results, original_address):
    if not results:
        return None
    location_terms = extract_location_context(original_address)
    print(f"\n🔍 Found {len(results)} matches for: '{original_address}'")
    print(f"📍 Location context: {', '.join(location_terms)}")

    scored = []
    for i, result in enumerate(results, 1):
        api_score = float(result.get('score', 0))
        result_address = result['address'].get('freeformAddress', '')
        result_municipality = result['address'].get('municipality', '')
        context_score = calculate_location_match(location_terms, result_address, result_municipality)
        total_score = api_score * 0.6 + context_score * 0.4
        scored.append((total_score, i - 1, result))

        print(f"\nOption {i}: \n 📍 {result_address}\n 🏙️ {result_municipality}\n 🔢 API Score: {api_score:.1f}\n 🎯 Context: {context_score:.1f}\n 💯 Total: {total_score:.1f}")

    scored.sort(reverse=True)
    _, _, best = scored[0]
    print(f"\n✅ Best: {best['address'].get('freeformAddress')} → {best['address'].get('municipality', 'N/A')}")
    return best

def get_coordinates(address, country_set=None):
    results = search_address(address, country_set)
    if not results:
        print(f"❌ No results found for: {address}")
        return None
    best = select_best_match(results, address)
    if not best:
        return None
    pos = best['position']
    print(f"🌐 Coordinates: {pos['lat']}, {pos['lon']}")
    return pos['lat'], pos['lon']

def calculate_route(start_coords, end_coords):
    endpoint = f"{BASE_URL}/routing/{ROUTING_API_VERSION}/calculateRoute/{start_coords}:{end_coords}/json"
    params = {
        'key': API_KEY,
        'travelMode': 'car',
        'routeType': 'fastest',
        'traffic': 'true',
        'language': 'en-US'
    }
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        route_data = response.json()
        if not route_data.get('routes'):
            raise ValueError("No route found.")
        summary = route_data['routes'][0]['summary']
        return summary['lengthInMeters'], summary['travelTimeInSeconds']
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Route calculation failed: {e}")
        return None

def format_duration(seconds):
    h, m = divmod(seconds, 3600)
    m = (seconds % 3600) // 60
    return f"{h}h {m}m" if h else f"{m} minutes"

def format_distance(meters):
    return f"{meters / 1000:.1f} km" if meters >= 1000 else f"{meters:.0f} meters"

def calculate_straight_line_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    return 6371000 * 2 * atan2(sqrt(a), sqrt(1 - a))
