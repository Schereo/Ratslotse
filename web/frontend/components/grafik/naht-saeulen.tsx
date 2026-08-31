"use client";

// <NahtSaeulen> — gestapelte Jahres-Säulen über einen Systembruch hinweg
// (GB-02). Mathe: d3-scale (Band + Linear).
//
// DIE NAHT IST DER PUNKT DIESER KOMPONENTE. Wo eine Reihe mitten im
// Zeitraum ihr Regelwerk wechselt (Investitionen: bis 2009 kameral, ab 2010
// doppisch), zeichnen links und rechts der Naht ZWEI FARBWELTEN derselben
// Rampen-Familie — links die neutrale Ausgaben-Rampe (graue Welt), rechts
// die Einnahmen-Rampe (blaue Welt). Die Komponente erzwingt das über
// `naht.zwischen`; es gibt keine Farb-Props, damit niemand „aus Versehen"
// glättet. Eine durchgehende Farbreihe behauptete eine Vergleichbarkeit,
// die die Quelle bestreitet.
//
// WAS DIE KOMPONENTE NICHT RECHNET: nichts über die Naht hinweg. Jede Säule
// ist die Summe ihrer eigenen Teile im eigenen Jahr; es gibt keine Summen-,
// Mittel- oder Veränderungsfunktion zwischen zwei Jahren — erst recht nicht
// zwischen zwei Regelwerken.
//
// LÜCKEN SIND DATEN (`{year, fehlt}`): Ein verworfener Jahrgang steht als
// schraffierte Säule in voller Höhe im Bild (Konvention des Bereichs, s.
// LueckenFeld) und darunter als beschriftetes <LueckenFeld> — gerendert von
// der Komponente, nie von der Seite. Die Ableseleiste nennt an dieser
// Stelle den Grund.
//
// GRUPPIERUNG: Die Stapel bündeln die Auszahlungsarten, damit 22 Säulen
// lesbar bleiben — Desktop/Tablet auf drei Gruppen, mobil auf
// `gruppierungMobil` (2, H4-A). Gebündelt wird NACH GRÖSSE je Farbwelt:
// Die größten Arten (über alle Jahre der Welt summiert) bleiben eigene
// Gruppen, der Rest heißt „übrige“ — keine Stichwort-Raterei, die Titel
// bleiben die der Quelle. Die ABLESELEISTE trennt weiterhin ALLE Arten,
// auf jedem Gerät.
//
// Direktbeschriftung nur an den Endwerten (erste und letzte belegte Säule);
// alles andere über die Ableseleiste — wie bei den Schulden. Deshalb auch
// keine Y-Achse: Das Bild trägt die Form, die Leiste die Zahl (H3-03).

import { useId } from "react";
import type { ReactNode } from "react";
import { scaleBand, scaleLinear } from "d3-scale";
import { useBreite } from "@/lib/use-breite";
import {
  AbleseBeschreibung, AbleseFlaeche, AbleseStelle, Ableseleiste, useAblesen,
} from "@/components/grafik/ablesen";
import { LueckenFeld } from "@/components/grafik/luecken-feld";
import { deZahl } from "@/components/grafik/format";

/** Ein Teil einer Säule — Titel wie in der Quelle, Wert in `einheit`. */
export type NahtTeil = { art: string; wert: number };

/** Ein Jahr der Reihe: entweder belegt (mit seinen Teilen) oder eine Lücke
 *  mit Grund — der Daten-Vertrag des Baukastens (daten.ts). */
export type NahtJahr =
  | { year: number; teile: NahtTeil[] }
  | { year: number; fehlt: string; datum?: string };

function istLuecke(j: NahtJahr): j is Extract<NahtJahr, { fehlt: string }> {
  return "fehlt" in j;
}

/** Die Farbwelten: links der Naht die neutrale Ausgaben-Rampe, rechts die
 *  Einnahmen-Rampe — dunkelste Stufe unten (größte Gruppe), hellste oben. */
const WELT_TOENE: readonly (readonly string[])[] = [
  ["var(--hh-aus-1)", "var(--hh-aus-4)", "var(--hh-aus-7)"],
  ["var(--hh-ein-0)", "var(--hh-ein-2)", "var(--hh-ein-4)"],
];

const H = 252, Y0 = 214, YTOP = 26, NAHT_W = 18;
/** Ab drei Gruppen (Desktop/Tablet); mobil entscheidet `gruppierungMobil`. */
const GRUPPEN_DESK = 3;

type Gruppe = { label: string; arten: string[]; farbe: string };

/** Die Gruppen einer Farbwelt: größte Arten zuerst (eigene Gruppen), der
 *  Rest gebündelt als „übrige“. Gerechnet über alle Jahre der Welt, damit
 *  die Stapel-Reihenfolge über die Jahre stabil bleibt. */
function gruppiere(jahre: NahtJahr[], count: number, toene: readonly string[]): Gruppe[] {
  const summen = new Map<string, number>();
  for (const j of jahre) {
    if (istLuecke(j)) continue;
    for (const t of j.teile) summen.set(t.art, (summen.get(t.art) ?? 0) + t.wert);
  }
  const sortiert = [...summen.entries()].sort((a, b) => b[1] - a[1]).map(([a]) => a);
  if (!sortiert.length) return [];
  const eigene = Math.min(Math.max(count - 1, 1), sortiert.length);
  const gruppen: Gruppe[] = sortiert.slice(0, eigene).map((art, i) => ({
    label: art, arten: [art], farbe: toene[Math.min(i, toene.length - 1)],
  }));
  const rest = sortiert.slice(eigene);
  if (rest.length) {
    gruppen.push({
      label: `übrige (${rest.length} Arten)`, arten: rest,
      farbe: toene[Math.min(eigene, toene.length - 1)],
    });
  }
  return gruppen;
}

export function NahtSaeulen({ jahre, naht, gruppierungMobil = 2, einheit, titel, beleg }: {
  /** Alle Jahre aufsteigend, Lücken eingeschlossen — die x-Achse ist
   *  vollständig, keine Säule kann still fehlen. */
  jahre: NahtJahr[];
  /** Der Systembruch: zwischen welchen Jahren, und der Satz dazu. Ohne Naht
   *  rendert die Komponente eine Welt (die blaue). */
  naht?: { zwischen: [number, number]; text: string };
  /** Wie viele Stapel-Gruppen mobil bleiben (H4-A: 2). */
  gruppierungMobil?: number;
  /** Einheit aller Werte, z. B. „Mio. €“. */
  einheit: string;
  titel: string;
  /** Beleg-Chip der Seite, steht an der Kopfzeile. */
  beleg?: ReactNode;
}) {
  const { box, breite } = useBreite();
  const beschreibungId = useId();
  const schmal = breite < 520;
  const gruppenZahl = schmal ? gruppierungMobil : GRUPPEN_DESK;

  // Die zwei Welten — geteilt an der Naht. Ohne Naht ist alles Welt 1 (blau).
  const grenze = naht ? naht.zwischen[0] : Number.NEGATIVE_INFINITY;
  const welten: NahtJahr[][] = [
    jahre.filter((j) => j.year <= grenze),
    jahre.filter((j) => j.year > grenze),
  ];
  // Kein useMemo: 22 Jahre × 6 Arten sind billiger als die Abhängigkeitsliste.
  const gruppen = welten.map((w, i) => gruppiere(w, gruppenZahl, WELT_TOENE[i]));

  const weltVon = (year: number) => (year <= grenze ? 0 : 1);
  const summe = (j: NahtJahr) =>
    istLuecke(j) ? 0 : j.teile.reduce((s, t) => s + t.wert, 0);

  // Vor dem frühen Ausstieg: Hooks müssen in jeder Render-Runde in derselben
  // Reihenfolge laufen, auch wenn die Reihe (noch) leer ist.
  const ablesen = useAblesen(jahre.length, Math.max(jahre.length - 1, 0));

  const belegte = jahre.filter((j) => !istLuecke(j));
  if (!belegte.length) return null;

  // ── Geometrie: d3-scale rechnet, React zeichnet. ──────────────────────────
  const W = breite;
  const X0 = 6, X1 = W - 6;
  const nahtIdx = naht ? jahre.findIndex((j) => j.year === naht.zwischen[1]) : -1;
  const innen = X1 - X0 - (naht ? NAHT_W : 0);
  const xBand = scaleBand<number>()
    .domain(jahre.map((_, i) => i))
    .range([0, Math.max(innen, 1)])
    .paddingInner(0.16);
  const versatz = (i: number) => (nahtIdx >= 0 && i >= nahtIdx ? NAHT_W : 0);
  const xVon = (i: number) => X0 + (xBand(i) ?? 0) + versatz(i);
  const mitte = (i: number) => xVon(i) + xBand.bandwidth() / 2;
  const maxWert = Math.max(...belegte.map(summe));
  const y = scaleLinear().domain([0, maxWert]).range([Y0, YTOP]).nice();

  const nahtX = nahtIdx > 0 ? (xVon(nahtIdx - 1) + xBand.bandwidth() + xVon(nahtIdx)) / 2 : null;

  // Endwerte: die erste und die letzte BELEGTE Säule tragen ihre Zahl direkt.
  const endwerte = new Set([belegte[0].year, belegte[belegte.length - 1].year]);

  // Jahresachse: zweistellig; mobil nur erste, letzte, Lücken — und die Naht.
  //
  // Das letzte Jahr steht IMMER da; ein Raster-Jahr direkt davor fällt weg.
  // Bei 54 Säulen ist die Schrittweite 2, und die vorletzte Rasterzahl liegt
  // dann genau eine Säule neben der letzten — im Bild stand dort „2425".
  const beschriftet = (j: NahtJahr, i: number): boolean => {
    const letzter = jahre.length - 1;
    if (i === letzter) return true;
    if (!schmal) {
      const schritt = Math.max(Math.ceil(20 / Math.max(xBand.step(), 1)), 1);
      return i % schritt === 0 && letzter - i >= schritt;
    }
    return i === 0 || istLuecke(j);
  };

  // ── Ableseleiste: trennt ALLE Arten, auf jedem Gerät. ─────────────────────
  const stellen: AbleseStelle[] = jahre.map((j) => {
    if (istLuecke(j)) {
      return {
        titel: String(j.year),
        werte: [{ label: "keine Angabe", wert: "—" }],
        vorlesen: `${j.year}: keine Angabe — ${j.fehlt}.`,
      };
    }
    const g = gruppen[weltVon(j.year)];
    const farbeVon = (art: string) =>
      g.find((x) => x.arten.includes(art))?.farbe;
    const teile = j.teile.map((t) => ({
      label: t.art, wert: `${deZahl(t.wert, 1)} ${einheit}`,
      farbe: farbeVon(t.art),
    }));
    // Eine Reihe mit nur EINER Art (die lange Ausgabenreihe) hätte sonst
    // zweimal denselben Betrag in der Leiste — „insgesamt 850,2" und darunter
    // die einzige Art mit 850,2. Dann trägt die Art die Zeile allein; ihr
    // Name sagt ohnehin mehr als das Wort „insgesamt".
    const eineArt = teile.length === 1;
    return {
      titel: String(j.year),
      werte: eineArt ? teile : [
        { label: "insgesamt", wert: `${deZahl(summe(j), 1)} ${einheit}` },
        ...teile,
      ],
      vorlesen: eineArt
        ? `${j.year}: ${j.teile[0].art} ${deZahl(summe(j), 1)} ${einheit}.`
        : `${j.year}: insgesamt ${deZahl(summe(j), 1)} ${einheit}, davon `
          + j.teile.map((t) => `${t.art} ${deZahl(t.wert, 1)}`).join(", ") + ".",
    };
  });

  return (
    <div ref={box}>
      <div className="mb-2 flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {titel}{beleg}
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {jahre[0].year}–{jahre[jahre.length - 1].year} · {belegte.length} Werte · {einheit}
        </span>
      </div>

      <AbleseBeschreibung id={beschreibungId}>
        {`${titel}, ${jahre[0].year} bis ${jahre[jahre.length - 1].year} in ${einheit}: `
          + jahre.map((j) => `${j.year} ${istLuecke(j) ? "keine Angabe" : deZahl(summe(j), 1)}`).join(", ")
          + (naht ? `. ${naht.text}` : "")}
      </AbleseBeschreibung>

      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="group"
        aria-describedby={beschreibungId}
        aria-label={`${titel}, ${jahre[0].year} bis ${jahre[jahre.length - 1].year}`}>
        <defs>
          <pattern id={`${beschreibungId}-luecke`} width="6" height="6"
            patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="2" height="6" className="fill-signal" opacity={0.25} />
          </pattern>
        </defs>

        <line x1={X0} y1={Y0} x2={X1} y2={Y0} className="stroke-border" />

        {jahre.map((j, i) => {
          const x = xVon(i);
          const b = xBand.bandwidth();
          if (istLuecke(j)) {
            // Volle Höhe: Der Platzhalter sagt „hier fehlt die Angabe", nicht
            // „hier war es niedrig" — Konvention wie überall im Bereich.
            return (
              <g key={j.year}>
                <rect x={x} y={YTOP} width={b} height={Y0 - YTOP}
                  fill={`url(#${beschreibungId}-luecke)`} />
                <rect x={x} y={YTOP} width={b} height={Y0 - YTOP} rx={3}
                  fill="none" strokeDasharray="3 3" strokeWidth={1}
                  className="stroke-signal/70" />
              </g>
            );
          }
          const g = gruppen[weltVon(j.year)];
          const werte = g.map((gr) => ({
            farbe: gr.farbe,
            wert: j.teile.filter((t) => gr.arten.includes(t.art))
              .reduce((s, t) => s + t.wert, 0),
          }));
          // Von unten stapeln: größte Gruppe unten, 2 px Fuge dazwischen.
          let unten = Y0;
          return (
            <g key={j.year}>
              {werte.map((s, k) => {
                const hoehe = Math.max(Y0 - y(s.wert), 0);
                const oben = unten - hoehe;
                unten = oben - 2;
                return hoehe > 0 ? (
                  <rect key={k} x={x} y={oben} width={b} height={hoehe}
                    style={{ fill: s.farbe }} />
                ) : null;
              })}
              {endwerte.has(j.year) && (() => {
                // Die Endwerte stehen über der ersten und der letzten Säule,
                // und beide stehen am Rand. Mittig zentriert ragt die Zahl
                // dort aus der viewBox: Bei 54 Säulen auf 375 px war aus
                // „76,5" ein „6,5" geworden. Am Rand rastet die Beschriftung
                // deshalb auf die Kante ein statt auf die Säulenmitte.
                const text = deZahl(summe(j), summe(j) >= 100 ? 0 : 1);
                const halb = text.length * 3.2;
                const links = mitte(i) - halb < X0;
                const rechts = mitte(i) + halb > X1;
                return (
                  <text x={links ? X0 : rechts ? X1 : mitte(i)}
                    y={y(summe(j)) - 6}
                    textAnchor={links ? "start" : rechts ? "end" : "middle"}
                    fontSize={10.5} className="fill-foreground font-mono font-semibold">
                    {text}
                  </text>
                );
              })()}
            </g>
          );
        })}

        {/* Die Naht: gestrichelte Signal-Linie — eine Markierung des
            Systemwechsels, keine Bewertung. */}
        {naht && nahtX != null && (
          <g>
            <line x1={nahtX} y1={YTOP - 12} x2={nahtX} y2={Y0}
              strokeDasharray="4 4" strokeWidth={1.5} className="stroke-signal/80" />
            <text x={nahtX} y={YTOP - 16} textAnchor="middle" fontSize={9.5}
              className="fill-signal font-mono font-semibold"
              style={{ letterSpacing: "0.07em" }}>
              {schmal ? "NAHT" : `NAHT ${naht.zwischen[0]}/${String(naht.zwischen[1]).slice(-2)}`}
            </text>
          </g>
        )}

        {jahre.map((j, i) => beschriftet(j, i) && (
          <text key={j.year} x={mitte(i)} y={Y0 + 16} textAnchor="middle" fontSize={10}
            className={i === jahre.length - 1
              ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
            {String(j.year).slice(-2)}
          </text>
        ))}

        <AbleseFlaeche
          stellen={stellen} steuerung={ablesen} gruppe="Jahre der Reihe"
          x={mitte} xVon={X0} xBis={X1}
          yVon={YTOP} hoehe={Y0 - YTOP} fangHoehe={Y0 + 20 - YTOP}
          marken={(i) => {
            const j = jahre[i];
            if (istLuecke(j)) return [];
            const welt = weltVon(j.year);
            return [{ y: y(summe(j)), farbe: WELT_TOENE[welt][0] }];
          }}
        />
      </svg>

      <Ableseleiste className="mt-2" stelle={stellen[ablesen.aktiv]} steuerung={ablesen}
        note={"Jahr überfahren, antippen oder mit den Pfeiltasten wechseln"
          + (belegte.some((j) => !istLuecke(j) && j.teile.length > 1)
            ? " — die Leiste trennt alle Arten." : ".")} />

      {/* Legende: je Farbwelt ihre Gruppen — zwei Welten, zwei Blöcke. */}
      <div className="mt-2.5 flex flex-col gap-1.5">
        {welten.map((w, wi) => {
          if (!w.length || !gruppen[wi].length) return null;
          const von = w[0].year, bis = w[w.length - 1].year;
          return (
            <div key={wi} className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
                {naht ? `${von}–${bis}` : "Arten"}
              </span>
              {gruppen[wi].map((g) => (
                <span key={g.label} className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                  <span aria-hidden="true" className="h-2.5 w-2.5 flex-none rounded-sm"
                    style={{ background: g.farbe }} />
                  {g.label}
                </span>
              ))}
            </div>
          );
        })}
      </div>

      {/* Der Satz zur Naht und die Lücken — von der Komponente gerendert,
          damit keine Seite sie wegkürzen kann. */}
      {naht && (
        <p className="mt-2.5 flex items-start gap-2 text-[11.5px] leading-relaxed text-muted-foreground">
          <span aria-hidden="true"
            className="mt-[5px] h-0 w-5 flex-none border-t-2 border-dashed border-signal/80" />
          {naht.text}
        </p>
      )}
      {jahre.filter(istLuecke).map((j) => (
        <LueckenFeld key={j.year} className="mt-2"
          label={String(j.year)} grund={j.fehlt} datum={j.datum} />
      ))}
    </div>
  );
}
