// Streaming passthrough for the "Frag den Rat" SSE endpoint.
//
// The catch-all next.config rewrite (/api/:path*) buffers the upstream response,
// which swallows the incremental Server-Sent Events (steps → sources → tokens). A
// filesystem route handler takes precedence over the (afterFiles) rewrite, fetches
// the backend, and returns the upstream ReadableStream *unbuffered* so the events
// reach the browser as they are produced. `no-transform` stops Caddy from gzip-
// buffering the stream on the edge.
//
// Die native iOS-App authentifiziert per Bearer-Token statt Cookie und meldet
// sich mit `X-Client` — beides wird ans Backend durchgereicht, falls ihre
// Anfrage hier ankommt statt direkt bei FastAPI (s. ios/README.md).

import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const auth = req.headers.get("authorization");
  const client = req.headers.get("x-client");
  const upstream = await fetch(`${BACKEND}/api/council/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Web authentifiziert per Cookie, die App per Bearer — beide durchreichen.
      cookie: req.headers.get("cookie") ?? "",
      ...(auth ? { authorization: auth } : {}),
      // `X-Client: app` wertet aktuell nur der Login aus; trotzdem
      // weiterreichen, damit das Backend hier dieselbe Sicht hat wie sonst.
      ...(client ? { "x-client": client } : {}),
    },
    body,
    // Bricht der Browser ab (Stopp, Seite verlassen), endet auch die Anfrage
    // ans Backend — sonst schrieb es die Antwort für niemanden zu Ende. Die
    // Recherche-Route tat das schon.
    signal: req.signal,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
      },
    });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
