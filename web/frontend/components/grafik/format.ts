// Zahlenformat des Grafik-Baukastens — Intl statt d3-format.
//
// GB-15 begründet den Verzicht auf d3-format/d3-time-format: deutsche Zahlen
// und Daten macht `Intl` besser und ohne zusätzliche Bytes. Jede Grafik des
// Baukastens formatiert ausschließlich hierüber (GB-00: „Intl.NumberFormat
// (de-DE) für alle Zahlen") — wer in einer Komponente `toLocaleString` oder
// gar einen eigenen Tausenderpunkt tippt, baut die zweite Wahrheit, die diese
// Datei verhindert.
//
// Die Formatter werden GECACHT: `new Intl.NumberFormat` ist teuer genug, dass
// es in einer Treemap mit 4.459 Kacheln auffiele. Der Schlüssel ist die
// Options-Signatur, der Cache lebt im Modul — auf dem Server wie im Browser.

import { deMio, amount } from "@/lib/haushalt";

// `deMio` („283,1" — eine Nachkommastelle, Werte kommen als Mio.) und
// `amount` (passende Einheit €/Tsd. €/Mio. €) existieren seit der ersten
// Haushalts-Runde in `lib/haushalt.ts`. Sie bleiben dort die eine
// Implementierung; der Baukasten reicht sie nur durch, damit Grafiken einen
// einzigen Format-Import haben.
export { deMio, amount };

const cache = new Map<string, Intl.NumberFormat>();

function formatter(opts: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = JSON.stringify(opts);
  let f = cache.get(key);
  if (!f) {
    f = new Intl.NumberFormat("de-DE", opts);
    cache.set(key, f);
  }
  return f;
}

/** „5.013" bzw. „62,0" — deutsche Gruppierung, feste Nachkommastellen.
 *
 *  Feste, nicht maximale Stellen: In einer Spalte aus „62,0" und „7,5" darf
 *  keine „7" ohne Komma stehen, sonst springt die Ausrichtung
 *  (`tabular-nums` hilft nur, wenn alle Werte gleich viele Zeichen tragen). */
export function deZahl(v: number | null | undefined, nachkomma = 0): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return formatter({
    minimumFractionDigits: nachkomma,
    maximumFractionDigits: nachkomma,
  }).format(v);
}

/** „+12,4" / „−6,2" / „0,0" — Differenzen tragen ihr Vorzeichen.
 *
 *  `exceptZero`: Eine Null ist keine Abweichung und bekommt kein Plus.
 *  Das ist dieselbe Konvention, die `zeitreihe.tsx` von Hand baute — wer
 *  eine Differenz zeigt (immer Signal-Orange), formatiert sie hierüber. */
export function mitVorzeichen(v: number | null | undefined, nachkomma = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return formatter({
    minimumFractionDigits: nachkomma,
    maximumFractionDigits: nachkomma,
    signDisplay: "exceptZero",
  }).format(v);
}
