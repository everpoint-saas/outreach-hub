# SQLite + USGBC Integrated Architecture Spec

> This document is the **unified blueprint** for the next phase of work.
> It combines: SQLite migration (Phase 5.1), USGBC scraper integration, and
> the data layer changes needed for Phase 4-5 code quality improvements.
>
> **Goal**: Do it once, do it right. No CSV-to-SQLite migration hacks.

---

## Why SQLite (Not CSV, Not PostgreSQL)

| Aspect | CSV (Current) | SQLite (Target) | PostgreSQL |
|--------|--------------|-----------------|------------|
| Concurrent access | Breaks | WAL mode, safe | Overkill |
| Dedup | Manual pandas | UNIQUE constraints | Overkill |
| Query speed | Full scan every time | Indexed | Overkill |
| Follow-up tracking | Fragile CSV upsert | SQL UPDATE | Overkill |
| Setup | Zero | Zero (stdlib) | Server needed |
| Backup | Copy file | Copy file | pg_dump |

**Decision**: SQLite via Python `sqlite3` (stdlib). No ORM. Raw SQL with parameterized queries.

---

## Database Schema

Single file: `data/mailing_list.db`

### Table: `leads`

The central table. Every lead from ANY source lands here.

```sql
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    company_norm TEXT NOT NULL,           -- lowercase, stripped
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    website TEXT DEFAULT '',
    contact_person TEXT DEFAULT '',        -- person name if available
    title TEXT DEFAULT '',                 -- job title
    address TEXT DEFAULT '',
    city TEXT DEFAULT '',
    state TEXT DEFAULT '',
    country TEXT DEFAULT 'United States',

    -- Source tracking
    source TEXT NOT NULL,                  -- 'google_maps', 'usgbc_org', 'usgbc_person', 'manual'
    source_id TEXT DEFAULT '',             -- external ID (e.g. USGBC member ID)

    -- USGBC-specific
    usgbc_level TEXT DEFAULT '',           -- 'Platinum', 'Gold', 'Silver', 'Organizational'
    usgbc_category TEXT DEFAULT '',        -- 'Professional Firms'
    usgbc_subcategory TEXT DEFAULT '',     -- 'Building/LEED Consultants'
    leed_credential TEXT DEFAULT '',       -- 'LEED AP BD+C' (for person leads)
    member_since TEXT DEFAULT '',          -- YYYY-MM-DD

    -- Google Maps specific
    rating TEXT DEFAULT '',
    review_count TEXT DEFAULT '',
    keyword TEXT DEFAULT '',               -- search keyword used

    -- Scoring
    score INTEGER DEFAULT 0,
    email_valid INTEGER DEFAULT -1,        -- -1=unchecked, 0=invalid, 1=valid (MX check)

    -- Timestamps
    scraped_at TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),

    -- Dedup constraint: one lead per normalized company per source
    UNIQUE(company_norm, source)
);

CREATE INDEX IF NOT EXISTS idx_leads_company_norm ON leads(company_norm);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_state ON leads(state);
```

### Table: `outreach`

Tracks every email interaction (sent, follow-up, replied).

```sql
CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    status TEXT NOT NULL,                  -- 'sent', 'followup_sent', 'replied', 'bounced', 'skipped'
    followup_number INTEGER DEFAULT 0,     -- 0=initial, 1=1st followup, 2=2nd, 3=final
    tracking_id TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    note TEXT DEFAULT '',
    sent_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_outreach_lead_id ON outreach(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach(status);
CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach(sent_at);
```

### Table: `daily_targets`

Snapshot of today's selected targets. Replaces `today_targets.csv`.

```sql
CREATE TABLE IF NOT EXISTS daily_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    target_date TEXT NOT NULL,              -- YYYY-MM-DD
    selected INTEGER DEFAULT 1,            -- 1=selected for outreach, 0=deselected by user
    draft_created INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
    UNIQUE(lead_id, target_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_targets_date ON daily_targets(target_date);
```

### Table: `scrape_runs`

Audit log for scraping sessions.

```sql
CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,                  -- 'google_maps', 'usgbc_org', 'usgbc_person'
    params TEXT DEFAULT '',                -- JSON string of search params
    total_found INTEGER DEFAULT 0,
    new_leads INTEGER DEFAULT 0,
    duplicates_skipped INTEGER DEFAULT 0,
    started_at TEXT DEFAULT (datetime('now')),
    finished_at TEXT DEFAULT ''
);
```

---

## Data Access Layer: `db.py`

Create a single `db.py` module as the **only** interface to SQLite.
Every other module goes through `db.py`. No direct SQL anywhere else.

```python
"""
db.py - Single source of truth for all database operations.

Usage:
    import db
    db.init()  # Call once at app startup

    # Insert leads
    lead_id = db.insert_lead({...})

    # Query
    leads = db.get_leads_by_source('usgbc_org')
    targets = db.get_daily_targets('2026-02-09')
"""

import sqlite3
import json
import os
from typing import Optional
from datetime import datetime

DB_PATH = "data/mailing_list.db"

def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Dict-like access
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init():
    """Create tables if they don't exist. Call once at startup."""
    conn = _get_conn()
    conn.executescript(_SCHEMA_SQL)  # The full CREATE TABLE statements above
    conn.close()
```

### Key functions to implement in `db.py`:

```python
# --- Leads ---
def insert_lead(data: dict) -> Optional[int]:
    """Insert or ignore (dedup by company_norm + source). Returns lead_id."""

def update_lead(lead_id: int, data: dict) -> bool:
    """Update specific fields of a lead."""

def get_lead_by_id(lead_id: int) -> Optional[dict]:

def get_leads_by_source(source: str, limit: int = 0) -> list[dict]:

def search_leads(query: str = "", source: str = "", state: str = "",
                 has_email: bool = False, min_score: int = 0,
                 limit: int = 100, offset: int = 0) -> list[dict]:
    """Flexible search with multiple filters."""

def count_leads(source: str = "") -> int:

def normalize_company(name: str) -> str:
    """Lowercase, strip whitespace."""
    return str(name).lower().strip() if name else ""

# --- Outreach ---
def record_outreach(lead_id: int, status: str, followup_number: int = 0,
                    tracking_id: str = "", subject: str = "", note: str = "") -> int:

def get_outreach_history(lead_id: int) -> list[dict]:

def get_latest_outreach(lead_id: int) -> Optional[dict]:

def get_due_followups(max_followups: int = 3) -> list[dict]:
    """
    Returns leads where:
    - Last outreach status is 'sent' or 'followup_sent'
    - Never replied or bounced
    - followup_number < max_followups
    - Enough days have passed since last outreach
      (3 days after initial, 7 days after each followup)
    """

def mark_replied(lead_id: int) -> bool:

# --- Daily Targets ---
def select_daily_targets(date: str, count: int = 15) -> list[dict]:
    """
    Pick today's targets from leads table:
    1. Must have email (and email_valid != 0)
    2. Not already in outreach with status 'sent'/'followup_sent'/'replied'
    3. Order by score DESC
    4. Insert into daily_targets table
    5. Return selected leads
    """

def get_daily_targets(date: str) -> list[dict]:

# --- Scrape Runs ---
def start_scrape_run(source: str, params: dict) -> int:

def finish_scrape_run(run_id: int, total_found: int, new_leads: int, dupes: int):

# --- Stats ---
def get_stats() -> dict:
    """
    Returns: {
        'total_leads': int,
        'leads_by_source': {'google_maps': N, 'usgbc_org': N, ...},
        'leads_with_email': int,
        'total_sent': int,
        'total_replied': int,
        'followups_due': int,
    }
    """
```

---

## USGBC Scraper: `usgbc_scraper.py`

> Full API details in [USGBC_SCRAPER_SPEC.md](./USGBC_SCRAPER_SPEC.md)

### Key Changes for SQLite Integration

The scraper should write directly to SQLite via `db.py`, NOT to CSV.

```python
"""
usgbc_scraper.py - USGBC Directory Scraper

Scrapes organizations and people from USGBC's public Elasticsearch API.
Writes directly to SQLite via db.py.
"""

import requests
import time
import db
from typing import Callable

BASE_URL = "https://pr-msearch.usgbc.org"
ORG_INDEX = "elasticsearch_index_live_usgbc_usgbc_org_dev"
PERSON_INDEX = "elasticsearch_index_live_usgbc_persons_dev"
DELAY_BETWEEN_REQUESTS = 1.0  # seconds


def scrape_organizations(
    subcategories: list[str] | None = None,
    states: list[str] | None = None,
    page_size: int = 100,
    log_callback: Callable = print,
) -> dict:
    """
    Scrape USGBC organization directory.

    Default: All "Building/LEED Consultants" in the United States.

    Returns: {'total_found': N, 'new_leads': N, 'duplicates': N}
    """
    if subcategories is None:
        subcategories = ["Building/LEED Consultants"]

    run_id = db.start_scrape_run("usgbc_org", {
        "subcategories": subcategories,
        "states": states or [],
    })

    # Build Elasticsearch query
    filters = [
        {"terms": {"country_name.raw": ["United States"]}}
    ]
    if subcategories:
        filters.append({"terms": {"member_subcategory.raw": subcategories}})
    if states:
        filters.append({"terms": {"state_name.raw": states}})

    query = {
        "query": {"bool": {"filter": filters}},
        "from": 0,
        "size": page_size,
        "sort": [{"org_membersince": {"order": "desc"}}],
        "track_total_hits": True,
    }

    total_found = 0
    new_leads = 0
    duplicates = 0
    offset = 0

    while True:
        query["from"] = offset

        try:
            resp = requests.post(
                f"{BASE_URL}/{ORG_INDEX}/_search",
                json=query,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log_callback(f"API error at offset {offset}: {e}")
            break

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {})
        if isinstance(total, dict):
            total_found = total.get("value", 0)

        if not hits:
            break

        for hit in hits:
            src = hit.get("_source", {})
            lead_data = {
                "company": src.get("title", ""),
                "email": src.get("org_email", ""),
                "phone": src.get("org_phone", ""),
                "website": src.get("org_website", ""),
                "contact_person": src.get("org_mailto", ""),
                "city": src.get("city_name", ""),
                "state": src.get("state_name", ""),
                "country": src.get("country_name", "United States"),
                "source": "usgbc_org",
                "source_id": hit.get("_id", ""),
                "usgbc_level": src.get("level", ""),
                "usgbc_category": src.get("member_category", ""),
                "usgbc_subcategory": src.get("member_subcategory", ""),
                "member_since": _parse_timestamp(src.get("org_membersince")),
                "score": 5,  # USGBC members are guaranteed LEED-relevant
            }

            result = db.insert_lead(lead_data)
            if result:
                new_leads += 1
                log_callback(f"NEW: {lead_data['company']} | {lead_data['email'] or 'no email'}")
            else:
                duplicates += 1

        log_callback(f"Progress: {offset + len(hits)}/{total_found}")
        offset += page_size

        if offset >= total_found:
            break

        time.sleep(DELAY_BETWEEN_REQUESTS)

    db.finish_scrape_run(run_id, total_found, new_leads, duplicates)
    log_callback(f"Done! Total: {total_found}, New: {new_leads}, Dupes: {duplicates}")

    return {"total_found": total_found, "new_leads": new_leads, "duplicates": duplicates}


def scrape_people(
    credentials: list[str] | None = None,
    states: list[str] | None = None,
    page_size: int = 100,
    log_callback: Callable = print,
) -> dict:
    """
    Scrape USGBC people directory.

    Default: All LEED AP BD+C credential holders in the United States.
    Same pattern as scrape_organizations but different index and field mapping.

    Maps to leads table with source='usgbc_person'.
    """
    # Same pagination pattern as scrape_organizations
    # Field mapping:
    #   per_fname + per_lname -> contact_person
    #   per_email -> email
    #   per_phone -> phone
    #   per_orgname -> company
    #   per_job_title -> title
    #   leed_credential -> leed_credential
    pass  # Implement same pattern as scrape_organizations


def _parse_timestamp(ts) -> str:
    """Convert USGBC timestamp (seconds since epoch) to YYYY-MM-DD."""
    if not ts:
        return ""
    try:
        from datetime import datetime
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return ""
```

---

## Migration Plan: Modules That Need Changes

### Must Change (CSV -> SQLite via db.py)

| Module | Current | Target |
|--------|---------|--------|
| `followup_manager.py` | Reads/writes `sent_log.csv` | Use `db.record_outreach()`, `db.get_due_followups()` |
| `mark_sent.py` | CSV-based history | Use `db.record_outreach()` |
| `process_leads.py` | Reads CSVs, writes `today_targets.csv` | Use `db.select_daily_targets()` |
| `google_maps_scraper.py` | Writes CSV to `data/raw/` | Use `db.insert_lead(source='google_maps')` |
| `crawl_emails.py` | Reads/writes CSV | Use `db.update_lead()` to set email |
| `gui/tab_mailing.py` | Reads `today_targets.csv` | Use `db.get_daily_targets()` |
| `gui/main_window.py` | History tab reads CSV | Use `db.search_leads()`, `db.get_stats()` |

### New Modules

| Module | Purpose |
|--------|---------|
| `db.py` | Data access layer (all SQL here) |
| `usgbc_scraper.py` | USGBC API scraper |

### Remove After Migration

| File | Reason |
|------|--------|
| `data/history/sent_log.csv` | Replaced by `outreach` table |
| `data/output/today_targets.csv` | Replaced by `daily_targets` table |
| `data/raw/*.csv` | Replaced by `leads` table |
| `data/processed/*.csv` | Replaced by `leads` table with scores |
| `linkedin_xray_scraper.py` | Ineffective (0% contactable, see LINKEDIN_XRAY_VERDICT.md) |

---

## GUI Changes

### New Tab: "USGBC Directory" (or add to existing scraper tab)

```
[USGBC Directory]
  Source: [x] Organizations  [ ] People  [ ] Both

  Filters:
    Subcategory: [Building/LEED Consultants ▼]  (dropdown, multi-select)
    State: [All States ▼]  (dropdown, multi-select)
    Level: [All Levels ▼]  (dropdown)

  [Start Scraping]  [Stop]

  Log:
  > Scraping USGBC Organizations...
  > NEW: Green Building Corp | info@greenbuilding.com
  > Progress: 100/4000
  > ...
```

### History/Data Tab Update

Replace CSV table view with SQLite query results:
- Source filter dropdown (All / Google Maps / USGBC Org / USGBC Person)
- State filter
- Has Email filter checkbox
- Search box (company name)
- Pagination (don't load 10K rows at once)

### Stats Dashboard (optional but easy)

```
Total Leads: 4,523
  - USGBC Orgs: 3,800
  - USGBC People: 500
  - Google Maps: 223
With Email: 3,950 (87%)

Outreach:
  Sent: 45
  Replied: 3 (6.7%)
  Follow-ups Due: 12
```

---

## Execution Order (Recommended)

### Step 1: Create `db.py` (Foundation)
- Schema creation
- All CRUD functions
- Test with simple inserts/queries

### Step 2: Create `usgbc_scraper.py`
- Organizations scraper (higher priority - has company emails)
- People scraper (secondary - personal emails, use carefully)
- Both write to `leads` table via `db.py`

### Step 3: Migrate `followup_manager.py` to SQLite
- Replace all CSV operations with `db.py` calls
- This is the most CSV-dependent module currently

### Step 4: Migrate `process_leads.py` (Pipeline)
- Replace scored CSV generation with `db.select_daily_targets()`
- Score calculation moves to `db.py` or stays in `process_leads.py` but writes to `leads.score`

### Step 5: Migrate `mark_sent.py` and `tab_mailing.py`
- Replace CSV reads with `db.get_daily_targets()`
- Replace history writes with `db.record_outreach()`

### Step 6: Migrate Google Maps scraper output
- `google_maps_scraper.py` writes to `leads` table instead of CSV
- Keep raw CSV export as optional backup feature

### Step 7: Phase 4 Code Quality
- Split `main_window.py` into tab modules
- Add logging
- Add type hints
- Remove `linkedin_xray_scraper.py` from pipeline

### Step 8: Cleanup
- Remove CSV data files (keep backup copy)
- Remove LinkedIn scraper from UI
- Update `config.py` with new settings

---

## Email Validation (New Feature)

Add to `db.py` or separate `email_validator.py`:

```python
import dns.resolver

def validate_email_mx(email: str) -> bool:
    """Check if email domain has valid MX records."""
    if not email or "@" not in email:
        return False
    domain = email.split("@")[1]
    try:
        dns.resolver.resolve(domain, "MX")
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return False
    except Exception:
        return False
```

Run after scraping, update `leads.email_valid` field:
- `-1` = not checked yet
- `0` = invalid (no MX record)
- `1` = valid (MX exists)

This protects Gmail sender reputation by filtering out bad emails before drafting.

---

## Config Changes (`config.py`)

Add these settings:

```python
# --- Database ---
DB_PATH = os.getenv("DB_PATH", "data/mailing_list.db")

# --- USGBC ---
USGBC_BASE_URL = "https://pr-msearch.usgbc.org"
USGBC_ORG_INDEX = "elasticsearch_index_live_usgbc_usgbc_org_dev"
USGBC_PERSON_INDEX = "elasticsearch_index_live_usgbc_persons_dev"
USGBC_PAGE_SIZE = _env_int("USGBC_PAGE_SIZE", 100)
USGBC_REQUEST_DELAY = _env_float("USGBC_REQUEST_DELAY", 1.0)
USGBC_DEFAULT_SUBCATEGORIES = [
    "Building/LEED Consultants",
    "Energy Services",
]

# --- Email Validation ---
VALIDATE_EMAILS = _env_bool("VALIDATE_EMAILS", True)
```

---

## Summary

| What | How |
|------|-----|
| Data storage | SQLite `data/mailing_list.db` (single file) |
| Data access | `db.py` module (all SQL centralized) |
| Lead sources | USGBC (primary), Google Maps (secondary) |
| Lead dedup | UNIQUE(company_norm, source) constraint |
| Outreach tracking | `outreach` table with FK to `leads` |
| Daily targets | `daily_targets` table, auto-selected by score |
| Email safety | MX validation before outreach |
| LinkedIn | Remove from pipeline (0% ROI) |
| CSV files | Phase out after SQLite migration complete |
