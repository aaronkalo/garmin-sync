import os
import json
import datetime
import io
import pandas as pd
from garminconnect import Garmin
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

def flatten_json(y):
    """Helper to turn nested Garmin data into a flat row for CSV"""
    out = {}
    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            out[name[:-1]] = json.dumps(x) # Keep lists as JSON strings
        else:
            out[name[:-1]] = x
    flatten(y)
    return out

def get_garmin_data():
    api = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
    api.login()
    target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    
    print(f"Deep-pulling ALL data for {target_date}...")

    # 1. Fetch the 3 main "Data Buckets"
    # These return massive dictionaries with 100+ fields each
    try: daily_summary = api.get_stats(target_date)
    except: daily_summary = {}
    
    try: sleep_data = api.get_sleep_data(target_date)
    except: sleep_data = {}
    
    try: hrv_data = api.get_hrv_data(target_date)
    except: hrv_data = {}

    try: body_battery = api.get_body_battery(target_date)
    except: body_battery = []

    # 2. Flatten and Combine
    # We prefix keys so you know where they came from (e.g., sleep_sleepScore)
    row = {"Date": target_date}
    row.update(flatten_json(daily_summary))
    row.update({f"sleep_{k}": v for k, v in flatten_json(sleep_data).items()})
    row.update({f"hrv_{k}": v for k, v in flatten_json(hrv_data).items()})
    
    # 3. Handle Activities separately (as a JSON blob in one cell)
    try:
        activities = api.get_activities(0, 20)
        daily_acts = [a for a in activities if a['startTimeLocal'].startswith(target_date)]
        row["All_Activities_Raw"] = json.dumps(daily_acts)
    except:
        row["All_Activities_Raw"] = "[]"

    return row

def sync_to_drive(new_entry):
    file_id = os.getenv("DRIVE_FILE_ID")
    service_account_info = json.loads(os.getenv("GDRIVE_JSON_KEY"))
    
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=creds)

    # Download, Append, and Update
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    try:
        while done is False:
            status, done = downloader.next_chunk()
        fh.seek(0)
        df_existing = pd.read_csv(fh)
    except:
        df_existing = pd.DataFrame()

    df_new = pd.DataFrame([new_entry])
    # Combine and ensure we don't lose old columns if Garmin changes formats
    df_combined = pd.concat([df_existing, df_new], sort=False).drop_duplicates(subset=['Date'], keep='last')
    
    df_combined.to_csv("sync.csv", index=False)
    media = MediaFileUpload("sync.csv", mimetype='text/csv', resumable=False)
    service.files().update(fileId=file_id, media_body=media).execute()
    print(f"Sync Complete. Row width: {len(df_combined.columns)} columns.")

if __name__ == "__main__":
    try:
        entry = get_garmin_data()
        sync_to_drive(entry)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
