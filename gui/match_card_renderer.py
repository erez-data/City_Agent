# 📦 match_card_renderer.py
import streamlit as st
import pandas as pd

def render_match_cards(df: pd.DataFrame, as_cards: bool = True):
    if not as_cards:
        st.dataframe(df, use_container_width=True, height=600)
        return

    grouped = df.groupby("Ride_ID")

    st.markdown("""
    <style>
    .ride-group {
        display: flex;
        flex-direction: column;
        gap: 40px;
        margin-bottom: 60px;
        overflow-x: auto;
        width: 100%;
        padding-top: 10px;
        padding-left: 12px;
    }
    .ride-row {
        display: inline-flex;
        flex-direction: row;
        align-items: stretch;
        gap: 16px;
        padding-bottom: 12px;
        min-width: max-content;
    }
    .ride-box, .match-box {
        background-color: #111522;
        border-radius: 15px;
        padding: 24px 16px 20px;
        color: white;
        font-family: monospace;
        box-shadow: 0 0 14px #00ccff;
        width: 280px;
        position: relative;
        min-height: 190px;
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .calendar-badge {
        position: absolute;
        top: -12px;
        right: -12px;
        background-color: #ffaa00;
        padding: 4px 10px;
        border-radius: 12px 0 12px 0;
        font-size: 11px;
        font-weight: bold;
        box-shadow: 0 0 5px rgba(0,0,0,0.4);
        z-index: 10;
    }
    .match-info {
        font-size: 13px;
        background-color: #222;
        padding: 8px;
        margin-top: 6px;
        border-left: 3px solid #00ccff;
        border-radius: 8px;
    }
    .direction-label {
        margin-top: 5px;
        font-weight: bold;
        color: #ddd;
    }
    .direction-label.bright {
        color: #ffcc00;
    }
    .source-icon {
        position: absolute;
        top: -12px;
        left: -12px;
        background-color: #0077cc;
        padding: 4px 10px;
        border-radius: 0 12px 0 12px;
        font-size: 11px;
        font-weight: bold;
        box-shadow: 0 0 5px rgba(0,0,0,0.4);
        z-index: 10;
    }
    .ride-title {
        color: #00ccff;
        font-weight: bold;
        font-size: 15px;
        margin-bottom: 4px;
        word-wrap: break-word;
    }
    .sub {
        font-size: 13px;
        margin-top: 2px;
    }
    .arrow-connector {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        font-size: 20px;
        color: #00ccff;
    }
    </style>
    """, unsafe_allow_html=True)

    for ride_id, group in grouped:
        base = group.iloc[0]
        pickup = base.get("Pickup", "?")
        dropoff = base.get("Dropoff", "?")
        ride_time = base.get("Ride_Time", "")
        ride_arrival = base.get("Ride_Arrival", "")
        price = base.get("Price", "₺N/A")
        double_str = "✅ Double Used" if base.get("DoubleUtilized") else "❌ Single Use"

        row_html = "<div class='ride-group'><div class='ride-row'>"

        row_html += f"""
        <div class='ride-box'>
            <div class='ride-title'>🚗 {pickup} ➜ {dropoff}</div>
            <div class='sub'>🕒 {ride_time} ➔ {ride_arrival}</div>
            <div class='sub'>💰 {price} | {double_str}</div>
        </div>
        """

        for _, row in group.iterrows():
            matched_pickup = row.get("Matched_Pickup", "")
            matched_dropoff = row.get("Matched_Dropoff", "")
            match_time = row.get("Match_Time", "")
            match_arrival = row.get("Match_Arrival", "")
            matched_price = row.get("Matched_Price", "₺N/A")
            direction = row.get("Match_Direction", "")
            calendar_pair = row.get("CalendarMatchPair", "")
            match_source = row.get("Match_Source", "")

            diff = row.get("Time_Difference_min", "")
            real_distance = row.get("Real_Distance_km", "")
            real_duration = row.get("Real_Duration_min", "")

            row_html += "<div class='arrow-connector'>➝</div>"

            direction_class = "bright" if direction.strip().lower() == "home return" else ""

            match_box = f"""
            <div class='match-box'>
                <div class='ride-title'>⇣ Match ➔ {matched_pickup} ➜ {matched_dropoff}</div>
                <div class='match-info'>
                    🕒 {match_time} ➔ {match_arrival}<br>
                    💰 {matched_price} | ⏱️ {diff} min | 📍 {real_distance} km | 🚘 {real_duration} min
                </div>
                <div class='direction-label {direction_class}'>[{direction}]</div>
            """

            if calendar_pair and str(calendar_pair).lower() != "nan":
                match_box += f"<div class='calendar-badge'>📅 {calendar_pair}</div>"

            if match_source.lower() == "calendar":
                match_box += "<div class='source-icon'>📅</div>"
            elif match_source.lower() == "rides":
                match_box += "<div class='source-icon'>🚗</div>"

            match_box += "</div>"
            row_html += match_box

        row_html += "</div></div>"
        st.markdown(row_html, unsafe_allow_html=True)
