from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

import config

DB_PATH = config.DB_PATH


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    company_norm TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    website TEXT DEFAULT '',
    contact_person TEXT DEFAULT '',
    title TEXT DEFAULT '',
    address TEXT DEFAULT '',
    city TEXT DEFAULT '',
    state TEXT DEFAULT '',
    country TEXT DEFAULT 'United States',
    source TEXT NOT NULL,
    source_id TEXT DEFAULT '',
    usgbc_level TEXT DEFAULT '',
    usgbc_category TEXT DEFAULT '',
    usgbc_subcategory TEXT DEFAULT '',
    leed_credential TEXT DEFAULT '',
    member_since TEXT DEFAULT '',
    org_foundation TEXT DEFAULT '',
    org_node_id TEXT DEFAULT '',
    org_linkedin TEXT DEFAULT '',
    rating TEXT DEFAULT '',
    review_count TEXT DEFAULT '',
    keyword TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    email_valid INTEGER DEFAULT -1,
    scraped_at TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(company_norm, source)
);

CREATE INDEX IF NOT EXISTS idx_leads_company_norm ON leads(company_norm);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_state ON leads(state);

CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    followup_number INTEGER DEFAULT 0,
    tracking_id TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    note TEXT DEFAULT '',
    sent_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_outreach_lead_id ON outreach(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach(status);
CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach(sent_at);

CREATE TABLE IF NOT EXISTS daily_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    target_date TEXT NOT NULL,
    selected INTEGER DEFAULT 1,
    draft_created INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
    UNIQUE(lead_id, target_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_targets_date ON daily_targets(target_date);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    params TEXT DEFAULT '',
    total_found INTEGER DEFAULT 0,
    new_leads INTEGER DEFAULT 0,
    duplicates_skipped INTEGER DEFAULT 0,
    started_at TEXT DEFAULT (datetime('now')),
    finished_at TEXT DEFAULT ''
);
"""


def normalize_company(name: str) -> str:
    return str(name).lower().strip() if name else ""


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that may not exist in older databases."""
    cursor = conn.execute("PRAGMA table_info(leads)")
    existing = {row[1] for row in cursor.fetchall()}
    migrations = [
        ("org_foundation", "TEXT DEFAULT ''"),
        ("org_node_id", "TEXT DEFAULT ''"),
        ("org_linkedin", "TEXT DEFAULT ''"),
    ]
    for col, typedef in migrations:
        if col not in existing:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {typedef}")


def init() -> None:
    conn = _get_conn()
    try:
        conn.executescript(_SCHEMA_SQL)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def insert_lead(data: dict) -> tuple[Optional[int], bool]:
    """Insert a lead. Returns (lead_id, is_new). is_new=False means duplicate."""
    company = str(data.get("company", "")).strip()
    if not company:
        return None, False

    source = str(data.get("source", "")).strip()
    if not source:
        return None, False

    company_norm = normalize_company(data.get("company_norm") or company)
    scraped_at = data.get("scraped_at") or datetime.now().isoformat()

    payload = {
        "company": company,
        "company_norm": company_norm,
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "website": data.get("website", ""),
        "contact_person": data.get("contact_person", ""),
        "title": data.get("title", ""),
        "address": data.get("address", ""),
        "city": data.get("city", ""),
        "state": data.get("state", ""),
        "country": data.get("country", "United States"),
        "source": source,
        "source_id": data.get("source_id", ""),
        "usgbc_level": data.get("usgbc_level", ""),
        "usgbc_category": data.get("usgbc_category", ""),
        "usgbc_subcategory": data.get("usgbc_subcategory", ""),
        "leed_credential": data.get("leed_credential", ""),
        "member_since": data.get("member_since", ""),
        "org_foundation": data.get("org_foundation", ""),
        "org_node_id": data.get("org_node_id", ""),
        "org_linkedin": data.get("org_linkedin", ""),
        "rating": data.get("rating", ""),
        "review_count": data.get("review_count", ""),
        "keyword": data.get("keyword", ""),
        "score": int(data.get("score", 0) or 0),
        "email_valid": int(data.get("email_valid", -1) if data.get("email_valid") is not None else -1),
        "scraped_at": scraped_at,
    }

    # Flatten any list values from API responses (e.g. USGBC returns arrays)
    for k, v in payload.items():
        if isinstance(v, list):
            payload[k] = ", ".join(str(x) for x in v)

    columns = list(payload.keys())
    placeholders = ",".join(["?"] * len(columns))
    sql = f"INSERT OR IGNORE INTO leads ({','.join(columns)}) VALUES ({placeholders})"

    conn = _get_conn()
    try:
        cur = conn.execute(sql, [payload[c] for c in columns])
        conn.commit()
        if cur.rowcount > 0:
            return int(cur.lastrowid), True

        # Duplicate found - update fields that were previously empty
        existing = conn.execute(
            "SELECT * FROM leads WHERE company_norm = ? AND source = ?",
            (company_norm, source),
        ).fetchone()
        if existing:
            updates = {}
            updatable = [
                "email", "phone", "website", "contact_person", "title",
                "city", "state", "org_foundation", "org_node_id", "org_linkedin",
                "usgbc_level", "usgbc_category", "usgbc_subcategory",
                "leed_credential", "member_since", "source_id",
            ]
            for field in updatable:
                new_val = str(payload.get(field, ""))
                old_val = str(existing[field] or "")
                if new_val and not old_val:
                    updates[field] = new_val
            if updates:
                updates["updated_at"] = datetime.now().isoformat()
                set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                conn.execute(
                    f"UPDATE leads SET {set_clause} WHERE id = ?",
                    list(updates.values()) + [int(existing["id"])],
                )
                conn.commit()
            return int(existing["id"]), False
        return None, False
    finally:
        conn.close()


def update_lead(lead_id: int, data: dict) -> bool:
    if not data:
        return False

    allowed = {
        "company", "company_norm", "email", "phone", "website", "contact_person", "title", "address",
        "city", "state", "country", "source", "source_id", "usgbc_level", "usgbc_category",
        "usgbc_subcategory", "leed_credential", "member_since",
        "org_foundation", "org_node_id", "org_linkedin",
        "rating", "review_count", "keyword",
        "score", "email_valid", "scraped_at"
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return False

    if "company" in updates and "company_norm" not in updates:
        updates["company_norm"] = normalize_company(str(updates["company"]))

    updates["updated_at"] = datetime.now().isoformat()

    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    params = list(updates.values()) + [lead_id]

    conn = _get_conn()
    try:
        cur = conn.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", params)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_lead_by_id(lead_id: int) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_leads_by_source(source: str, limit: int = 0) -> list[dict]:
    conn = _get_conn()
    try:
        sql = "SELECT * FROM leads WHERE source = ? ORDER BY score DESC, id DESC"
        params: list[Any] = [source]
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def search_leads(
    query: str = "",
    source: str = "",
    state: str = "",
    has_email: bool = False,
    min_score: int = 0,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    where = ["1=1"]
    params: list[Any] = []

    if query:
        where.append("(company LIKE ? OR contact_person LIKE ? OR email LIKE ?)")
        q = f"%{query}%"
        params.extend([q, q, q])

    if source:
        where.append("source = ?")
        params.append(source)

    if state:
        where.append("state = ?")
        params.append(state)

    if has_email:
        where.append("email != ''")

    if min_score > 0:
        where.append("score >= ?")
        params.append(min_score)

    sql = f"SELECT * FROM leads WHERE {' AND '.join(where)} ORDER BY score DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([max(1, limit), max(0, offset)])

    conn = _get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def count_leads(source: str = "") -> int:
    conn = _get_conn()
    try:
        if source:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM leads WHERE source = ?", (source,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM leads").fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def record_outreach(
    lead_id: int,
    status: str,
    followup_number: int = 0,
    tracking_id: str = "",
    subject: str = "",
    note: str = "",
) -> int:
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO outreach (lead_id, status, followup_number, tracking_id, subject, note, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (lead_id, status, int(followup_number), tracking_id, subject, note),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_outreach_history(lead_id: int) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM outreach WHERE lead_id = ? ORDER BY sent_at DESC, id DESC",
            (lead_id,),
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def get_latest_outreach(lead_id: int) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM outreach WHERE lead_id = ? ORDER BY sent_at DESC, id DESC LIMIT 1",
            (lead_id,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_due_followups(max_followups: int = 3) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            WITH latest AS (
                SELECT o.*
                FROM outreach o
                JOIN (
                    SELECT lead_id, MAX(id) AS max_id
                    FROM outreach
                    GROUP BY lead_id
                ) last ON last.max_id = o.id
            )
            SELECT
                l.*, lt.status AS latest_status, lt.followup_number, lt.sent_at AS last_sent_at
            FROM latest lt
            JOIN leads l ON l.id = lt.lead_id
            WHERE lt.status IN ('sent', 'followup_sent')
              AND lt.followup_number < ?
              AND NOT EXISTS (
                  SELECT 1 FROM outreach o2
                  WHERE o2.lead_id = lt.lead_id
                    AND o2.status IN ('replied', 'bounced')
              )
              AND (
                  (lt.followup_number = 0 AND julianday('now') - julianday(lt.sent_at) >= 3)
                  OR (lt.followup_number >= 1 AND julianday('now') - julianday(lt.sent_at) >= 7)
              )
            ORDER BY l.score DESC, lt.sent_at ASC
            """,
            (max_followups,),
        ).fetchall()

        result = _rows_to_dicts(rows)
        for item in result:
            item["next_followup_number"] = int(item.get("followup_number", 0)) + 1
        return result
    finally:
        conn.close()


def mark_replied(lead_id: int) -> bool:
    try:
        record_outreach(lead_id, status="replied", followup_number=0, note="marked_replied")
        return True
    except Exception:
        return False


def clear_outreach_for_lead(lead_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM outreach WHERE lead_id = ?", (lead_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def clear_daily_targets(date: str) -> int:
    """Delete all daily targets for the given date so they can be re-selected."""
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM daily_targets WHERE target_date = ?", (date,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def select_daily_targets(date: str, count: int = 15) -> list[dict]:
    conn = _get_conn()
    try:
        existing = conn.execute(
            """
            SELECT l.*
            FROM daily_targets dt
            JOIN leads l ON l.id = dt.lead_id
            WHERE dt.target_date = ? AND dt.selected = 1
            ORDER BY l.score DESC, l.id DESC
            """,
            (date,),
        ).fetchall()
        if existing:
            return _rows_to_dicts(existing)

        # Step 1: Get candidates excluding already-sent lead_ids
        # Split into US and non-US pools (50/50 slot allocation)
        _candidate_order = """
              CASE WHEN l.email_valid = 2 THEN 0 ELSE 1 END ASC,
              CASE l.source
                WHEN 'usgbc_org' THEN 0
                WHEN 'usgbc_person' THEN 2
                ELSE 1
              END ASC,
              l.score DESC,
              l.id DESC
        """
        _candidate_filter = """
            FROM leads l
            WHERE l.email != ''
              AND l.email_valid != 0
              AND NOT EXISTS (
                  SELECT 1 FROM outreach o
                  WHERE o.lead_id = l.id
                    AND o.status IN ('sent', 'followup_sent', 'replied')
              )
        """
        raw_us = conn.execute(
            f"SELECT l.* {_candidate_filter} AND l.country = 'United States' ORDER BY {_candidate_order}",
        ).fetchall()
        raw_intl = conn.execute(
            f"SELECT l.* {_candidate_filter} AND (l.country != 'United States' OR l.country IS NULL) ORDER BY {_candidate_order}",
        ).fetchall()

        # Step 2: Deduplicate by email (keep first seen = highest priority per ORDER BY above)
        # Also exclude emails already sent via a different lead_id
        sent_emails = {
            row[0].lower() for row in conn.execute(
                """
                SELECT l.email FROM outreach o
                JOIN leads l ON l.id = o.lead_id
                WHERE o.status IN ('sent', 'followup_sent', 'replied')
                  AND l.email != ''
                """
            ).fetchall()
        }

        us_slot = count // 2
        intl_slot = count - us_slot

        seen_emails: set[str] = set()

        def _pick(pool: list, limit: int) -> list:
            picked = []
            for row in pool:
                email_lower = str(row["email"]).strip().lower()
                if email_lower in sent_emails or email_lower in seen_emails:
                    continue
                seen_emails.add(email_lower)
                picked.append(row)
                if len(picked) >= limit:
                    break
            return picked

        us_picks = _pick(raw_us, us_slot)
        intl_picks = _pick(raw_intl, intl_slot)

        # If one pool is short, fill remaining from the other
        us_remaining = us_slot - len(us_picks)
        intl_remaining = intl_slot - len(intl_picks)
        if intl_remaining > 0:
            us_picks.extend(_pick(raw_us, intl_remaining))
        if us_remaining > 0:
            intl_picks.extend(_pick(raw_intl, us_remaining))

        candidates = us_picks + intl_picks

        for row in candidates:
            conn.execute(
                """
                INSERT OR IGNORE INTO daily_targets (lead_id, target_date, selected, draft_created)
                VALUES (?, ?, 1, 0)
                """,
                (int(row["id"]), date),
            )
        conn.commit()
        return _rows_to_dicts(candidates)
    finally:
        conn.close()


def get_daily_targets(date: str) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT l.*, dt.id AS daily_target_id, dt.selected, dt.draft_created, dt.target_date
            FROM daily_targets dt
            JOIN leads l ON l.id = dt.lead_id
            WHERE dt.target_date = ?
            ORDER BY l.score DESC, l.id DESC
            """,
            (date,),
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def mark_draft_created(lead_id: int, date: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE daily_targets SET draft_created = 1 WHERE lead_id = ? AND target_date = ?",
            (lead_id, date),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def start_scrape_run(source: str, params: dict) -> int:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO scrape_runs (source, params, started_at) VALUES (?, ?, datetime('now'))",
            (source, json.dumps(params, ensure_ascii=False)),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def finish_scrape_run(run_id: int, total_found: int, new_leads: int, dupes: int) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            UPDATE scrape_runs
            SET total_found = ?, new_leads = ?, duplicates_skipped = ?, finished_at = datetime('now')
            WHERE id = ?
            """,
            (int(total_found), int(new_leads), int(dupes), run_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats() -> dict:
    conn = _get_conn()
    try:
        total_leads = int(conn.execute("SELECT COUNT(*) AS cnt FROM leads").fetchone()["cnt"])

        by_source_rows = conn.execute(
            "SELECT source, COUNT(*) AS cnt FROM leads GROUP BY source"
        ).fetchall()
        leads_by_source = {r["source"]: int(r["cnt"]) for r in by_source_rows}

        leads_with_email = int(
            conn.execute("SELECT COUNT(*) AS cnt FROM leads WHERE email != ''").fetchone()["cnt"]
        )

        total_sent = int(
            conn.execute(
                "SELECT COUNT(*) AS cnt FROM outreach WHERE status IN ('sent','followup_sent')"
            ).fetchone()["cnt"]
        )
        total_replied = int(
            conn.execute("SELECT COUNT(*) AS cnt FROM outreach WHERE status = 'replied'").fetchone()["cnt"]
        )

        followups_due = len(get_due_followups())

        return {
            "total_leads": total_leads,
            "leads_by_source": leads_by_source,
            "leads_with_email": leads_with_email,
            "total_sent": total_sent,
            "total_replied": total_replied,
            "followups_due": followups_due,
        }
    finally:
        conn.close()


def get_lead_by_company_norm(company_norm: str, source: str = "") -> Optional[dict]:
    conn = _get_conn()
    try:
        if source:
            row = conn.execute(
                "SELECT * FROM leads WHERE company_norm = ? AND source = ? LIMIT 1",
                (normalize_company(company_norm), source),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM leads WHERE company_norm = ? ORDER BY id DESC LIMIT 1",
                (normalize_company(company_norm),),
            ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_leads_missing_email(limit: int = 100, min_score: int = 0) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM leads
            WHERE (email = '' OR email IS NULL)
              AND website != ''
              AND score >= ?
            ORDER BY score DESC, id DESC
            LIMIT ?
            """,
            (int(min_score), int(limit)),
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def get_history_snapshot() -> list[dict]:
    """Return latest outreach state per lead for UI/history views."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            WITH latest AS (
                SELECT o.*
                FROM outreach o
                JOIN (
                    SELECT lead_id, MAX(id) AS max_id
                    FROM outreach
                    GROUP BY lead_id
                ) x ON x.max_id = o.id
            )
            SELECT
                l.id AS lead_id,
                l.company,
                l.company_norm,
                l.source,
                lt.status,
                substr(lt.sent_at, 1, 10) AS date,
                substr(lt.sent_at, 12, 8) AS time,
                lt.note,
                l.email,
                lt.followup_number AS followup_count,
                substr(lt.sent_at, 1, 10) AS last_sent_date,
                CASE WHEN EXISTS (
                    SELECT 1 FROM outreach o2
                    WHERE o2.lead_id = l.id AND o2.status = 'replied'
                ) THEN 1 ELSE 0 END AS replied,
                lt.tracking_id
            FROM latest lt
            JOIN leads l ON l.id = lt.lead_id
            ORDER BY lt.sent_at DESC, lt.id DESC
            """
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def get_tracking_records() -> list[dict]:
    """Return outreach records with tracking IDs and contact info for the tracking dashboard."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            WITH latest AS (
                SELECT o.*
                FROM outreach o
                JOIN (
                    SELECT lead_id, MAX(id) AS max_id
                    FROM outreach
                    GROUP BY lead_id
                ) x ON x.max_id = o.id
                WHERE o.tracking_id != '' AND o.tracking_id IS NOT NULL
            )
            SELECT
                l.id AS lead_id,
                l.company,
                l.contact_person,
                l.email,
                lt.status,
                substr(lt.sent_at, 1, 10) AS date,
                lt.tracking_id
            FROM latest lt
            JOIN leads l ON l.id = lt.lead_id
            ORDER BY lt.sent_at DESC, lt.id DESC
            """
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def validate_email_mx(email: str) -> bool:
    if not email or "@" not in email:
        return False
    try:
        import dns.resolver
        domain = email.split("@", 1)[1]
        dns.resolver.resolve(domain, "MX")
        return True
    except Exception:
        return False
