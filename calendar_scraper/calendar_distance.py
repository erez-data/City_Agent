import os
import pickle
import re
import google.auth
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pandas as pd
import tkinter as tk
from tkinter import ttk
from dateutil import parser

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Define paths relative to the script location
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(SCRIPT_DIR, 'token.pickle')

SCOPES = ['https://www.googleapis.com/auth/tasks.readonly']

def authenticate_google():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    service = build('tasks', 'v1', credentials=creds)
    return service


# Fetch all tasks, including completed and hidden ones
def fetch_all_tasks(service):
    tasklist_id = '@default'
    tasks = []
    next_page_token = None

    while True:
        result = service.tasks().list(
            tasklist=tasklist_id,
            pageToken=next_page_token,
            showCompleted=True,
            showHidden=True
        ).execute()

        tasks.extend(result.get('items', []))
        next_page_token = result.get('nextPageToken')

        if not next_page_token:
            break

    return tasks

# Convert ISO 8601 date to readable string
def convert_date(date):
    if not date:
        return 'No Date'
    try:
        return parser.isoparse(date).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return 'Invalid Date'

# Extract time, start and end location from Title
def extract_transfer_info(title, due_date):
    if not title or not due_date:
        return pd.NaT, None, None, None

    # Match format: "10:50 DALAMAN FETHIYE"
    match = re.match(r"(\d{1,2}:\d{2})\s+([^\s]+)\s+(.+)", title)
    if match:
        time_str = match.group(1)
        start_loc = match.group(2)
        end_loc = match.group(3)
        try:
            full_datetime = pd.to_datetime(f"{due_date.date()} {time_str}")
        except Exception:
            full_datetime = pd.NaT
    else:
        time_str = None
        start_loc = None
        end_loc = None
        full_datetime = pd.NaT

    return full_datetime, time_str, start_loc, end_loc

# UI display
def display_dataframe_in_ui(df):
    def on_double_click(event):
        selected_item = tree.selection()
        if selected_item:
            values = tree.item(selected_item[0], "values")
            detail_win = tk.Toplevel(root)
            detail_win.title("Task Details")
            text_widget = tk.Text(detail_win, wrap=tk.WORD, width=80, height=20)
            text_widget.pack(padx=10, pady=10)
            content = ""
            for col, val in zip(df.columns, values):
                content += f"{col}: {val}\n\n"
            text_widget.insert(tk.END, content)
            text_widget.config(state=tk.DISABLED)

    root = tk.Tk()
    root.title("Google Tasks")

    tree = ttk.Treeview(root, columns=df.columns.tolist(), show="headings")

    for col in df.columns:
        tree.heading(col, text=col)
        tree.column(col, width=150)

    for _, row in df.iterrows():
        tree.insert("", "end", values=row.tolist())

    tree.bind("<Double-1>", on_double_click)
    tree.pack(fill="both", expand=True)

    root.mainloop()

# Main
def main():
    service = authenticate_google()
    task_list = fetch_all_tasks(service)

    if task_list:
        task_data = []

        for index, task in enumerate(task_list, start=1):
            due_str = task.get('due')
            due_dt = pd.to_datetime(convert_date(due_str), errors='coerce')

            title = task.get('title', 'No Title')
            transfer_datetime, transfer_time, start_loc, end_loc = extract_transfer_info(title, due_dt)

            task_dict = {
                'Task Number': index,
                'Due': due_dt,
                'Title': title,
                'Notes': task.get('notes', 'No Notes'),
                'Status': task.get('status', 'No Status'),
                'Updated': pd.to_datetime(convert_date(task.get('updated')), errors='coerce'),
                'Transfer Time': transfer_time,
                'Transfer Start Location': start_loc,
                'Transfer End Location': end_loc,
                'Transfer Datetime': transfer_datetime
            }
            task_data.append(task_dict)

        df = pd.DataFrame(task_data)
        df = df.sort_values(by='Due', ascending=True)
    else:
        df = pd.DataFrame(columns=[
            'Task Number', 'Due', 'Title', 'Notes', 'Status', 'Updated',
            'Transfer Time', 'Transfer Start Location', 'Transfer End Location', 'Transfer Datetime'
        ])

    display_dataframe_in_ui(df)
    pd.set_option('display.max_rows', None)  # Show all rows
    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.width', None)  # Don't break lines
    pd.set_option('display.max_colwidth', None)  # Show full column content
    # File path
    file_path = r"C:\Users\EREZ\Desktop\Requirements\my_data.csv"

    # Save to CSV
    df.to_csv(file_path, index=False)

    print(df)

if __name__ == '__main__':
    main()
