import os
import json
import datetime
import pandas as pd
from garminconnect import Garmin
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_garmin_data():
    # 1. Garmin Authentication
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    api = Garmin(email, password)
    api.login()

    # Define date (Yesterday)
    target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    print(f"Fetching data for {target_date}...")

    # 2. Fetch Health Metrics with Safety Defaults
    try:
        stats = api.get_stats(target_date)
    except: stats = {}

    try:
        sleep = api.get_sleep_data(target_date)
    except: sleep = {}

    try:
        hrv = api.get_hrv_data(target_date)
    except: hrv = {}

    # --- FIXED BODY BATTERY LOGIC ---
    bb_max = "N/A"
    try:
        bb_data = api.get_body_battery(target_date)
        if bb_data and isinstance(bb_data, list):
            # The key is often 'value' in recent wrapper updates
            values = [val.get('value') or val.get('bodyBatteryValue') for val in bb_data if (val.get('value') or val.get('bodyBatteryValue'))]
            if values:
                bb_max = max(values)
    except Exception as e:
        print(f"Note: Could not process Body Battery: {e}")

    # 3. Fetch Activities
    recent_workouts = []
    try:
        activities = api.get_activities(0, 10)
        for act in activities:
            if act['startTimeLocal'].startswith(target_date):
                recent_workouts.append({
                    "Type": act['activityType']['typeKey'],
                    "Name": act['activityName'],
                    "Duration_Min": round(act['duration'] / 60, 1),
                    "Calories": act['calories']
                })
    except: pass

    # 4. Consolidate
    data_summary = {
        "Date": target_date,
        "Sleep_Score": sleep.get('dailySleepDTO', {}).get('sleepScore', "N/A"),
        "HRV_Avg": hrv.get('hrvSummary', {}).get('lastNightAvg', "N/A"),
        "Body_Battery_Max": bb_max,
        "Stress_Avg": stats.get('averageStressLevel', "N/A"),
        "Workouts": json.dumps(recent_workouts)
    }
    
    df = pd.DataFrame([data_summary])
    filename = "garmin_daily_summary.csv"
    df.to_csv(filename, index=False)
    return filename

def upload_to_drive(file_path):
    # Setup Drive
    service_account_info = json.loads(os.getenv("GDRIVE_JSON_KEY"))
    folder_id = os.getenv("DRIVE_FOLDER_ID")
    
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, 
        scopes=['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=creds)

    # File Metadata
    file_metadata = {
        'name': 'Garmin_Data_Live.csv',
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='text/csv')

    # Upload
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Success! Uploaded to Drive. File ID: {file.get('id')}")

if __name__ == "__main__":
    try:
        csv_file = get_garmin_data()
        upload_to_drive(csv_file)
    except Exception as e:
        print(f"Critical Error: {e}")
