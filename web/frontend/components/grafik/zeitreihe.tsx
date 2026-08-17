"use client";

// <Zeitreihe> — die allgemeine Linien-Zeitreihe des Grafik-Baukastens (GB-01),
// dazu <ZeitreiheMini> als Karten-Sparkline (H3-02: Beteiligungs-Karten).
//
// MATHE: d3-scale (Skalen, nice ticks) + d3-shape (`line`/`area` mit
// `defined`). Das `defined`-Prädikat (`definiert`, der Type Guard über der
// normalisierten Reihe — dasselbe Muster wie `vorhanden` im Daten-Vertrag)
// lässt die Linie an jeder Lücke ABREISSEN, weil d3-shape dort schlicht kein
// Segment zeichnet. Interpolation ist damit im Code unmöglich, nicht nur
// verboten: Es gibt keine Stelle, an der ein Zwischenwert entstünde.
//
// LÜCKEN SIND DATEN (GB-00): `{jahr, fehlt}` steht IN der Reihe. Im Bild
// rendert die Lücke als schraffierter Kasten mit gestrichelter Signal-Kante
// (die Konvention des Bereichs), darunter beschriftet sie ein <LueckenFeld> —
// von der Komponente, nie von der Seite. Ein Jahr, das in der Reihe einfach
// FEHLT (weder Wert noch Lücke), bricht die Linie ebenfalls und bekommt einen
// „?"-Kasten: lieber sichtbar unerklärt als still durchgezogen.
//
// DIREKTBESCHRIFTUNG NUR ENDWERTE (GB-01) — alles andere liest die
// <Ableseleiste> (GB-00): Desktop Hover, mobil sticky Tap-Zeile, immer
// Pfeiltasten. Kein Tooltip; was nur beim Hovern existiert, fehlt im
// Ausdruck und in der Vorlesehilfe.
//
// BREAKPOINTS EINGEBAUT, KEIN PROP (H4-A „Zeitreihe + Ableseleiste"):
// unter 520 px Containerbreite wird die Zeichenfläche 180 px hoch, die
// Achse zeigt nur Dekaden, die Schrift wächst auf Fingermaß. Gemessen wird
// der Container (`lib/use-breite.ts`), damit die viewBox auf Faktor 1,0
// bleibt und nichts mitgestaucht wird.
//
// KEINE BEWERTUNGSFARBEN: Die Reihe trägt den neutralen Schieferton
// `--hh-aus-0` (theme-geprüft gegen die Karte), die Zweitreihe eine eigene
// Rampenstufe — nie Signal-Orange, denn eine zweite Größe ist keine
// Abweichung. Orange bleibt den Lücken-Markierungen vorbehalten.

import { useId, type ReactNode } from "react";
import { scaleLinear } from "d3-scale";
import { area, line } from "d3-shape";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";
import { istLuecke, type JahrLuecke, type JahrPunkt, type JahrWert } from "./daten";
import { deZahl } from "./format";
import { LueckenFeld } from "./luecken-feld";
import {
  AbleseBeschreibung, AbleseFlaeche, Ableseleiste, useAblesen,
  type AbleseStelle, type AbleseWert,
} from "./ablesen";

/** Farbe der Hauptreihe: der neutrale Schieferton des Bereichs. */
const TON = "var(--hh-aus-0)";
/** Farbe der Zweitreihe: eigene Rampenstufe, KEIN Orange (eine zweite
 *  Größe ist keine Abweichung — H4-13: „Zins ist keine Abweichung"). */
const TON_ZWEIT = "var(--hh-ein-1)";

// Beschriftungen im Bild bekommen einen Kontur-Halo in Kartenfarbe, sonst
// schneidet die Kurve mitten durch die Ziffern (Muster aus `schulden-kurve`).
const halo = { paintOrder: "stroke", strokeWidth: 3, strokeLinejoin: "round" } as const;

export type ZeitreiheAnnotation = { jahr: number; text: string };

export type ZeitreiheUmschalter = {
  /** Beschriftungen der Ansichten, z. B. ["absolut", "pro Kopf"]. */
  optionen: readonly string[];
  aktiv: number;
  onWahl: (i: number) => void;
};

/** Ein Jahr der normalisierten Reihe: Wert, erklärte Lücke — oder ein Jahr,
 *  das in der Reihe schlicht fehlt (`unerklaert`). */
type Stelle =
  | { jahr: number; art: "wert"; punkt: JahrWert }
  | { jahr: number; art: "luecke"; punkt: JahrLuecke }
  | { jahr: number; art: "unerklaert" };

type WertStelle = Extract<Stelle, { art: "wert" }>;

/** Das `defined`-Prädikat für d3-shape — UND der Type Guard fürs Lesen:
 *  Wer an den Wert will, kommt am Lücken-Zweig nicht vorbei. */
const definiert = (s: Stelle): s is WertStelle => s.art === "wert";

/** Die Reihe auf den vollen Jahresbereich normalisieren — so kann kein
 *  fehlendes Jahr aus der x-Achse herausfallen und still interpoliert wirken. */
function normalisiere(reihe: JahrPunkt[]): Stelle[] {
  const sortiert = [...reihe].sort((a, b) => a.jahr - b.jahr);
  if (!sortiert.length) return [];
  const nach = new Map(sortiert.map((p) => [p.jahr, p]));
  const aus: Stelle[] = [];
  for (let jahr = sortiert[0].jahr; jahr <= sortiert[sortiert.length - 1].jahr; jahr++) {
    const p = nach.get(jahr);
    if (!p) aus.push({ jahr, art: "unerklaert" });
    else if (istLuecke(p)) aus.push({ jahr, art: "luecke", punkt: p });
    else aus.push({ jahr, art: "wert", punkt: p });
  }
  return aus;
}

export function Zeitreihe({
  reihe, einheit, ariaTitel, nachkomma = 1, format, zweitreihe, annotationen,
  umschalter, beleg, nullbasis = true, hinweis, className,
}: {
  /** Punkte UND Lücken in einer Liste (Daten-Vertrag GB-00). */
  reihe: JahrPunkt[];
  /** Steht in der Ableseleiste und der Kopf-Zeile, z. B. „Mio. €". */
  einheit: string;
  /** Der Satz für die Vorlesehilfe — Pflicht, eine Grafik ohne Namen ist
   *  für den Screenreader ein leeres Rechteck. */
  ariaTitel: string;
  nachkomma?: number;
  /** Eigenes Zahlenformat (Vorgabe: `deZahl` mit `nachkomma`). Für Reihen,
   *  deren Werte nicht als Mio. kommen — gebaut aus `format.ts`, nie aus
   *  `toLocaleString`. */
  format?: (wert: number) => string;
  /** Dünn und gestrichelt IN derselben Zeichenfläche (GB-01),
   *  z. B. die Zinslast zur Schuldenreihe. */
  zweitreihe?: { label: string; reihe: JahrPunkt[]; format?: (wert: number) => string };
  /** Beschriftete Stellen („2010: 108,9 Mio. an Eigenbetriebe umgebucht").
   *  Im Bild ein ⓘ-Marker, der Text steht IMMER unter der Grafik — nie nur
   *  beim Hovern (Kein-Tooltip-Regel). */
  annotationen?: ZeitreiheAnnotation[];
  /** Ansichts-Umschalter („absolut" / „pro Kopf") — gerendert von der
   *  Komponente (mobil full-width, H4-13), Daten wechselt die Seite. */
  umschalter?: ZeitreiheUmschalter;
  /** Beleg-Chip-Slot (GB-00): die Seite wählt die Quelle. */
  beleg?: ReactNode;
  /** Bestandsgrößen starten bei null (Vorgabe); reine Abstands-Reihen
   *  dürfen abschneiden. */
  nullbasis?: boolean;
  /** Eigener Bedien-Hinweis unter der Ableseleiste. */
  hinweis?: string;
  className?: string;
}) {
  const { box, breite } = useBreite();
  const stellenListe = normalisiere(reihe);
  const beschreibungId = useId();
  const ablesen = useAblesen(
    stellenListe.length,
    Math.max(stellenListe.length - 1, 0),
  );

  const fmt = format ?? ((v: number) => deZahl(v, nachkomma));
  const fmtZweit = zweitreihe?.format ?? fmt;
  const schmal = breite < 520;
  const fs = schmal
    ? { achse: 13, jahr: 13, wert: 14, legende: 12.5 }
    : { achse: 11, jahr: 11, wert: 13, legende: 12 };

  const werte = stellenListe.filter(definiert);
  if (werte.length < 2) return null;

  const zweitStellen = zweitreihe ? normalisiere(zweitreihe.reihe) : [];
  const zweitNach = new Map(zweitStellen.map((s) => [s.jahr, s]));

  // --- Skalen (d3-scale) ---------------------------------------------------
  const plotH = schmal ? 180 : 210;
  const YTOP = 18;
  const Y0 = YTOP + plotH;
  const yJahr = Y0 + (schmal ? 21 : 18);
  const H = yJahr + 8;

  const alleWerte = [
    ...werte.map((s) => (s.punkt as JahrWert).wert),
    ...zweitStellen.filter(definiert).map((s) => s.punkt.wert),
  ];
  const ySkala = scaleLinear()
    .domain([nullbasis ? 0 : Math.min(...alleWerte), Math.max(...alleWerte)])
    .nice(schmal ? 3 : 4)
    .range([Y0, YTOP + 12]);
  const gitter = ySkala.ticks(schmal ? 3 : 4);
  const achsenText = gitter.map((v) => deZahl(v, 0));

  // Linker Rand nach der BREITESTEN Achsenzahl (Mono ≈ 0,62 em je Zeichen) —
  // ein fester Wert ragte im schmalen Container aus der Fläche (schulden-kurve).
  const W = breite;
  const X0 = Math.ceil(Math.max(...achsenText.map((t) => t.length)) * fs.achse * 0.62) + 9;
  const X1 = W - 16;

  const von = stellenListe[0].jahr;
  const bis = stellenListe[stellenListe.length - 1].jahr;
  const x = (jahr: number) => X0 + ((jahr - von) / Math.max(bis - von, 1)) * (X1 - X0);
  const y = (v: number) => ySkala(v);

  // --- Pfade (d3-shape, defined = vorhanden) -------------------------------
  // `defined` läuft über die NORMALISIERTE Reihe: Lücken UND unerklärte Jahre
  // sind nicht defined — d3-shape beendet dort das Segment und beginnt hinter
  // der Lücke ein neues. Genau das ist der Lückenbruch des Vertrags.
  const linie = line<Stelle>()
    .defined(definiert)
    .x((s) => x(s.jahr))
    .y((s) => y((s as { punkt: JahrWert }).punkt.wert));
  const flaeche = area<Stelle>()
    .defined(definiert)
    .x((s) => x(s.jahr))
    .y0(Y0)
    .y1((s) => y((s as { punkt: JahrWert }).punkt.wert));
  const zweitLinie = line<Stelle>()
    .defined(definiert)
    .x((s) => x(s.jahr))
    .y((s) => y((s as { punkt: JahrWert }).punkt.wert));

  const luecken = stellenListe.filter((s) => s.art !== "wert");
  const abstand = stellenListe.length > 1 ? x(stellenListe[1].jahr) - x(von) : 60;
  const halbeLuecke = Math.max(9, Math.min(30, abstand * 0.45));

  const erster = werte[0].punkt;
  const letzter = werte[werte.length - 1].punkt;

  // --- Jahresachse: mobil nur Dekaden (H4-A), sonst ausgedünnt -------------
  const jahresmarken: number[] = [];
  if (schmal) {
    for (let j = Math.ceil(von / 10) * 10; j <= bis; j += 10) jahresmarken.push(j);
  } else {
    const schritt = Math.max(Math.ceil((bis - von) / 6), 1);
    for (let j = von; j <= bis; j += schritt) jahresmarken.push(j);
  }
  if (jahresmarken[jahresmarken.length - 1] !== bis) {
    if (jahresmarken.length && bis - jahresmarken[jahresmarken.length - 1] < (bis - von) / 10) {
      jahresmarken.pop();
    }
    jahresmarken.push(bis);
  }

  // --- Ableseleiste: eine Stelle je Jahr, auch für Lücken ------------------
  const annotationNach = new Map((annotationen ?? []).map((a) => [a.jahr, a]));
  const ableseStellen: AbleseStelle[] = stellenListe.map((s) => {
    const zweit = zweitNach.get(s.jahr);
    const werteZeile: AbleseWert[] =
      s.art === "wert"
        ? [{ label: einheit, wert: fmt(s.punkt.wert), farbe: TON }]
        : [{ label: einheit, wert: "—", signal: true }];
    if (zweitreihe) {
      werteZeile.push({
        label: zweitreihe.label,
        wert: zweit?.art === "wert" ? fmtZweit((zweit.punkt as JahrWert).wert) : "—",
        farbe: TON_ZWEIT,
      });
    }
    const grund = s.art === "luecke" ? s.punkt.fehlt : s.art === "unerklaert" ? "keine Angabe" : null;
    const anno = annotationNach.get(s.jahr);
    return {
      titel: String(s.jahr) + (anno ? " ⓘ" : ""),
      werte: werteZeile,
      vorlesen: [
        `${s.jahr}:`,
        s.art === "wert" ? `${fmt(s.punkt.wert)} ${einheit}.` : `keine Zahl — ${grund}.`,
        zweitreihe && zweit?.art === "wert"
          ? `${zweitreihe.label} ${fmtZweit((zweit.punkt as JahrWert).wert)}.`
          : "",
        anno ? `Anmerkung: ${anno.text}` : "",
      ].filter(Boolean).join(" "),
    };
  });

  const beschreibung = [
    `${ariaTitel}, ${von} bis ${bis}.`,
    werte.map((s) => `${s.jahr}: ${fmt((s.punkt as JahrWert).wert)}`).join(", "),
    `${einheit}.`,
    luecken.length
      ? `Ohne Zahl: ${luecken.map((s) =>
          `${s.jahr} (${s.art === "luecke" ? s.punkt.fehlt : "keine Angabe"})`).join(", ")}.`
      : "",
  ].filter(Boolean).join(" ");

  return (
    <div ref={box} className={cn("min-w-0", className)}>
      {umschalter && (
        <div
          role="group" aria-label="Ansicht wählen"
          className="mb-2.5 grid gap-1 rounded-full border border-border bg-card p-1 ab-tablet:inline-grid"
          style={{ gridTemplateColumns: `repeat(${umschalter.optionen.length}, minmax(0, 1fr))` }}
        >
          {umschalter.optionen.map((o, i) => (
            <button
              key={o} type="button" aria-pressed={i === umschalter.aktiv}
              onClick={() => umschalter.onWahl(i)}
              className={cn(
                "min-h-[36px] rounded-full px-3.5 text-[12.5px] transition-colors",
                i === umschalter.aktiv
                  ? "bg-primary font-semibold text-primary-foreground"
                  : "text-foreground/75 hover:bg-accent",
              )}
            >
              {o}
            </button>
          ))}
        </div>
      )}

      <AbleseBeschreibung id={beschreibungId}>{beschreibung}</AbleseBeschreibung>
      {/* `role="group"`, nicht `img`: Die Jahres-Ziele der Ablese-Fläche
          wären in einem `img` für die Vorlesehilfe unsichtbar. */}
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="group"
        aria-label={ariaTitel} aria-describedby={beschreibungId}>
        {gitter.map((v, i) => (
          <g key={v}>
            <line x1={X0} y1={y(v)} x2={X1} y2={y(v)} className="stroke-border/60" />
            <text x={X0 - 6} y={y(v) + 4} textAnchor="end" fontSize={fs.achse}
              className="fill-muted-foreground font-mono">{achsenText[i]}</text>
          </g>
        ))}
        <line x1={X0} y1={Y0} x2={X1} y2={Y0} className="stroke-border" />

        {/* Lücken-Kästen: Schraffur + gestrichelte Signal-Kante — Markierung,
            keine Fläche in Orange (GB-00). */}
        {luecken.map((s) => {
          const xl = x(s.jahr) - halbeLuecke, xr = x(s.jahr) + halbeLuecke;
          return (
            <g key={s.jahr}>
              <foreignObject x={xl} y={YTOP} width={xr - xl} height={Y0 - YTOP}>
                <div className="hh-schraffur h-full w-full opacity-60" />
              </foreignObject>
              <rect x={xl} y={YTOP} width={xr - xl} height={Y0 - YTOP} fill="none"
                strokeDasharray="4 3" className="stroke-signal" />
              {s.art === "unerklaert" && (
                <text x={x(s.jahr)} y={(Y0 + YTOP) / 2} textAnchor="middle" fontSize={11}
                  className="fill-signal font-mono">?</text>
              )}
            </g>
          );
        })}

        {/* Fläche + Linie: `defined()` hat die Segmente an den Lücken schon
            getrennt — hier wird nur noch gezeichnet. */}
        {nullbasis && <path d={flaeche(stellenListe) ?? undefined} style={{ fill: TON }} opacity={0.08} />}
        {zweitreihe && (
          <path d={zweitLinie(zweitStellen) ?? undefined} fill="none" strokeWidth={1.5}
            strokeDasharray="5 4" strokeLinecap="round" style={{ stroke: TON_ZWEIT }} />
        )}
        <path d={linie(stellenListe) ?? undefined} fill="none" strokeWidth={2.2}
          strokeLinejoin="round" strokeLinecap="round" style={{ stroke: TON }} />

        {/* Annotationen: ⓘ im Bild, der Text steht unter der Grafik. */}
        {(annotationen ?? []).map((a) => {
          const stelle = stellenListe.find((s) => s.jahr === a.jahr);
          if (!stelle) return null;
          const py = stelle.art === "wert" ? y(stelle.punkt.wert) : (Y0 + YTOP) / 2;
          return (
            <g key={a.jahr}>
              <line x1={x(a.jahr)} y1={YTOP + 8} x2={x(a.jahr)} y2={py - 8}
                strokeWidth={1} strokeDasharray="2 3" className="stroke-foreground/40" />
              <circle cx={x(a.jahr)} cy={YTOP + 8} r={7.5} className="fill-card stroke-foreground/45"
                strokeWidth={1.2} />
              <text x={x(a.jahr)} y={YTOP + 11.5} textAnchor="middle" fontSize={10} fontStyle="italic"
                className="fill-foreground/75 font-mono">i</text>
            </g>
          );
        })}

        {/* Direktbeschriftung NUR Endwerte (GB-01). */}
        <circle cx={x(erster.jahr)} cy={y(erster.wert)} r={4} className="fill-card"
          strokeWidth={2} style={{ stroke: TON }} />
        <circle cx={x(letzter.jahr)} cy={y(letzter.wert)} r={5} style={{ fill: TON }} />
        <text x={x(letzter.jahr) - 7} y={y(letzter.wert) - 10} textAnchor="end"
          fontSize={fs.wert + 1} fontWeight={700} className="stroke-card" {...halo}
          style={{ fill: TON }}>{fmt(letzter.wert)}</text>

        {jahresmarken.map((j) => (
          <text key={j} x={x(j)} y={yJahr} textAnchor="middle" fontSize={fs.jahr}
            className={j === bis ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
            {j}
          </text>
        ))}

        {/* Zuletzt: die Ablese-Fläche über allem, sonst fängt die Kurve den
            Zeiger ab. */}
        <AbleseFlaeche
          stellen={ableseStellen} steuerung={ablesen} gruppe="Jahre der Reihe"
          x={(i) => x(stellenListe[i].jahr)} xVon={X0} xBis={X1}
          yVon={YTOP} hoehe={Y0 - YTOP} fangHoehe={yJahr + 4 - YTOP}
          marken={(i) => {
            const s = stellenListe[i];
            return s.art === "wert" ? [{ y: y(s.punkt.wert), farbe: TON }] : [];
          }}
        />
      </svg>

      <Ableseleiste className="mt-2" stelle={ableseStellen[ablesen.aktiv]} steuerung={ablesen}
        hinweis={hinweis ?? `${einheit} · Jahr überfahren, antippen oder mit den Pfeiltasten wechseln.`} />

      {/* Annotations-Texte: immer sichtbar, nie nur beim Hovern. */}
      {(annotationen ?? []).length > 0 && (
        <div className="mt-2 flex flex-col gap-1">
          {annotationen!.map((a) => (
            <p key={a.jahr} className="text-[11.5px] leading-relaxed text-muted-foreground">
              <span className="font-mono text-[10px] font-semibold text-foreground/75">ⓘ {a.jahr}</span>
              {" — "}{a.text}
            </p>
          ))}
        </div>
      )}

      {/* Lücken beschriftet die GRAFIK (GB-00) — nie einklappbar. */}
      {luecken.length > 0 && (
        <div className="mt-2 flex flex-col gap-1.5">
          {luecken.map((s) => (
            <LueckenFeld key={s.jahr} label={String(s.jahr)}
              grund={s.art === "luecke" ? s.punkt.fehlt : "in der Reihe ohne Wert und ohne Grund"}
              datum={s.art === "luecke" ? s.punkt.datum : undefined} />
          ))}
        </div>
      )}

      {/* Quellenzeile mit Beleg-Chip-Slot + Legende der Zweitreihe. */}
      {(beleg || zweitreihe) && (
        <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] leading-relaxed text-muted-foreground">
          {zweitreihe && (
            <span className="inline-flex items-center gap-1.5">
              <svg width="18" height="4" aria-hidden="true" className="flex-none">
                <line x1="0" y1="2" x2="18" y2="2" strokeWidth={1.5} strokeDasharray="5 4"
                  style={{ stroke: TON_ZWEIT }} />
              </svg>
              {zweitreihe.label}
            </span>
          )}
          {beleg && <span className="inline-flex items-center">Quelle{beleg}</span>}
        </p>
      )}
    </div>
  );
}

/** <ZeitreiheMini> — die Sparkline-Variante für Karten (GB-01 „mini",
 *  H3-02/H4-11: Beteiligungs-Karten, „Sparkline behält Endpunkt-Beschriftung").
 *
 *  Bewusst OHNE Ableseleiste und ohne Achsen: Auf einer Karte ist die große
 *  Kennzahl daneben die Auskunft, die Sparkline zeigt nur die Form des
 *  Verlaufs. Deshalb hier `role="img"` mit vollständigem `aria-label` (die
 *  Seite liefert den Satz) — es gibt keine Einzelziele, die verloren gingen.
 *  Lücken brechen die Linie über dasselbe `defined()`; ein Sparkline-Knick
 *  über eine Lücke hinweg wäre dieselbe Interpolation wie im großen Bild. */
export function ZeitreiheMini({ reihe, ariaLabel, format, className }: {
  reihe: JahrPunkt[];
  /** Ganzer Satz für die Vorlesehilfe — die Mini-Form ist EIN Bild. */
  ariaLabel: string;
  /** Formatiert die Endpunkt-Beschriftung (Vorgabe: `deZahl(v, 1)`). */
  format?: (wert: number) => string;
  className?: string;
}) {
  const { box, breite } = useBreite(220, 120);
  const stellen = normalisiere(reihe);
  const werte = stellen.filter(definiert);
  if (werte.length < 2) return null;

  const fmt = format ?? ((v: number) => deZahl(v, 1));
  const letzterWert = werte[werte.length - 1].punkt;
  const endText = fmt(letzterWert.wert);

  const H = 46, YTOP = 5, Y0 = 33, yJahr = 44;
  const W = breite;
  // Rechts Platz für die Endpunkt-Beschriftung (≈0,58 em je Zeichen + Punkt).
  const reserve = Math.ceil(endText.length * 10.5 * 0.58) + 12;
  const X0 = 2;
  const X1 = Math.max(W - reserve, X0 + 40);

  const von = stellen[0].jahr, bis = stellen[stellen.length - 1].jahr;
  const zahlen = werte.map((s) => s.punkt.wert);
  const lo = Math.min(...zahlen), hi = Math.max(...zahlen);
  const x = (jahr: number) => X0 + ((jahr - von) / Math.max(bis - von, 1)) * (X1 - X0);
  const y = (v: number) => (hi === lo ? (Y0 + YTOP) / 2 : Y0 - ((v - lo) / (hi - lo)) * (Y0 - YTOP));

  const linie = line<Stelle>()
    .defined(definiert)
    .x((s) => x(s.jahr))
    .y((s) => y((s as { punkt: JahrWert }).punkt.wert));

  const luecken = stellen.filter((s) => s.art !== "wert");

  return (
    <div ref={box} className={cn("min-w-0", className)}>
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label={ariaLabel}>
        {/* Nulllinie, wenn die Reihe das Vorzeichen wechselt — sonst läse
            sich ein Verlust-zu-Gewinn-Verlauf wie eine beliebige Steigung. */}
        {lo < 0 && hi > 0 && (
          <line x1={X0} y1={y(0)} x2={X1} y2={y(0)} strokeWidth={1}
            className="stroke-border" strokeDasharray="2 3" />
        )}
        {/* Lücken als schmale Schraffur-Streifen — auch die Sparkline hat
            keine Erlaubnis, eine Lücke zu glätten. */}
        {luecken.map((s) => (
          <g key={s.jahr}>
            <foreignObject x={x(s.jahr) - 3} y={YTOP} width={6} height={Y0 - YTOP}>
              <div className="hh-schraffur h-full w-full opacity-70" />
            </foreignObject>
            <rect x={x(s.jahr) - 3} y={YTOP} width={6} height={Y0 - YTOP} fill="none"
              strokeDasharray="2 2" strokeWidth={0.8} className="stroke-signal" />
          </g>
        ))}
        <path d={linie(stellen) ?? undefined} fill="none" strokeWidth={1.8}
          strokeLinejoin="round" strokeLinecap="round" style={{ stroke: TON }} />
        <circle cx={x(letzterWert.jahr)} cy={y(letzterWert.wert)} r={3.5} style={{ fill: TON }} />
        {/* Endpunkt-Beschriftung — bleibt auf jedem Gerät (H4-11). */}
        <text x={X1 + 6} y={y(letzterWert.wert) + 3.5} fontSize={10.5} fontWeight={700}
          className="tabular-nums" style={{ fill: TON }}>{endText}</text>
        <text x={X0} y={yJahr} fontSize={9} className="fill-muted-foreground font-mono">{von}</text>
        <text x={X1} y={yJahr} textAnchor="end" fontSize={9}
          className="fill-muted-foreground font-mono">{bis}</text>
      </svg>
    </div>
  );
}
