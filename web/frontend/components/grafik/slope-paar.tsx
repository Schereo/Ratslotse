"use client";

// <SlopePaar> — Vorher/Nachher als Slope-Graph (GB-12, Board H3-07).
//
// Zwei Wertspalten, eine Linie je Paar: Der Blick liest Richtung und Ausmaß
// aller Sprünge auf einmal — und wer 2024 wo stand, gegen wer 2025 wo steht.
//
// DER BRUCH-MARKER IST TEIL DER KOMPONENTE, kein Prop mit Default: Ein Slope
// über einen Systembruch (Grundsteuerreform: neue Messbeträge, neue Basis)
// ohne Beschriftung wäre genau die Grafik, die so tut, als seien beide Seiten
// vergleichbar. `bruchLabel` ist deshalb Pflicht — ohne Label ist der Slope
// nicht baubar.
//
// „UNVERÄNDERT" WIRD AUSGESCHRIEBEN, nie als flache Linie versteckt: Eine
// flache Linie zwischen zwei Spalten, deren Basis nicht dieselbe ist, sähe
// aus wie „alles beim Alten" — dabei ist ein unveränderter Hebesatz auf neuen
// Messbeträgen eine eigene Entscheidung.
//
// KEINE BEWERTUNGSFARBEN (Regel des Bereichs, components/grafik/hantel.tsx):
// Ob ein Sprung nach oben schlecht ist, entscheidet diese Grafik nicht.
// `hervorgehoben` zeichnet eine Zeile dunkler, damit man die eigene Stadt
// findet. Der Bruch ist ein Systemwechsel, keine Abweichung — er bleibt
// neutral gestrichelt, kein Signal-Orange.
//
// Mobil (H4-A/H4-12, eingebaut): Unter 480 px Containerbreite wird der Slope
// automatisch zur Delta-Liste („445 → 539"), der Bruch zur Trennzeile.
//
// MATHE: d3-scale linear für die y-Positionen; das Entzerren der Labels
// (SVG-Text weicht nicht von selbst aus) ist ein einfacher Durchlauf von
// oben nach unten mit Mindestabstand — dieselbe Sorte Handarbeit wie in
// components/grafik/zeitreihe.tsx.

import { useId, type ReactNode } from "react";
import { scaleLinear } from "d3-scale";
import { deZahl } from "@/components/grafik/format";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";

export type SlopePaarZeile = {
  label: string;
  vorher: number;
  nachher: number;
  /** Dunkler zeichnen, damit man die Zeile findet — keine Bewertung. */
  hervorgehoben?: boolean;
};

/** Labels einer Spalte entzerren: sortiert von oben nach unten, dann jedes
 *  mindestens `abstand` unter seinem Vorgänger — und am Ende zurück in die
 *  Zeichenfläche geklemmt. */
function entzerre(ys: number[], abstand: number, von: number, bis: number): number[] {
  const sort_order = ys.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y);
  let letzte = -Infinity;
  for (const e of sort_order) {
    e.y = Math.max(e.y, letzte + abstand);
    letzte = e.y;
  }
  // Läuft die Kette unten heraus, alles gemeinsam hochschieben.
  const ueberhang = Math.max(0, (sort_order.at(-1)?.y ?? von) - bis);
  const aus = new Array<number>(ys.length);
  for (const e of sort_order) aus[e.i] = Math.max(e.y - ueberhang, von);
  return aus;
}

export function SlopePaar({
  paare, bruchLabel, unit, vonLabel, bisLabel, nachkomma = 0, beleg,
}: {
  paare: SlopePaarZeile[];
  /** Was die beiden Spalten trennt — Pflicht, s. Kopfkommentar. */
  bruchLabel: string;
  /** Steht hinter jedem Wert: „%", „€". */
  unit: string;
  /** Spaltenköpfe: „2024" und „2025 · Reform". */
  vonLabel: string;
  bisLabel: string;
  nachkomma?: number;
  /** Beleg-Chip-Slot (GB-00) — die Seite wählt die Quelle. */
  beleg?: ReactNode;
}) {
  const { box, breite } = useBreite();
  const beschreibungId = useId();
  if (!paare.length) return null;

  const value = (v: number) => `${deZahl(v, nachkomma)} ${unit}`;
  const unveraendert = (p: SlopePaarZeile) => p.vorher === p.nachher;

  // Die Delta-Liste ist zugleich die Fassung für die Vorlesehilfe — sie sagt
  // wortwörtlich, was der Slope zeigt.
  const deltaListe = (sichtbar: boolean) => (
    <div className={sichtbar ? undefined : "sr-only"}>
      <p className="flex items-baseline justify-between gap-3 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        <span>{vonLabel}</span>
        <span>{bisLabel}</span>
      </p>
      {/* Der Bruch als Trennzeile (H4-12) — er verschwindet mobil nicht. */}
      <p className="my-1.5 text-center font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
        — {bruchLabel} —
      </p>
      <ul className="flex flex-col gap-1.5">
        {paare.map((p) => (
          <li key={p.label} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
            <span className={cn("text-[12.5px]",
              p.hervorgehoben ? "font-bold" : "text-foreground/85")}>
              {p.label}
            </span>
            {unveraendert(p) ? (
              <span className="font-mono text-[12px] tabular-nums text-muted-foreground">
                {value(p.vorher)} · unverändert
              </span>
            ) : (
              <span className={cn("whitespace-nowrap font-mono text-[12px] tabular-nums",
                p.hervorgehoben ? "font-bold text-foreground" : "text-muted-foreground")}>
                {value(p.vorher)}
                <span aria-hidden="true" className="mx-1.5">→</span>
                <span className="sr-only">auf </span>
                {value(p.nachher)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );

  if (breite < 480) {
    return <div ref={box}>{deltaListe(true)}</div>;
  }

  // --- Der Slope --------------------------------------------------------
  const alle = paare.flatMap((p) => [p.vorher, p.nachher]);
  const zeilenhoehe = 17;
  const KOPF = 24;
  const H = Math.max(200, paare.length * 2 * zeilenhoehe) + KOPF + 8;
  const y = scaleLinear()
    .domain([Math.min(...alle), Math.max(...alle)])
    .range([H - 14, KOPF + 10]);

  const fs = 12;
  const zeichen = 0.58 * fs;
  const linksText = (p: SlopePaarZeile) => `${p.label} ${deZahl(p.vorher, nachkomma)}`;
  const rechtsText = (p: SlopePaarZeile) =>
    `${p.label} ${deZahl(p.nachher, nachkomma)}${unveraendert(p) ? " · unverändert" : ""}`;
  const linksBreit = Math.max(...paare.map((p) => linksText(p).length)) * zeichen;
  const rechtsBreit = Math.max(...paare.map((p) => rechtsText(p).length)) * zeichen;

  const W = breite;
  const xL = Math.min(linksBreit + 10, W * 0.42);
  const xR = Math.max(W - rechtsBreit - 10, W * 0.58);

  const yL = entzerre(paare.map((p) => y(p.vorher)), zeilenhoehe, KOPF + 10, H - 6);
  const yR = entzerre(paare.map((p) => y(p.nachher)), zeilenhoehe, KOPF + 10, H - 6);
  const mitte = (xL + xR) / 2;

  return (
    <div ref={box}>
      <svg
        viewBox={`0 0 ${W} ${H}`} className="block w-full" role="group"
        aria-describedby={beschreibungId}
        aria-label={`${vonLabel} gegen ${bisLabel}, ${paare.length} Paare`}
      >
        {/* Spaltenköpfe */}
        <text x={xL} y={14} textAnchor="end" fontSize={10}
          className="fill-muted-foreground font-mono" style={{ textTransform: "uppercase", letterSpacing: "0.09em" }}>
          {vonLabel}
        </text>
        <text x={xR} y={14} textAnchor="start" fontSize={10}
          className="fill-muted-foreground font-mono" style={{ textTransform: "uppercase", letterSpacing: "0.09em" }}>
          {bisLabel}
        </text>

        {/* Der Bruch: neutral gestrichelt — ein Systemwechsel, keine
            Abweichung, deshalb kein Signal-Orange. */}
        <line x1={mitte} y1={KOPF} x2={mitte} y2={H - 6}
          strokeDasharray="4 4" strokeWidth={1} className="stroke-foreground/35" />
        <text x={mitte} y={14} textAnchor="middle" fontSize={9.5}
          className="fill-muted-foreground font-mono"
          style={{ textTransform: "uppercase", letterSpacing: "0.09em" }}>
          {bruchLabel}
        </text>

        {paare.map((p, i) => {
          const ton = p.hervorgehoben ? "var(--hh-ein-0)" : "var(--hh-ein-3)";
          return (
            <g key={p.label}>
              <line x1={xL + 6} y1={yL[i]} x2={xR - 6} y2={yR[i]}
                strokeWidth={p.hervorgehoben ? 2.4 : 1.5}
                strokeDasharray={unveraendert(p) ? "2 4" : undefined}
                strokeLinecap="round" style={{ stroke: ton }} opacity={0.9} />
              <circle cx={xL + 6} cy={yL[i]} r={3} style={{ fill: ton }} />
              <circle cx={xR - 6} cy={yR[i]} r={3} style={{ fill: ton }} />
              <text x={xL} y={yL[i] + 4} textAnchor="end" fontSize={fs}
                className={p.hervorgehoben ? "fill-foreground font-semibold" : "fill-muted-foreground"}>
                {p.label}{" "}
                <tspan className="font-mono" fontWeight={p.hervorgehoben ? 700 : 500}>
                  {deZahl(p.vorher, nachkomma)}
                </tspan>
              </text>
              <text x={xR} y={yR[i] + 4} textAnchor="start" fontSize={fs}
                className={p.hervorgehoben ? "fill-foreground font-semibold" : "fill-muted-foreground"}>
                {p.label}{" "}
                <tspan className="font-mono" fontWeight={p.hervorgehoben ? 700 : 500}>
                  {deZahl(p.nachher, nachkomma)}
                </tspan>
                {unveraendert(p) && <tspan fontSize={10}> · unverändert</tspan>}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Für die Vorlesehilfe: die Delta-Liste in Worten. */}
      <div id={beschreibungId}>{deltaListe(false)}</div>

      <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-muted-foreground">
        <span>Werte in {unit === "%" ? "Prozent v. H." : unit}.</span>
        {beleg}
      </p>
    </div>
  );
}
