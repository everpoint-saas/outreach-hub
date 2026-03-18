"""
Lead Processing Pipeline (SQLite)

Usage:
    python process_leads.py

What it does:
1. Recalculate lead scores in SQLite
2. Select today's daily targets into daily_targets table
3. Print summary
"""

from __future__ import annotations

import dns.resolver
from datetime import datetime

import config
import db
import usgbc_scraper
import millionverifier

BLACKLIST = config.DEFAULT_BLACKLIST
SCORE_KEYWORDS = config.SCORE_KEYWORDS
DAILY_TARGET_COUNT = config.DAILY_TARGET_COUNT
MIN_LEAD_SCORE = config.MIN_LEAD_SCORE


def _score_text(lead: dict) -> int:
    company = str(lead.get("company", "")).strip()

    # Discard junk leads: inactive/expired orgs, numeric-only names
    company_lower = company.lower()
    if "not active" in company_lower or "expired" in company_lower:
        return 0
    if company.isdigit():
        return 0

    text_fields = [
        "company",
        "contact_person",
        "title",
        "keyword",
        "address",
        "city",
        "state",
        "source",
        "usgbc_category",
        "usgbc_subcategory",
        "leed_credential",
    ]
    text = " ".join(str(lead.get(k, "")).lower() for k in text_fields)

    if any(bl in text for bl in BLACKLIST):
        return 0

    score = 0
    for keyword, points in SCORE_KEYWORDS.items():
        if keyword in text:
            score += points

    # USGBC sources are guaranteed domain relevance.
    if str(lead.get("source", "")).startswith("usgbc"):
        score = max(score, 5)

    return score


def _score_usgbc_org_by_activity(lead: dict) -> int:
    """For usgbc_org leads, query project activity and return score."""
    node_id = str(lead.get("org_node_id", "")).strip()
    return usgbc_scraper.score_from_project_activity(node_id)


def recalculate_scores(use_project_activity: bool = False,
                       log_callback=print) -> int:
    leads = db.search_leads(limit=100000, offset=0)
    updated = 0
    activity_checked = 0

    for lead in leads:
        score = _score_text(lead)

        # For USGBC org leads, override score with project activity data
        if use_project_activity and lead.get("source") == "usgbc_org":
            node_id = str(lead.get("org_node_id", "")).strip()
            if node_id:
                score = _score_usgbc_org_by_activity(lead)
                activity_checked += 1
                if activity_checked % 50 == 0:
                    log_callback(f"  Activity checked: {activity_checked} orgs...")

        if score < MIN_LEAD_SCORE:
            score = 0
        if int(lead.get("score", 0)) != score:
            if db.update_lead(int(lead["id"]), {"score": score}):
                updated += 1

    if activity_checked > 0:
        log_callback(f"  Project activity checked for {activity_checked} USGBC orgs")
    return updated


def _mx_host_resolves(hostname: str) -> bool:
    """Check if an MX hostname has a valid A or AAAA record."""
    for rdtype in ("A", "AAAA"):
        try:
            answers = dns.resolver.resolve(hostname, rdtype, lifetime=5)
            if len(answers) > 0:
                return True
        except Exception:
            continue
    return False


def _check_mx(domain: str) -> bool:
    """Return True if the domain has a reachable MX host.

    Checks both MX record existence AND whether the MX host
    actually resolves to an IP address (A/AAAA record).
    This catches cases like integrativedesign.net where the MX
    record exists but points to a non-existent host (NXDOMAIN).
    """
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        if len(answers) == 0:
            return False
        mx_hosts = sorted(answers, key=lambda r: r.preference)
        primary_mx = str(mx_hosts[0].exchange)
        return _mx_host_resolves(primary_mx)
    except Exception:
        return False


# Cache: domain -> bool (has MX)
_mx_cache: dict[str, bool] = {}


def verify_mx_records(log_callback=print) -> tuple[int, int]:
    """Check MX records for leads whose email_valid is still unknown (-1).

    Returns (checked, invalid) counts.
    """
    leads = db.search_leads(limit=100000, offset=0)
    checked = 0
    invalid = 0

    for lead in leads:
        email = str(lead.get("email", "")).strip()
        if not email or "@" not in email:
            continue
        if int(lead.get("email_valid", -1)) != -1:
            continue  # already checked

        domain = email.rsplit("@", 1)[1].lower()

        if domain not in _mx_cache:
            _mx_cache[domain] = _check_mx(domain)

        valid = 1 if _mx_cache[domain] else 0
        db.update_lead(int(lead["id"]), {"email_valid": valid})
        checked += 1

        if not valid:
            invalid += 1
            log_callback(f"  MX FAIL: {email} (domain: {domain}, MX host unreachable)")

        if checked % 100 == 0:
            log_callback(f"  MX checked: {checked}...")

    return checked, invalid


def verify_emails_millionverifier(log_callback=print) -> tuple[int, int, int]:
    """Verify emails via MillionVerifier API for leads that passed MX check
    but haven't been verified by MV yet (email_valid == 1 from MX check only).

    We re-verify email_valid=1 leads because MX check only confirms the domain
    exists, not that the specific mailbox is deliverable.

    Also verifies email_valid=-1 leads (never checked at all).

    Returns (checked, valid, invalid) counts.
    """
    if not config.MILLIONVERIFIER_API_KEY:
        log_callback("MillionVerifier API key not configured, skipping.")
        return 0, 0, 0

    # Get leads that need verification:
    # email_valid = -1 (never checked) or email_valid = 1 (MX-only, not MV-verified)
    leads = db.search_leads(limit=100000, offset=0)
    to_verify = []
    for lead in leads:
        email = str(lead.get("email", "")).strip()
        if not email or "@" not in email:
            continue
        ev = int(lead.get("email_valid", -1))
        # Skip leads already marked invalid (0) - no point re-checking
        # Verify: unchecked (-1) and MX-only-passed (1)
        # We use email_valid=2 to mark "MV verified" so we don't re-check
        if ev in (-1, 1):
            to_verify.append(lead)

    if not to_verify:
        log_callback("All emails already verified by MillionVerifier.")
        return 0, 0, 0

    log_callback(f"Verifying {len(to_verify)} emails via MillionVerifier...")

    results = millionverifier.verify_batch(to_verify, log_callback=log_callback)

    valid = 0
    invalid = 0
    for result in results:
        lead_id = result["lead_id"]
        mv_valid = result["email_valid"]

        if mv_valid == 1:
            # MV confirmed deliverable -> mark as 2 (MV-verified)
            db.update_lead(lead_id, {"email_valid": 2})
            valid += 1
        elif mv_valid == 0:
            # MV says invalid/disposable -> mark as 0
            db.update_lead(lead_id, {"email_valid": 0})
            invalid += 1
        # mv_valid == -1 (unknown) -> leave as-is, retry later

    checked = len(results)
    log_callback(f"MillionVerifier done: {checked} checked, {valid} valid, {invalid} invalid")
    return checked, valid, invalid


def process_leads(use_project_activity: bool = False) -> None:
    db.init()

    print("\n=== SQLite Pipeline ===")
    total_leads = db.count_leads()
    print(f"Total leads in DB: {total_leads}")

    if total_leads == 0:
        print("No leads found. Run a scraper first (Google Maps or USGBC).")
        return

    if use_project_activity:
        print("Project activity scoring ENABLED (will query USGBC API)")

    updated = recalculate_scores(
        use_project_activity=use_project_activity,
        log_callback=print,
    )
    print(f"Scores recalculated/updated: {updated}")

    print("Verifying MX records for unchecked emails...")
    mx_checked, mx_invalid = verify_mx_records(log_callback=print)
    if mx_checked > 0:
        print(f"MX verified: {mx_checked} checked, {mx_invalid} invalid domains removed")
    else:
        print("MX: all emails already verified")

    today = datetime.now().strftime("%Y-%m-%d")
    selected = db.select_daily_targets(today, count=DAILY_TARGET_COUNT)

    # Filter out 0-score records from selected output if they slipped through manual inserts.
    selected = [row for row in selected if int(row.get("score", 0)) >= MIN_LEAD_SCORE]

    # MillionVerifier: verify only today's targets (saves credits)
    if config.MILLIONVERIFIER_API_KEY and selected:
        targets_to_verify = [
            lead for lead in selected
            if lead.get("email") and "@" in str(lead.get("email", ""))
            and int(lead.get("email_valid", -1)) in (-1, 1)
        ]
        if targets_to_verify:
            print(f"\nVerifying {len(targets_to_verify)} daily target emails via MillionVerifier...")
            results = millionverifier.verify_batch(targets_to_verify, log_callback=print)
            mv_valid = 0
            mv_invalid = 0
            for result in results:
                lead_id = result["lead_id"]
                if result["email_valid"] == 1:
                    db.update_lead(lead_id, {"email_valid": 2})
                    mv_valid += 1
                elif result["email_valid"] == 0:
                    db.update_lead(lead_id, {"email_valid": 0})
                    mv_invalid += 1
            print(f"MV verified: {len(results)} checked, {mv_valid} valid, {mv_invalid} invalid")

            # If any targets were invalid, replace them with next best candidates
            if mv_invalid > 0:
                print(f"Replacing {mv_invalid} invalid targets...")
                db.clear_daily_targets(today)
                selected = db.select_daily_targets(today, count=DAILY_TARGET_COUNT)
                selected = [row for row in selected if int(row.get("score", 0)) >= MIN_LEAD_SCORE]
        else:
            print("All daily targets already verified by MillionVerifier.")
    elif not config.MILLIONVERIFIER_API_KEY:
        print("MillionVerifier: API key not configured, skipping deep verification")

    print(f"Daily targets selected for {today}: {len(selected)}")

    source_counts: dict[str, int] = {}
    for row in selected:
        source = str(row.get("source", "unknown"))
        source_counts[source] = source_counts.get(source, 0) + 1

    if source_counts:
        print("By source:")
        for src, count in sorted(source_counts.items(), key=lambda x: x[0]):
            print(f"  - {src}: {count}")

    print("Pipeline done.")


if __name__ == "__main__":
    import sys
    use_activity = "--activity" in sys.argv
    process_leads(use_project_activity=use_activity)
