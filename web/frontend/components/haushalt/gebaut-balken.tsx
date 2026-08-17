"use client";

// Was in einem Jahr wirklich abgeflossen ist — ein gestapelter Balken je Jahr.
//
// BALKEN UND KEINE KURVE, und das ist die tragende Entscheidung. Eine Linie
// behauptet, dass zwischen zwei Jahren etwas liegt, und sie behauptet es
// besonders laut über eine Lücke hinweg. Diese Reihe hat eine: 2019 geht die
// Zeilensumme in der Quelle selbst nicht auf, der Jahrgang steht deshalb nicht
// im Bestand. Balken stehen einzeln — ein fehlendes Jahr ist ein leerer Platz,
// und der ist als leerer Platz zu sehen.
//
// DIE LÜCKE WIRD GEZEICHNET, NICHT ÜBERSPRUNGEN. Ein Jahr, das einfach fehlt,
// liest sich als „damals wurde nichts gebaut" oder gar nicht — beides falsch.
// Es bekommt deshalb einen schraffierten Platzhalter in voller Spaltenbreite,
// die Konvention des Bereichs für „keine Angabe" (anteilsbalken.tsx, Regel 4).
//
// EINE REIHE JE RECHNUNGSWESEN. Diese Komponente zeichnet IMMER nur eine —
// die Seite ruft sie zweimal auf. Beide in ein Bild zu legen wäre der Fehler,
// den das Quelldokument mit seiner Fußnote gerade ausschließt: Kameral (bis
// 2009) und doppisch (ab 2010) zählen verschiedene Arten und heißen sogar
// verschieden („Ausgaben" gegen „Auszahlungen"). Eine gemeinsame X-Achse
// machte daraus eine Zeitreihe, die es nicht gibt.
//
// KEINE BEWERTUNGSFARBEN (components/haushalt/hantel.tsx). Die Segmente sind
// Stufen der neutralen Ausgabenrampe `--hh-aus-*`, in der Spaltenfolge der
// Quelle. Viel Bautätigkeit ist weder gut noch schlecht — ein hoher Balken
// kann eine sanierte Schule sein oder eine Kapitaleinlage.

import { useEffect, useId, useRef, useState } from "react";
import {
  AbleseBeschreibung, AbleseFlaeche, AbleseStelle, Ableseleiste, useAblesen,
} from "@/components/haushalt/ablesen";
import { Art, GebautJahr, deMioEuro } from "@/lib/haushalt-gebaut";

const H = 208, Y0 = 168, YTOP = 20;

/** Die Rampe, aus der die Auszahlungsarten ihre Töne bekommen — dunkel nach
 *  hell, in der Spaltenfolge der Quelle. Sechs reichen: Mehr Arten führt
 *  keine der beiden Tabellen, und liefe eine siebte auf, fiele sie auf den
 *  letzten Ton zurück statt in eine Farbe, die niemand geprüft hat. */
const TOENE = ["var(--hh-aus-0)", "var(--hh-aus-2)", "var(--hh-aus-4)",
  "var(--hh-aus-6)", "var(--hh-aus-1)", "var(--hh-aus-3)"];

export function tonFuer(i: number): string {
  return TOENE[Math.min(i, TOENE.length - 1)];
}

/** Die Schraffur der Legende. Bewusst mit einem festen Ton statt
 *  `currentColor`: Bei 10 px Kantenlänge und der Textfarbe des Umfelds ergab
 *  das einen einzelnen dünnen Strich, der wie ein Icon aussah und nicht wie
 *  eine Musterfläche (gemessen 17.08.2026). */
function schraffur(): string {
  return "repeating-linear-gradient(45deg, var(--hh-aus-4) 0 2px, "
    + "transparent 2px 4px)";
}

export function GebautBalken({ jahre, fehlend, arten, titel }: {
  jahre: GebautJahr[];
  /** Jahre, die in dieser Reihe fehlen — sie bekommen einen Platzhalter. */
  fehlend: number[];
  /** Die Auszahlungsarten dieser Reihe, in Spaltenfolge — die Legende. */
  arten: { feld: string; titel: string }[];
  titel: string;
}) {
  const [tabelle, setTabelle] = useState(false);
  // viewBox-Breite = Containerbreite, sonst staucht das SVG die Schrift mit.
  // `getBoundingClientRect` statt `clientWidth`: letzteres rundet auf ganze
  // Pixel (dieselbe Messfalle wie in `schulden-kurve.tsx`).
  const box = useRef<HTMLDivElement>(null);
  const [breite, setBreite] = useState(640);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const pruefe = () => {
      const w = Math.max(el.getBoundingClientRect().width, 280);
      setBreite((alt) => (Math.abs(w - alt) > 0.5 ? w : alt));
    };
    pruefe();
    const ro = new ResizeObserver(pruefe);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Alle Spalten der Reihe: belegte Jahrgänge UND die Lücken dazwischen.
  const belegt = new Map(jahre.map((z) => [z.jahr, z]));
  const von = jahre.length ? jahre[0].jahr : 0;
  const bis = jahre.length ? jahre[jahre.length - 1].jahr : 0;
  const spalten: { jahr: number; zeile: GebautJahr | null }[] = [];
  for (let j = von; j <= bis; j++) {
    spalten.push({ jahr: j, zeile: belegt.get(j) ?? null });
  }

  const ablesen = useAblesen(spalten.length, Math.max(spalten.length - 1, 0));
  const beschreibungId = useId();
  const schmal = breite < 520;
  const fs = schmal ? { achse: 12, jahr: 11 } : { achse: 11, jahr: 11 };
  if (!jahre.length) return null;

  const werte = jahre.map((z) => z.insgesamt / 1e6);
  // Nullbasis, wie überall im Bereich: Ein abgeschnittener Sockel macht aus
  // 5 % Bewegung ein Gebirge.
  const stufe = 20;
  const hi = Math.max(Math.ceil(Math.max(...werte) / stufe) * stufe, stufe);
  const gitter = [0.25, 0.5, 0.75, 1].map((f) => Math.round(hi * f));
  const achsenText = gitter.map((v) => v.toLocaleString("de-DE"));

  const W = breite;
  // Der linke Rand richtet sich nach der breitesten Achsenzahl statt fest zu
  // sein — sonst ragt er im schmalen Container aus der Zeichenfläche.
  const X0 = Math.ceil(Math.max(...achsenText.map((t) => t.length)) * fs.achse * 0.62) + 9;
  const X1 = W - 8;
  const spalte = (X1 - X0) / Math.max(spalten.length, 1);
  const balken = Math.max(Math.min(spalte - 3, 26), 3);
  const mitte = (i: number) => X0 + spalte * (i + 0.5);
  const y = (v: number) => Y0 - (v / hi) * (Y0 - YTOP);

  // Jahres-Beschriftung ausdünnen, damit nichts überlappt. Das letzte Jahr
  // steht immer — es trägt die Aussage „bis hierhin reicht die Reihe".
  const proBeschriftung = schmal ? 44 : 34;
  const schritt = Math.max(Math.ceil(proBeschriftung / spalte), 1);
  const jahresmarken: number[] = [];
  for (let i = 0; i < spalten.length; i += schritt) jahresmarken.push(spalten[i].jahr);
  if (jahresmarken[jahresmarken.length - 1] !== bis) {
    if (bis - jahresmarken[jahresmarken.length - 1] < schritt * 0.6) jahresmarken.pop();
    jahresmarken.push(bis);
  }

  const stellen: AbleseStelle[] = spalten.map(({ jahr, zeile }) => {
    if (!zeile) {
      return {
        titel: String(jahr),
        werte: [{ label: "nicht belegt", wert: "—" }],
        vorlesen: `${jahr}: keine Angabe. Die Auszahlungsarten ergeben in der `
          + `Quelltabelle nicht die Summe daneben; der Jahrgang steht deshalb `
          + `nicht im Bestand.`,
      };
    }
    return {
      titel: String(jahr),
      werte: [
        { label: "insgesamt", wert: `${deMioEuro(zeile.insgesamt)} Mio. €` },
        ...zeile.arten.map((a, i) => ({
          label: a.titel, wert: `${deMioEuro(a.betrag)} Mio. €`, farbe: tonFuer(i),
        })),
      ],
      vorlesen: `${jahr}: ${deMioEuro(zeile.insgesamt)} Millionen Euro, davon `
        + zeile.arten
          .map((a) => `${a.titel} ${deMioEuro(a.betrag)} Millionen`)
          .join(", ") + ".",
    };
  });

  return (
    <div ref={box}>
      <div className="mb-2 flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {titel}
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {von}–{bis} · {jahre.length} Werte · Mio. €
        </span>
      </div>

      <AbleseBeschreibung id={beschreibungId}>
        {`Auszahlungen ${von} bis ${bis} in Millionen Euro: `
          + spalten
            .map(({ jahr, zeile }) =>
              `${jahr} ${zeile ? deMioEuro(zeile.insgesamt) : "keine Angabe"}`)
            .join(", ")}
      </AbleseBeschreibung>
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="group"
        aria-describedby={beschreibungId}
        aria-label={`${titel}, ${von} bis ${bis}`}>
        <defs>
          {/* Der Platzhalter für ein fehlendes Jahr — dieselbe Schraffur wie
              in `anteilsbalken.tsx`, nur als SVG-Muster. */}
          <pattern id={`${beschreibungId}-luecke`} width="6" height="6"
            patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="2" height="6" className="fill-muted-foreground" opacity={0.3} />
          </pattern>
        </defs>

        {gitter.map((v, i) => (
          <g key={v}>
            <line x1={X0} y1={y(v)} x2={X1} y2={y(v)} className="stroke-border/60" />
            <text x={X0 - 6} y={y(v) + 4} textAnchor="end" fontSize={fs.achse}
              className="fill-muted-foreground font-mono">
              {achsenText[i]}
            </text>
          </g>
        ))}
        <line x1={X0} y1={Y0} x2={X1} y2={Y0} className="stroke-border" />

        {spalten.map(({ jahr, zeile }, i) => {
          const x = mitte(i) - balken / 2;
          if (!zeile) {
            // Volle Höhe bis zur obersten Gitterlinie: Der Platzhalter sagt
            // „über diese ganze Spanne fehlt die Angabe", nicht „hier war es
            // so hoch". Damit er trotzdem nicht als höchster Balken der Reihe
            // gelesen wird, trägt er einen GESTRICHELTEN RAHMEN und eine sehr
            // dünne Schraffur — gemessen am 17.08.2026 sah eine kräftigere
            // Füllung neben Nachbarn von 48 und 70 Mio. € wie eine Spitze aus.
            // Ein kurzer Stummel am Fuß wäre die andere Möglichkeit gewesen
            // und die schlechtere: Der liest sich als „fast null".
            return (
              <g key={jahr}>
                <rect x={x} y={YTOP} width={balken} height={Y0 - YTOP}
                  fill={`url(#${beschreibungId}-luecke)`} />
                <rect x={x} y={YTOP} width={balken} height={Y0 - YTOP}
                  fill="none" strokeDasharray="3 3" strokeWidth={1}
                  className="stroke-border" />
              </g>
            );
          }
          // Von unten stapeln, in der Spaltenfolge der Quelle.
          let unten = Y0;
          return (
            <g key={jahr}>
              {zeile.arten.map((a: Art, k) => {
                const hoehe = (a.betrag / 1e6 / hi) * (Y0 - YTOP);
                unten -= hoehe;
                return (
                  <rect key={a.feld} x={x} y={unten} width={balken}
                    height={Math.max(hoehe, 0)} style={{ fill: tonFuer(k) }} />
                );
              })}
            </g>
          );
        })}

        {jahresmarken.map((j) => {
          const i = spalten.findIndex((s) => s.jahr === j);
          return (
            <text key={j} x={mitte(i)} y={188} textAnchor="middle" fontSize={fs.jahr}
              className={j === bis
                ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
              {j}
            </text>
          );
        })}

        {/* Zuletzt: die Ablese-Fläche liegt über allem, sonst fangen die
            Balken den Zeiger ab. */}
        <AbleseFlaeche
          stellen={stellen} steuerung={ablesen} gruppe="Jahre der Reihe"
          x={(i) => mitte(i)} xVon={X0} xBis={X1}
          yVon={YTOP} hoehe={Y0 - YTOP} fangHoehe={192 - YTOP}
          marken={(i) => {
            const z = spalten[i].zeile;
            return z ? [{ y: y(z.insgesamt / 1e6), farbe: "var(--hh-aus-0)" }] : [];
          }}
        />
      </svg>

      <Ableseleiste className="mt-2" stelle={stellen[ablesen.aktiv]} steuerung={ablesen}
        hinweis="Jahr überfahren, antippen oder mit den Pfeiltasten wechseln." />

      {/* Die Legende steht unter dem Bild und nicht daneben: Sechs
          Auszahlungsarten mit ihren vollen Namen brauchen die Breite. */}
      <ul className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
        {arten.map((a, i) => (
          <li key={a.feld} className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            <span className="h-2.5 w-2.5 flex-none rounded-sm"
              style={{ background: tonFuer(i) }} />
            {a.titel}
          </li>
        ))}
        {fehlend.length > 0 && (
          <li className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            <span className="h-2.5 w-2.5 flex-none rounded-sm border border-dashed border-border"
              style={{ background: schraffur() }} />
            keine Angabe ({fehlend.join(", ")})
          </li>
        )}
      </ul>

      <button type="button" onClick={() => setTabelle((t) => !t)}
        aria-expanded={tabelle} className="mt-2 text-[12px] font-semibold text-primary">
        {tabelle ? "Tabelle ausblenden" : `Alle ${jahre.length} Werte als Tabelle`}
      </button>
      {tabelle && (
        <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(116px,1fr))] gap-x-3 gap-y-1 text-[11.5px] tabular-nums">
          {spalten.map(({ jahr, zeile }) => (
            <span key={jahr} className="flex justify-between border-t border-border/60 py-1">
              <span className="font-mono text-muted-foreground">{jahr}</span>
              <span>{zeile ? `${deMioEuro(zeile.insgesamt)} Mio.` : "—"}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
