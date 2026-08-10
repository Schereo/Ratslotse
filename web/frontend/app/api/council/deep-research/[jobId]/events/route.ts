// Streaming-Passthrough für die Events der „Gründlichen Recherche" (RG-10).
//
// Dieselbe Falle wie bei /api/council/ask, nur später bemerkt: Der Catch-all-
// Rewrite aus next.config (/api/:path*) PUFFERT die Antwort des Backends. Für
// eine JSON-Antwort ist das egal, für einen Event-Stream tödlich — sämtliche
// Events (phase → facetten → facette → sources → token → done) trafen erst
// gebündelt ein, wenn der Job fertig war. Sichtbare Folge: Die Fortschritts-
// Karte blieb die ganze Recherche über beim ersten Schritt stehen und sprang
// dann direkt zum fertigen Bericht (Tims Befund).
//
// Ein Datei-Route-Handler hat Vorrang vor dem (afterFiles-)Rewrite, holt das
// Backend selbst und reicht dessen ReadableStream UNGEPUFFERT durch.
// `no-transform` hält Caddy davon ab, den Stream am Rand zu gzip-puffern.
//
// CORS wie in der ask-Route: Die native App ruft cross-origin auf
// (capacitor://localhost → ratslotse.de) und authentifiziert per Bearer-Token;
// ein Next-Route-Handler setzt von sich aus KEINE CORS-Header.

import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

const APP_ORIGINS = new Set(["capacitor://localhost", "https://localhost"]);

function corsHeaders(req: NextRequest): Record<string, string> {
  const origin = req.headers.get("origin");
  if (!origin || !APP_ORIGINS.has(origin)) return {};
  const requested = req.headers.get("access-control-request-headers");
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": requested || "Content-Type, Authorization, X-Client",
    "Vary": "Origin, Access-Control-Request-Headers",
  };
}

export function OPTIONS(req: NextRequest) {
  return new Response(null, { status: 204, headers: corsHeaders(req) });
}

export async function GET(req: NextRequest, { params }: { params: { jobId: string } }) {
  const cors = corsHeaders(req);
  // Job-IDs sind token_urlsafe(12) — alles andere gar nicht erst ans Backend
  // weiterreichen, damit hier kein Pfad zusammengebaut werden kann.
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(params.jobId)) {
    return new Response(JSON.stringify({ detail: "Unbekannter Job." }), {
      status: 404, headers: { "Content-Type": "application/json", ...cors },
    });
  }
  const ab = req.nextUrl.searchParams.get("ab");
  const abParam = ab && /^\d{1,9}$/.test(ab) ? `?ab=${ab}` : "";
  const auth = req.headers.get("authorization");
  const client = req.headers.get("x-client");

  const upstream = await fetch(
    `${BACKEND}/api/council/deep-research/${params.jobId}/events${abParam}`,
    {
      headers: {
        cookie: req.headers.get("cookie") ?? "",
        ...(auth ? { authorization: auth } : {}),
        ...(client ? { "x-client": client } : {}),
      },
      // Bricht der Client ab (Tab zu, Navigation), soll auch diese Verbindung
      // fallen — der Job selbst läuft server-seitig weiter, das ist der Sinn.
      signal: req.signal,
    },
  );

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
