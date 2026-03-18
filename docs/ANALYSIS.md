# Lead Generator Pro - Comprehensive Analysis

> Reviewed: 2026-02-09
> Scope: All files in `C:\Users\gnt85\mailing_list\`

---

## 1. Architecture Overview

### Data Pipeline

```
[Scraping]          [Processing]          [Outreach]

Google Maps    -->  process_leads.py  -->  crawl_emails.py  -->  Gemini AI  -->  Gmail Drafts
  Scraper             (pipeline)          (email finder)      (personalize)     (send)

LinkedIn       -->       |                     |                    |               |
  X-Ray                  v                     v                    v               v
                   Raw CSV merge         today_targets.csv     AI intro/full    Draft creation
                   Dedup                 + Email column         email gen        + sent_log.csv
                   Blacklist
                   Score
                   Daily targets
```

### File Map (16 files)

| File | Lines | Role |
|------|-------|------|
| `main.py` | 15 | PySide6 app entry point |
| `google_maps_scraper.py` | 310 | Google Maps scraping (Playwright + Edge) |
| `linkedin_xray_scraper.py` | 340 | LinkedIn X-Ray via Google search |
| `process_leads.py` | 275 | Lead processing pipeline (dedup, score, targets) |
| `crawl_emails.py` | 391 | Email crawler (regex + Playwright + Gemini AI) |
| `gemini_helper.py` | 207 | Gemini AI integration (intro, full email, extraction) |
| `gmail_sender.py` | 112 | Gmail API (OAuth2, drafts, send) |
| `mark_sent.py` | 222 | History tracking (interactive + batch) |
| `us_cities.py` | ~55 | Top 50 US cities list |
| `gui/main_window.py` | 1361 | Main GUI window (6 tabs, all UI logic) |
| `gui/tab_mailing.py` | 490 | Mailing tab (templates, AI config, draft worker) |
| `gui/workers.py` | 182 | QThread workers (scraper, pipeline, crawler, smart hunt) |
| `gui/dialogs.py` | ~100 | Scoring/Blacklist editor dialogs |
| `gui/styles.py` | ~150 | Dark/Light theme QSS |
| `discord_admin_bot.py` | ~200 | Discord CS channel setup bot (separate utility) |
| `requirements.txt` | ~25 | Dependencies (has duplicates) |

### Data Directory Structure

```
data/
  raw/               # Raw scraped CSVs (google_maps_*.csv, linkedin_*.csv)
  processed/         # Scored leads after pipeline (scored_leads_YYYYMMDD.csv)
  output/            # today_targets.csv (daily target list)
  history/           # sent_log.csv + per-date draft history folders
```

---

## 2. Component Analysis

### 2.1 Google Maps Scraper (EFFECTIVE)

**How it works**:
1. Playwright launches Edge browser
2. Searches Google Maps with keywords + location
3. Scrolls result feed to load more items
4. Clicks each item to extract website URL from detail panel (`data-item-id="authority"`)
5. Parses raw text for phone, address, rating, reviews
6. Saves to `data/raw/google_maps_TIMESTAMP.csv`

**Strengths**:
- Extracts **website URLs** directly (critical for email crawling)
- Gets phone numbers, ratings, reviews (useful for scoring)
- CAPTCHA detection with auto-switch from headless to visible mode
- Pause/resume/stop support via `ScraperState`
- Top 50 US cities loop for broad scraping
- Detail panel click for accurate website extraction

**Weaknesses**:
- Scroll termination relies on fixed count (3 scrolls), not "no more results" detection
- No stale result count tracking (could miss or over-scroll)
- Google Maps UI selector changes can break parsing silently
- `os` import at line 298 inside function body (should be at top)

**Data Quality** (from actual data):
```
Typical row:
  Company: "YEC Engineering"
  Website: (extracted from detail panel)
  Phone: "646-248-6788"
  Rating: 5.0, Reviews: 5
  -> HAS website + phone -> email crawlable -> CAN send cold email
```

**Verdict**: Core pipeline component. Works well for finding LEED consultants with contact info.

---

### 2.2 LinkedIn X-Ray Scraper (INEFFECTIVE)

**How it works**:
1. Playwright launches Edge browser
2. Searches Google with `site:linkedin.com/in/ "LEED AP BD+C" "United States"`
3. Parses Google search results (title text split by " - ")
4. Extracts Name, Title, Company, LinkedIn URL
5. Saves to `data/raw/linkedin_TIMESTAMP.csv`

**Critical Problems**:

#### Problem 1: No Email Addresses
LinkedIn profiles do NOT expose email addresses publicly. The scraper collects:
- Name
- Title
- Company (often "Unknown")
- LinkedIn URL

But **none of these lead to an email**. The email crawler requires a `Website` column, which LinkedIn data doesn't have.

**Actual data proof** (from `linkedin_20260105_143337.csv`):
```csv
Name,Title,Company,LinkedIn_URL
Mary Ellen Mika,"Director, Sustainability / Global ESG ...",Unknown,https://www.linkedin.com/in/mary-ellen-mika-a163136
Sarah Volkman,Sustainability Director,Unknown,https://www.linkedin.com/in/volkmansarah
Autumn Fox,Global Sustainability Director at Mars,Unknown,https://www.linkedin.com/in/autumn-fox
```

- 59 leads scraped
- Company = "Unknown" for most (Google search result titles don't consistently include company)
- No Website column
- No Email column
- No Phone column

#### Problem 2: Company Field Unreliable
The title parsing logic `parts = title_text.split(" - ")` is fragile:
```python
name = parts[0].strip()       # "Mary Ellen Mika"
title_role = parts[1].strip()  # "Director, Sustainability"
company = parts[2].strip()     # "LinkedIn" -> filtered to "Unknown"
```
Google search result titles for LinkedIn profiles don't follow a consistent format. The third segment is often "LinkedIn" itself, which gets filtered to "Unknown".

#### Problem 3: No Path to Outreach
Without email or website, LinkedIn leads enter the pipeline but **cannot be contacted**:
1. Pipeline scores them (minimum score of 2 guaranteed for LinkedIn leads)
2. They get selected as daily targets
3. Email crawler skips them (no Website column)
4. Mailing tab skips them (no Email)

They consume target slots that could go to Google Maps leads that CAN be contacted.

#### Problem 4: Google CAPTCHA Risk
X-Ray scraping hits Google Search directly (not Google Maps), which is more aggressive about CAPTCHAs. This means:
- More frequent CAPTCHA interruptions
- Risk of IP being flagged for all Google services (including Maps scraping)

**Verdict**: LinkedIn X-Ray produces leads that **cannot be used** in the current pipeline. It wastes daily target slots and increases CAPTCHA risk. Recommend removing from default workflow.

---

### 2.3 Pipeline (process_leads.py) - SOLID

**How it works**:
1. Loads all CSVs from `data/raw/`
2. Splits by source (Google Maps vs LinkedIn)
3. Dedup: Google Maps by company name, LinkedIn by URL
4. Blacklist filter (yelp, glassdoor, etc.)
5. History exclusion (already contacted)
6. Keyword scoring (leed=3, sustainab=2, etc.)
7. Minimum score filter (>= 2)
8. Balanced output: 50/50 split between sources, up to 15/day

**Strengths**:
- Clean separation of concerns
- Good scoring system with configurable keywords
- History exclusion prevents re-contacting
- Source-balanced daily targets

**Issues**:
- LinkedIn leads get guaranteed minimum score of 2 (line 147) even if irrelevant
- 50/50 source balancing wastes slots on unusable LinkedIn leads
- `normalize_company()` is duplicated in both `process_leads.py` and `mark_sent.py`
- No timestamp-based data staleness check (old raw CSVs accumulate)

---

### 2.4 Email Crawler (crawl_emails.py) - GOOD

**How it works**:
1. `crawl_site()`: Visit homepage -> regex extract emails -> find contact/about pages -> extract more
2. `smart_hunt_email()`: Playwright + Gemini AI fallback for hard-to-find emails
3. Obfuscated email detection (e.g., "name [at] domain [dot] com")
4. Priority: info@, contact@, hello@, support@ emails preferred

**Strengths**:
- Multi-strategy approach (regex -> subpage crawl -> AI)
- Resource blocking for speed (only loads document/script/xhr)
- `mailto:` link parsing
- Auto-save every 5 rows (crash protection)
- Smart email prioritization

**Issues**:
- `smart_hunt_email()` creates new Playwright browser per call (expensive)
- No email validation (MX record check, SMTP verify)
- Broad exception handling (`except Exception as e: pass`)
- `STOP_REQUESTED` global variable is not thread-safe

---

### 2.5 Gemini Integration (gemini_helper.py) - FUNCTIONAL

**Three functions**:
1. `generate_intro()`: 15-word personalized opener
2. `extract_email_from_text()`: AI email finder from website text
3. `generate_full_email()`: Complete email with Subject/Body

**Issues**:
- Model hardcoded: `gemini-2.5-flash` (should be configurable)
- API key stored in plaintext file (`gemini_api.txt`)
- All errors caught as generic `Exception`, no rate limit handling
- `generate_intro()` has fallback for >25 words but returns generic template
- `generate_full_email()` has sender info hardcoded (name, company, domain, LinkedIn)

---

### 2.6 Gmail Integration (gmail_sender.py) - CLEAN

**Strengths**:
- Clean OAuth2 flow with token caching
- Silent auth mode for auto-login
- Separate `create_draft()` and `send_email()` methods
- Profile retrieval for UI display

**Issues**:
- Token refresh failure returns `False` with no clear message to user
- No rate limiting on API calls
- No HTML email support (plaintext only via `MIMEText('plain')`)

---

### 2.7 GUI (main_window.py) - NEEDS REFACTORING

**1361 lines** containing all 6 tabs' logic (except Mailing which is separated).

**Strengths**:
- Feature-rich: scraping, pipeline, data editing, smart hunt, mailing
- Dark/Light theme toggle
- Ctrl+Click URL opening in Data Editor
- Real-time log output from workers

**Issues**:
- God Object: one file handles 5 tabs' worth of UI + logic
- Only `tab_mailing.py` is extracted; Google Maps, LinkedIn, Pipeline, History, Data Editor tabs are all inline
- Some UI state management is fragile (e.g., `active_targets_df` shared attribute)

---

## 3. Bugs Found

| # | Severity | File | Description |
|---|----------|------|-------------|
| B1 | Medium | `requirements.txt` | Duplicate packages: playwright x2, google-auth-httplib2 x3, google-api-python-client x2 |
| B2 | Low | `google_maps_scraper.py:298` | `import os` inside function body (should be at module top) |
| B3 | Medium | `crawl_emails.py:224` | `STOP_REQUESTED` global variable not thread-safe |
| B4 | Low | `crawl_emails.py:66` | `.io` in junk_extensions filters out valid `.io` domain emails |
| B5 | Medium | `process_leads.py:147` | LinkedIn leads get guaranteed score=2, inflating their ranking |
| B6 | Low | `gemini_helper.py:111` | Python comment syntax `# Increase limit` inside f-string text gets sent to AI |
| B7 | Medium | `tab_mailing.py:453` | `self.sender()` tries to call `QWidget.sender()` which may crash |
| B8 | Low | `linkedin_xray_scraper.py:7` | Imports `ScraperState` from `google_maps_scraper` (tight coupling) |

---

## 4. Security Considerations

| Item | Status | Notes |
|------|--------|-------|
| Gemini API key | Plaintext file (`gemini_api.txt`) | Low risk for local desktop app, but `.gitignore` should exclude |
| Gmail credentials | `credentials.json` + `token.json` | Standard Google OAuth2 flow, tokens cached locally |
| Debug files | 12 debug screenshots/HTML dumps in root dir | Should be in a `debug/` folder or auto-cleaned |
| User-Agent strings | Hardcoded generic Chrome UA | Standard practice for scraping |

---

## 5. Actual Data Assessment

### Google Maps (5 raw files, ~200 total leads)
- Companies with websites: ~70% (email crawlable)
- Companies with phones: ~60%
- Average rating available: ~50%
- **Actionable leads** (has website or phone): ~75%

### LinkedIn (2 raw files, ~107 total leads)
- Company = "Unknown": ~80%
- Has website: 0%
- Has email: 0%
- Has phone: 0%
- **Actionable leads**: 0%

### Pipeline Output
- `scored_leads_20260105.csv`: Combined scored leads
- `today_targets.csv`: 15 daily targets (mixed sources)
- Effective targets (contactable): ~7-8 out of 15 (LinkedIn leads waste ~half)

---

## 6. Cost Analysis

| Resource | Cost | Notes |
|----------|------|-------|
| Gemini 2.5 Flash | ~$0.001/email | Intro generation + full email |
| Gmail API | Free | Up to 500 emails/day (drafts unlimited) |
| Playwright | Free | Local browser automation |
| Google Maps scraping | Free | But risk of CAPTCHA/block |
| LinkedIn X-Ray | Free | But high CAPTCHA risk on Google Search |

**Total cost per campaign (15 emails/day)**: ~$0.015/day (essentially free)
