import type { ApiAntwort } from "@/lib/vertrag";

/** Die Ebene „Wahlergebnis" der Stadtkarte (docs/plan-viertel-wahlkarte.md):
 *  je Urnenbezirk die Farbe dessen, der dort vorn lag — die Deckkraft sagt,
 *  wie deutlich.
 *
 *  Gerechnet hat das Backend (`/api/wahlabend/karte`): wer vorn lag, der
 *  Vorsprung, in welchen Ortsbereichen ein Bezirk liegt. Hier steht nur, was
 *  die Anzeige daraus macht — Farbe, Deckkraft, Auswahl.
 *
 *  Bis 09/2026 tönte die Ebene die Ortsbereiche nach ihrem Wahlbereich in
 *  Primärblau, „ungefähr". Die Bezirke liegen aber nicht in den
 *  Ortsbereichen (23 von 91 zu weniger als 80 % in einem); die genaue
 *  Antwort ist die Bezirksfläche selbst.
 */
export type Wahlkarte = ApiAntwort<"/wahlabend/karte">;
export type WahlkarteBezirk = Wahlkarte["districts"][number];
export type WahlkarteBereich = Wahlkarte["areas"][number];
export type WahlkarteWer = Wahlkarte["contestants"][number];

/** Ab diesem Vorsprung (Prozentpunkte) ist eine Fläche satt. Knapper als
 *  drei Punkte bleibt sie fast leer — 29 der 91 Bezirke der Ratswahl. */
export const VORSPRUNG_SATT = 20;

/** Die Deckkraft einer Bezirksfläche aus dem Vorsprung. */
export function deckkraft(margin: number | null | undefined): number {
  if (margin == null) return 0;
  return 0.15 + 0.6 * Math.min(1, Math.max(0, margin) / VORSPRUNG_SATT);
}

export function werNachSlug(daten: Wahlkarte): Map<string, WahlkarteWer> {
  return new Map(daten.contestants.map((c) => [c.slug, c]));
}

/** Die Farbe einer Liste im aktuellen Modus — CDU-Schwarz wäre im Dunkeln
 *  eine Wand, deshalb die `color_dark` der Stammdaten. */
export function farbe(wer: WahlkarteWer | undefined, dunkel: boolean): string {
  if (!wer) return dunkel ? "#94a3b8" : "#64748b";
  return dunkel ? wer.color_dark || wer.color : wer.color;
}

/** Die Bezirke, die einen Ortsbereich berühren — größter Anteil zuerst. */
export function bezirkeIn(daten: Wahlkarte, ort: string): WahlkarteBezirk[] {
  return daten.districts
    .filter((d) => d.places.some((p) => p.name === ort))
    .sort((a, b) => anteilIn(b, ort) - anteilIn(a, ort) || a.number - b.number);
}

/** Wie viel der Fläche eines Bezirks im Ortsbereich liegt (0…1). */
export function anteilIn(d: WahlkarteBezirk, ort: string): number {
  return d.places.find((p) => p.name === ort)?.share ?? 0;
}

/** Der Satz zur Lage eines Bezirks — leer, wenn er (fast) ganz im
 *  Ortsbereich liegt. Ohne ihn sähe ein Bezirk, der nur zu einem Viertel
 *  dazugehört, aus wie „so hat dieser Stadtteil gewählt". */
export function lageSatz(d: WahlkarteBezirk, ort: string | null): string | null {
  if (!ort) {
    if (d.places.length < 2) return null;
    return `Liegt in ${aufzaehlen(d.places.map((p) => p.name))}.`;
  }
  const a = anteilIn(d, ort);
  if (a >= 0.8) return null;
  const andere = d.places.filter((p) => p.name !== ort).map((p) => p.name);
  const pct = Math.round(a * 100);
  return `Liegt nur zu ${pct} % in ${ort}${andere.length ? `, sonst in ${aufzaehlen(andere)}` : ""}.`;
}

function aufzaehlen(namen: string[]): string {
  if (namen.length <= 1) return namen.join("");
  return `${namen.slice(0, -1).join(", ")} und ${namen[namen.length - 1]}`;
}

export function prozent(share: number | null | undefined): string {
  return share == null ? "–" : `${share.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}

export function punkte(margin: number | null | undefined): string {
  if (margin == null) return "–";
  return `${margin.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} Pkt.`;
}

/** „vorn: SPD" / „Gleichstand" / „noch nicht gezählt". */
export function fuehrungText(d: WahlkarteBezirk, wer: Map<string, WahlkarteWer>): string {
  if (!d.counted) return "noch nicht gezählt";
  if (!d.leader) return "Gleichstand";
  return `vorn: ${wer.get(d.leader)?.short ?? d.leader}`;
}

/** Die Wahlen für die Chips, in der Reihenfolge der Antwort. */
export function wahlParam(slug: string | null | undefined, daten: Wahlkarte | undefined): string | null {
  if (!slug || !daten) return slug ?? null;
  // Die Vorgabe (die erste) bleibt aus der Adresse heraus.
  return daten.elections[0]?.slug === slug ? null : slug;
}
