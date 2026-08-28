// Die Skalen-Regeln des Grafik-Baukastens (GB-00).
//
// Zwei Rechnungen, die vor dem 20.08.2026 mitten in `zeitreihe.tsx` standen
// und dort beide falsch waren, ohne dass es jemand sah: Die Kurve wurde ja
// gezeichnet — nur eben außerhalb ihres eigenen Bildes. Sie stehen jetzt
// hier, weil sie so von `scripts/pruefe-skala.mjs` in der CI nachgerechnet
// werden können. Eine Kopie der Regel in der Probe hätte genau den Fall
// nicht gefangen, um den es geht: dass jemand die Regel im Modul ändert.

/** Die Spanne der y-Achse.
 *
 *  `nullbasis` heißt **„die Null gehört ins Bild"** — nicht „die Null ist
 *  unten". Bis zum 20.08.2026 stand hier `[0, max]`, und für jede Reihe des
 *  Haushalts-Bereichs stimmte das auch, weil alle im Plus liegen: Schulden,
 *  Ausgaben, Investitionen, Einnahmen.
 *
 *  Die erste durchweg NEGATIVE Reihe — das geplante Jahresergebnis der
 *  Bäderbetriebsgesellschaft, −2,65 bis −10,13 Mio. € — bekam damit die
 *  Spanne `[0, −2,65]`: umgedreht, und ihr eigenes Minimum lag außerhalb.
 *  Die Kurve lief oben aus dem Bild, die Achse zeigte 0 bis −3, während
 *  unten in der Ableseleiste −10,13 stand. Dieselbe Zeile brach auch jede
 *  gemischte Reihe (−1,2 / 0,8 / 2,4 ergab `[0, 2,4]`) — nur hatte der
 *  Bereich bis dahin keine.
 *
 *  Mit `Math.min(0, …)` / `Math.max(0, …)` bleibt die Null im Bild, egal von
 *  welcher Seite die Werte kommen. Für rein positive Reihen ändert sich
 *  nichts — das ist die Bedingung, unter der diese Änderung sicher ist. */
export function ySpanne(werte: number[], nullbasis: boolean): [number, number] {
  const min = Math.min(...werte);
  const max = Math.max(...werte);
  if (!nullbasis) return [min, max];
  return [Math.min(0, min), Math.max(0, max)];
}

/** So viele Nachkommastellen, dass zwei benachbarte Gitterlinien sich
 *  UNTERSCHEIDEN — abgeleitet aus dem Abstand der Linien.
 *
 *  Vorher stand an der Achse fest `deZahl(v, 0)`. Das ging gut, solange jede
 *  Reihe in zweistelligen Millionen lief. Die erste darunter — die
 *  Wirtschaftspläne der Eigenbetriebe, teils unter 1 Mio. € — bekam eine
 *  Achse, auf der dreimal „0" und zweimal „1" übereinanderstanden.
 *
 *  Bewusst NICHT einfach das `nachkomma` der Reihe genommen: Das schriebe an
 *  die Schuldenkurve „300,0" statt „300". Die Achse braucht so viele Stellen
 *  wie ihr Raster, nicht wie ihre Werte. */
export function achsenStellen(gitter: number[]): number {
  if (gitter.length < 2) return 0;
  const schritt = Math.abs(gitter[1] - gitter[0]);
  if (!(schritt > 0) || schritt >= 1) return 0;
  return Math.min(2, Math.ceil(-Math.log10(schritt)));
}
