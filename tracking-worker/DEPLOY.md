# Tracking Server Deployment Guide

## Prerequisites
- Node.js installed (already have it)
- Cloudflare account with vertiq.net domain

---

## Step 1: Install Dependencies

Open terminal in `C:\Users\gnt85\mailing_list\tracking-worker\`:

```bash
cd C:\Users\gnt85\mailing_list\tracking-worker
npm install
```

This installs wrangler CLI and TypeScript types.

---

## Step 2: Login to Cloudflare

```bash
npx wrangler login
```

This opens a browser window. Click "Allow" to authorize wrangler.

To verify login:
```bash
npx wrangler whoami
```

---

## Step 3: Create KV Namespace

```bash
npx wrangler kv namespace create TRACKING_DATA
```

This outputs something like:
```
{ binding = "TRACKING_DATA", id = "abc123def456..." }
```

**Copy the `id` value** and paste it into `wrangler.toml`:
- Open `wrangler.toml`
- Replace `REPLACE_WITH_KV_NAMESPACE_ID` with the actual ID

---

## Step 4: Set API Key for Stats Endpoint

Open `wrangler.toml` and replace `REPLACE_WITH_YOUR_SECRET_KEY` with any
random string you want. This protects the /stats endpoint.

Example: generate one with `node -e "console.log(require('crypto').randomBytes(24).toString('hex'))"`

Save the key somewhere (you'll need it to query stats from your desktop app).

---

## Step 5: Deploy

```bash
npx wrangler deploy
```

This deploys to `email-tracking.<your-account>.workers.dev`.

You can test it immediately:
- Open browser: `https://email-tracking.<your-subdomain>.workers.dev/health`
- Should return: `{"status":"ok","timestamp":"..."}`

---

## Step 6: Set Up Custom Domain (t.vertiq.net)

1. Go to Cloudflare Dashboard: https://dash.cloudflare.com
2. Click "Workers & Pages" in the left sidebar
3. Click on "email-tracking" worker
4. Click "Settings" tab -> "Domains & Routes"
5. Click "Add" -> "Custom Domain"
6. Enter: `t.vertiq.net`
7. Click "Add Domain"

Cloudflare automatically handles DNS and SSL. No manual DNS record needed.

Wait 1-2 minutes for it to propagate, then test:
- `https://t.vertiq.net/health` -> should return JSON

---

## Step 7: Verify Everything Works

### Test open tracking:
Open in browser: `https://t.vertiq.net/open?tid=test123`
- Should show a tiny blank page (1x1 pixel)

### Test click tracking:
Open in browser: `https://t.vertiq.net/click?tid=test123&url=https%3A%2F%2Fwww.google.com`
- Should redirect to Google

### Test stats:
Open in browser: `https://t.vertiq.net/stats?tid=test123&key=YOUR_API_KEY`
- Should show JSON with open and click counts from the tests above

---

## Done!

The tracking server is live. Your desktop app's `config.py` is already
updated to use `https://t.vertiq.net`.

Next time you send emails with tracking enabled, opens and clicks will
be logged to Cloudflare KV automatically.

---

## Useful Commands

```bash
# View real-time logs
npx wrangler tail

# Re-deploy after code changes
npx wrangler deploy

# Local development (port 8787)
npx wrangler dev
```

## Cost

Cloudflare Workers free tier: 100,000 requests/day.
You send 15 emails/day. Even if each email triggers 100 pixel loads
(email clients pre-fetch), that's 1,500 requests. Nowhere near the limit.
