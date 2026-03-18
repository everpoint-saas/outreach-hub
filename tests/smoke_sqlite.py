from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import db


def _backdate_latest_outreach(lead_id: int, days: int) -> None:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        target = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE outreach SET sent_at = ? WHERE id = (SELECT MAX(id) FROM outreach WHERE lead_id = ?)",
            (target, lead_id),
        )
        conn.commit()
    finally:
        conn.close()


def run_smoke() -> int:
    print("[smoke] init db")
    db.init()

    lead_name = f"Smoke Test Co {datetime.now().strftime('%H%M%S')}"
    lead_id = None
    try:
        lead_id, is_new = db.insert_lead(
            {
                "company": lead_name,
                "email": "hello@smoketest.example",
                "website": "https://example.com",
                "source": "manual",
                "score": 9,
                "email_valid": 1,
            }
        )
        if not lead_id or not is_new:
            print("[smoke] failed: lead insert")
            return 1
        print(f"[smoke] inserted lead_id={lead_id}")

        today = datetime.now().strftime("%Y-%m-%d")
        targets = db.select_daily_targets(today, count=10)
        print(f"[smoke] daily targets count={len(targets)}")

        out_id = db.record_outreach(lead_id, status="sent", followup_number=0, subject="Smoke", note="smoke")
        print(f"[smoke] outreach id={out_id}")

        _backdate_latest_outreach(lead_id, days=4)
        due = db.get_due_followups(max_followups=3)
        due_ids = {int(x["id"]) for x in due}
        if lead_id not in due_ids:
            print("[smoke] failed: follow-up lead not found in due list")
            return 2
        print("[smoke] due follow-up check ok")

        if not db.mark_replied(lead_id):
            print("[smoke] failed: mark_replied")
            return 3

        stats = db.get_stats()
        required_keys = {"total_leads", "leads_by_source", "leads_with_email", "total_sent", "total_replied", "followups_due"}
        if not required_keys.issubset(stats.keys()):
            print("[smoke] failed: stats schema")
            return 4

        print("[smoke] stats", stats)
        print("[smoke] SUCCESS")
        return 0
    finally:
        if lead_id:
            conn = sqlite3.connect(db.DB_PATH)
            try:
                conn.execute("DELETE FROM daily_targets WHERE lead_id = ?", (lead_id,))
                conn.execute("DELETE FROM outreach WHERE lead_id = ?", (lead_id,))
                conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
                conn.commit()
            finally:
                conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite migration smoke test")
    parser.add_argument("--reset-db", action="store_true", help="Delete current DB before running smoke test")
    args = parser.parse_args()

    if args.reset_db and os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
        print(f"[smoke] removed {db.DB_PATH}")

    return run_smoke()


if __name__ == "__main__":
    raise SystemExit(main())
