// Thin fetch wrapper around the /api backend.
// On the web this is same-origin and auth rides in the httpOnly cookie. In the
// native app the base is the absolute backend origin and auth is a bearer token.
import { toast } from "sonner";
import { entwurfSichern, entwurfZiel } from "./draft";
import { apiBase, clientMarke, isNativeApp } from "./platform";
import { getCachedToken } from "./token";

/** Feldnamen aus Pydantics ``loc`` in etwas, das man vorlesen kann. */
const FIELD_LABELS: Record<string, string> = {
  email: "E-Mail-Adresse",
  password: "Passwort",
  new_password: "Neues Passwort",
  current_password: "Aktuelles Passwort",
  name: "Name",
  display_name: "Anzeigename",
  description: "Beschreibung",
  message: "Nachricht",
  question: "Frage",
};

/** Der erste Pydantic-Fehler als deutscher Satz. Bewusst grob: Die genaue
 *  Ursache steht englisch im ``msg`` und hilft niemandem — was zählt, ist,
 *  welches Feld nicht stimmt. */
function validationMessage(errors: { loc?: unknown[]; msg?: string; type?: string }[]): string {
  const first = errors[0];
  if (!first) return "Eingabe ungültig.";
  const field = [...(first.loc ?? [])].reverse().find((p) => typeof p === "string" && p !== "body");
  const label = typeof field === "string" ? (FIELD_LABELS[field] ?? field) : null;
  if (label === "E-Mail-Adresse") return "Diese E-Mail-Adresse ist ungültig.";
  if (first.type === "too_short" || first.type === "string_too_short") {
    return label ? `${label} ist zu kurz.` : "Eingabe zu kurz.";
  }
  if (first.type === "too_long" || first.type === "string_too_long") {
    return label ? `${label} ist zu lang.` : "Eingabe zu lang.";
  }
  if (first.type === "missing") return label ? `${label} fehlt.` : "Es fehlt eine Angabe.";
  return label ? `${label} ist ungültig.` : "Eingabe ungültig.";
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Global handler invoked when a session expires mid-use (401 on a non-auth
// endpoint). The AuthProvider registers it to clear state and redirect.
let unauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  unauthorizedHandler = fn;
}

/** Wie lange eine Anfrage höchstens dauern darf, bevor die Oberfläche
 *  aufgibt und einen Ausweg zeigt.
 *
 *  Ohne Grenze hing ein Abruf im Funkloch beliebig lange — der Spinner drehte,
 *  bis jemand die Seite schloss. Im Web bricht zwar die Next-Weiterleitung nach
 *  30 s ab, meldete das aber als rohes „Fehler 500". 20 s liegen darunter und
 *  über allem, was ein gesunder Endpunkt braucht (der langsamste, die
 *  Analyse, misst um 1 s). Ströme laufen nicht hierüber. */
export const ANFRAGE_GRENZE_MS = 20_000;

/** Fehlertexte, die eine Bürgerin versteht. Der Browser sagt „Failed to
 *  fetch" (Chrome) oder „Load failed" (Safari), die Weiterleitung „Internal
 *  Server Error" — beides landete bis 10/2026 wörtlich im Toast. */
export const FEHLER_OFFLINE = "Keine Verbindung zu Ratslotse. Prüfe dein Netz und versuch es gleich nochmal.";
export const FEHLER_ZEIT = "Ratslotse antwortet gerade nicht. Versuch es gleich nochmal.";
export const FEHLER_KURZ_WEG = "Ratslotse ist gerade kurz nicht erreichbar, vermutlich wegen eines Updates. Versuch es in einer Minute nochmal.";

/** Gibt es das nicht, oder kam die Antwort nicht an? Nur ein 404 heißt
 *  „gibt es nicht" — ein 500er, ein Funkloch oder eine Zeitüberschreitung
 *  dürfen nie als „Diesen Beschluss finde ich nicht" erscheinen. */
export function istNichtGefunden(fehler: unknown): boolean {
  return fehler instanceof ApiError && fehler.status === 404;
}

/** Lohnt ein neuer Versuch? Nein bei 4xx (die Antwort wird gleich bleiben),
 *  ja bei Netz, Zeit und 5xx. Für `retry` in react-query. */
export function lohntWiederholen(fehler: unknown): boolean {
  return !(fehler instanceof ApiError && fehler.status >= 400 && fehler.status < 500);
}

/** Bricht nach `ms` ab — und ebenso, wenn der Aufrufer selbst abbricht. */
function mitGrenze(eigenes: AbortSignal | null | undefined, ms: number): { signal: AbortSignal; zeitUm: () => boolean; fertig: () => void } {
  const ctrl = new AbortController();
  let um = false;
  const t = setTimeout(() => { um = true; ctrl.abort(); }, ms);
  if (eigenes) {
    if (eigenes.aborted) ctrl.abort();
    else eigenes.addEventListener("abort", () => { clearTimeout(t); ctrl.abort(); }, { once: true });
  }
  ctrl.signal.addEventListener("abort", () => clearTimeout(t), { once: true });
  return { signal: ctrl.signal, zeitUm: () => um, fertig: () => clearTimeout(t) };
}

async function request<T>(path: string, options: RequestInit & { grenzeMs?: number } = {}): Promise<T> {
  const native = isNativeApp();
  const token = native ? getCachedToken() : null;
  const { grenzeMs = ANFRAGE_GRENZE_MS, ...rest } = options;
  const grenze = mitGrenze(rest.signal, grenzeMs);
  let res: Response;
  try {
    res = await fetch(`${apiBase()}/api${path}`, {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        // The native app has no cross-site cookie: it flags itself so the backend
        // returns a long-lived token on login, and carries that token as a bearer.
        // Der Wert nennt die Plattform (ios | android), damit das Backend „App
        // oder Web?" beantworten kann; Browser schicken den Header gar nicht.
        ...(native ? { "X-Client": clientMarke() } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(rest.headers || {}),
      },
      ...rest,
      signal: grenze.signal,
    });
  } catch (e) {
    // Selbst abgebrochen (Seite verlassen, neue Suche): unverändert weiter,
    // die Aufrufer erkennen den AbortError und schweigen.
    if (rest.signal?.aborted) throw e;
    if (grenze.zeitUm()) throw new ApiError(0, FEHLER_ZEIT);
    throw new ApiError(0, FEHLER_OFFLINE);
  }

  if (res.status === 401 && !path.startsWith("/auth/")) {
    // Design 29a (P8): Erst den getippten Text retten, dann rauswerfen. Wer
    // zwei Minuten an einer Frage geschrieben hat, fand danach ein leeres Feld.
    const gerettet = (() => {
      try {
        entwurfSichern(window.location.pathname + window.location.search);
        return !!entwurfZiel();
      } catch { return false; }
    })();
    // Feste id: Läuft die Sitzung ab, scheitern auf „Heute" ein Dutzend
    // Abrufe gleichzeitig — ohne id stapelten sich ebenso viele Toasts.
    toast.info(gerettet
      ? "Sitzung abgelaufen — dein Text ist gesichert."
      : "Sitzung abgelaufen – bitte melde dich erneut an.", { id: "sitzung-abgelaufen" });
    unauthorizedHandler?.();
  }

  if (!res.ok) {
    let detail = `Fehler ${res.status}`;
    // Das Backend startet gerade neu (Deploy) oder die Weiterleitung hat
    // aufgegeben: Antwort kommt als Klartext, nicht als JSON.
    if (res.status === 502 || res.status === 503 || res.status === 504) detail = FEHLER_KURZ_WEG;
    let json = false;
    try {
      const body = await res.json();
      json = true;
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body?.detail)) {
        // FastAPI/Pydantic liefern bei 422 ein Array von Fehler-Objekten. Das
        // wurde bisher als rohes JSON in die Oberfläche geschrieben („[{"type":
        // "value_error","loc":…") — im Simulator an einer ungültigen E-Mail
        // gesehen. Stattdessen der erste Fehler als lesbarer Satz.
        detail = validationMessage(body.detail);
      } else if (body?.detail) {
        detail = JSON.stringify(body.detail);
      }
    } catch {
      /* ignore */
    }
    // Ein 500er OHNE JSON kommt nie vom Backend (das antwortet immer mit
    // `detail`), sondern von der Next-Weiterleitung: Backend weg oder nach
    // 30 s aufgegeben. „Fehler 500" half dort niemandem.
    if (res.status === 500 && !json) detail = FEHLER_KURZ_WEG;
    grenze.fertig();
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) { grenze.fertig(); return undefined as T; }
  try {
    return (await res.json()) as T;
  } catch (e) {
    if (rest.signal?.aborted) throw e;
    throw new ApiError(0, grenze.zeitUm() ? FEHLER_ZEIT : FEHLER_OFFLINE);
  } finally {
    grenze.fertig();
  }
}

export const api = {
  get: <T>(path: string, opts: { signal?: AbortSignal } = {}) => request<T>(path, opts),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "DELETE", body: body ? JSON.stringify(body) : undefined }),
};

/** Absolute URL for a backend path: same-origin on web, absolute in the native app. */
export function apiUrl(path: string): string {
  return `${apiBase()}/api${path}`;
}

/** Auth headers for manual fetches (e.g. SSE streaming) that bypass the `api` wrapper.
 *  Empty on web (the cookie handles auth); bearer + client marker in the app. */
export function authHeaders(): Record<string, string> {
  const native = isNativeApp();
  const token = native ? getCachedToken() : null;
  return {
    ...(native ? { "X-Client": clientMarke() } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function qs(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}
