import datetime

import scheduling as sc
import gmail_management as gm
import threading
import time

gmail_service = gm.service
cal_service = sc.service


def main():
    desiredFilters = [
        {
            "criteria": {
                "subject": "add event",
            },
            "action": {
                "addLabelIds": [],
                "removeLabelIds": ["UNREAD"]
            }
        },
    ]

    for df in desiredFilters:
        threads = gm.applyFilterToMatchingThreads(gmail_service, "me", df)

        for e in threads:
            response_txt = "Hello, this is Shion, Tyler's Virtual Assistant. " \
                           "Your message has been successfully scheduled! \n " \
                           "No need to respond to this message."

            msg = gm.get_message(gmail_service, "me", e["messages"][0]['id'])
            print(msg['Body'])
            # Check if body is formatted correctly
            event = msg['Body'].split('\r\n')

            formatted = True

            try:
                summary = event[0][:100] if len(event[0]) > 100 else event[0]

                datetime.datetime.strptime(event[1], "%Y-%m-%d")
                date = event[1]

                duration = int(event[2])
                priority = int(event[3])

                description = event[4][:300] if len(event[4]) > 300 else event[4]
            except Exception as error:
                formatted = False
                print(error)

            if not formatted:
                response_txt = "Hello, this is Shion, Tyler's Virtual Assistant. " \
                               "There was an error processing your request.\n" \
                               "The event email should be formatted as follows: " \
                               "'Event Title' (max 100 characters)\n" \
                               "[Date] (YYYY-MM-DD)\n" \
                               "[Duration] (number in minutes)\n" \
                               "[Priority] (number between 1 and 10, 1 being the highest priority)" \
                               "\nDo not respond to this message."
            else:
                # Add to SQL
                try:
                    sc.add_event(summary, date, duration, priority, description)
                    sc.print_events()
                except Exception as error:
                    response_txt = "Hello, this is Shion, Tyler's Virtual Assistant. " \
                                   "There was an error processing your request, however" \
                                   "I've notified Tyler to add it to his calendar manually." \
                                   "\nNo need to respond to this message."
                    personal_msg = gm.create_message("me", "me", "Failed to add event",
                                                     "Error in adding event. Please schedule the following information "
                                                     "manually:\n Title: {}\n Date: {}\n Duration: {}\n Priority: {}\n",
                                                     None)
                    gm.send_message(gmail_service, "me", personal_msg)
                    continue

            # If added to SQL is done safely, confirm with sender

            response = gm.create_message("me", msg['Sender'], msg['Subject'], response_txt, e['id'])
            gm.send_message(gmail_service, "me", response)

    time.sleep(3600)


main()
# Start main thread
main_thread = threading.Thread(target=main())
main_thread.start()
