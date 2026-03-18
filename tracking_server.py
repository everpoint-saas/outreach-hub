from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from urllib.parse import unquote_plus

from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse, Response, JSONResponse


app = FastAPI(title="Lead Generator Tracking Server", version="1.0.0")
EVENT_FILE = "data/history/tracking_events.csv"


def _ensure_event_file() -> None:
    os.makedirs("data/history", exist_ok=True)
    if not os.path.exists(EVENT_FILE):
        with open(EVENT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp_utc", "event", "tracking_id", "target_url"])


def _log_event(event: str, tracking_id: str, target_url: str = "") -> None:
    _ensure_event_file()
    with open(EVENT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(timezone.utc).isoformat(), event, tracking_id, target_url])


@app.get("/open")
def open_event(tid: str = Query(default="")):
    _log_event("open", tid, "")
    pixel = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
        b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00"
        b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )
    return Response(content=pixel, media_type="image/gif")


@app.get("/click")
def click_event(
    tid: str = Query(default=""),
    url: str = Query(default="https://www.example.com"),
):
    target = unquote_plus(url)
    _log_event("click", tid, target)
    return RedirectResponse(url=target, status_code=302)


@app.get("/events")
def events():
    _ensure_event_file()
    rows = []
    with open(EVENT_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return JSONResponse(content={"count": len(rows), "events": rows[-200:]})

