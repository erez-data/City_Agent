import pandas as pd
import tkinter as tk
from tkinter import ttk
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

def get_mongo_collection(collection_name):
    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "city_agent")
    client = MongoClient(uri)
    return client[db_name][collection_name]

def show_match_data_ui():
    collection = get_mongo_collection("match_data")
    records = list(collection.find().sort("last_updated", -1).limit(100))

    columns = [
        "Ride_ID", "Ride_Time", "Ride_Arrival", "Pickup", "Dropoff",
        "Match_Source", "Matched_ID", "Match_Time", "Match_Arrival",
        "Match_Direction", "Time_Difference_min", "Geo_Distance_km",
        "Real_Distance_km", "Real_Duration_min", "Matched_Pickup",
        "Matched_Dropoff", "DoubleUtilized", "last_updated","MatchStatus","CalendarMatchPair"
    ]
    df = pd.DataFrame(records)
    df = df[columns]

    root = tk.Tk()
    root.title("Recent Match Data Viewer")
    root.geometry("1500x600")

    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150, anchor="center")

    for _, row in df.iterrows():
        tree.insert("", "end", values=list(row))

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.pack(side="right", fill="y")
    hsb.pack(side="bottom", fill="x")
    tree.pack(side="left", fill="both", expand=True)

    root.mainloop()

show_match_data_ui()
