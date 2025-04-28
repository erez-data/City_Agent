import os
import sys
import pandas as pd
import streamlit as st
from PIL import Image
from datetime import datetime, timedelta

# PATH AYARLAMASI
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.mongodb_utils import get_mongo_collection

# LOGO PATH
logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
if os.path.exists(logo_path):
    image = Image.open(logo_path)
else:
    image = None

# STREAMLIT CONFIG
st.set_page_config(page_title="City AI Dashboard", page_icon="🧡", layout="wide")

# CSS - Responsive ve Modern Tema
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
        background-color: #0d1117;
        color: #c9d1d9;
    }
    .stTabs [role="tablist"] {
        background-color: #161b22;
        border-radius: 12px;
        padding: 0.5rem;
    }
    .stTabs [role="tab"] {
        font-weight: 600;
        color: #8b949e;
        padding: 0.6rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636;
        color: white;
        border-radius: 10px;
        transition: background-color 0.3s ease;
    }
    img {
        max-width: 150px;
        height: auto;
    }
    @media only screen and (max-width: 768px) {
        .stTabs [role="tab"] {
            font-size: 14px;
            padding: 0.4rem 0.8rem;
        }
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# LOGO VE BAŞLIK
st.markdown("<div style='display: flex; align-items: center; gap: 1rem;'>" +
            (f"<img src='data:image/png;base64,{image}' style='height: 80px;'>" if image else "") +
            "<h1 style='margin: 0;'>🏙️ CITY AI - Dashboard</h1></div>", unsafe_allow_html=True)

# DATA LOADERS
def load_match_data():
    return pd.DataFrame(list(get_mongo_collection("match_data").find()))

def load_calendar_tasks():
    return pd.DataFrame(list(get_mongo_collection("calendar_tasks").find()))

def load_rides_data():
    return pd.DataFrame(list(get_mongo_collection("enriched_rides").find()))

def load_system_status():
    collections = {
        "calendar_tasks": ("LastSeen", "calendar_tasks"),
        "distance_cache": ("LastUpdated", "distance_cache"),
        "elife_rides": ("LastSeen", "elife_rides"),
        "enriched_rides": ("LastSeen", "enriched_rides"),
        "geo_addresses": ("LastUpdated", "geo_addresses"),
        "match_data": ("last_updated", "match_data"),
        "wt_rides": ("LastSeen", "wt_rides"),
    }
    now = datetime.utcnow()
    status_data = []
    for name, (date_field, db_collection) in collections.items():
        collection = get_mongo_collection(db_collection)
        docs = list(collection.find({}, {date_field: 1}))
        last_update = None
        if docs:
            dates = [doc.get(date_field) for doc in docs if doc.get(date_field)]
            if dates:
                last_update = max(pd.to_datetime(dates))
        count = len(docs)
        color = "🟩" if last_update and (now - last_update) <= timedelta(hours=1) else "🟨"
        status_data.append({
            "Collection": name,
            "Document Count": count,
            "Last Update": last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else "Unknown",
            "Status": color
        })
    return pd.DataFrame(status_data)

# TABS
match_tab, calendar_tab, rides_tab, system_tab = st.tabs([
    "🚗 Match Data", "🗓️ Calendar Tasks", "🛻 Rides Data", "📈 System Status"])

# MATCH DATA TAB
with match_tab:
    st.subheader("🚗 Match Data Overview")
    df = load_match_data()
    if not df.empty:
        selected_cols = [
            "Pickup", "Dropoff", "Ride_Time", "Ride_Arrival",
            "Match_Source", "Matched_Pickup", "Matched_Dropoff",
            "Match_Time", "Match_Arrival", "Match_Direction",
            "Time_Difference_min", "Real_Distance_km", "Real_Duration_min",
            "DoubleUtilized", "MatchStatus", "CalendarMatchPair"
        ]
        st.data_editor(df[selected_cols], use_container_width=True, height=600)
    else:
        st.warning("No Match Data Found.")

# CALENDAR TASKS TAB
with calendar_tab:
    st.subheader("🗓️ Calendar Tasks")
    df = load_calendar_tasks()
    if not df.empty:
        st.data_editor(df, use_container_width=True, height=600)
    else:
        st.warning("No Calendar Tasks Found.")

# RIDES DATA TAB
with rides_tab:
    st.subheader("🛻 Rides Data")
    df = load_rides_data()
    if not df.empty:
        st.data_editor(df, use_container_width=True, height=600)
    else:
        st.warning("No Rides Data Found.")

# SYSTEM STATUS TAB
with system_tab:
    st.subheader("📈 System Status Overview")
    df = load_system_status()
    if not df.empty:
        st.data_editor(df, use_container_width=True, height=600)
    else:
        st.warning("No System Status Available.")