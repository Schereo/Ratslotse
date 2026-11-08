import { NextResponse, type NextRequest } from "next/server";

/**
 * Angemeldet auf „/": gleich aufs Dashboard — schon auf dem Server.
 *
 * Bis 11/2026 tat das nur `components/landing-redirect.tsx`, im Browser, und
 * erst nachdem `/api/auth/me` geantwortet hatte. Bis dahin lud die Landing
 * vollständig: three.js für die 3D-Lotti (188 KB gzip), ihre Bilder und vier
 * eigene Anfragen — für eine Seite, die sofort wieder verschwand. Gemessen:
 * „/" angemeldet 22 Anfragen und 764 KB JS, „/dashboard" direkt 19 und 562.
 * Die Komponente bleibt als Rückfall für alles, was hier durchgeht.
 *
 * **Warum der Server fragt, statt nur das Cookie zu sehen.** Ein vorhandenes
 * Sitzungs-Cookie ist nicht immer eine gültige Sitzung: Ein Passwortwechsel
 * oder -Reset auf einem anderen Gerät, ein gelöschtes Konto oder ein neues
 * Signiergeheimnis machen das Token ungültig, das Cookie bleibt aber bis zu
 * seinem Ablauf liegen (das Backend löscht es bei einem 401 nicht). Wer nur aufs Cookie schaut, schickt so jemanden wochenlang von der
 * Startseite über /dashboard auf /login — die Landing wäre für ihn weg. Also
 * nur umleiten, wenn das Backend die Sitzung bestätigt; bei jedem Zweifel
 * (401, Zeitüberschreitung, Backend weg) steht die Landing wie bisher.
 * Ohne Cookie — der Normalfall für Besuch von außen — fragt niemand.
 *
 * **Nur ganze Seitenaufrufe.** Client-Navigation und Prefetch gehen durch: Ein
 * Prefetch kostete sonst je sichtbarem Startseiten-Link einen Aufruf ans
 * Backend, und eine zwischengespeicherte Umleitung überlebte im Router das
 * Abmelden. Beim Klicken übernimmt wie bisher der Rückfall im Browser.
 * Erkannt wird das an `Sec-Fetch-Dest` — die `RSC`-Kopfzeilen und `?_rsc=`
 * nimmt Next der Middleware vorher weg.
 */

/** Wie `COOKIE_NAME` in `web/backend/app/session.py`. */
export const SESSION_COOKIE = "access_token";

/** Die Fluchttür `/?start=1` merkt sich für die Sitzung, dass die Landing
 *  gewollt ist. `sessionStorage` (so macht es der Rückfall im Browser) sieht
 *  der Server nicht — daher zusätzlich dieses Sitzungs-Cookie. */
export const LANDING_WANTED_COOKIE = "ratslotse_landing";

/** Wie lange die Prüfung das erste Byte der Startseite aufhalten darf. Danach
 *  steht die Landing, und der Rückfall im Browser leitet wie früher um. */
export const SESSION_CHECK_TIMEOUT_MS = 800;

export type SessionCheck = (token: string) => Promise<boolean>;

/** Lädt der Browser hier eine ganze Seite? Alle heutigen Browser sagen das mit
 *  `Sec-Fetch-Dest: document`; Next' eigene Abrufe tragen `empty`. Fehlt die
 *  Kopfzeile, entscheidet, ob HTML verlangt wird. */
export function isDocumentRequest(req: NextRequest): boolean {
  const dest = req.headers.get("sec-fetch-dest");
  if (dest) return dest === "document";
  return (req.headers.get("accept") ?? "").includes("text/html");
}

export async function redirectSignedIn(req: NextRequest, sessionValid: SessionCheck): Promise<NextResponse> {
  if (req.nextUrl.searchParams.has("start")) {
    const res = NextResponse.next();
    res.cookies.set(LANDING_WANTED_COOKIE, "1", { path: "/", sameSite: "lax", httpOnly: true });
    return res;
  }
  if (req.method !== "GET" || !isDocumentRequest(req)) return NextResponse.next();
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!token || req.cookies.has(LANDING_WANTED_COOKIE)) return NextResponse.next();
  if (!(await sessionValid(token))) return NextResponse.next();
  // Relativ zur Adresse, die Next selbst kennt — der Router macht daraus ein
  // `Location: /dashboard`, das hinter dem Reverse-Proxy stimmt.
  const res = NextResponse.redirect(new URL("/dashboard", req.url), 307);
  // Persönlich: Kein Zwischenspeicher darf diese Antwort für andere halten.
  res.headers.set("Cache-Control", "private, no-store");
  return res;
}

/** Fragt `/api/auth/me` mit genau diesem Cookie — dieselbe Prüfung, die die
 *  App danach ohnehin macht. */
export function backendSessionCheck(backend: string): SessionCheck {
  return async (token) => {
    try {
      const res = await fetch(`${backend}/api/auth/me`, {
        headers: { cookie: `${SESSION_COOKIE}=${token}` },
        cache: "no-store",
        signal: AbortSignal.timeout(SESSION_CHECK_TIMEOUT_MS),
      });
      return res.ok;
    } catch {
      return false;
    }
  };
}
