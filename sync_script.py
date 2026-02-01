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

    # Define date (pulling yesterday's complete data)
    target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    # 2. Fetch Health Metrics
    stats = api.get_stats(target_date)
    sleep = api.get_sleep_data(target_date)
    hrv = api.get_hrv_data(target_date)
    # Body Battery comes as a list of values throughout the day
    bb_data = api.get_body_battery(target_date)
    bb_max = max([val['bodyBatteryValue'] for val in bb_data]) if bb_data else "N/A"

    # 3. Fetch Activities (Last 5)
    activities = api.get_activities(0, 5)
    recent_workouts = []
    for act in activities:
        # Check if activity happened on target date
        if act['startTimeLocal'].startswith(target_date):
            recent_workouts.append({
                "Type": act['activityType']['typeKey'],
                "Name": act['activityName'],
                "Duration_Min": round(act['duration'] / 60, 1),
                "Calories": act['calories']
            })

    # 4. Consolidate into a flat dictionary for CSV
    data_summary = {
        "Date": target_date,
        "Sleep_Score": sleep.get('dailySleepDTO', {}).get('sleepScore', "N/A"),
        "HRV_Avg": hrv.get('hrvSummary', {}).get('lastNightAvg', "N/A"),
        "Body_Battery_Max": bb_max,
        "Stress_Avg": stats.get('averageStressLevel', "N/A"),
        "Workouts": json.dumps(recent_workouts) # JSON string to keep CSV clean
    }
    
    df = pd.DataFrame([data_summary])
    filename = "garmin_daily_summary.csv"
    df.to_csv(filename, index=False)
    return filename

def upload_to_drive(file_path):
    # 1. Drive Authentication via Service Account Secret
    service_account_info = json.loads(os.getenv("GDRIVE_JSON_KEY"))
    folder_id = os.getenv("DRIVE_FOLDER_ID")
    
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, 
        scopes=['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=creds)

    # 2. Upload/Update Logic
    file_metadata = {
        'name': 'Garmin_Data_Live.csv', # Keeping same name so Gemini doesn't get confused
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='text/csv', resumable=True)

    # Note: This creates a NEW file daily. 
    # To keep it "clean," we just upload it with the same name.
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"File uploaded successfully. ID: {file.get('id')}")

if __name__ == "__main__":
    try:
        csv_file = get_garmin_data()
        upload_to_drive(csv_file)
    except Exception as e:
        print(f"Error during sync: {e}")
