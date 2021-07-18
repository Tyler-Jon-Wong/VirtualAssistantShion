import mysql.connector
from datetime import datetime, timedelta
import bisect
import uuid

import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SHION_ID = "86ukdml44ruvlvrtupfild7cek@group.calendar.google.com"
TIMEZONE = 'America/Toronto'
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('cal_token.json'):
        creds = Credentials.from_authorized_user_file('cal_token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('cal_token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    return service

# SQL

db = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="tictac!1",
    database="testdatabase"
)

mycursor = db.cursor()


def create_events_table():
    Q = "CREATE TABLE Events (" \
        "id VARCHAR(32), " \
        "summary VARCHAR(100), " \
        "date VARCHAR(15), " \
        "start_time VARCHAR(50) DEFAULT '', " \
        "end_time VARCHAR(50) DEFAULT '', " \
        "duration int DEFAULT 0, " \
        "priority smallint DEFAULT 0, " \
        "description VARCHAR(300) DEFAULT '', " \
        "PRIMARY KEY (id), " \
        "UNIQUE (summary, date, duration, priority))"
    mycursor.execute(Q)


# Updates google calendar given an event from the sql database
def update_google_event(event):
    try:
        cal_event = service.events().get(calendarId=SHION_ID, eventId=event[0]).execute()

        start_time = event[3].split(" ")
        start_time = start_time[0] + "T" + start_time[1]
        end_time = event[4].split(" ")
        end_time = end_time[0] + "T" + end_time[1]

        cal_event['start']['dateTime'] = start_time
        cal_event['end']['dateTime'] = end_time
        updated_event = service.events().update(calendarId=SHION_ID, eventId=event[0], body=cal_event).execute()
        return True
    except Exception as e:
        print("ERR IN UPDATING GOOGLE EVENT")
        print(e)
        return False


# Creates a new event in the google calendar given an event from the sql database
def create_google_event(event):
    id = event[0]
    summary = event[1]
    description = event[7]
    start_time = event[3].split(" ")
    start_time = start_time[0] + "T" + start_time[1]
    end_time = event[4].split(" ")
    end_time = end_time[0] + "T" + end_time[1]

    cal_event = {
        'id': id,
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': TIMEZONE,
        },
        'end': {
            'dateTime': end_time,
            'timeZone': TIMEZONE,
        },
        'attendees': [
            {'email': 'tylerwong7555@gmail.com'}
        ],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 10},
            ],
        },
    }
    if event[6] <= 3:
        cal_event['reminders']['overrides'].append({'method': 'email', 'minutes': 24 * 60})

    try:
        added_event = service.events().insert(calendarId=SHION_ID, body=cal_event).execute()
        return True

    except Exception as e:
        print("ERR IN CREATING GOOGLE EVENT")
        print(e)
        return False


def update_events(index, events, end_time):
    results = events
    for i in range(index, len(results)):

        start_time = end_time + timedelta(minutes=60)
        end_time = start_time + timedelta(minutes=results[i][5])

        if (1 < end_time.hour < 13) or (end_time.hour == 1 and end_time.minute > 0):
            start_time = datetime(end_time.year, end_time.month, end_time.day, 13, 0, 0)
            end_time = start_time + timedelta(minutes=results[i][5])

        mycursor.execute(
            f"UPDATE Events SET date='{str(start_time.date())}', start_time='{str(start_time)}', end_time='{str(end_time)}' WHERE id='{results[i][0]}'")

        mycursor.execute(f"SELECT * FROM Events WHERE id='{results[i][0]}'")
        event = list(mycursor)[0]

        # Remove from database
        if not update_google_event(event):
            mycursor.execute(f"DELETE FROM Events WHERE id='{results[i][0]}'")


# Adds an event to the database and updates the start and end times of all other events appropriately
def add_event(summary, date, duration, priority, description):
    # Event will be in the form of a tuple as follows:
    # (summary, date, duration, priority)
    mycursor.execute(f"SELECT * FROM Events WHERE date='{date}' ORDER BY Priority")
    results = list(mycursor)
    id = uuid.uuid1().hex
    if len(results) == 0:
        start_time = datetime.strptime(date + " " + "13:00:00", "%Y-%m-%d %H:%M:%S")
        end_time = start_time + timedelta(minutes=duration)
    else:

        i, summ, dte, strt, end, dur, prio, desc = zip(*results)
        index = bisect.bisect(prio, priority)

        if index == len(results):
            start_time = datetime.strptime(results[index - 1][4], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=60)
        else:
            start_time = datetime.strptime(results[index][3], "%Y-%m-%d %H:%M:%S")
        end_time = start_time + timedelta(minutes=duration)

        # Check if task will be between the no task period of 1am to 1pm
        # Otherwise schedule for start of the next day
        if (1 < end_time.hour < 13) or (end_time.hour == 1 and end_time.minute > 0):
            start_time = datetime(end_time.year, end_time.month, end_time.day, 13, 0, 0)
            end_time = start_time + timedelta(minutes=duration)

        # Update later events
        update_events(index, results, end_time)

    mycursor.execute(
        "INSERT IGNORE INTO Events (id, summary, date, start_time, end_time, duration, priority, description) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (id, summary, str(start_time.date()), str(start_time), str(end_time), duration, priority, description))
    db.commit()

    # Add to Google Calendar
    mycursor.execute(f"SELECT * FROM Events WHERE id='{id}'")
    event = list(mycursor)[0]
    create_google_event(event)


def clear():
    mycursor.execute("DROP TABLE Events")
    create_events_table()


def print_events():
    print("SQL Results:")
    mycursor.execute("SELECT * FROM Events ORDER BY Priority")
    results = list(mycursor)
    print(results)


service = main()

# add_event("Event 1", "2021-06-28", 180, 5, "This is an event!")
# add_event("Event 2", "2021-06-28", 60, 1, "This is an event!")

# add_event(input("summary: "), input("date: "), int(input("duration: ")), int(input("priority: ")))
