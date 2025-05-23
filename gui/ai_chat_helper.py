# 📦 ai_chat_helper.py

import streamlit as st
import requests
import pandas as pd
from utils.mongodb_utils import get_mongo_collection
import json
from test_deepseek1 import ask_deepseek
from datetime import datetime

# ----------------------------
# 🧠 Collection Loader with Date Filters
# ----------------------------
def load_filtered_data(collection_name, start_dt, end_dt):
    if not collection_name:
        return []  # 🛡️ No collection selected, no data

    collection = get_mongo_collection(collection_name)
    query = {}

    if collection_name == "match_data":
        query = {
            "MatchStatus": "Active",
            "Ride_Time": {"$gte": start_dt, "$lte": end_dt}
        }
    elif collection_name == "calendar_tasks":
        query = {
            "Status": "ACTIVE",
            "Transfer_Datetime": {"$gte": start_dt, "$lte": end_dt}
        }
    elif collection_name in ["wt_rides", "elife_rides", "enriched_rides"]:
        query = {
            "Status": "ACTIVE",
            "ride_datetime": {"$gte": start_dt, "$lte": end_dt}
        }
    else:
        query = {"Status": "ACTIVE"}

    docs = list(collection.find(query))
    return docs

# ----------------------------
# 🧠 Data Summarizer for Prompt
# ----------------------------
def summarize_documents(docs, collection_name):
    summaries = []

    for doc in docs:
        if collection_name == "match_data":
            summary = f"Pickup: {doc.get('Pickup', '')} ➔ Dropoff: {doc.get('Dropoff', '')}, Ride_Time: {doc.get('Ride_Time', '')}, Match_Time: {doc.get('Match_Time', '')}, Time Diff (min): {doc.get('Time_Difference_min', '')}, Distance (km): {doc.get('Real_Distance_km', '')}, Direction: {doc.get('Match_Direction', '')}"
        else:
            summary = f"Pickup: {doc.get('Pickup', '')} ➔ Dropoff: {doc.get('Dropoff', '')}, Transfer Time: {doc.get('Transfer_Datetime', doc.get('ride_datetime', ''))}, Distance: {doc.get('Distance', '')}, Duration: {doc.get('Duration', '')}, Notes: {doc.get('Notes', '')}, Price: {doc.get('Price', '')}"
        summaries.append(summary)

    return "\n".join(summaries)

# ----------------------------
# 🧠 Smart Prompt Builder
# ----------------------------
def build_prompt(history, user_message, mongo_summary=None):
    today_date = datetime.now().strftime("%Y-%m-%d")
    prompt = f"You are answering based on business ride data. (Today is {today_date})\n"

    if mongo_summary:
        prompt += f"Here is some reference data:\n{mongo_summary}\n"
    else:
        prompt += f"No database records were selected. Answer generally.\n"

    if history:
        prompt += "\nPrevious conversation:\n"
        for item in history[-3:]:
            role = "User" if item['role'] == 'user' else "AI"
            prompt += f"{role}: {item['content']}\n"

    prompt += f"\nNew question:\n{user_message}\n"
    prompt += "\nAnswer clearly:"

    return prompt

# ----------------------------
# 🧠 Call DeepSeek AI Model API
# ----------------------------
def call_ai(prompt):
    result = ask_deepseek(prompt)
    try:
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("DeepSeek parsing error:", e)
        return "⚠️ Yanıt işlenemedi."

# ----------------------------
# 🧠 Traffic Light Status
# ----------------------------
def show_traffic_light(collection_selected, mongo_docs):
    if not collection_selected:
        st.markdown("### 🟡 General Question (no collection selected)")
    elif mongo_docs:
        st.markdown("### 🟢 Data Fetched Successfully")
    else:
        st.markdown("### 🔴 No Data Found (check collection filter)")

# ----------------------------
# 🧠 Full Tab UI Builder
# ----------------------------
def build_ask_ai_tab(start_dt, end_dt):
    st.header("🤖 Ask AI About Your Business Data")

    # Session State Setup
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Collection selection
    collection_selected = st.selectbox("Select a data collection (optional):", ["", "calendar_tasks", "wt_rides", "elife_rides", "enriched_rides", "match_data"])

    mongo_docs = []
    mongo_summary = None

    if collection_selected:
        mongo_docs = load_filtered_data(collection_selected, start_dt, end_dt)
        if mongo_docs:
            mongo_summary = summarize_documents(mongo_docs, collection_selected)

    # Traffic Light Indicator
    show_traffic_light(collection_selected, mongo_docs)

    # Show existing chat messages
    for message in st.session_state.messages:
        role_color = "#1e1e1e" if message['role'] == 'user' else "#2e2e2e"
        with st.chat_message(message['role']):
            st.markdown(f"""
                <div style='background-color:{role_color}; padding:12px; border-radius:10px; color:white; font-size:16px;'>
                    {message['content']}
                </div>
            """, unsafe_allow_html=True)

    # User Input
    prompt = st.chat_input("Type your question here...")

    if prompt:
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Build full prompt
        full_prompt = build_prompt(st.session_state.messages[:-1], prompt, mongo_summary)

        # Call AI
        with st.spinner("Thinking..."):
            ai_response = call_ai(full_prompt)

        # Add AI response to history
        st.session_state.messages.append({"role": "assistant", "content": ai_response})

        # Refresh to show
        st.rerun()
