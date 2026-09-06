"use client";

/**
 * Fehler aus dem Browser an den EIGENEN Endpunkt melden.
 *
 * **Warum selbst gebaut und kein fertiges Werkzeug.** Sentry & Co. sind
 * bequem, aber sie sind ein weiterer Empfänger für Daten aus fremden Browsern
 * — in einem Projekt, das bei den Sprachmodellen China-Anbieter ausschließt
 * und Zero-Data-Retention verlangt, wäre das ein Bruch im Muster. Diese
 * Fassung schickt an dieselbe Domäne, aus der die Seite kommt, und landet in
 * derselben Tabelle wie die Fehler des Backends.
 *
 * **Was gemeldet wird:** Ausnahmetyp, Meldung, die ersten Zeilen des Stapels
 * und der PFAD OHNE QUERY.
 *
 * **Was NICHT gemeldet wird**, und das ist der Punkt:
 *
 * * **Keine Query.** `?q=wohnungsnot+kreyenbrück` wäre eine Suchanfrage — also
 *   genau das, was niemand über sich preisgeben will.
 * * **Kein Konto, keine Kennung, kein Cookie.** Wir setzen nichts und lesen
 *   nichts; es gibt keinen Wiedererkennungswert zwischen zwei Meldungen.
 * * **Kein `navigator.userAgent`.** Er ist ein guter Teil eines
 *   Fingerabdrucks und beantwortet keine Frage, die wir stellen.
 * * **Keine Sitzungsaufzeichnung.** Werkzeuge, die das können, sind das
 *   Gegenteil von datensparsam.
 *
 * Der Server säubert zusätzlich (`kern/fehler.py`) — hier wird schon gar nicht
 * erst gesammelt, was dort maskiert werden müsste.
 *
 * **Er darf nie stören.** Jeder Schritt ist abgesichert, der Versand ist
 * `keepalive` und blockiert nichts, und ein Fehler beim Melden wird
 * verschluckt: Ein Melder, der selbst wirft, erzeugt eine Endlosschleife.
 */
import { apiUrl } from "./api";

/** So viele Meldungen je Seitenaufruf. Eine kaputte Schleife feuert sonst
 *  hunderte — die Bremse im Backend fängt das zwar, aber sie soll gar nicht
 *  erst gebraucht werden. */
const MAX_JE_SEITE = 5;
/** Dieselbe Meldung nicht zweimal: React ruft `onerror` gern doppelt. */
const gesehen = new Set<string>();
let gesendet = 0;
let angemeldet = false;

function pfadOhneQuery(): string {
  try {
    return window.location.pathname || "/";
  } catch {
    return "/";
  }
}

/** Die ersten Zeilen des Stapels — mehr sagt nichts, und jede Zeile ist eine
 *  Gelegenheit, versehentlich etwas mitzunehmen. */
function stapel(e: unknown): string {
  const roh = (e as Error | undefined)?.stack;
  return typeof roh === "string" ? roh.split("\n").slice(0, 8).join("\n") : "";
}

/** Eine Fehlermeldung abschicken. Wirft nie. */
export function meldeFehler(e: unknown, zusatz?: { route?: string }): void {
  try {
    if (gesendet >= MAX_JE_SEITE) return;
    const fehler = e instanceof Error ? e : new Error(String(e));
    const schluessel = `${fehler.name}|${fehler.message}|${stapel(fehler).slice(0, 200)}`;
    if (gesehen.has(schluessel)) return;
    gesehen.add(schluessel);
    gesendet += 1;

    void fetch(apiUrl("/client-errors"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // KEIN `credentials: "include"` — die Meldung braucht kein Konto, und
      // ohne Cookie kann sie keinem zugeordnet werden.
      keepalive: true,
      body: JSON.stringify({
        name: String(fehler.name || "Error").slice(0, 100),
        message: String(fehler.message || "").slice(0, 1000),
        stack: stapel(fehler).slice(0, 4000),
        route: (zusatz?.route ?? pfadOhneQuery()).slice(0, 200),
      }),
    }).catch(() => {
      /* Der Melder darf nicht selbst melden — sonst dreht sich das im Kreis. */
    });
  } catch {
    /* dito */
  }
}

/** Einmal je Seitenaufruf anhängen. Mehrfach aufzurufen ist folgenlos. */
export function fehlerMelderAnhaengen(): void {
  if (angemeldet || typeof window === "undefined") return;
  angemeldet = true;

  window.addEventListener("error", (ev) => {
    // Fehler beim Laden einer Datei (`<img>`, `<script>`) tragen kein
    // `error`-Objekt und sagen uns nichts über den Code — sie kommen aus dem
    // Netz des Besuchers, nicht aus unserem Programm.
    if (ev.error) meldeFehler(ev.error);
  });

  window.addEventListener("unhandledrejection", (ev) => {
    meldeFehler(ev.reason);
  });
}
