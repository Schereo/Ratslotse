/** Die Wahlbereiche und Wahlbezirke Oldenburgs als Flächen.
 *
 *  Quelle: openGEOdata der Stadt (Feature Service „Wahlen"), Lizenz
 *  dl-zero-de/2.0, geholt und vereinfacht von `scripts/wahl_geodaten.py`.
 *  Die Dateien liegen als statische Assets im Repo — Wahlbezirke ändern sich
 *  vor einer Wahl, nicht dazwischen.
 *
 *  Geladen wird erst, wenn eine Karte sie braucht (die Wahlbezirke sind
 *  42 KB), und höchstens einmal je Seitenaufruf.
 */

import type { GeoFlaeche } from "@/lib/gebiete";

/** Ein Wahlbereich: `nr` ist 1…6, im Wahlabend die römische Ziffer. */
export type Wahlbereichflaeche = GeoFlaeche<{ nr: number }>;

/** Ein Wahlbezirk: `nr` ist die Bezirksnummer (101…966), `wb` sein
 *  Wahlbereich, `name` der Stadtbezirk, `lokal` die Wahllokal-Kennung. */
export type Wahlbezirkflaeche = GeoFlaeche<{ nr: number; wb: number; name: string; lokal: number | null }>;

const speicher = new Map<string, Promise<unknown[]>>();

function lade<T>(datei: string): Promise<T[]> {
  const vorhanden = speicher.get(datei) as Promise<T[]> | undefined;
  if (vorhanden) return vorhanden;
  const versprechen = fetch(`/geo/${datei}`)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .then((fc) => fc.features as T[])
    .catch(() => {
      // Beim nächsten Aufruf noch einmal versuchen — eine Karte, die einmal
      // nicht geladen hat, soll nicht bis zum Neuladen der Seite leer bleiben.
      speicher.delete(datei);
      return [] as T[];
    });
  speicher.set(datei, versprechen as Promise<unknown[]>);
  return versprechen;
}

export function ladeWahlbereiche(): Promise<Wahlbereichflaeche[]> {
  return lade<Wahlbereichflaeche>("wahlbereiche-oldenburg.json");
}

export function ladeWahlbezirke(): Promise<Wahlbezirkflaeche[]> {
  return lade<Wahlbezirkflaeche>("wahlbezirke-oldenburg.json");
}

/** Römische Ziffer eines Wahlbereichs — dieselbe Schreibweise wie im
 *  Backend (`ElectionArea.roman`), für Flächen, die nur ihre Nummer kennen. */
export function roemisch(nr: number): string {
  return ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][nr] ?? String(nr);
}
