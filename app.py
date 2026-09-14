import os
import json
import re
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from jinja2 import Template
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from playwright.sync_api import sync_playwright

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")



BASE_DIR = Path(__file__).resolve().parent
RESUME_TEMPLATE = BASE_DIR / "resume_template.html"
GENERATED_DIR = BASE_DIR / "generated_resumes"
GENERATED_DIR.mkdir(exist_ok=True)

SHEET_NAME = "Abdullah Muhammad Siam -Job tracker"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")


def safe_filename(value: str) -> str:
    """Make company/position safe for a filename without changing displayed data."""
    value = str(value).strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] or "Unknown"


def get_google_credentials():
    """
    Cloud:
      GOOGLE_SERVICE_ACCOUNT_JSON = complete JSON string

    Local/terminal:
      credentials.json next to this file
    """
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if raw_json:
        try:
            info = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    credential_file = BASE_DIR / "credentials.json"
    if credential_file.exists():
        return Credentials.from_service_account_file(
            str(credential_file), scopes=SCOPES
        )

    raise RuntimeError(
        "Google credentials not found. Put credentials.json beside app.py "
        "for local use, or set GOOGLE_SERVICE_ACCOUNT_JSON on the server."
    )


def generate_pdf(company_name, job_position, career_objective):
    """Generate the resume PDF using the existing resume template."""
    if not RESUME_TEMPLATE.exists():
        raise FileNotFoundError(f"Missing resume_template.html: {RESUME_TEMPLATE}")

    with RESUME_TEMPLATE.open("r", encoding="utf-8") as f:
        template_content = f.read()

    template = Template(template_content)
    rendered_html = template.render(
        job_position=job_position,
        career_objective=career_objective,
    )

    pdf_filename = (
        GENERATED_DIR
        / f"AbdullahMSiam_{safe_filename(company_name)}_{safe_filename(job_position)}.pdf"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(rendered_html)
            page.pdf(
                path=str(pdf_filename),
                format="A4",
                print_background=True,
                margin={
                    "top": "0in",
                    "bottom": "0in",
                    "left": "0in",
                    "right": "0in",
                },
            )
        finally:
            browser.close()

    return pdf_filename


def upload_pdf_to_drive(pdf_path: Path):
    """
    Upload the generated PDF to Google Drive.

    Recommended production setup:
      DRIVE_FOLDER_ID = a Google Drive folder shared with the service account.
    Optional:
      DRIVE_SHARE_EMAIL = your Google account email. If set, the uploaded
      file is explicitly shared with that account as a reader.
    """
    folder_id = os.environ.get("DRIVE_FOLDER_ID")
    share_email = os.environ.get("DRIVE_SHARE_EMAIL")

    # Drive upload is optional. If no folder is configured, the system still
    # generates the PDF and updates the sheet with the local/server path.
    if not folder_id:
        return None

    creds = get_google_credentials()
    drive = build("drive", "v3", credentials=creds)

    metadata = {
        "name": pdf_path.name,
        "mimeType": "application/pdf",
        "parents": [folder_id],
    }

    media = MediaFileUpload(str(pdf_path), mimetype="application/pdf", resumable=True)

    uploaded = (
        drive.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    file_id = uploaded["id"]

    if share_email:
        drive.permissions().create(
            fileId=file_id,
            body={
                "type": "user",
                "role": "reader",
                "emailAddress": share_email,
            },
            sendNotificationEmail=False,
            supportsAllDrives=True,
        ).execute()

    # webViewLink is returned by Drive when available. Construct a stable
    # fallback if the API does not return it.
    return uploaded.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"


def update_google_sheet(
    company_name,
    job_position,
    job_link,
    pdf_reference,
    job_nature="Full time",
    job_type="Remote",
    company_location="",
    job_status="no response",
    how_applied="email",
    comment="",
):
    """Preserve the existing Google Sheet workflow and formatting behavior."""
    creds = get_google_credentials()
    client = gspread.authorize(creds)

    sheet = client.open(SHEET_NAME).sheet1

    today = datetime.now().strftime("%d, %B").lstrip("0")

    # Keep the existing clickable job-link behavior.
    escaped_job_link = str(job_link).replace('"', '""')
    formatted_job_link = f'=HYPERLINK("{escaped_job_link}", "{escaped_job_link}")'

    row_data = [
        today,
        company_name,
        job_position,
        pdf_reference,
        job_nature,
        job_type,
        company_location,
        formatted_job_link,
        job_status,
        how_applied,
        comment,
    ]

    existing_rows = len(sheet.get_all_values())
    next_row = existing_rows + 1

    sheet.insert_row(
        row_data,
        index=next_row,
        value_input_option="USER_ENTERED",
    )

    # Preserve the existing formatting-copy behavior.
    sheet.copy_range(
        "A2:K2",
        f"A{next_row}:K{next_row}",
        paste_type="PASTE_FORMAT",
    )

    return next_row


def generate_pdf_and_sheet(
    company_name,
    job_position,
    career_objective,
    job_link,
    job_nature="Full time",
    job_type="Remote",
    company_location="",
    job_status="no response",
    how_applied="email",
    comment="",
):
    """
    Shared core used by BOTH terminal and phone/web interfaces.

    This is intentionally kept as the single source of truth so the two
    interfaces cannot slowly develop different resume/sheet behavior.
    """
    pdf_path = generate_pdf(
        company_name=company_name,
        job_position=job_position,
        career_objective=career_objective,
    )

    # On cloud, upload the PDF to Drive. Locally, if DRIVE_FOLDER_ID is not
    # configured, preserve the old local-path behavior.
    drive_url = upload_pdf_to_drive(pdf_path)
    pdf_reference = drive_url if drive_url else str(pdf_path.relative_to(BASE_DIR))

    try:
        next_row = update_google_sheet(
            company_name=company_name,
            job_position=job_position,
            job_link=job_link,
            pdf_reference=pdf_reference,
            job_nature=job_nature,
            job_type=job_type,
            company_location=company_location,
            job_status=job_status,
            how_applied=how_applied,
            comment=comment,
        )
    except Exception:
        # Do not hide the original sheet error from the caller.
        raise

    return pdf_path, drive_url, next_row


def get_input(prompt, default=""):
    """Original terminal input behavior, retained for backward compatibility."""
    if default:
        val = input(f"{prompt} (Default: '{default}'): ").strip()
        return val if val else default

    val = input(f"{prompt}: ").strip()
    while not val:
        print("⚠️ এটি আবশ্যক ফিল্ড!")
        val = input(f"{prompt}: ").strip()
    return val


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/generate")
def generate_from_web():
    company = request.form.get("company_name", "").strip()
    position = request.form.get("job_position", "").strip()
    job_link = request.form.get("job_link", "").strip()
    objective = request.form.get("career_objective", "").strip()

    job_nature = request.form.get("job_nature", "Full time").strip() or "Full time"
    job_type = request.form.get("job_type", "Remote").strip() or "Remote"
    location = request.form.get("company_location", "").strip()
    how_applied = request.form.get("how_applied", "email").strip() or "email"
    comment = request.form.get("comment", "").strip()

    if not company or not position or not job_link or not objective:
        flash("Company, Position, Job Link এবং Career Objective অবশ্যই দিতে হবে।", "error")
        return redirect(url_for("index"))

    try:
        pdf_path, drive_url, next_row = generate_pdf_and_sheet(
            company_name=company,
            job_position=position,
            career_objective=objective,
            job_link=job_link,
            job_nature=job_nature,
            job_type=job_type,
            company_location=location,
            job_status="no response",
            how_applied=how_applied,
            comment=comment,
        )

        return render_template(
            "success.html",
            pdf_name=pdf_path.name,
            drive_url=drive_url,
            sheet_row=next_row,
        )

    except Exception as exc:
        app.logger.exception("Resume generation failed")
        flash(f"কাজটি সম্পন্ন হয়নি: {exc}", "error")
        return redirect(url_for("index"))


@app.get("/download/<path:filename>")
def download_pdf(filename):
    # Only serve files from the generated directory.
    requested = (GENERATED_DIR / filename).resolve()
    if GENERATED_DIR.resolve() not in requested.parents:
        return "Invalid file path", 400
    if not requested.is_file():
        return "File not found", 404
    return send_file(requested, as_attachment=True)


def run_terminal():
    """The original terminal workflow."""
    print("--- Job Application Automation ---")

    company = get_input("Company Name")
    position = get_input("Job Position (e.g. Software Engineer)")
    job_link = get_input("Job Link")

    print("\nCareer Objective:")
    objective = input("> ").strip()
    while not objective:
        objective = input("> ").strip()

    print("\n--- Options ---")
    job_nature = get_input(
        "Job Nature [Full time / Internship / Constructual]",
        default="Full time",
    )
    job_type = get_input(
        "Job Type [Remote / Onsite / Hybrid]",
        default="Remote",
    )
    location = input("Company Location (Optional): ").strip()
    how_applied = get_input(
        "How Applied [email / google form]",
        default="email",
    )
    comment = input("Comment (Optional): ").strip()

    pdf_path, drive_url, next_row = generate_pdf_and_sheet(
        company_name=company,
        job_position=position,
        career_objective=objective,
        job_link=job_link,
        job_nature=job_nature,
        job_type=job_type,
        company_location=location,
        job_status="no response",
        how_applied=how_applied,
        comment=comment,
    )

    print(f"\n✅ PDF তৈরি সম্পন্ন: {pdf_path}")
    if drive_url:
        print(f"✅ Google Drive: {drive_url}")
    print(f"✅ Google Sheet-এর {next_row} নম্বর সারিতে তথ্য যুক্ত করা হয়েছে!")


if __name__ == "__main__":
    # Use: python app.py
    # Or:  python app.py --web
    import sys

    if "--web" in sys.argv:
        # Local web mode. For cloud platforms, use their normal WSGI command:
        # gunicorn app:app
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
    else:
        run_terminal()
