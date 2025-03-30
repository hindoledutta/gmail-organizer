import os
import pickle
import json
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def authenticate_gmail():
    creds = None

    # Use token.json or token.pkl depending on your setup
    if os.path.exists("token.pkl"):
        with open("token.pkl", "rb") as token:
            creds = pickle.load(token)

    # If no (valid) token, authenticate manually
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Load the credentials file (already available as a Secret File in Render)
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)

            if os.environ.get("RENDER") == "true":
                raise Exception(
                    "This app is running on Render, but token.pkl is missing or invalid.\n"
                    "Please authenticate locally and upload token.pkl as a Render Secret File."
                )
            else:
                creds = flow.run_local_server(port=8000)

        # Save token for future use
        with open("token.pkl", "wb") as token:
            pickle.dump(creds, token)

    return creds
