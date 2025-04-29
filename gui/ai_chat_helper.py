# 📦 ai_chat_helper.py

import streamlit as st
import requests
import pandas as pd
from utils.mongodb_utils import get_mongo_collection
import json

# ----------------------------
# 🧠 Collection Loader with Filters
# ----------------------------
def load_filtered_data(collection_name):
    collection = get_mongo_collection(collection_name)

    if collection_name == "match_data":
        query = {"MatchStatus": "Active"}
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
            summary = f"Pickup: {doc.get('Pickup', '')} ➔ Dropoff: {doc.get('Dropoff', '')}, Transfer Time: {doc.get('Transfer_Datetime', doc.get('ride_datetime', ''))}, Distance: {doc.get('Distance', '')}, Duration: {doc.get('Duration', '')}"
        summaries.append(summary)

    return "\n".join(summaries)

# ----------------------------
# 🧠 Smart Prompt Builder
# ----------------------------

def build_prompt(history, user_message, mongo_summary=None):
    prompt = "You are answering based on business ride data.\n"

    if mongo_summary:
        prompt += f"Here is some reference data:\n{mongo_summary}\n"

    if history:
        prompt += "\nPrevious conversation:\n"
        for item in history[-3:]:
            role = "User" if item['role'] == 'user' else "AI"
            prompt += f"{role}: {item['content']}\n"

    prompt += f"\nNew question:\n{user_message}\n"
    prompt += "\nAnswer clearly:"

    return prompt

# ----------------------------
# 🧠 Call Phi-2 Ollama Model API
# ----------------------------

def call_phi2(prompt):
    response = requests.post("http://ollama:11434/api/generate", json={
        "model": "phi",
        "prompt": prompt
    }, timeout=120, stream=True)  # <--- Çok önemli: stream=True

    result = ""
    for line in response.iter_lines(decode_unicode=True):
        if line:
            try:
                parsed = json.loads(line)
                part = parsed.get("response", "")
                result += part
            except Exception as e:
                print("Parse error:", e)
                continue
    return result.strip()

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

def build_ask_ai_tab():
    st.header("🤖 Ask AI About Your Business Data")

    # Session State Setup
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Collection selection
    collection_selected = st.selectbox("Select a data collection (optional):", ["", "calendar_tasks", "wt_rides", "elife_rides", "enriched_rides", "match_data"])

    mongo_docs = []
    mongo_summary = None

    if collection_selected:
        mongo_docs = load_filtered_data(collection_selected)
        if mongo_docs:
            mongo_summary = summarize_documents(mongo_docs, collection_selected)

    # Traffic Light Indicator
    show_traffic_light(collection_selected, mongo_docs)

    # Show existing chat messages
    for message in st.session_state.messages:
        role_color = "#ADD8E6" if message['role'] == 'user' else "#90EE90"
        with st.chat_message(message['role']):
            st.markdown(f"<div style='background-color:{role_color}; padding:10px; border-radius:10px'>{message['content']}</div>", unsafe_allow_html=True)

    # User Input
    prompt = st.chat_input("Type your question here...")

    if prompt:
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Build full prompt
        full_prompt = build_prompt(st.session_state.messages[:-1], prompt, mongo_summary)

        # Call AI
        with st.spinner("Thinking..."):
            ai_response = call_phi2(full_prompt)

        # Add AI response to history
        st.session_state.messages.append({"role": "assistant", "content": ai_response})

        # Refresh to show
        st.rerun()
