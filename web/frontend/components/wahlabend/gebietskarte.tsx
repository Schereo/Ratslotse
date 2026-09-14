"use client";

// „Wo is eigentlich nochmal Wahlbereich 5?" — Tims Frage am Abend nach der
// Wahl. Die Seite kannte die sechs Wahlbereiche bis dahin nur als römische
// Ziffern und ihre Namen („Süd", „Nordost"); wo sie liegen, stand nirgends.
//
// Die Grenzen sind die amtlichen (openGEOdata der Stadt, dl-zero-de/2.0,
// geholt von `scripts/wahl_geodaten.py`). Vorher näherte die Stadtkarte den
// Wahlbereich über die Ortsbereiche an — „ungefähr, und die Quellenzeile
// sagt es".
//
// **Kein Kartengrund, wie bei der Ortsbereichs-Karte** (`stadtteil-karte.tsx`):
// Für „wo liegt das?" braucht es keine Straßen, keine Kacheln und keinen
// CARTO-Schlüssel — nur die Umrisse. Als SVG folgt die Karte dem Theme und
// kostet keine Netz-Runde zu einem fremden Server. Die Rechnung dahinter
// steht in `lib/gebiete.ts`.
//
// **Parteifarben werden hier NICHT zu Flächen** (Designsprache): Getönt wird
// mit `--primary` nach der Stärke der gewählten Liste, der Punkt in
// Listenfarbe steht daneben in der Rangfolge.

import { useEffect, useMemo, useRef, useState } from "react";
import { KICKER } from "@/components/wahlabend/bausteine";
import { projiziere, toenungSpanne, type GeoFlaeche } from "@/lib/gebiete";
import { cn } from "@/lib/utils";

const HOEHE = 320;

/** Was eine Fläche mindestens mitbringen muss: ihre Nummer. */
export type Gebiet = { nr: number };

export function Gebietskarte<P extends Gebiet>({
  flaechen,
  werte,
  gewaehlt,
  onWaehlen,
  beschriftung,
  titel,
  hinweis,
  hoehe = HOEHE,
  className,
}: {
  flaechen: readonly GeoFlaeche<P>[];
  /** Nummer → Zahl, nach der getönt wird (Anteil der gewählten Liste).
   *  Leer = alle Flächen neutral. */
  werte?: Map<number, number>;
  gewaehlt?: number | null;
  onWaehlen?: (nr: number) => void;
  /** Was in der Fläche steht — leer heißt: nichts. Bei 91 Wahlbezirken
   *  wäre jede Beschriftung ein Knäuel. */
  beschriftung?: (e: P) => string;
  /** Tooltip je Fläche. */
  titel?: (e: P) => string;
  /** Ein Satz unter der Karte — was die Tönung bedeutet. */
  hinweis?: string;
  hoehe?: number;
  className?: string;
}) {
  const [breite, setBreite] = useState(520);
  const [schwebt, setSchwebt] = useState<number | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // Die Karte skaliert mit ihrer Spalte.
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const beobachter = new ResizeObserver(([eintrag]) => {
      const w = eintrag.contentRect.width;
      if (w > 0) setBreite(w);
    });
    beobachter.observe(el);
    return () => beobachter.disconnect();
  }, []);

  const { pfade, hoehe: gemessen } = useMemo(() => projiziere(flaechen, breite, hoehe), [flaechen, breite, hoehe]);
  // Gemessen wird zwischen dem schwächsten und dem stärksten Wahlbereich
  // dieser Liste, nicht gegen null — s. `toenungSpanne`.
  const [min, max] = useMemo(() => {
    const v = werte ? [...werte.values()] : [];
    return v.length ? [Math.min(...v), Math.max(...v)] : [0, 0];
  }, [werte]);

  return (
    <div ref={boxRef} className={cn("relative", className)}>
      {!pfade.length ? (
        <div className="h-[200px] w-full animate-pulse rounded-2xl border border-dashed border-border bg-muted/30" />
      ) : (
        <svg
          viewBox={`0 0 ${breite} ${gemessen}`}
          width="100%"
          height={gemessen}
          role="img"
          aria-label="Karte von Oldenburg"
          className="overflow-visible"
        >
          {pfade.map((p) => {
            const nr = p.eigenschaften.nr;
            const aktiv = gewaehlt === nr;
            const hell = schwebt === nr;
            const ton = !aktiv && !hell ? toenungSpanne(werte?.get(nr), min, max) : null;
            return (
              // Nicht fokussierbar, wie bei der Ortsbereichs-Karte: Chrome
              // legt den Fokus-Ring einer SVG-Fläche um deren Bounding-Box,
              // nicht um den Umriss. Der Weg für Tastatur und Screenreader
              // ist die Rangfolge daneben — sie nennt dieselben sechs.
              <path
                key={nr}
                d={p.d}
                className={cn(
                  "transition-[fill,stroke] duration-150",
                  onWaehlen ? "cursor-pointer" : "cursor-default",
                  aktiv
                    ? "fill-primary stroke-primary"
                    : hell
                      ? "fill-primary/25 stroke-primary/50"
                      : "fill-muted stroke-border",
                )}
                style={ton ? { fill: ton } : undefined}
                strokeWidth={aktiv ? 2 : 1}
                onMouseEnter={() => setSchwebt(nr)}
                onMouseLeave={() => setSchwebt((n) => (n === nr ? null : n))}
                onClick={() => onWaehlen?.(nr)}
              >
                <title>{titel ? titel(p.eigenschaften) : String(nr)}</title>
              </path>
            );
          })}
          {/* Sechs römische Ziffern passen alle auf die Karte; 91
              Bezirksnummern nicht — dort gibt `beschriftung` nichts zurück
              und der Name steht im Tooltip. */}
          {beschriftung ? pfade.map((p) => {
            const text = beschriftung(p.eigenschaften);
            if (!text) return null;
            const aktiv = gewaehlt === p.eigenschaften.nr;
            return (
              <g key={`t-${p.eigenschaften.nr}`} className="pointer-events-none">
                <text
                  x={p.cx} y={p.cy} textAnchor="middle" dominantBaseline="middle"
                  className="font-display text-[13px] font-bold"
                  stroke={aktiv ? "hsl(var(--primary))" : "hsl(var(--background))"}
                  strokeWidth="3" strokeLinejoin="round"
                >
                  {text}
                </text>
                <text
                  x={p.cx} y={p.cy} textAnchor="middle" dominantBaseline="middle"
                  className={cn("font-display text-[13px] font-bold",
                    aktiv ? "fill-primary-foreground" : "fill-foreground")}
                >
                  {text}
                </text>
              </g>
            );
          }) : null}
        </svg>
      )}
      {hinweis ? <p className={cn(KICKER, "mt-1.5")}>{hinweis}</p> : null}
    </div>
  );
}
