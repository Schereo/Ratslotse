// Die Geometrie der Kachelfläche (GB-08) — dasselbe Muster wie `skala.ts`:
// Was sich nachrechnen lässt, wohnt in einem kopflosen Modul, damit
// `scripts/pruefe-kachelflaeche.mjs` es in der CI prüfen kann (Node liest die
// `.ts` direkt). Die Probe prüft damit das ECHTE Modul und keine Kopie seiner
// Regeln — der Fehler, den sie fängt, ist auf einem Bildschirm zu sehen und
// sonst nirgends.
//
// `treemapSquarify` zielt von Haus aus auf den goldenen Schnitt (φ ≈ 1,618).
// Auf einer 854 × 440 großen Fläche legte es den kleinsten Posten der
// Ertragsseite (1,8 von 788,6 Mio. €) als 100 × 5 px quer unter die Reihe —
// und ein 5-px-Streifen liest sich nicht als „sehr kleiner Anteil", sondern
// als Zeichenfehler. Auf Quadrate gezielt wird derselbe Posten 14 × 49 px:
// immer noch winzig, aber als Kachel erkennbar.
//
// Gemessen über alle Breiten von 520 bis 1200 px (Schritt 4), beide
// Datensätze der Komponente, Kürzestseite < 10 px = Splitter:
//
// | Datensatz     | φ (bis 24.08.) | Quadrat (jetzt) |
// |---------------|----------------|-----------------|
// | Erträge       | 0,20 je Breite | 0,00            |
// | Investitionen | 0,00           | 0,00            |
//
// Unbeschriftete Kacheln gehen dabei ebenfalls zurück (Erträge 1,56 → 1,47,
// Investitionen 0,54 → 0,16) — die Umstellung kostet an keiner Stelle etwas.

import { hierarchy, treemap, treemapSquarify } from "d3-hierarchy";

/** Zielverhältnis 1 statt φ — Begründung samt Messung oben. */
export const QUADRATISCH = treemapSquarify.ratio(1);

/** Fuge zwischen zwei Kacheln. Sie trennt auch gleichfarbige Nachbarn: Am
 *  leisen Ende der Rampe teilen sich mehrere Posten eine Stufe. */
export const FUGE = 3;

/** Die Fläche ist etwas breiter als hoch, bleibt aber in einem Rahmen, in dem
 *  auch kleine Kacheln noch Kacheln sind — unten 300 px, damit die Fläche auf
 *  520 px Breite nicht zum Band wird, oben 440 px, damit sie am Desktop nicht
 *  die halbe Seite nimmt. */
export function kachelHoehe(breite: number): number {
  return Math.round(Math.min(Math.max(breite * 0.56, 300), 440));
}

export type Kachel<T> = {
  daten: T;
  x: number;
  y: number;
  breite: number;
  hoehe: number;
};

/** Das Layout, zur Laufzeit gerechnet — je Jahrgang, je Filter neu. */
export function kacheln<T extends { wert: number }>(
  knoten: T[], breite: number, hoehe: number,
): Kachel<T>[] {
  if (!knoten.length || breite <= 0 || hoehe <= 0) return [];
  const wurzel = hierarchy<{ children?: T[]; wert?: number }>({ children: knoten })
    .sum((d) => d.wert ?? 0)
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  return treemap<{ children?: T[]; wert?: number }>()
    .tile(QUADRATISCH)
    .size([breite, hoehe])
    .paddingInner(FUGE)(wurzel)
    .leaves()
    .map((b) => ({
      daten: b.data as T,
      x: b.x0, y: b.y0, breite: b.x1 - b.x0, hoehe: b.y1 - b.y0,
    }));
}

/** Trägt die Kachel ihre Beschriftung? Unter diesen Maßen zeigt erst
 *  Überfahren, Antippen oder der Fokus den Namen — in der Zeile unter dem
 *  Bild, nicht in einem Tooltip. */
export function beschriftet(breite: number, hoehe: number): boolean {
  const winzig = breite < 40 || hoehe < 34;
  return !winzig && (hoehe >= 40 || breite >= 64);
}

/** Schmale Kacheln beschriften vertikal (GB-08). */
export function schmal(breite: number): boolean {
  return breite < 64;
}

/** Zeilenhöhe der Kachel-Beschriftung: 11 px auf `leading-tight` (1,25). */
const ZEILE = 14;
/** Innenabstand der Kachel (`p-1.5`, oben und unten) plus die Wertzeile. */
const RAND = 12;
const WERTZEILE = 16;

/** Wie viele Zeilen der NAME auf dieser Kachel bekommt.
 *
 *  Ohne diese Zahl schnitt `overflow-hidden` die Beschriftung hart ab — bei
 *  854 px Containerbreite endete „Transfererträge" als „Transferer-" mit einem
 *  angeschnittenen „träge" darunter, bei 620 px fehlten „Auflösung von
 *  Sonderposten" 45 px. Ein angeschnittenes Wort liest sich als Fehler; ein
 *  Auslassungszeichen sagt „hier steht mehr", und wo mehr steht, sagt es die
 *  Zeile unter dem Bild vollständig.
 *
 *  Die Schwelle `beschriftet()` bleibt daneben nötig: Sie entscheidet, ob
 *  überhaupt Text auf die Kachel kommt. Diese Zahl entscheidet, wie viel. */
export function namenszeilen(breite: number, hoehe: number): number {
  const platz = schmal(breite)
    // Vertikal gesetzt: Die „Zeilen" sind Spalten, und der Wert steht daneben.
    ? breite - RAND - 30
    : hoehe - RAND - WERTZEILE;
  return Math.max(1, Math.floor(platz / ZEILE));
}

/** Welche Textfarbe eine Kachel dieser Rampenstufe trägt.
 *
 *  `--hh-seg-text` ist für die Anzeigetafel gemacht, deren Rampe bei 69 %
 *  Helligkeit endet. Auf einer KARTE laufen die Rampen weiter — hell bis 90
 *  bzw. 93 %, dunkel bis 18 bzw. 15 % —, und dort trägt sie nur das laute
 *  Ende. Am leisen steht `--foreground`, in beiden Themes: Die Rampen drehen
 *  sich im Dunkelmodus um, die Grenze wandert deshalb NICHT mit.
 *
 *  Gemessen an den Token in `app/globals.css` (WCAG-Verhältnis, Text gegen
 *  Kachelgrund); die Probe rechnet die Tabelle nach:
 *
 *  | Rampe | seg-text | foreground | schlechteste Stelle          |
 *  |-------|----------|------------|------------------------------|
 *  | ein   | Stufe 0–1| Stufe 2–6  | 4,41 : 1 (hell, Stufe 1)     |
 *  | aus   | Stufe 0–2| Stufe 3–9  | 4,30 : 1 (dunkel, Stufe 3)   |
 *
 *  Beide schlechtesten Stellen sind die Mitte ihrer Rampe — dort erreicht
 *  KEINE der beiden Farben 4,5 : 1, gewählt ist die bessere von beiden. Wer
 *  eine Rampe ändert, lässt die Probe laufen. */
export function rampenText(rampe: "ein" | "aus", stufe: number): string {
  const letzteLaute = rampe === "ein" ? 1 : 2;
  return stufe <= letzteLaute ? "var(--hh-seg-text)" : "hsl(var(--foreground))";
}
