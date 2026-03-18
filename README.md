# Outreach Hub

Desktop app for B2B cold outreach:
- Import leads from CSV or scrape from Google Maps
- Score and select daily targets
- Create personalized Gmail drafts with AI (Gemini)
- Track email opens and clicks

**[Download Windows exe](https://github.com/everpoint-saas/outreach-hub/releases/latest)**

## Quick Start (exe)

1. Download and unzip the release folder
2. Run `OutreachHub.exe`
3. Open the **Setup** tab and fill in your info:
   - Gmail credentials file (OAuth JSON)
   - Gemini API key (for AI personalization, optional)
   - Sender profile (name, company, LinkedIn, etc.)
   - Product info (what you're selling)
4. Click **Save Setup** - settings apply immediately

That's it. No Python, no terminal, no installs.

## Getting API Keys

### Gmail (Required)

You need a Google OAuth credentials file to create Gmail drafts.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Go to **APIs & Services > Enabled APIs** and enable the **Gmail API**
4. Go to **APIs & Services > Credentials**
5. Click **Create Credentials > OAuth client ID**
6. Choose **Desktop app** as the application type
7. Download the JSON file and save it to the `secrets/` folder
8. In the app's Setup tab, set the path to this file

The first time you connect Gmail, a browser window will open to authorize access. After that, a token is saved locally so you don't need to log in again.

### Gemini API Key (Optional, for AI personalization)

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Click **Create API Key**
3. Copy the key and paste it in the Setup tab

This is optional. Without it, emails use your template as-is. With it, each email gets a personalized opening line.

### MillionVerifier (Optional, for email verification)

1. Go to [MillionVerifier](https://www.millionverifier.com/)
2. Sign up and get an API key from your dashboard
3. Paste it in the Setup tab

This is optional. It verifies that email addresses are real before you send.

## How to Use

Use the tabs in order:

| Step | Tab | What to do |
|------|-----|------------|
| 1 | **Setup** | Save your keys and sender info |
| 2 | **Data Editor** | Load a CSV and click "Import to Leads DB" |
| 3 | **Google Maps** | (Optional) Scrape leads by keyword and location |
| 4 | **Pipeline & Targets** | Score leads, verify emails, select daily targets |
| 5 | **Mailing (Gmail)** | Connect Gmail and create drafts |
| 6 | **History** | Track sent emails, mark replies |

## CSV Import

You can import a CSV with any column names. The importer will ask you to map columns before saving.

Common columns:
`company`, `email`, `phone`, `website`, `contact person`, `title`, `city`, `state`, `country`, `score`

## Google Maps Scraper (Optional Setup)

The Google Maps scraper requires a browser engine. If you want to use it, open a terminal and run:

```
pip install playwright
playwright install chromium
```

All other features work without this.

## Running from Source (Developers)

```bash
pip install -r requirements.txt
python main.py
```

## File Structure

```
OutreachHub/
  OutreachHub.exe      # Main application
  _internal/           # Runtime dependencies (do not modify)
  secrets/             # Place Gmail credentials here
  data/                # SQLite database (auto-created)
  .env.example         # Template for manual config (optional)
```

## Configuration

All settings are managed through the **Setup** tab in the app. No need to edit files manually.

For advanced users: settings are stored in `.env` and can be edited directly.

## Privacy

- All data stays on your machine (SQLite database in `data/`)
- Gmail drafts are created locally via OAuth - emails are never sent automatically
- No data is sent to any server except Gmail API and Gemini API (if enabled)

## Disclaimer

This tool is provided for legitimate business outreach purposes only. Users are responsible for compliance with applicable laws including CAN-SPAM, GDPR, and platform terms of service.
