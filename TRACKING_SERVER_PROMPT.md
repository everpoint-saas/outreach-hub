# Tracking Server Implementation - Cloudflare Workers

## Context

I have a cold email outreach tool (Python/PySide6 desktop app) that sends personalized emails via Gmail API to LEED consultants. Each email contains a 1x1 tracking pixel and wrapped links for open/click tracking.

Current setup:
- `config.py` has `TRACKING_BASE_URL = "http://localhost:8787"` (not working in production)
- `tracking.py` generates tracking IDs and wraps content:
  - Pixel: `<img src="{TRACKING_BASE_URL}/t/{tracking_id}" width="1" height="1" />`
  - Link wrapping: `{TRACKING_BASE_URL}/c/{tracking_id}?url={original_url}`
- Tracking IDs are stored in SQLite `outreach` table (`tracking_id` column)
- I own the domain `vertiq.net` (managed via Cloudflare)

## What I Need

Build a Cloudflare Worker that:

1. **Open Tracking** (`GET /t/{tracking_id}`)
   - Log the open event (tracking_id, timestamp, IP, User-Agent)
   - Return a transparent 1x1 PNG pixel
   - Response headers: `Content-Type: image/png`, `Cache-Control: no-cache`

2. **Click Tracking** (`GET /c/{tracking_id}?url={encoded_url}`)
   - Log the click event (tracking_id, timestamp, IP, User-Agent, destination URL)
   - 302 redirect to the original URL
   - Validate the URL (must start with http:// or https://)

3. **Stats API** (`GET /stats/{tracking_id}`)
   - Return JSON with open count, click count, last opened, last clicked
   - This endpoint is for me to query from my desktop app

4. **Storage**: Use Cloudflare KV namespace called `TRACKING_DATA`
   - Key format: `open:{tracking_id}` -> JSON array of events
   - Key format: `click:{tracking_id}` -> JSON array of events
   - Each event: `{"ts": "ISO timestamp", "ip": "x.x.x.x", "ua": "User-Agent"}`

## Deployment Steps I Need

1. How to create the Cloudflare Worker project (wrangler CLI)
2. The complete worker code (TypeScript preferred)
3. How to create the KV namespace
4. How to deploy
5. How to set up custom domain: `t.vertiq.net` -> this worker
6. How to update my `config.py` to use `https://t.vertiq.net`

## Constraints

- Must be within Cloudflare Workers free tier (100k requests/day - I send 15 emails/day so plenty)
- No authentication needed for /t/ and /c/ endpoints (they're accessed by email clients)
- /stats/ endpoint should have a simple API key check (query param `?key=xxx`)
- Keep it simple - minimal code, no frameworks
- The worker should handle errors gracefully (bad tracking_id, missing URL param, etc.)

## My Environment

- Windows 11 (no WSL)
- Node.js installed
- Cloudflare account with vertiq.net domain
- wrangler CLI: need install instructions if required
