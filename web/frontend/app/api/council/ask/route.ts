// Streaming passthrough for the "Frag den Rat" SSE endpoint.
//
// The catch-all next.config rewrite (/api/:path*) buffers the upstream response,
// which swallows the incremental Server-Sent Events (steps → sources → tokens). A
// filesystem route handler takes precedence over the (afterFiles) rewrite, fetches
// the backend, and returns the upstream ReadableStream *unbuffered* so the events
// reach the browser as they are produced. `no-transform` stops Caddy from gzip-
// buffering the stream on the edge.
//
// Die native App ruft diesen Endpoint cross-origin auf (capacitor://localhost →
// ratslotse.de) und authentifiziert per Bearer-Token statt Cookie. Anders als die
// FastAPI-Route (die via CORS-Middleware die App-Origins erlaubt) setzt ein
// Next-Route-Handler von sich aus KEINE CORS-Header — ohne die scheitert der
// Preflight und die App zeigt „Load failed". Darum: CORS für die App-Origins
// spiegeln und den Authorization-Header ans Backend durchreichen.

import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

// WebView-Origins der Capacitor-Apps (iOS: capacitor://localhost, Android:
// https://localhost) — deckungsgleich mit app_cors_origins im Backend.
const APP_ORIGINS = new Set(["capacitor://localhost", "https://localhost"]);

function corsHeaders(origin: string | null): Record<string, string> {
  if (!origin || !APP_ORIGINS.has(origin)) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Vary": "Origin",
  };
}

export function OPTIONS(req: NextRequest) {
  return new Response(null, { status: 204, headers: corsHeaders(req.headers.get("origin")) });
}

export async function POST(req: NextRequest) {
  const cors = corsHeaders(req.headers.get("origin"));
  const body = await req.text();
  const auth = req.headers.get("authorization");
  const upstream = await fetch(`${BACKEND}/api/council/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Web authentifiziert per Cookie, die App per Bearer — beide durchreichen.
      cookie: req.headers.get("cookie") ?? "",
      ...(auth ? { authorization: auth } : {}),
    },
    body,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
        ...cors,
      },
    });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      ...cors,
    },
  });
}
