import os
import json
import datetime
import pandas as pd
from garminconnect import Garmin
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_garmin_data():
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    api = Garmin(email, password)
    api.login()

    target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    print(f"Fetching data for {target_date}...")

    # Fetch stats with safety
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

    data_summary = {
        "Date": target_date,
        "Sleep_Score": sleep.get('dailySleepDTO', {}).get('sleepScore', "N/A"),
        "HRV_Avg": hrv.get('hrvSummary', {}).get('lastNightAvg', "N/A"),
        "Body_Battery_Max": bb_max,
        "Stress_Avg": stats.get('averageStressLevel', "N/A")
    }
    
    filename = "garmin_daily_summary.csv"
    pd.DataFrame([data_summary]).to_csv(filename, index=False)
    return filename

def upload_to_drive(file_path):
    folder_id = os.getenv("DRIVE_FOLDER_ID")
    if not folder_id:
        raise ValueError("DRIVE_FOLDER_ID is missing from GitHub Secrets!")

    service_account_info = json.loads(os.getenv("GDRIVE_JSON_KEY"))
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, 
        scopes=['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': 'Garmin_Data_Live.csv',
        'parents': [folder_id]
    }
    
    # Using simple upload instead of resumable to avoid 404 session errors
    media = MediaFileUpload(file_path, mimetype='text/csv', resumable=False)
    
    print(f"Uploading to folder: {folder_id}...")
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Success! File ID: {file.get('id')}")

if __name__ == "__main__":
    try:
        csv_file = get_garmin_data()
        upload_to_drive(csv_file)
    except Exception as e:
        print(f"Critical Error: {e}")
