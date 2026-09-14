from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

flow = InstalledAppFlow.from_client_secrets_file(
    "oauth_client.json",
    SCOPES
)

credentials = flow.run_local_server(
    port=0,
    access_type="offline",
    prompt="consent"
)

with open("token.json", "w") as token:
    token.write(credentials.to_json())

print("Google Drive authorization successful.")
print("token.json has been created.")