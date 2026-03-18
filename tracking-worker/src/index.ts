/**
 * Email Tracking Worker for Cloudflare
 *
 * Endpoints:
 *   GET /open?tid={tracking_id}          - Log open event, return 1x1 pixel
 *   GET /click?tid={tracking_id}&url=... - Log click event, 302 redirect
 *   GET /stats?tid={tracking_id}&key=... - Return JSON stats (auth required)
 *   GET /health                          - Health check
 *
 * Storage: Cloudflare KV namespace "TRACKING_DATA"
 *   Key: "open:{tracking_id}"  -> JSON array of open events
 *   Key: "click:{tracking_id}" -> JSON array of click events
 */

interface Env {
  TRACKING_DATA: KVNamespace;
  STATS_API_KEY: string;
}

interface TrackingEvent {
  ts: string;
  ip: string;
  ua: string;
  url?: string;
}

// 1x1 transparent GIF (smallest possible)
const TRANSPARENT_GIF = new Uint8Array([
  0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00, 0x01, 0x00, 0x80, 0x00,
  0x00, 0x00, 0x00, 0x00, 0xff, 0xff, 0xff, 0x21, 0xf9, 0x04, 0x01, 0x00,
  0x00, 0x00, 0x00, 0x2c, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
  0x00, 0x02, 0x02, 0x44, 0x01, 0x00, 0x3b,
]);

async function appendEvent(
  kv: KVNamespace,
  key: string,
  event: TrackingEvent,
): Promise<void> {
  const existing = await kv.get(key);
  const events: TrackingEvent[] = existing ? JSON.parse(existing) : [];
  events.push(event);
  // Cap at 500 events per key to stay within KV value size limits (25MB)
  if (events.length > 500) {
    events.splice(0, events.length - 500);
  }
  await kv.put(key, JSON.stringify(events));
}

function getClientIP(request: Request): string {
  return request.headers.get("CF-Connecting-IP") || "unknown";
}

function getUserAgent(request: Request): string {
  return request.headers.get("User-Agent") || "unknown";
}

// --- Route Handlers ---

async function handleOpen(
  request: Request,
  url: URL,
  env: Env,
): Promise<Response> {
  const tid = url.searchParams.get("tid");
  if (!tid) {
    return new Response(TRANSPARENT_GIF, {
      headers: { "Content-Type": "image/gif", "Cache-Control": "no-store" },
    });
  }

  const event: TrackingEvent = {
    ts: new Date().toISOString(),
    ip: getClientIP(request),
    ua: getUserAgent(request),
  };

  // Fire-and-forget: log event but don't block the pixel response
  const ctx = (request as any).ctx;
  if (ctx?.waitUntil) {
    ctx.waitUntil(appendEvent(env.TRACKING_DATA, `open:${tid}`, event));
  } else {
    await appendEvent(env.TRACKING_DATA, `open:${tid}`, event);
  }

  return new Response(TRANSPARENT_GIF, {
    headers: {
      "Content-Type": "image/gif",
      "Cache-Control": "no-store, no-cache, must-revalidate",
      Pragma: "no-cache",
      Expires: "0",
    },
  });
}

async function handleClick(
  request: Request,
  url: URL,
  env: Env,
): Promise<Response> {
  const tid = url.searchParams.get("tid");
  const destination = url.searchParams.get("url");

  if (!destination) {
    return new Response("Missing url parameter", { status: 400 });
  }

  // Decode the URL (it may be double-encoded from quote_plus)
  let targetUrl: string;
  try {
    targetUrl = decodeURIComponent(destination);
  } catch {
    targetUrl = destination;
  }

  // Validate URL scheme
  if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
    return new Response("Invalid URL scheme", { status: 400 });
  }

  if (tid) {
    const event: TrackingEvent = {
      ts: new Date().toISOString(),
      ip: getClientIP(request),
      ua: getUserAgent(request),
      url: targetUrl,
    };

    const ctx = (request as any).ctx;
    if (ctx?.waitUntil) {
      ctx.waitUntil(appendEvent(env.TRACKING_DATA, `click:${tid}`, event));
    } else {
      await appendEvent(env.TRACKING_DATA, `click:${tid}`, event);
    }
  }

  return Response.redirect(targetUrl, 302);
}

async function handleStats(url: URL, env: Env): Promise<Response> {
  const key = url.searchParams.get("key");
  if (!key || key !== env.STATS_API_KEY) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const tid = url.searchParams.get("tid");
  if (!tid) {
    return Response.json({ error: "Missing tid parameter" }, { status: 400 });
  }

  const [openData, clickData] = await Promise.all([
    env.TRACKING_DATA.get(`open:${tid}`),
    env.TRACKING_DATA.get(`click:${tid}`),
  ]);

  const opens: TrackingEvent[] = openData ? JSON.parse(openData) : [];
  const clicks: TrackingEvent[] = clickData ? JSON.parse(clickData) : [];

  return Response.json({
    tracking_id: tid,
    opens: {
      count: opens.length,
      last: opens.length > 0 ? opens[opens.length - 1].ts : null,
      events: opens,
    },
    clicks: {
      count: clicks.length,
      last: clicks.length > 0 ? clicks[clicks.length - 1].ts : null,
      events: clicks,
    },
  });
}

async function handleBulkStats(url: URL, env: Env): Promise<Response> {
  const key = url.searchParams.get("key");
  if (!key || key !== env.STATS_API_KEY) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Accept comma-separated tracking IDs
  const tids = url.searchParams.get("tids");
  if (!tids) {
    return Response.json(
      { error: "Missing tids parameter" },
      { status: 400 },
    );
  }

  const idList = tids.split(",").slice(0, 50); // Max 50 at a time
  const results: Record<
    string,
    { open_count: number; click_count: number; last_open: string | null; last_click: string | null }
  > = {};

  await Promise.all(
    idList.map(async (tid) => {
      const [openData, clickData] = await Promise.all([
        env.TRACKING_DATA.get(`open:${tid}`),
        env.TRACKING_DATA.get(`click:${tid}`),
      ]);
      const opens: TrackingEvent[] = openData ? JSON.parse(openData) : [];
      const clicks: TrackingEvent[] = clickData ? JSON.parse(clickData) : [];
      results[tid] = {
        open_count: opens.length,
        click_count: clicks.length,
        last_open: opens.length > 0 ? opens[opens.length - 1].ts : null,
        last_click: clicks.length > 0 ? clicks[clicks.length - 1].ts : null,
      };
    }),
  );

  return Response.json({ results });
}

// --- Main Export ---

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    // Attach ctx to request for waitUntil in handlers
    (request as any).ctx = ctx;

    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405 });
    }

    switch (path) {
      case "/open":
        return handleOpen(request, url, env);
      case "/click":
        return handleClick(request, url, env);
      case "/stats":
        return handleStats(url, env);
      case "/bulk-stats":
        return handleBulkStats(url, env);
      case "/health":
        return Response.json({ status: "ok", timestamp: new Date().toISOString() });
      default:
        return new Response("Not found", { status: 404 });
    }
  },
};
