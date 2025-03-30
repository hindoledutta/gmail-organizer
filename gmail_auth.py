import os.path
import pickle
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define the Gmail read scope
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def authenticate_gmail():
    creds = None

    # Load saved credentials if available
    if os.path.exists('token.pkl'):
        with open('token.pkl', 'rb') as token:
            creds = pickle.load(token)

    # If not available or expired, run the OAuth flow
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=8000)
        # Save credentials for future use
        with open('token.pkl', 'wb') as token:
            pickle.dump(creds, token)

    # Build the Gmail API service
    service = build('gmail', 'v1', credentials=creds)
    return service

if __name__ == '__main__':
    service = authenticate_gmail()

    # Test: Fetch labels to confirm it worked
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    print("✅ Gmail Authenticated. Found labels:")
    for label in labels:
        print(f"- {label['name']}")
