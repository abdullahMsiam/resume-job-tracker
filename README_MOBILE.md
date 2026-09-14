# Job Application Resume Automation

This version keeps the original terminal workflow and adds a mobile-friendly web interface.

## 1. Local terminal mode

Keep these files together:

- `app.py`
- `resume_template.html`
- `credentials.json`

Install:

```bash
pip install -r requirements.txt
playwright install chromium
```

Run the original terminal workflow:

```bash
python app.py
```

## 2. Local phone/web mode

Run:

```bash
python app.py --web
```

Then open the computer's local/network URL from your phone if both devices can reach the computer.

## 3. Cloud deployment

Recommended setup:

- Put the project in GitHub.
- Deploy as a Python web service.
- Use the included `render.yaml` or configure the same commands manually.
- Do NOT commit `credentials.json`.

Set these environment variables/secrets:

### GOOGLE_SERVICE_ACCOUNT_JSON
Paste the complete JSON contents of your Google service-account key.

### DRIVE_FOLDER_ID
The ID of the Google Drive folder where generated resumes should be uploaded.

The folder should be accessible to the service account.

### DRIVE_SHARE_EMAIL (recommended)
Your Google account email. The generated PDF will be shared with this account as a reader.

### FLASK_SECRET_KEY
A long random secret. Render can generate it automatically.

## Important

`credentials.json` contains a private service-account key. Never commit it to GitHub.

The core resume generation and Google Sheet logic is shared by terminal and web modes so they use the same workflow.
