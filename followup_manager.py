from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import pandas as pd

import config
import db

HISTORY_FILE = config.DB_PATH
TARGETS_FILE = "data/output/today_targets.csv"  # legacy constant kept for compatibility

HISTORY_COLUMNS = [
    "lead_id",
    "company",
    "company_norm",
    "source",
    "status",
    "date",
    "time",
    "note",
    "email",
    "followup_count",
    "last_sent_date",
    "replied",
    "tracking_id",
]

MAX_FOLLOWUPS = 3


def normalize_company(name: str) -> str:
    return db.normalize_company(name)


def _latest_outreach_rows() -> list[dict]:
    db.init()
    return db.get_history_snapshot()


def ensure_history_schema() -> pd.DataFrame:
    rows = _latest_outreach_rows()
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    for col in HISTORY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["replied"] = df["replied"].astype(int).astype(bool)
    df["followup_count"] = pd.to_numeric(df["followup_count"], errors="coerce").fillna(0).astype(int)
    return df[HISTORY_COLUMNS]


def _resolve_or_create_lead(record: Dict) -> int | None:
    company = str(record.get("company", "")).strip()
    if not company:
        return None

    source = str(record.get("source", "manual")).strip() or "manual"
    company_norm = record.get("company_norm") or normalize_company(company)

    lead = db.get_lead_by_company_norm(company_norm, source=source)
    if lead:
        update_payload = {}
        email = str(record.get("email", "")).strip()
        if email and not str(lead.get("email", "")).strip():
            update_payload["email"] = email
        if update_payload:
            db.update_lead(int(lead["id"]), update_payload)
        return int(lead["id"])

    lead_id, _ = db.insert_lead(
        {
            "company": company,
            "company_norm": company_norm,
            "email": record.get("email", ""),
            "source": source,
            "score": int(record.get("score", 0) or 0),
        }
    )
    return lead_id


def save_records(records: List[Dict]) -> int:
    if not records:
        return 0

    db.init()
    now = datetime.now()
    updated = 0

    for raw in records:
        lead_id = raw.get("lead_id")
        if lead_id is None:
            lead_id = _resolve_or_create_lead(raw)
        if not lead_id:
            continue

        status = str(raw.get("status", "sent"))
        followup_count = int(raw.get("followup_count", 0) or 0)
        subject = str(raw.get("subject", ""))
        note = str(raw.get("note", ""))
        tracking_id = str(raw.get("tracking_id", ""))

        db.record_outreach(
            int(lead_id),
            status=status,
            followup_number=followup_count,
            tracking_id=tracking_id,
            subject=subject,
            note=note,
        )
        updated += 1

        email = str(raw.get("email", "")).strip()
        if email:
            db.update_lead(int(lead_id), {"email": email, "updated_at": now.isoformat()})

    return updated


def mark_replied(company_or_email: str, replied: bool = True) -> bool:
    key = company_or_email.strip().lower()
    if not key:
        return False

    leads = db.search_leads(query=company_or_email, limit=50)
    matched = [l for l in leads if l.get("company_norm", "").lower() == key or str(l.get("email", "")).lower() == key]
    if not matched:
        return False

    changed = False
    for lead in matched:
        lead_id = int(lead["id"])
        if replied:
            changed = db.mark_replied(lead_id) or changed
    return changed


def load_due_followups(reference_date: str | None = None) -> pd.DataFrame:
    # reference_date is intentionally ignored to keep logic centralized in SQL (julianday('now')).
    due = db.get_due_followups(max_followups=MAX_FOLLOWUPS)
    if not due:
        return pd.DataFrame(
            columns=["lead_id", "company", "company_norm", "email", "followup_count", "last_sent_date", "next_followup_number"]
        )

    rows = []
    for item in due:
        rows.append(
            {
                "lead_id": item.get("id"),
                "company": item.get("company", ""),
                "company_norm": item.get("company_norm", ""),
                "email": item.get("email", ""),
                "followup_count": int(item.get("followup_number", 0)),
                "last_sent_date": str(item.get("last_sent_at", ""))[:10],
                "next_followup_number": int(item.get("next_followup_number", 1)),
            }
        )
    return pd.DataFrame(rows)


def mark_followup_sent(company_norm: str = "", tracking_id: str = "", lead_id: int | None = None) -> bool:
    if lead_id is None:
        lead = db.get_lead_by_company_norm(company_norm)
        if not lead:
            return False
        lead_id = int(lead["id"])

    latest = db.get_latest_outreach(lead_id)
    current = int(latest.get("followup_number", 0)) if latest else 0
    next_followup = min(current + 1, MAX_FOLLOWUPS)

    db.record_outreach(
        lead_id,
        status="followup_sent",
        followup_number=next_followup,
        tracking_id=tracking_id,
        note="auto_followup",
    )
    return True


def enrich_records_from_targets(records: List[Dict]) -> List[Dict]:
    if not records:
        return records

    today = datetime.now().strftime("%Y-%m-%d")
    targets = db.get_daily_targets(today)
    indexed = {str(t.get("company_norm", "")): t for t in targets}

    enriched: List[Dict] = []
    for record in records:
        company_norm = record.get("company_norm") or normalize_company(record.get("company", ""))
        merged = dict(record)
        target = indexed.get(company_norm)
        if target:
            merged["lead_id"] = target.get("id")
            if not merged.get("email"):
                merged["email"] = target.get("email", "")
        enriched.append(merged)
    return enriched
