# Lead Generator Pro - Improvement Roadmap

> Created: 2026-02-09
> Reference: [ANALYSIS.md](./ANALYSIS.md), [LINKEDIN_XRAY_VERDICT.md](./LINKEDIN_XRAY_VERDICT.md)

---

## Phase 1: Quick Wins (1-2 hours each)

### 1.1 Fix requirements.txt Duplicates
**Effort**: 5 min | **Impact**: Stability

Current duplicates:
- `playwright` x2
- `google-auth-httplib2` x3
- `google-api-python-client` x2

Just deduplicate and pin versions.

### 1.2 Remove LinkedIn from Default Pipeline
**Effort**: 30 min | **Impact**: High (double effective daily targets)

Changes:
- `process_leads.py`: Remove LinkedIn 50/50 balancing (lines 236-246)
- `process_leads.py`: Remove LinkedIn minimum score guarantee (lines 146-148)
- Pipeline now outputs 15 Google Maps leads (all contactable) instead of ~8

LinkedIn tab stays in GUI for manual use, just not in the automated pipeline.

### 1.3 Create config.py
**Effort**: 1 hour | **Impact**: Maintainability

Extract hardcoded values into one file:

```python
# config.py
GEMINI_MODEL = "gemini-2.5-flash"
DAILY_TARGET_COUNT = 15
MAX_SCROLL_COUNT = 30
MAX_CAPTCHA_WAIT = 120
SENDER_NAME = "Jooyeol Lee"
SENDER_COMPANY = "Everpoint"
SENDER_DOMAIN = "vertiq.net"
SENDER_LINKEDIN = "https://www.linkedin.com/in/jooyeol-lee-978b20132/"
```

Currently scattered across: `gemini_helper.py`, `process_leads.py`, `google_maps_scraper.py`, `linkedin_xray_scraper.py`

### 1.4 Fix Known Bugs
**Effort**: 1 hour | **Impact**: Stability

- B4: Remove `.io` from junk_extensions in `crawl_emails.py` (filters valid emails like `info@company.io`)
- B6: Fix Python comment inside f-string in `gemini_helper.py:111` (`{text[:8000]} # Increase limit`)
- B2: Move `import os` to top of `google_maps_scraper.py`

### 1.5 Clean Up Debug Files
**Effort**: 10 min | **Impact**: Cleanliness

12 debug screenshots and HTML dumps sitting in project root:
```
debug_page_141032.html
debug_screenshot_141032.png
... (12 files)
```

Move to `debug/` folder or add to `.gitignore`.

---

## Phase 2: Email Quality (2-4 hours each)

### 2.1 Email Validation
**Effort**: 2 hours | **Impact**: Critical (Gmail reputation protection)

Currently crawled emails go straight to drafts with zero validation.
Bad emails -> bounces -> Gmail sender reputation damage -> future emails go to spam.

Implementation:
```python
# email_validator.py
import dns.resolver

def validate_email(email: str) -> dict:
    """Validate email via MX record check"""
    domain = email.split("@")[1]
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        return {"valid": True, "mx": str(mx_records[0].exchange)}
    except:
        return {"valid": False, "mx": None}
```

Add to pipeline between email crawling and mailing steps.
Package: `dnspython` (pip install dnspython)

### 2.2 Improve Email Crawler Success Rate
**Effort**: 3 hours | **Impact**: High

Current crawl_site() checks:
1. Homepage regex
2. Contact/About page regex
3. mailto: links

Additional checks to add:
- Footer section extraction (most emails are in footers)
- `<meta>` tag email extraction
- Schema.org structured data (`contactPoint` field)
- Social media profile links -> company domain -> email pattern guess

### 2.3 Smart Browser Reuse
**Effort**: 2 hours | **Impact**: Performance

`smart_hunt_email()` creates a new Playwright browser per call.
For 15 targets, that's 15 browser launches.

Fix: Pass browser context as parameter, create once in the calling thread.

---

## Phase 3: Outreach Effectiveness (4-8 hours each)

### 3.1 Follow-up Automation
**Effort**: 6 hours | **Impact**: Critical (2-3x response rate)

Cold email statistics:
- 1st email: ~5-8% response rate
- 2nd follow-up (3 days later): +7-10%
- 3rd follow-up (7 days later): +5-7%
- Total with follow-ups: ~20-25%

Implementation:
```
sent_log.csv has: company, date, status
  -> Filter: sent > 3 days ago AND no reply
  -> Generate follow-up draft (different template)
  -> Track follow-up count (max 3)
```

New fields in sent_log.csv:
- `followup_count`: 0, 1, 2, 3
- `last_sent_date`: for calculating next follow-up timing
- `replied`: boolean (manual marking)

### 3.2 Send Time Optimization
**Effort**: 2 hours | **Impact**: Medium (open rate improvement)

Target audience: US LEED consultants
Optimal send window: EST 9:00-11:00 AM (Tuesday-Thursday)

Options:
- A) Schedule drafts manually (current: user reviews and sends)
- B) Add timer in app: "Schedule send at EST 9:00 AM"
- C) Use Gmail scheduled send feature via API

### 3.3 Open/Click Tracking
**Effort**: 4 hours | **Impact**: Medium (campaign optimization)

Basic tracking pixel approach:
- Generate unique pixel URL per email (tiny transparent image)
- Host on a simple endpoint (Vercel/Cloudflare Worker)
- When opened, pixel loads -> log open event
- UTM parameters on CTA links for click tracking

Enables: "Which companies opened my email but didn't reply?" -> Higher priority follow-up

---

## Phase 4: Code Quality (ongoing)

### 4.1 Split main_window.py into Tab Modules
**Effort**: 4 hours | **Impact**: Maintainability

Current: 1361 lines, 5 tabs inline
Target:
```
gui/
  main_window.py       # ~200 lines (tab composition only)
  tab_google_maps.py   # Google Maps scraper tab
  tab_linkedin.py      # LinkedIn X-Ray tab
  tab_pipeline.py      # Pipeline & Targets tab
  tab_history.py       # History tab
  tab_data_editor.py   # Data Editor tab
  tab_mailing.py       # Already separated
```

### 4.2 Add Logging System
**Effort**: 2 hours | **Impact**: Debugging

Replace all `print()` calls with Python `logging` module.
Output to both console and `logs/app.log` (rotated daily).

### 4.3 Add Type Hints
**Effort**: 3 hours | **Impact**: Code quality

None of the core modules have type hints.
Priority files: `process_leads.py`, `crawl_emails.py`, `gemini_helper.py`

---

## Phase 5: Scale (future, if needed)

### 5.1 SQLite Migration
**Effort**: 8 hours | **Impact**: Scalability

Replace CSV files with SQLite database.
Only needed if daily volume exceeds 50+ leads or data corruption becomes an issue.

### 5.2 Email Finder API Integration
**Effort**: 4 hours | **Impact**: High (for LinkedIn leads)

If LinkedIn leads become valuable, integrate Hunter.io or Apollo.io API:
- Name + Company -> email lookup
- Requires company name (currently "Unknown" for most LinkedIn leads)
- Cost: $49-99/month

### 5.3 Multi-sender Support
**Effort**: 6 hours | **Impact**: Scale

Gmail has daily send limits. For higher volume:
- Multiple Gmail accounts rotation
- Or switch to dedicated email service (SendGrid, Mailgun)
- Warm-up protocol for new accounts

---

## Priority Matrix

```
                    HIGH IMPACT
                        |
   [2.1 Email Valid.]   |   [3.1 Follow-ups]
   [1.2 Remove LI]     |
                        |
  LOW EFFORT -----------+----------- HIGH EFFORT
                        |
   [1.1 Fix reqs]       |   [4.1 Split GUI]
   [1.3 Config]         |   [5.1 SQLite]
   [1.4 Fix bugs]       |
                        |
                    LOW IMPACT
```

### Recommended Order
1. **1.2** Remove LinkedIn from pipeline (immediate ROI: double daily contacts)
2. **2.1** Email validation (protect Gmail reputation)
3. **1.1 + 1.3 + 1.4** Quick fixes batch
4. **3.1** Follow-up automation (biggest outreach improvement)
5. **2.2** Improve email crawler
6. **2.3** Browser reuse
7. **3.2** Send time optimization
8. Everything else as needed
