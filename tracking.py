from __future__ import annotations

import html
import re
from urllib.parse import quote_plus
from uuid import uuid4


URL_PATTERN = re.compile(r"(https?://[^\s)>\"]+)", re.IGNORECASE)


def new_tracking_id() -> str:
    return uuid4().hex


def append_utm(url: str, campaign: str = "cold_outreach") -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}utm_source=gmail&utm_medium=email&utm_campaign={quote_plus(campaign)}"


def build_click_tracking_url(tracking_base_url: str, tracking_id: str, destination_url: str) -> str:
    base = tracking_base_url.rstrip("/")
    encoded_dest = quote_plus(destination_url)
    return f"{base}/click?tid={tracking_id}&url={encoded_dest}"


def build_open_pixel_url(tracking_base_url: str, tracking_id: str) -> str:
    base = tracking_base_url.rstrip("/")
    return f"{base}/open?tid={tracking_id}"


def wrap_links_for_tracking(text: str, tracking_base_url: str, tracking_id: str, campaign: str = "cold_outreach") -> str:
    # Split at signature divider "---" to avoid wrapping footer URLs
    # Also split at "Best," / "Best regards," to catch signature block
    sig_markers = ["\n---\n", "\nBest,\n", "\nBest regards,\n"]
    sig_start = len(text)
    for marker in sig_markers:
        idx = text.find(marker)
        if idx != -1 and idx < sig_start:
            sig_start = idx

    body_part = text[:sig_start]
    sig_part = text[sig_start:]

    def _replace(match: re.Match) -> str:
        original = match.group(1)
        with_utm = append_utm(original, campaign=campaign)
        return build_click_tracking_url(tracking_base_url, tracking_id, with_utm)

    tracked_body = URL_PATTERN.sub(_replace, body_part)
    return tracked_body + sig_part


def _linkify_urls(html_text: str) -> str:
    """Convert plain-text URLs in already-escaped HTML into clickable <a> tags."""
    # After html.escape, URLs have &amp; instead of & — match those too
    url_pat = re.compile(r"(https?://[^\s<>&]*(?:&amp;[^\s<>&]*)*)", re.IGNORECASE)

    def _make_link(m: re.Match) -> str:
        display_url = m.group(1)
        # Restore real URL for href (unescape &amp; back to &)
        href = display_url.replace("&amp;", "&")

        # For tracking click URLs, extract the final destination for display text
        if "/click?" in href and "url=" in href:
            # Extract destination from ...&url=encoded_dest
            idx = href.index("url=") + 4
            encoded_dest = href[idx:]
            from urllib.parse import unquote_plus
            dest = unquote_plus(encoded_dest)
            # Show friendly label based on destination
            if "linkedin.com" in dest:
                label = "LinkedIn"
            elif "vertiq" in dest:
                label = "vertiq.net"
            else:
                label = dest.split("?")[0][:50]
        else:
            label = display_url[:60]

        return f'<a href="{html.escape(href)}" style="color:#1a73e8;text-decoration:none;">{html.escape(label)}</a>'

    return url_pat.sub(_make_link, html_text)


def to_simple_html_email(body_text: str, tracking_base_url: str | None = None, tracking_id: str | None = None) -> str:
    escaped = html.escape(body_text).replace("\n", "<br>\n")
    escaped = _linkify_urls(escaped)
    pixel = ""
    if tracking_base_url and tracking_id:
        pixel_url = build_open_pixel_url(tracking_base_url, tracking_id)
        pixel = f'<img src="{html.escape(pixel_url)}" width="1" height="1" alt="" style="display:none;">'
    return f"<html><body>{escaped}<br><br>{pixel}</body></html>"

