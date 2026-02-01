import os
import json
import datetime
import io
import pandas as pd
from garminconnect import Garmin
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

def get_garmin_data():
    api = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
    api.login()
    
    # Logic to fetch data for "Yesterday"
    target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    print(f"Fetching data for {target_date}...")

    try: stats = api.get_stats(target_date)
    except: stats = {}
    try: sleep = api.get_sleep_data(target_date)
    except: sleep = {}
    try: hrv = api.get_hrv_data(target_date)
    except: hrv = {}
    
    bb_max = "N/A"
    try:
        bb_data = api.get_body_battery(target_date)
        if bb_data:
            values = [val.get('value') or val.get('bodyBatteryValue') for val in bb_data if (val.get('value') or val.get('bodyBatteryValue'))]
            if values: bb_max = max(values)
    except: pass

    recent_workouts = []
    try:
        activities = api.get_activities(0, 10)
        for act in activities:
            if act['startTimeLocal'].startswith(target_date):
                recent_workouts.append(f"{act['activityType']['typeKey']}({round(act['duration']/60)}m)")
    except: pass

    return {
        "Date": target_date,
        "Sleep_Score": sleep.get('dailySleepDTO', {}).get('sleepScore', "N/A"),
        "HRV_Avg": hrv.get('hrvSummary', {}).get('lastNightAvg', "N/A"),
        "Body_Battery_Max": bb_max,
        "Stress_Avg": stats.get('averageStressLevel', "N/A"),
        "Workouts": ", ".join(recent_workouts) if recent_workouts else "None"
    }

def sync_to_drive(new_entry):
    file_id = os.getenv("DRIVE_FILE_ID")
    service_account_info = json.loads(os.getenv("GDRIVE_JSON_KEY"))
    
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=creds)

    # 1. Download Existing History
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    try:
        while done is False:
            status, done = downloader.next_chunk()
        fh.seek(0)
        df_existing = pd.read_csv(fh)
    except Exception:
        df_existing = pd.DataFrame(columns=["Date", "Sleep_Score", "HRV_Avg", "Body_Battery_Max", "Stress_Avg", "Workouts"])

    # 2. Append New Data (Keep Everything)
    df_new = pd.DataFrame([new_entry])
    df_combined = pd.concat([df_existing, df_new]).drop_duplicates(subset=['Date'], keep='last')
    
    # Sort by date so the newest is always at the bottom
    df_combined['Date'] = pd.to_datetime(df_combined['Date'])
    df_combined = df_combined.sort_values('Date')
    
    df_combined.to_csv("sync.csv", index=False)

    # 3. Update File
    media = MediaFileUpload("sync.csv", mimetype='text/csv', resumable=False)
    service.files().update(fileId=file_id, media_body=media).execute()
    print(f"Sync Successful. Total records: {len(df_combined)}")

if __name__ == "__main__":
    try:
        entry = get_garmin_data()
        sync_to_drive(entry)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
