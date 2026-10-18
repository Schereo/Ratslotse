/**
 * Übersicht der Wahlen: reine Helfer für `/wahlen`.
 *
 * Die Reihenfolge und die Texte kommen aus der Antwort (`GET /api/wahlen`);
 * hier steht nur, was die Anzeige daraus macht.
 */
import type { ApiAntwort } from "./vertrag";
import type { AppWahl } from "./features";

export type Wahlliste = ApiAntwort<"/wahlen">;
export type Wahlzeile = Wahlliste["elections"][number];
export type Wahlpunkt = Wahlzeile["top"][number];

/** Die Wahl, für die sich ein Konto lohnen würde: Es gibt ein Tippspiel, aber
 *  nicht für Anonyme. Das Backend sagt es (`tipp_locked`); die Seite sucht
 *  nur die erste — eine Einladung reicht. */
export function gesperrtesTippspiel(zeilen: readonly Wahlzeile[]): Wahlzeile | null {
  return zeilen.find((z) => z.tipp_locked) ?? null;
}

/** Was oben steht und was darunter: die Wahl im Fokus zuerst, dann die
 *  übrigen in der Reihenfolge der Antwort (neueste zuerst).
 *
 *  Der Fokus ist NICHT immer die neueste: Am 20.09.2026 ist die kommende
 *  Stichwahl im Fokus, während die Ratswahl vom 13.09. das jüngste Ergebnis
 *  ist. Beide Fälle sollen richtig aussehen. */
export function geteilt(zeilen: readonly Wahlzeile[]): { fokus: Wahlzeile | null; weitere: Wahlzeile[] } {
  const fokus = zeilen.find((z) => z.focus) ?? null;
  return { fokus, weitere: zeilen.filter((z) => z !== fokus) };
}

/** Nach Jahren gruppiert — die Übersicht wächst mit jeder Wahl, und ein
 *  Jahrgang ist die Gliederung, die Leute im Kopf haben. */
export function nachJahren(zeilen: readonly Wahlzeile[]): { jahr: string; zeilen: Wahlzeile[] }[] {
  const gruppen = new Map<string, Wahlzeile[]>();
  for (const z of zeilen) {
    const jahr = z.date.slice(0, 4);
    const liste = gruppen.get(jahr);
    if (liste) liste.push(z);
    else gruppen.set(jahr, [z]);
  }
  return [...gruppen.entries()].map(([jahr, zeilen]) => ({ jahr, zeilen }));
}

/** Darf die Wahl gerade laut sein — Hinweis oben auf Heute, Streifen auf der
 *  Startseite? Das entscheidet das Backend aus dem Kalender
 *  (`elections.prominent`: eine Woche vor bis drei Tage nach dem
 *  Wahlschluss). Fehlt das Feld (ältere Antwort), lieber still: Ein Hinweis
 *  zur falschen Zeit ist der Fehler, den Tim am 03.10.2026 gemeldet hat. */
export function wahlLaut(wahl: { prominent?: AppWahl["prominent"] } | null | undefined): boolean {
  return wahl?.prominent === true;
}

/** Ist das Ergebnis amtlich festgestellt? Nur, wenn das Backend es ausdrücklich
 *  sagt (`result_status: "amtlich"` aus dem eingefrorenen Stand). */
export function istAmtlich(status: string | null | undefined): boolean {
  return status === "amtlich";
}

/** Der eine Satz zur Herkunft eines fertigen Ergebnisses. Bis 10/2026 stand
 *  überall „Eigene Rechnung, kein amtliches Ergebnis" — auch drei Wochen,
 *  nachdem der Wahlausschuss es festgestellt hatte. */
export function ergebnisVermerk(status: string | null | undefined): string {
  return istAmtlich(status)
    ? "Das amtliche Endergebnis, vom Wahlausschuss festgestellt."
    : "Vorläufiges Ergebnis — das amtliche stellt der Wahlausschuss fest.";
}
