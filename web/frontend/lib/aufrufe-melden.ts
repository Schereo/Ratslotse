"use client";

/**
 * Seitenaufrufe an den EIGENEN Endpunkt melden — anonym und aggregiert.
 *
 * **Warum überhaupt.** Die Nutzung ohne Anmeldung war vollständig unbeobachtet:
 * kein Zugriffslog auf dem Reverse-Proxy, keine Analytik im Frontend. Wer die
 * Startseite ansah oder einem geteilten Beschluss-Link folgte, hinterließ keine
 * Spur. „Viele neue Besucher" ließ sich damit weder bestätigen noch
 * widerlegen.
 *
 * **Warum selbst gebaut und kein fertiges Werkzeug.** Dieselbe Begründung wie
 * bei {@link file://./fehler-melden.ts}: Plausible & Co. sind ein weiterer
 * Empfänger für Daten aus fremden Browsern. Diese Fassung schickt an dieselbe
 * Domäne, aus der die Seite kommt, und landet in einer Tabelle, die nur
 * Summen kennt.
 *
 * **Was gemeldet wird:** der Pfad OHNE Query, der Client, ob jemand angemeldet
 * ist, und ob dies der erste Aufruf in diesem Tab war.
 *
 * **Was NICHT gemeldet wird**, und das ist der Punkt:
 *
 * * **Keine Query.** `?id=8525` verriete, welchen Beschluss jemand liest,
 *   `?q=…` wäre eine Suchanfrage. Der Pfad allein ist stumpf.
 * * **Kein Cookie.** Der Versand geht ausdrücklich OHNE `credentials`. Der
 *   Server löst für diese Meldung kein Konto auf — ob jemand angemeldet ist,
 *   sagt das Feld `logged_in`, und mehr als dieses Ja/Nein wird nicht daraus.
 * * **Kein Referrer, kein User-Agent, keine Verweildauer.** Der Referrer
 *   verriete die Herkunft, der User-Agent ist ein guter Teil eines
 *   Fingerabdrucks.
 * * **Keine Wiedererkennung.** Die Tab-Marke liegt im `sessionStorage` und
 *   verschwindet mit dem Tab; sie ist ein Ja/Nein, keine Kennung — sie wird
 *   nie mitgeschickt.
 *
 * Der Server prüft den Pfad zusätzlich gegen eine Positivliste
 * (`kern/seitenaufrufe.py`); alles Unbekannte fällt in eine Sammelzeile.
 *
 * **Er darf nie stören.** Jeder Schritt ist abgesichert, der Versand ist
 * `keepalive` und blockiert nichts, ein Fehler wird verschluckt.
 */
import { apiUrl } from "./api";

/** Marke für „in diesem Tab war ich schon". Nur lokal, nie im Versand. */
const TAB_MARKE = "ratslotse.aufruf-gesehen";

/** Denselben Pfad nicht zweimal hintereinander melden: Next rendert bei
 *  Query-Wechseln neu, und ein Filterklick ist kein neuer Seitenaufruf. */
let letzterPfad: string | null = null;

function ersterImTab(): boolean {
  try {
    if (window.sessionStorage.getItem(TAB_MARKE)) return false;
    window.sessionStorage.setItem(TAB_MARKE, "1");
    return true;
  } catch {
    // Privates Fenster, blockierter Speicher: dann zählt der Aufruf, aber
    // nicht als Besuch. Lieber eine Zahl zu wenig als ein geworfener Fehler.
    return false;
  }
}

/** Einen Seitenaufruf melden. Wirft nie. */
export function meldeAufruf(pfad: string, angemeldet: boolean, client = "web"): void {
  try {
    if (typeof window === "undefined") return;
    if (pfad === letzterPfad) return;
    letzterPfad = pfad;

    void fetch(apiUrl("/page-views"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // KEIN `credentials: "include"` — die Zählung braucht kein Konto, und
      // ohne Cookie kann der Server sie keinem zuordnen, selbst wenn er wollte.
      keepalive: true,
      body: JSON.stringify({
        route: pfad.slice(0, 200),
        client,
        first: ersterImTab(),
        logged_in: angemeldet,
      }),
    }).catch(() => {
      /* Eine gescheiterte Zählung ist kein Ereignis. */
    });
  } catch {
    /* dito */
  }
}
