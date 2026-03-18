import os.path
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config

# Scopes required for the application
SCOPES = [
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly' # Optional, for checking history if needed
]

class GmailSender:
    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        self.credentials_path = credentials_path or config.GMAIL_CREDENTIALS_PATH
        self.token_path = token_path or config.GMAIL_TOKEN_PATH
        self.service = None
        self.creds = None

    def authenticate(self, silent=False):
        """Authenticates the user. If silent=True, only tries existing token/refresh without launching browser."""
        self.creds = None
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                self.creds = None

        if not self.creds or not self.creds.valid:
            if silent:
                return False # Silent fail

            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(f"Could not find {self.credentials_path}.")

            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
            self.creds = flow.run_local_server(port=0)

            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())

        try:
            self.service = build('gmail', 'v1', credentials=self.creds, cache_discovery=False)
            return True
        except Exception as e:
            print(f"Service build failed: {e}")
            return False

    def get_profile(self):
        """Returns the user's email address if authenticated."""
        if not self.service:
            return None
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile['emailAddress']
        except Exception as e:
            print(f"Error getting profile: {e}")
            return None

    def create_message(self, to_email: str, subject: str, body_text: str, body_html: Optional[str] = None):
        """Create a message for an email."""
        message = MIMEMultipart()
        message['to'] = to_email
        message['subject'] = subject

        if body_html:
            # multipart/alternative-like body for better client compatibility
            alt = MIMEMultipart('alternative')
            alt.attach(MIMEText(body_text, 'plain'))
            alt.attach(MIMEText(body_html, 'html'))
            message.attach(alt)
        else:
            msg = MIMEText(body_text, 'plain')
            message.attach(msg)

        # Encode the message in base64url format
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return {'raw': raw_message}

    def create_draft(self, to_email: str, subject: str, body_text: str, body_html: Optional[str] = None):
        """Create a draft email."""
        if not self.service:
            print("Not authenticated.")
            return None

        try:
            message_body = self.create_message(to_email, subject, body_text, body_html=body_html)
            draft = {'message': message_body}
            draft_response = self.service.users().drafts().create(userId='me', body=draft).execute()
            print(f"Draft id: {draft_response['id']} created.")
            return draft_response
        except HttpError as error:
            print(f"An error occurred creating draft: {error}")
            return None

    def send_email(self, to_email: str, subject: str, body_text: str, body_html: Optional[str] = None):
        """Send an email immediately."""
        if not self.service:
            print("Not authenticated.")
            return None

        try:
            message_body = self.create_message(to_email, subject, body_text, body_html=body_html)
            message = self.service.users().messages().send(userId='me', body=message_body).execute()
            print(f"Message Id: {message['id']} sent.")
            return message
        except HttpError as error:
            print(f"An error occurred sending message: {error}")
            return None
