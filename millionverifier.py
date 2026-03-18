"""
MillionVerifier API client for email deliverability verification.

API docs: https://www.millionverifier.com/api
Single verify: GET /api/v3/?api={key}&email={email}

Result codes:
  1 = ok (safe to send)
  2 = catch_all (domain accepts everything, risky but usually ok)
  3 = unknown (could not determine, skip or retry later)
  4 = invalid (hard bounce guaranteed, never send)
  5 = disposable (temporary email, not a real person)
"""

from __future__ import annotations

import logging
import requests
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Map MillionVerifier resultcode to our email_valid values:
#   1 = valid (ok to send)
#   0 = invalid (do not send)
#  -1 = unknown (keep as unchecked)
_RESULTCODE_TO_VALID = {
    1: 1,   # ok
    2: 1,   # catch_all (accept the risk for cold email)
    3: -1,  # unknown
    4: 0,   # invalid
    5: 0,   # disposable
    6: 0,   # dns_error (domain doesn't exist)
}


def verify_single(email: str) -> dict:
    """Verify a single email address via MillionVerifier API.

    Returns dict with keys:
        email_valid: int (1=valid, 0=invalid, -1=unknown)
        mv_result: str (ok, catch_all, unknown, invalid, disposable, error)
        mv_quality: str (good, risky, bad, unknown)
        free: bool (Gmail, Yahoo, etc.)
        role: bool (info@, admin@, etc.)
        error: str | None
    """
    api_key = config.MILLIONVERIFIER_API_KEY
    if not api_key:
        logger.warning("MillionVerifier API key not configured, skipping verification")
        return {
            "email_valid": -1,
            "mv_result": "error",
            "mv_quality": "unknown",
            "free": False,
            "role": False,
            "error": "API key not configured",
        }

    try:
        resp = requests.get(
            config.MILLIONVERIFIER_API_URL,
            params={"api": api_key, "email": email},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        resultcode = int(data.get("resultcode", 3))
        email_valid = _RESULTCODE_TO_VALID.get(resultcode, -1)

        return {
            "email_valid": email_valid,
            "mv_result": data.get("result", "unknown"),
            "mv_quality": data.get("quality", "unknown"),
            "free": bool(data.get("free", False)),
            "role": bool(data.get("role", False)),
            "error": None,
        }

    except requests.RequestException as e:
        logger.error(f"MillionVerifier API error for {email}: {e}")
        return {
            "email_valid": -1,
            "mv_result": "error",
            "mv_quality": "unknown",
            "free": False,
            "role": False,
            "error": str(e),
        }


def verify_batch(
    emails: list[dict],
    log_callback=print,
) -> list[dict]:
    """Verify a list of lead dicts (must have 'id' and 'email' keys).

    Returns list of dicts with lead_id and verification results.
    Calls the single API per email (MillionVerifier charges 1 credit per call).
    """
    results = []
    total = len(emails)

    for i, lead in enumerate(emails, 1):
        email = str(lead.get("email", "")).strip()
        lead_id = int(lead.get("id", 0))

        if not email or "@" not in email:
            results.append({"lead_id": lead_id, "email_valid": 0, "mv_result": "invalid", "error": "bad format"})
            continue

        result = verify_single(email)
        result["lead_id"] = lead_id

        status_icon = {1: "OK", 0: "INVALID", -1: "UNKNOWN"}.get(result["email_valid"], "?")
        log_callback(f"  [{i}/{total}] {email} -> {status_icon} ({result['mv_result']})")

        results.append(result)

    return results
