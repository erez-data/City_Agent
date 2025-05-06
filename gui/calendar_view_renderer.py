
import sys
import os
# Add the project root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.mongodb_utils import get_mongo_collection
# 📅 calendar_view_renderer.py

# 📅 calendar_view_renderer.py

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
from utils.mongodb_utils import get_mongo_collection
import uuid


# ----------------------------
# 🎨 Calendar Styling
# ----------------------------
def _apply_calendar_styles():
    st.markdown("""
    <style>
    /* Main Calendar Container */
    .calendar-app {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* Calendar Header */
    .calendar-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
    }

    /* Navigation Controls */
    .calendar-nav {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .calendar-nav-btn {
        background: #2a2a40;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 5px 10px;
        cursor: pointer;
    }

    .calendar-title {
        font-size: 1.3rem;
        font-weight: bold;
        color: #00ccff;
    }

    /* Day Columns */
    .day-columns {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 10px;
        margin-bottom: 20px;
    }

    .day-column {
        background: #1a1a2e;
        border-radius: 8px;
        padding: 10px;
        min-height: 150px;
    }

    .day-header {
        font-weight: bold;
        color: #ffaa00;
        margin-bottom: 8px;
        text-align: center;
    }

    .day-header.today {
        color: #00ccff;
    }

    .day-number {
        font-size: 1.1rem;
    }

    .day-number.today {
        background: #00ccff;
        color: #000;
        border-radius: 50%;
        width: 28px;
        height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }

    /* Calendar Events */
    .calendar-event {
        background: #2a2a40;
        border-left: 3px solid #00ccff;
        margin: 6px 0;
        padding: 8px;
        border-radius: 4px;
        font-size: 0.85rem;
    }

    .event-time {
        color: #ffaa00;
        font-size: 0.8rem;
        margin-right: 5px;
    }

    /* Task Form */
    .task-form-container {
        background: #1a1a2e;
        padding: 15px;
        border-radius: 8px;
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)


# ----------------------------
# 📅 Calendar View - Day Columns
# ----------------------------
def render_day_columns(df, current_date):
    _apply_calendar_styles()

    # Ensure current_date is a datetime.date object
    if isinstance(current_date, datetime):
        current_date = current_date.date()

    # Get the start and end of the week
    start_of_week = current_date - timedelta(days=current_date.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    today = date.today()

    # Calendar Header
    st.markdown("""
    <div class="calendar-app">
        <div class="calendar-header">
            <div class="calendar-nav">
    """, unsafe_allow_html=True)

    if st.button("◀ Previous Week", key="prev_week"):
        st.session_state.week_start = start_of_week - timedelta(days=7)
        st.rerun()

    st.markdown(f"""
    <div class="calendar-title">
        {start_of_week.strftime('%b %d')} - {(start_of_week + timedelta(days=6)).strftime('%b %d, %Y')}
    </div>
    """, unsafe_allow_html=True)

    if st.button("Next Week ▶", key="next_week"):
        st.session_state.week_start = start_of_week + timedelta(days=7)
        st.rerun()

    if st.button("Today", key="today_btn"):
        st.session_state.week_start = today
        st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)

    # Day columns
    st.markdown("<div class='day-columns'>", unsafe_allow_html=True)

    for day in week_dates:
        # Convert day to date object for comparison
        day_date = day.date() if isinstance(day, datetime) else day
        day_events = df[df['Transfer_Date'] == day_date].sort_values('Transfer_Datetime')
        day_class = "day-header today" if day_date == today else "day-header"

        st.markdown(f"""
        <div class='day-column'>
            <div class='{day_class}'>
                {calendar.day_abbr[day.weekday()]}<br>
                <span class='{"day-number today" if day_date == today else "day-number"}'>
                    {day.day}
                </span>
            </div>
        """, unsafe_allow_html=True)

        # Add events for this day
        if not day_events.empty:
            for _, event in day_events.iterrows():
                event_time = pd.to_datetime(event['Transfer_Datetime']).strftime("%H:%M")
                st.markdown(f"""
                <div class='calendar-event'>
                    <span class='event-time'>{event_time}</span>
                    {event.get('Title', '')}
                </div>
                """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------
# ➕ Task Form
# ----------------------------
def render_task_form(task_id=None):
    collection = get_mongo_collection("calendar_tasks")
    task_data = None

    if task_id:
        task_data = collection.find_one({"Task_ID": task_id})

    with st.container():
        st.markdown("<div class='task-form-container'>", unsafe_allow_html=True)

        # Form header
        st.subheader("✏️ Edit Task" if task_id else "➕ Add New Task")

        if task_id and st.button("🗑️ Delete Task", key="delete_task", type="secondary"):
            collection.delete_one({"Task_ID": task_id})
            st.success("Task deleted successfully!")
            st.rerun()

        # Form fields
        title = st.text_input("Title", value=task_data.get("Title", "") if task_data else "")

        col1, col2 = st.columns(2)
        with col1:
            transfer_date = st.date_input(
                "Date",
                value=pd.to_datetime(task_data["Transfer_Datetime"]).date() if task_data else datetime.now().date()
            )
        with col2:
            transfer_time = st.time_input(
                "Time",
                value=pd.to_datetime(task_data["Transfer_Datetime"]).time() if task_data else datetime.now().time()
            )

        pickup = st.text_input("Pickup Location", value=task_data.get("Pickup", "") if task_data else "")
        dropoff = st.text_input("Dropoff Location", value=task_data.get("Dropoff", "") if task_data else "")
        notes = st.text_area("Notes", value=task_data.get("Notes", "") if task_data else "")

        # Submit button
        if st.button("💾 Save Task", type="primary"):
            full_transfer_dt = datetime.combine(transfer_date, transfer_time)
            now = datetime.utcnow()

            doc = {
                "Title": title,
                "Transfer_Datetime": full_transfer_dt,
                "Transfer_Time": full_transfer_dt.strftime("%H:%M"),
                "Pickup": pickup,
                "Dropoff": dropoff,
                "Notes": notes,
                "Due": full_transfer_dt.replace(hour=0, minute=0, second=0, microsecond=0),
                "Updated": now,
                "LastSeen": now,
                "Source": "UI",
                "Status": "ACTIVE",
                "API_Status": "needsAction",
                "GeoStatus": "",
                "DistanceStatus": "",
                "TelegramSent": False,
                "MatchAnalyzed": False,
                "Analyzed": False
            }

            if task_id:
                result = collection.update_one({"Task_ID": task_id}, {"$set": doc})
                if result.modified_count:
                    st.success("✅ Task updated successfully!")
                else:
                    st.warning("No changes detected or task not found.")
            else:
                doc["Task_ID"] = str(uuid.uuid4()).replace("-", "")[:22]
                doc["ID"] = f"TASK_{doc['Task_ID']}"
                doc["FirstSeen"] = now
                collection.insert_one(doc)
                st.success(f"✅ New task created: {doc['ID']}")

            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------
# 📅 Main Calendar Page
# ----------------------------
def render_calendar_page(start_dt, end_dt):
    # Load calendar data
    df = load_calendar_data(start_dt, end_dt)

    # Initialize session state for week navigation
    if 'week_start' not in st.session_state:
        st.session_state.week_start = date.today()

    # Handle query params
    query_params = st.query_params
    if 'week_start' in query_params and query_params['week_start']:
        try:
            st.session_state.week_start = datetime.strptime(query_params['week_start'], "%Y-%m-%d").date()
        except:
            st.session_state.week_start = date.today()

    # Two-column layout
    col1, col2 = st.columns([3, 1])

    with col1:
        render_day_columns(df, st.session_state.week_start)

    with col2:
        # Display upcoming events
        st.subheader("📅 Upcoming Events")
        upcoming = df[df['Transfer_Date'] >= date.today()].sort_values('Transfer_Datetime').head(5)

        if not upcoming.empty:
            for _, event in upcoming.iterrows():
                event_time = pd.to_datetime(event['Transfer_Datetime']).strftime("%H:%M")
                with st.expander(f"{event_time} - {event.get('Title', '')}"):
                    st.write(f"**From:** {event.get('Pickup', '')}")
                    st.write(f"**To:** {event.get('Dropoff', '')}")
                    if event.get('Notes'):
                        st.write(f"**Notes:** {event.get('Notes')}")

                    if st.button("Edit", key=f"edit_{event['Task_ID']}"):
                        st.session_state.edit_task = event['Task_ID']

        # Task form
        if 'edit_task' in st.session_state:
            render_task_form(st.session_state.edit_task)
        elif st.button("➕ Add New Task"):
            st.session_state.edit_task = None
            render_task_form()


# ----------------------------
# 📂 Data Loading
# ----------------------------
def load_calendar_data(start_dt, end_dt):
    collection = get_mongo_collection("calendar_tasks")
    data = list(collection.find({
        "Status": "ACTIVE",
        "Transfer_Datetime": {"$gte": start_dt, "$lte": end_dt}
    }))
    df = pd.DataFrame(data)

    if not df.empty:
        df["Transfer_Date"] = pd.to_datetime(df["Transfer_Datetime"]).dt.date
    return df