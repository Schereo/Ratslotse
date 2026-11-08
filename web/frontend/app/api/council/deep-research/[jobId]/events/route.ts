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
// Bearer-Token und `X-Client` der nativen iOS-App werden wie in der ask-Route
// durchgereicht.

import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest, { params }: { params: { jobId: string } }) {
  // Job-IDs sind token_urlsafe(12) — alles andere gar nicht erst ans Backend
  // weiterreichen, damit hier kein Pfad zusammengebaut werden kann.
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(params.jobId)) {
    return new Response(JSON.stringify({ detail: "Unbekannter Job." }), {
      status: 404, headers: { "Content-Type": "application/json" },
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
