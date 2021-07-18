from __future__ import print_function

import base64
import email
import os.path
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import time

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('email_token.json'):
        creds = Credentials.from_authorized_user_file('email_token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('email_token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)

    return service


def get_messages(service, user_id):
    try:
        results = service.users().messages().list(userId=user_id, labelIds=['INBOX']).execute()
        return results.get('messages', [])
    except Exception as error:
        print('An error occurred: %s' % error)


def get_message(service, user_id, msg_id):
    try:
        msg = service.users().messages().get(userId=user_id, id=msg_id, format='raw').execute()
        msg_raw = base64.urlsafe_b64decode(msg['raw'].encode("utf-8")).decode("utf-8")
        msg_str = email.message_from_string(msg_raw)

        full_msg = {
            "Date:": msg_str['Date'],
            "Subject": msg_str['Subject'],
            "Sender": msg_str['From'],
        }

        content_types = msg_str.get_content_maintype()

        if content_types == 'multipart':
            pt1, pt2 = msg_str.get_payload()

            payload = pt1.get_payload()

            full_msg["Body"] = payload
            return full_msg
        else:
            full_msg["Body"] = msg_str.get_payload()
            return full_msg

    except Exception as error:
        print('An error occurred: %s' % error)


def search_email(service):
    while True:
        messages = get_messages(service, "me")
        msg = get_message(service, "me", messages[0]['id'])
        print(msg)

        time.sleep(5)


def getMatchingThreads(service, userId, labelIds, query):
    """Get all threads from gmail that match the query"""

    response = service.users().threads().list(userId=userId, labelIds=labelIds,
                                              q=query).execute().get('threads', [])

    threads = []
    if response:
        threads.extend(response)

    # Do the response while there is a next page to receive.
    while 'nextPageToken' in response:
        pageToken = response['nextPageToken']
        response = service.users().threads().list(
            userId=userId,
            labelIds=labelIds,
            q=query,
            pageToken=pageToken).execute().get('threads', [])
        threads.extend(response)

    return threads


def buildSearchQuery(criteria):
    """Input is the criteria in a filter object. Iterate over it and return a
    gmail query string that can be used for thread search"""

    queryList = []
    positiveStringKeys = ["from", "to", "subject"]
    for k in positiveStringKeys:
        v = criteria.get(k)
        if v is not None:
            queryList.append("(" + k + ":" + v + ")")

    v = criteria.get("query")
    if v is not None:
        queryList.append("(" + v + ")")

    return " AND ".join(queryList)


def applyFilterToMatchingThreads(service, userId, filterObject):
    """After creating the filter we want to apply it to all matching threads
    This function searches all threads with the criteria and appends the same
    label of the filter"""

    query = buildSearchQuery(filterObject["criteria"])
    response = getMatchingThreads(service, userId, ["UNREAD"], query)

    threads = []
    for thread in response:
        threads.append(service.users().threads().get(userId=userId, id=thread['id']).execute())

    addLabels = filterObject["action"]["addLabelIds"]
    removeLabels = filterObject["action"]["removeLabelIds"]
    print("Adding labels {} to {} threads".format(addLabels, len(threads)))

    for t in threads:
        body = {
            "addLabelIds": addLabels,
            "removeLabelIds": removeLabels
        }
        service.users().threads().modify(userId=userId, id=t["id"],
                                         body=body).execute()

    return threads


def create_message(sender, to, subject, message_text, threadId):
    """Create a message for an email.

  Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.

  Returns:
    An object containing a base64url encoded email object.
  """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw_msg = base64.urlsafe_b64encode(message.as_string().encode('utf-8'))
    if threadId:
        return {'raw': raw_msg.decode('utf-8'), 'threadId': threadId}
    return {'raw': raw_msg.decode('utf-8')}

def send_message(service, user_id, message):
    """Send an email message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

  Returns:
    Sent Message.
  """
    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                   .execute())

        return message

    except Exception as error:
        print('An error occurred: %s' % error)


service = main()

# search_thread = threading.Thread(target=search_email(service))
# search_thread.start()
#
# desiredFilters = [
#     {
#         "criteria": {
#             "subject": "add event",
#         },
#         "action": {
#             "addLabelIds": [],
#             "removeLabelIds": ["UNREAD"]
#         }
#     },
# ]
#
# for df in desiredFilters:
#     threads = applyFilterToMatchingThreads(service, "me", df)
#
#     for e in threads:
#         msg = get_message(service, "me", e["messages"][-1]['id'])
#
#         # Add to SQL
#
#         # If added to SQL is done safely, confirm with sender
#
#         response = create_message("me", msg['Sender'], msg['Subject'],
#                                   "Hello, this is Shion, Tyler's Virtual Assistant. "
#                                   "Your message has been successfully scheduled! \n "
#                                   "No need to respond to this message.", e['id'])
#         send_message(service, "me", response)
