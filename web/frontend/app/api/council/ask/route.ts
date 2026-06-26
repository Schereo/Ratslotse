// Streaming passthrough for the "Frag den Rat" SSE endpoint.
//
// The catch-all next.config rewrite (/api/:path*) buffers the upstream response,
// which swallows the incremental Server-Sent Events (steps → sources → tokens). A
// filesystem route handler takes precedence over the (afterFiles) rewrite, fetches
// the backend, and returns the upstream ReadableStream *unbuffered* so the events
// reach the browser as they are produced. `no-transform` stops Caddy from gzip-
// buffering the stream on the edge.

import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const upstream = await fetch(`${BACKEND}/api/council/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      cookie: req.headers.get("cookie") ?? "",
    },
    body,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
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
