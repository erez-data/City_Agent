# 📦 streamlit_app.py (FINAL CLEAN VERSION)

import os
import sys
import pandas as pd
import streamlit as st
from PIL import Image
from datetime import datetime, timedelta
from match_card_renderer import render_match_cards
from calendar_view_renderer import  render_calendar_page



# 🔧 Utility to convert image to base64
import base64
from io import BytesIO

def image_to_base64(img):
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

# 📍 PATH Settings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.mongodb_utils import get_mongo_collection
from ai_chat_helper import build_ask_ai_tab  # 🚀 Importing new AI module

# 📸 LOGO Settings
logo_path = os.path.join(os.path.dirname(__file__), "logo.png")

if not os.path.exists(logo_path):
    st.warning(f"Logo file not found at: {logo_path}")
    image = None
else:
    image = Image.open(logo_path)

# 🧡 Streamlit Page Config
st.set_page_config(page_title="City AI Dashboard", page_icon="🚁", layout="wide")

# 🌐 Cyber Theme and Logo Placement
if image:
    st.markdown("""
    <div style='display:flex; align-items:center; gap:20px;'>
        <img src='data:image/png;base64,{0}' width='100'>
        <h1 style='color:#00ccff; font-family:monospace;'>CITY AGENT - Management Dashboard</h1>
    </div>
    """.format(image_to_base64(image)), unsafe_allow_html=True)

# 🎨 Cyberpunk Styling
st.markdown("""
    <style>
    body {
        background-color: #0a0a0f;
        color: #d0d0ff;
    }
    .stTabs [role="tablist"] {
        background-color: #1a1a2e;
    }
    .stTabs [role="tab"] {
        color: #66ccff;
    }
    .stTabs [aria-selected="true"] {
        background-color: #00ccff;
        color: #000000;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# 🕒 Date Filter UI
st.sidebar.markdown("## 🔍 Date Filter")
today = datetime.today().date()
start_date = st.sidebar.date_input("Start Date", value=today)
end_date = st.sidebar.date_input("End Date", value=today + timedelta(days=7))

if start_date > end_date:
    st.sidebar.error("Start date must be before end date.")
start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())

# 📦 MongoDB Data Loaders (With Filter)
def load_match_data():
    collection = get_mongo_collection("match_data")
    data = list(collection.find({
        "MatchStatus": "Active",
        "Ride_Time": {"$gte": start_dt, "$lte": end_dt}
    }))
    return pd.DataFrame(data)

def load_calendar_tasks():
    collection = get_mongo_collection("calendar_tasks")
    data = list(collection.find({
        "Status": "ACTIVE",
        "Transfer_Datetime": {"$gte": start_dt, "$lte": end_dt}
    }))
    return pd.DataFrame(data)

def load_rides_data():
    collection = get_mongo_collection("enriched_rides")
    data = list(collection.find({
        "Status": "ACTIVE",
        "ride_datetime": {"$gte": start_dt, "$lte": end_dt}
    }))
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
            "Now": now.strftime('%Y-%m-%d %H:%M:%S'),
            "Status": color
        })

    return pd.DataFrame(status_data)

# 🗂️ Tabs Structure
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚗 Match Data",
    "🗓️ Calendar Tasks",
    "🚛 Rides Data",
    "📈 System Status",
    "🤖 Ask AI"
])

# 🚗 Match Data Tab
with tab1:
    st.subheader("🚗 Match Data Overview")
    df = load_match_data()
    if not df.empty:
        view_mode = st.radio("Select view mode:", ["Cards", "Table"], horizontal=True)
        render_match_cards(df, as_cards=(view_mode == "Cards"))
    else:
        st.warning("No Match Data Found.")


# 🗓️ Calendar Tasks Tab
with tab2:
    st.subheader("🗓️ Calendar Tasks")
    render_calendar_page(start_dt, end_dt)

# 🚛 Rides Data Tab
with tab3:
    st.subheader("🚛 Rides Data")
    df = load_rides_data()
    if not df.empty:
        st.dataframe(df, use_container_width=True, height=600)
    else:
        st.warning("No Rides Data Found.")

# 📈 System Status Tab
with tab4:
    st.subheader("📈 System Status Overview")
    status_df = load_system_status()
    if not status_df.empty:
        st.dataframe(status_df, use_container_width=True, height=600)
    else:
        st.warning("No System Status Available.")

# 🤖 Ask AI Tab (New)
with tab5:
    build_ask_ai_tab(start_dt, end_dt)  # 🚀 Call the new AI tab builder with dates passed
