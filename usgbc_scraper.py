from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Optional

import requests

import config
import db

BASE_URL = config.USGBC_BASE_URL
ORG_INDEX = config.USGBC_ORG_INDEX
PERSON_INDEX = config.USGBC_PERSON_INDEX
PROJECT_INDEX = config.USGBC_PROJECT_INDEX
DELAY_BETWEEN_REQUESTS = config.USGBC_REQUEST_DELAY


def _str(value) -> str:
    """Flatten USGBC API values: list -> comma-joined string, else str."""
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    return str(value) if value else ""


def _parse_timestamp(ts) -> str:
    if not ts:
        return ""
    # USGBC API sometimes returns timestamps as lists e.g. [1761048600]
    if isinstance(ts, list):
        ts = ts[0] if ts else None
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return ""


_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.usgbc.org",
    "Referer": "https://www.usgbc.org/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def _post_search(index: str, query: dict) -> dict:
    response = requests.post(
        f"{BASE_URL}/{index}/_search",
        json=query,
        headers=_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_org_projects(org_node_id: str, years: int = config.USGBC_PROJECT_ACTIVITY_YEARS) -> dict:
    """Query USGBC projects index for a given org's node_id.

    Returns:
        {
            "total": int,           # all-time project count
            "recent": int,          # projects within `years`
            "latest_date": str,     # most recent registration date (YYYY-MM-DD or "")
            "recent_projects": [],  # list of dicts with title/date/status for recent ones
        }
    """
    if not org_node_id:
        return {"total": 0, "recent": 0, "latest_date": "", "recent_projects": []}

    cutoff_ts = int((datetime.now().replace(year=datetime.now().year - years)).timestamp())

    query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"prjt_admin_org": org_node_id}},
                ]
            }
        },
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "recent_count": {
                "filter": {"range": {"registration_date": {"gte": cutoff_ts}}},
                "aggs": {
                    "top_recent": {
                        "top_hits": {
                            "size": 5,
                            "sort": [{"registration_date": {"order": "desc"}}],
                            "_source": ["title", "registration_date", "status",
                                        "rating_system_version", "is_certified"],
                        }
                    }
                }
            }
        }
    }

    try:
        data = _post_search(PROJECT_INDEX, query)
    except Exception:
        return {"total": 0, "recent": 0, "latest_date": "", "recent_projects": []}

    total_raw = data.get("hits", {}).get("total", {})
    total = int(total_raw.get("value", 0)) if isinstance(total_raw, dict) else 0

    recent_agg = data.get("aggregations", {}).get("recent_count", {})
    recent = int(recent_agg.get("doc_count", 0))

    recent_projects = []
    top_hits = recent_agg.get("top_recent", {}).get("hits", {}).get("hits", [])
    latest_date = ""
    for hit in top_hits:
        src = hit.get("_source", {})
        reg_date = _parse_timestamp(src.get("registration_date"))
        if not latest_date and reg_date:
            latest_date = reg_date
        recent_projects.append({
            "title": _str(src.get("title")),
            "date": reg_date,
            "status": _str(src.get("status")),
            "rating_system": _str(src.get("rating_system_version")),
            "certified": bool(src.get("is_certified")),
        })

    return {
        "total": total,
        "recent": recent,
        "latest_date": latest_date,
        "recent_projects": recent_projects,
    }


def score_from_project_activity(org_node_id: str) -> int:
    """Calculate a lead score based on USGBC project activity.

    Scoring logic:
        - 5+ recent projects  -> 10 (hot lead)
        - 1-4 recent projects ->  7 (active lead)
        - 0 recent but has historical projects -> 3 (dormant)
        - no org_node_id or 0 total projects   -> 5 (unknown, keep default)
    """
    if not org_node_id:
        return 5

    activity = fetch_org_projects(org_node_id)

    if activity["recent"] >= 5:
        return 10
    elif activity["recent"] >= 1:
        return 7
    elif activity["total"] > 0:
        return 3
    else:
        return 5


def scrape_organizations(
    subcategories: Optional[list[str]] = None,
    states: Optional[list[str]] = None,
    countries: Optional[list[str]] = None,
    page_size: int = config.USGBC_PAGE_SIZE,
    log_callback: Callable = print,
) -> dict:
    db.init()
    if subcategories is None:
        subcategories = list(config.USGBC_DEFAULT_SUBCATEGORIES)
    if countries is None:
        countries = ["United States"]

    run_id = db.start_scrape_run("usgbc_org", {
        "subcategories": subcategories,
        "states": states or [],
        "countries": countries,
    })

    filters = [{"terms": {"country_name.raw": countries}}]
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
            data = _post_search(ORG_INDEX, query)
        except Exception as e:
            log_callback(f"API error at offset {offset}: {e}")
            break

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {})
        if isinstance(total, dict):
            total_found = int(total.get("value", 0))

        if not hits:
            break

        for hit in hits:
            src = hit.get("_source", {})
            lead_data = {
                "company": _str(src.get("title")),
                "email": _str(src.get("org_email")),
                "phone": _str(src.get("org_phone")),
                "website": _str(src.get("org_website")),
                "contact_person": _str(src.get("org_mailto")),
                "city": _str(src.get("city_name")),
                "state": _str(src.get("state_name")),
                "country": _str(src.get("country_name")),
                "source": "usgbc_org",
                "source_id": hit.get("_id", ""),
                "usgbc_level": _str(src.get("level")),
                "usgbc_category": _str(src.get("member_category")),
                "usgbc_subcategory": _str(src.get("member_subcategory")),
                "member_since": _parse_timestamp(src.get("org_membersince")),
                "org_foundation": _str(src.get("org_foundation_statement")),
                "org_node_id": _str(src.get("node_id")),
                "org_linkedin": _str(src.get("org_linkedin")),
                "score": 5,  # default, overridden for new leads below
                "scraped_at": datetime.now().isoformat(),
            }

            lead_id, is_new = db.insert_lead(lead_data)
            if is_new:
                # Only query project activity for NEW leads (skip duplicates to save API calls)
                node_id = lead_data["org_node_id"]
                if node_id:
                    lead_data["score"] = score_from_project_activity(node_id)
                    db.update_lead(lead_id, {"score": lead_data["score"]})
                new_leads += 1
                log_callback(
                    f"NEW: {lead_data['company']} | {lead_data['email'] or 'no email'} "
                    f"| score={lead_data['score']}"
                )
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
    credentials: Optional[list[str]] = None,
    states: Optional[list[str]] = None,
    countries: Optional[list[str]] = None,
    page_size: int = config.USGBC_PAGE_SIZE,
    log_callback: Callable = print,
) -> dict:
    db.init()
    if credentials is None:
        credentials = list(config.USGBC_DEFAULT_CREDENTIALS)
    if countries is None:
        countries = ["United States"]

    run_id = db.start_scrape_run("usgbc_person", {
        "credentials": credentials,
        "states": states or [],
        "countries": countries,
    })

    filters = [{"terms": {"country_name.raw": countries}}]
    if credentials:
        filters.append({"terms": {"leed_credential.raw": credentials}})
    if states:
        filters.append({"terms": {"state_name.raw": states}})

    query = {
        "query": {"bool": {"filter": filters}},
        "from": 0,
        "size": page_size,
        "sort": [{"published_date": {"order": "desc"}}],
        "track_total_hits": True,
    }

    total_found = 0
    new_leads = 0
    duplicates = 0
    offset = 0

    while True:
        query["from"] = offset
        try:
            data = _post_search(PERSON_INDEX, query)
        except Exception as e:
            log_callback(f"API error at offset {offset}: {e}")
            break

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {})
        if isinstance(total, dict):
            total_found = int(total.get("value", 0))

        if not hits:
            break

        for hit in hits:
            src = hit.get("_source", {})
            full_name = f"{_str(src.get('per_fname'))} {_str(src.get('per_lname'))}".strip()
            org_name = _str(src.get("organization_name"))
            # Use "Name @ Org" as company so each person gets a unique lead row
            lead_data = {
                "company": f"{full_name} @ {org_name}" if full_name and org_name else full_name or org_name or "Unknown",
                "email": _str(src.get("per_email")),
                "phone": "",
                "website": "",
                "contact_person": full_name,
                "title": "",
                "city": _str(src.get("city_name")),
                "state": _str(src.get("state_name")),
                "country": _str(src.get("country_name")),
                "source": "usgbc_person",
                "source_id": hit.get("_id", ""),
                "usgbc_level": _str(src.get("level")),
                "usgbc_category": _str(src.get("member_category")),
                "usgbc_subcategory": _str(src.get("member_subcategory")),
                "leed_credential": _str(src.get("leed_credential")),
                "member_since": _parse_timestamp(src.get("published_date")),
                "score": 5,
                "scraped_at": datetime.now().isoformat(),
            }
            lead_id, is_new = db.insert_lead(lead_data)
            if is_new:
                new_leads += 1
                log_callback(f"NEW PERSON: {full_name or lead_data['company']} | {lead_data['email'] or 'no email'}")
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
