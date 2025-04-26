import os
import sys
import pandas as pd
import streamlit as st
from PIL import Image
from datetime import datetime, timedelta

# 📍 PATH AYARLAMASI
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.mongodb_utils import get_mongo_collection

# 📸 LOGO DOSYASI PATH - Düzeltilmiş versiyon
logo_path = os.path.join(os.path.dirname(__file__), "logo.png")

# Logo dosyasının varlığını kontrol et
if not os.path.exists(logo_path):
    st.warning(f"Logo file not found at: {logo_path}")
    image = None
else:
    image = Image.open(logo_path)

# 🧡 Streamlit sayfa ayarları
st.set_page_config(page_title="City AI Dashboard", page_icon="🧡", layout="wide")

# 🏙️ Logo ve Başlık (sadece logo varsa göster)
if image:
    st.image(image, width=120)
st.title("🏙️ CITY AI - Management Dashboard")

# ... (diğer kodlar aynı şekilde devam eder) ...


# 🎨 Custom CSS (Railway tarzı koyu renk tema)
st.markdown("""
    <style>
    body {
        background-color: #0f0f0f;
        color: #e0e0e0;
    }
    .stTabs [role="tablist"] {
        background-color: #1a1a1a;
    }
    .stTabs [role="tab"] {
        color: #e0e0e0;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ff6600;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# 🏙️ Logo ve Başlık
st.image(logo_path, width=120)
st.title("🏙️ CITY AI - Management Dashboard")

# 📦 MongoDB veri çekme fonksiyonları
def load_match_data():
    collection = get_mongo_collection("match_data")
    data = list(collection.find())
    return pd.DataFrame(data)

def load_calendar_tasks():
    collection = get_mongo_collection("calendar_tasks")
    data = list(collection.find())
    return pd.DataFrame(data)

def load_rides_data():
    collection = get_mongo_collection("enriched_rides")
    data = list(collection.find())
    return pd.DataFrame(data)

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

    status_data = []
    now = datetime.utcnow()

    for name, (date_field, db_collection) in collections.items():
        collection = get_mongo_collection(db_collection)
        docs = list(collection.find({}, {date_field: 1}))
        last_update = None
        if docs:
            dates = [doc.get(date_field) for doc in docs if doc.get(date_field)]
            if dates:
                last_update = max(pd.to_datetime(dates))
        count = len(docs)

        if last_update:
            delta = now - last_update
            color = "🟩" if delta <= timedelta(hours=1) else "🟨"
        else:
            color = "❓"

        status_data.append({
            "Collection": name,
            "Document Count": count,
            "Last Update": last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else "Unknown",
            "Status": color
        })

    return pd.DataFrame(status_data)

# 🗂️ 4 sekmeli yapı
tab1, tab2, tab3, tab4 = st.tabs([
    "🚗 Match Data",
    "🗓️ Calendar Tasks",
    "🛻 Rides Data",
    "📈 System Status"
])

# 🚗 Match Data Tab
with tab1:
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
        df_display = df[selected_cols]
        st.dataframe(df_display)
    else:
        st.warning("No Match Data Found.")

# 🗓️ Calendar Tasks Tab
with tab2:
    st.subheader("🗓️ Calendar Tasks")
    df = load_calendar_tasks()
    if not df.empty:
        st.dataframe(df)
    else:
        st.warning("No Calendar Tasks Found.")

# 🛻 Rides Data Tab
with tab3:
    st.subheader("🛻 Rides Data")
    df = load_rides_data()
    if not df.empty:
        st.dataframe(df)
    else:
        st.warning("No Rides Data Found.")

# 📈 System Status Tab
with tab4:
    st.subheader("📈 System Status Overview")
    status_df = load_system_status()
    if not status_df.empty:
        st.dataframe(status_df)
    else:
        st.warning("No System Status Available.")
