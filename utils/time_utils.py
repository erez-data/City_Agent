# time_utils.py

import pandas as pd  # This was missing!
from datetime import datetime

def standardize_ride_time(time_str):
    """
    Simplified time parser for format: "2025-04-16 03:10 AM"
    Just removes the AM/PM since the time is already in correct 24-hour format
    """
    if pd.isna(time_str) or not time_str.strip():
        return None

    try:
        # Remove AM/PM and any extra whitespace
        clean_time = time_str.replace(' AM', '').replace(' PM', '').strip()
        return pd.to_datetime(clean_time, format='%Y-%m-%d %H:%M')
    except Exception as e:
        print(f"⚠️ Could not parse time: '{time_str}' - Error: {str(e)}")
        return None


def format_time_for_display(dt):
    """Convert datetime back to display format (without AM/PM)"""
    if pd.isna(dt):
        return ""
    return dt.strftime('%Y-%m-%d %H:%M')