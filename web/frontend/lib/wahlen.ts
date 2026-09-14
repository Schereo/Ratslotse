/**
 * Übersicht der Wahlen: reine Helfer für `/wahlen`.
 *
 * Die Reihenfolge und die Texte kommen aus der Antwort (`GET /api/wahlen`);
 * hier steht nur, was die Anzeige daraus macht.
 */
import type { ApiAntwort } from "./vertrag";

export type Wahlliste = ApiAntwort<"/wahlen">;
export type Wahlzeile = Wahlliste["elections"][number];

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

/** „Am 27. September", „Heute", „Seit dem 13. September" — ein Satzanfang
 *  für die Zeile, je nachdem ob die Wahl noch kommt. */
export function wann(zeile: Wahlzeile, jetzt: Date = new Date()): string {
  const schluss = new Date(zeile.polls_close).getTime();
  if (!Number.isFinite(schluss)) return "";
  return jetzt.getTime() < schluss ? "kommt" : "gelaufen";
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
