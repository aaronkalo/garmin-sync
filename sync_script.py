import os
import datetime
from garminconnect import Garmin

# 1. Authenticate with Garmin
email = os.getenv("GARMIN_EMAIL")
password = os.getenv("GARMIN_PASSWORD")

api = Garmin(email, password)
api.login()

# 2. Define the date (Yesterday)
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)
date_str = yesterday.isoformat()

# 3. Fetch specific metrics
stats = api.get_stats(date_str)
sleep = api.get_sleep_data(date_str)
hrv = api.get_hrv_data(date_str)
bb = api.get_body_battery(date_str) # Body Battery
activities = api.get_activities(0, 5) # Last 5 activities

# 4. Format for Gemini (Creating a Summary)
summary = f"""
# Garmin Health Report: {date_str}
- **Body Battery:** Max {bb[0]['baselineValue'] if bb else 'N/A'}
- **Sleep Score:** {sleep.get('dailySleepDTO', {}).get('sleepScore', 'N/A')}
- **HRV Average:** {hrv.get('hrvSummary', {}).get('lastNightAvg', 'N/A')}
- **Stress Level:** {stats.get('averageStressLevel', 'N/A')}

## Activities:
"""
for activity in activities:
    if activity['startTimeLocal'].startswith(date_str):
        summary += f"- {activity['activityName']}: {activity['duration']/60:.1f} mins, {activity['calories']} cal\n"

# 5. Save to a file
with open("garmin_health_summary.md", "a") as f:
    f.write(summary + "\n---\n")

print(f"Data synced for {date_str}")
