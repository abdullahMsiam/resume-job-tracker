import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from jinja2 import Template
from playwright.sync_api import sync_playwright

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
    comment=""
):
    # ১. HTML টেমপ্লেট লোড
    with open("resume_template.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # ২. ডায়নামিক ডেটা রিপ্লেস
    template = Template(template_content)
    rendered_html = template.render(
        job_position=job_position,
        career_objective=career_objective
    )

    # ৩. Playwright দিয়ে PDF তৈরি
    if not os.path.exists("generated_resumes"):
        os.makedirs("generated_resumes")
        
    pdf_filename = f"generated_resumes/AbdullahMSiam_{company_name}_{job_position}.pdf"
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(rendered_html)
        page.pdf(
            path=pdf_filename,
            format="A4",
            print_background=True,
            margin={"top": "0in", "bottom": "0in", "left": "0in", "right": "0in"}
        )
        browser.close()
        
    print(f"\n✅ PDF তৈরি সম্পন্ন: {pdf_filename}")

    # ৪. Google Sheet-এ ফরম্যাটিং রক্ষা করে এন্ট্রি দেওয়া
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
    
        sheet = client.open("Abdullah Muhammad Siam -Job tracker").sheet1
        
        # আগের রো-গুলোর তারিখের সাথে মিলিয়ে ফরম্যাটিং (যেমন: 10, September)
        today = datetime.now().strftime("%d, %B").lstrip("0")

        # Job link-কে ক্লিকঅ্যাবল সূত্র হিসেবে কনভার্ট করা
        formatted_job_link = f'=HYPERLINK("{job_link}", "{job_link}")'

        row_data = [
            today,                 # 1. Date (e.g. 10, September)
            company_name,          # 2. Company
            job_position,          # 3. Position
            pdf_filename,          # 4. Resume Drive
            job_nature,            # 5. Job Nature
            job_type,              # 6. Job Type
            company_location,      # 7. Company Location
            formatted_job_link,    # 8. Job link (clickable)
            job_status,            # 9. Job status
            how_applied,           # 10. How Applied
            comment                # 11. Comment
        ]

        # বিদ্যমান ব্যবহৃত রোর সংখ্যা বের করা
        existing_rows = len(sheet.get_all_values())
        next_row = existing_rows + 1

        # ১. নতুন খালি রো ইনসার্ট করা
        sheet.insert_row(row_data, index=next_row, value_input_option="USER_ENTERED")

        # ২. ড্রপডাউন চিপস ও সেল ফরম্যাটিং রক্ষা করা (২ নম্বর সারির ফরম্যাট নতুন সারিতে কপি করা)
        # গুগল স্প্রেডশিট API দিয়ে ২ নম্বর রোর Data Validation (Dropdown) কপি করে নতুন রোতে পেস্ট
        sheet.copy_range(
            f"A2:K2", 
            f"A{next_row}:K{next_row}", 
            paste_type="PASTE_FORMAT"
        )

        print(f"✅ Google Sheet-এর {next_row} নম্বর সারিতে সঠিক ফরম্যাটে তথ্য যুক্ত করা হয়েছে!")
        
    except Exception as e:
        print(f"❌ Google Sheet আপডেট ব্যর্থ: {e}")

def get_input(prompt, default=""):
    if default:
        val = input(f"{prompt} (Default: '{default}'): ").strip()
        return val if val else default
    else:
        val = input(f"{prompt}: ").strip()
        while not val:
            print("⚠️ এটি আবশ্যক ফিল্ড!")
            val = input(f"{prompt}: ").strip()
        return val

if __name__ == "__main__":
    print("--- Job Application Automation ---")
    company = get_input("Company Name")
    position = get_input("Job Position (e.g. Software Engineer)")
    job_link = get_input("Job Link")
    
    print("\nCareer Objective:")
    objective = input("> ").strip()
    while not objective:
        objective = input("> ").strip()

    print("\n--- Options ---")
    job_nature = get_input("Job Nature [Full time / Internship / Constructual]", default="Full time")
    job_type = get_input("Job Type [Remote / Onsite / Hybrid]", default="Remote")
    location = input("Company Location (Optional): ").strip()
    how_applied = get_input("How Applied [email / google form]", default="email")
    comment = input("Comment (Optional): ").strip()

    generate_pdf_and_sheet(
        company_name=company,
        job_position=position,
        career_objective=objective,
        job_link=job_link,
        job_nature=job_nature,
        job_type=job_type,
        company_location=location,
        job_status="no response",
        how_applied=how_applied,
        comment=comment
    )