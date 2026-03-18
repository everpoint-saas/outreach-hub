"""
Mark Sent - History Tracking Tool

Usage:
    python mark_sent.py                    # Interactive mode
    python mark_sent.py --from-output      # Mark all from SQLite daily_targets as sent

What it does:
1. Loads today's targets from SQLite
2. Lets you mark companies as "sent" or "skip"
3. Saves outreach records to SQLite
4. These companies will be excluded from future processing
"""

import os
from datetime import datetime

import pandas as pd

import followup_manager
import db

# Configuration
HISTORY_DIR = "data/history"


def ensure_dirs():
    """Create necessary directories."""
    os.makedirs(HISTORY_DIR, exist_ok=True)


def load_targets() -> pd.DataFrame:
    """Load today's targets from SQLite daily_targets table."""
    db.init()
    today = datetime.now().strftime("%Y-%m-%d")
    targets = db.get_daily_targets(today)
    if not targets:
        print(f"No targets found for {today}.")
        print("Run process_leads.py first to generate daily targets.")
        return pd.DataFrame()
    return pd.DataFrame(targets)


def load_history() -> pd.DataFrame:
    """Load existing history with normalized schema."""
    return followup_manager.ensure_history_schema()


def save_to_history(records: list):
    """Save records to history with schema enforcement and upsert."""
    ensure_dirs()
    enriched_records = followup_manager.enrich_records_from_targets(records)
    saved = followup_manager.save_records(enriched_records)
    print(f"Saved {saved} records to history.")


def normalize_company(name: str) -> str:
    """Normalize company name for matching."""
    return followup_manager.normalize_company(name)


def _base_record(company: str, status: str, note: str, now: datetime, lead_id: int | None = None, email: str = "") -> dict:
    return {
        "lead_id": lead_id,
        "company": company,
        "company_norm": normalize_company(company),
        "source": "today_targets",
        "status": status,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "note": note,
        "email": email,
        "followup_count": 0,
        "last_sent_date": now.strftime("%Y-%m-%d"),
        "replied": False,
    }


def mark_all_as_sent(note: str = ""):
    """Mark all targets as sent (batch mode)."""
    targets = load_targets()
    if targets.empty:
        return

    print(f"\nMarking {len(targets)} targets as SENT...")

    records = []
    now = datetime.now()

    for _, row in targets.iterrows():
        company = row.get("company", row.get("Company", row.get("Name", "Unknown")))
        lead_id = int(row.get("id")) if pd.notna(row.get("id")) else None
        email = str(row.get("email", row.get("Email", "")))
        records.append(_base_record(company, "sent", note, now, lead_id=lead_id, email=email))

    save_to_history(records)
    print("Done! These companies will be excluded from future processing.")


def interactive_mode():
    """Interactive mode - review and mark each target."""
    targets = load_targets()
    if targets.empty:
        return

    print(f"\n=== Interactive Mode: {len(targets)} targets ===")
    print("Commands: [s]ent, [k]ip, [q]uit, [a]ll sent\n")

    records = []
    now = datetime.now()

    for idx, row in targets.iterrows():
        company = row.get("company", row.get("Company", row.get("Name", "Unknown")))
        lead_id = int(row.get("id")) if pd.notna(row.get("id")) else None
        email = str(row.get("email", row.get("Email", "")))
        score = row.get("score", "N/A")

        print(f"\n[{idx + 1}/{len(targets)}] {company}")
        print(f"  Score: {score}")

        if "Website" in row and pd.notna(row["Website"]):
            print(f"  Website: {row['Website']}")
        if "Phone" in row and pd.notna(row["Phone"]):
            print(f"  Phone: {row['Phone']}")
        if "Title" in row and pd.notna(row["Title"]):
            print(f"  Title: {row['Title']}")
        if "LinkedIn_URL" in row and pd.notna(row["LinkedIn_URL"]):
            print(f"  LinkedIn: {row['LinkedIn_URL']}")

        while True:
            action = input("  Action [s/k/q/a]: ").strip().lower()

            if action == "s":
                note = input("  Note (optional): ").strip()
                records.append(_base_record(company, "sent", note, now, lead_id=lead_id, email=email))
                print("  -> Marked as SENT")
                break

            if action == "k":
                records.append(_base_record(company, "skipped", "", now, lead_id=lead_id, email=email))
                print("  -> Skipped (will still be excluded)")
                break

            if action == "q":
                print("\nQuitting...")
                if records:
                    save_to_history(records)
                return

            if action == "a":
                print("\nMarking all remaining as SENT...")
                for remaining_idx in range(idx, len(targets)):
                    remaining_row = targets.iloc[remaining_idx]
                    remaining_company = remaining_row.get("company", remaining_row.get("Company", remaining_row.get("Name", "Unknown")))
                    remaining_lead_id = int(remaining_row.get("id")) if pd.notna(remaining_row.get("id")) else None
                    remaining_email = str(remaining_row.get("email", remaining_row.get("Email", "")))
                    records.append(_base_record(remaining_company, "sent", "batch", now, lead_id=remaining_lead_id, email=remaining_email))
                save_to_history(records)
                return

            print("  Invalid command. Use s/k/q/a")

    if records:
        save_to_history(records)

    print("\n=== Done! ===")


def show_history_stats():
    """Show history statistics."""
    history = load_history()
    if history.empty:
        print("No history yet.")
        return

    print(f"\n=== History Stats ===")
    print(f"Total records: {len(history)}")
    print(f"Sent: {len(history[history['status'] == 'sent'])}")
    print(f"Skipped: {len(history[history['status'] == 'skipped'])}")
    print(f"Follow-up Sent: {len(history[history['status'] == 'followup_sent'])}")
    print(f"Replied: {len(history[history['status'] == 'replied'])}")

    print(f"\nLast 5 entries:")
    for _, row in history.tail(5).iterrows():
        print(f"  {row['date']} - {row['company']} ({row['status']})")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--from-output":
            note = sys.argv[2] if len(sys.argv) > 2 else ""
            mark_all_as_sent(note)
        elif sys.argv[1] == "--stats":
            show_history_stats()
        else:
            print("Usage:")
            print("  python mark_sent.py              # Interactive mode")
            print("  python mark_sent.py --from-output [note]  # Mark all as sent")
            print("  python mark_sent.py --stats      # Show history stats")
    else:
        interactive_mode()
