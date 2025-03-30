import os
import json
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def authenticate_gmail():
    creds = None

    # ✅ Load from token.json
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # 🔁 If missing or expired, refresh or re-auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # ⛔ On Render, bail out if token is missing
            if os.environ.get("RENDER") == "true":
                raise Exception("Missing token.json in Render. Upload it as a Secret File.")

            # ✅ Local: trigger login
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8000, prompt='consent')

        # 💾 Save token for future use
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    # ✅ Return Gmail API service object
    return build("gmail", "v1", credentials=creds)
