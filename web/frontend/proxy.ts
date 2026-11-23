import type { NextRequest } from "next/server";
import { backendSessionCheck, redirectSignedIn } from "@/lib/landing-redirect";

// Dieselbe Variable wie für die /api-Weiterleitung in next.config.mjs. Zur
// Laufzeit gelesen, nicht beim Bauen eingesetzt (kein NEXT_PUBLIC_).
const sessionValid = backendSessionCheck(process.env.BACKEND_URL || "http://localhost:8000");

/** Angemeldete auf „/" gleich aufs Dashboard — Begründung und Grenzen in
 *  `lib/landing-redirect.ts`. */
export function proxy(req: NextRequest) {
  return redirectSignedIn(req, sessionValid);
}

// NUR die Startseite. Alles andere läuft am Proxy vorbei. (Bis Next 15 hieß
// die Datei `middleware.ts`; seit Next 16 läuft sie immer in der
// Node-Laufzeit.)
export const config = { matcher: "/" };
