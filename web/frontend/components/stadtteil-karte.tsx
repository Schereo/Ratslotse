"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { loadOrtsbereiche, type OrtsbereichFeature } from "@/lib/districts";
import { projiziere, toenung } from "@/lib/gebiete";

/** Oldenburg als anklickbare Fläche — 31 Ortsbereiche, ein Inline-SVG.
 *
 *  **Warum kein Leaflet.** Die Karten der App zeigen Beschlüsse auf echtem
 *  Kartengrund; hier geht es um genau eine Frage: „wo wohnst du?". Dafür
 *  braucht es keine Straßen, keine Kacheln und keinen CARTO-Key — nur die
 *  Umrisse, die als 19-KB-GeoJSON ohnehin im Repo liegen. Als SVG folgt die
 *  Karte außerdem dem Theme (Tokens statt Bildpixel) und kostet keine
 *  Netz-Runde zu einem Kachel-Server.
 *
 *  **Warum eine Karte und nicht nur eine Liste.** Ein Stadtteilname ist
 *  amtlich; wo er liegt, weiß man. „Bümmerstede" oder „Drielaker-Moor" aus
 *  einer Liste von 31 zu finden setzt voraus, dass man den Stadtteil beim
 *  Namen nennt — auf der Karte zeigt man hin. Die Liste bleibt trotzdem
 *  daneben stehen: Sie ist der Weg für Tastatur und Screenreader, und sie
 *  gewinnt, wenn man den Namen doch kennt.
 *
 *  Mehrere Auswahlen sind erlaubt und werden alle hervorgehoben.
 *
 *  Die Projektion selbst steht in `lib/gebiete.ts` — sie rechnet auch die
 *  Wahlbereichs-Karte des Wahlabends.
 */

/** Ein Ortsbereich, fertig als SVG-Pfad. */
type Flaeche = { name: string; d: string; cx: number; cy: number };

const HOEHE = 460;

function projizieren(features: OrtsbereichFeature[], breite: number): { flaechen: Flaeche[]; hoehe: number } {
  const { pfade, hoehe } = projiziere(features, breite, HOEHE);
  return { flaechen: pfade.map((p) => ({ name: p.eigenschaften.name, d: p.d, cx: p.cx, cy: p.cy })), hoehe };
}

export function StadtteilKarte({ gewaehlt, auswaehlbar, onWaehlen, gewichte, titel, className }: {
  /** Namen der gewählten Ortsbereiche. Mehrere sind erlaubt: Man interessiert
   *  sich für den eigenen Stadtteil und für den, in dem gerade gebaut wird. */
  gewaehlt: Set<string>;
  /** Namen, zu denen es überhaupt Beschlüsse gibt. Alle anderen bleiben
   *  sichtbar, aber stumm: Die Stadt soll vollständig aussehen, und ein
   *  fehlendes Stück wäre erklärungsbedürftiger als ein blasses. */
  auswaehlbar: Set<string>;
  onWaehlen: (name: string) => void;
  /** Optional: eine Zahl je Ortsbereich, die die Fläche tönt — die Karte
   *  wird zur Wärmekarte („wo ist am meisten los?"). Ohne Gewichte bleibt
   *  sie die Zeige-Karte des Einrichtungs-Assistenten: eine Farbe für alle
   *  wählbaren. Die Tönung folgt der Wurzel, nicht der Zahl selbst: Bei
   *  0 bis 14 Vorhaben wären sonst zwei Drittel der Stadt kaum von der
   *  leeren Fläche zu unterscheiden. */
  gewichte?: Map<string, number>;
  /** Optional: der Tooltip-Text je Fläche (Vorgabe: nur der Name). */
  titel?: (name: string) => string;
  className?: string;
}) {
  const [features, setFeatures] = useState<OrtsbereichFeature[]>([]);
  const [breite, setBreite] = useState(560);
  const [schwebt, setSchwebt] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => { void loadOrtsbereiche().then(setFeatures); }, []);

  // Die Karte skaliert mit ihrer Spalte — im Zweispalter ist sie schmaler als
  // am ganz breiten Schirm.
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

  const { flaechen, hoehe } = useMemo(() => projizieren(features, breite), [features, breite]);
  const maxGewicht = useMemo(() => Math.max(0, ...(gewichte ? [...gewichte.values()] : [])), [gewichte]);
  // Deckkraft des Primärtons: 0,12 für „ein Vorhaben", 0,62 für den Spitzenwert.
  const ton = (name: string): string | undefined =>
    (gewichte ? toenung(gewichte.get(name), maxGewicht) : null) ?? undefined;

  return (
    <div ref={boxRef} className={cn("relative", className)}>
      {!flaechen.length ? (
        // Kein Platzhalter-Text: Die Karte ist Beiwerk zur Liste daneben, und
        // ein „wird geladen" an dieser Stelle zöge den Blick von der Auswahl ab.
        <div className="h-[220px] w-full animate-pulse rounded-2xl border border-dashed border-border bg-muted/30" />
      ) : (
        <svg viewBox={`0 0 ${breite} ${hoehe}`} width="100%" height={hoehe}
          className="overflow-visible" role="img"
          aria-label={gewaehlt.size
            ? `Karte von Oldenburg, hervorgehoben: ${[...gewaehlt].join(", ")}`
            : "Karte der Oldenburger Stadtteile"}>
          {flaechen.map((f) => {
            const aktiv = gewaehlt.has(f.name);
            const offen = auswaehlbar.has(f.name);
            const hell = schwebt === f.name && offen;
            const fuellung = !aktiv && !hell ? ton(f.name) : undefined;
            return (
              // Bewusst NICHT fokussierbar: Chrome legt den Fokus-Ring einer
              // SVG-Fläche um deren Bounding-Box, nicht um den Umriss — beim
              // Klick stand also ein blaues Rechteck quer über der Stadt. Die
              // Karte ist die Zeige-Geste; Tastatur und Screenreader gehen
              // über die Liste daneben (das svg trägt role="img" und ist
              // damit ohnehin ein Blatt im Baum, die Flächen waren dort nie
              // erreichbar — nur 31 Tab-Stopps lagen davor).
              <path key={f.name} d={f.d}
                className={cn(
                  "transition-[fill,stroke] duration-150",
                  offen ? "cursor-pointer" : "cursor-default",
                  aktiv ? "fill-primary stroke-primary"
                    : hell ? "fill-primary/25 stroke-primary/50"
                      // Wählbar = etwas kräftiger als der Rest. Ohne den
                      // Unterschied wäre die Stadt ein gleichmäßiger Fleck, und
                      // man sähe nicht, wo überhaupt etwas anklickbar ist.
                      : offen ? "fill-muted stroke-border" : "fill-muted/30 stroke-border/50",
                )}
                style={fuellung ? { fill: fuellung } : undefined}
                strokeWidth={aktiv ? 2 : 1}
                onMouseEnter={() => setSchwebt(f.name)}
                onMouseLeave={() => setSchwebt((n) => (n === f.name ? null : n))}
                onClick={() => offen && onWaehlen(f.name)}
              >
                {/* Nativer Tooltip: Der eingeblendete Name folgt erst dem
                    Hover-Zustand von React, `<title>` steht sofort — und ist
                    zugleich der zugängliche Name der Fläche. */}
                <title>{titel ? titel(f.name) : f.name}</title>
              </path>
            );
          })}
          {/* Nur der gewählte trägt seinen Namen. 31 Beschriftungen auf 460 px
              wären ein Knäuel — und die Liste daneben nennt sie ohnehin alle. */}
          {flaechen.filter((f) => gewaehlt.has(f.name) || f.name === schwebt).map((f) => {
            const aktiv = gewaehlt.has(f.name);
            return (
              <g key={`t-${f.name}`} className="pointer-events-none">
                {/* Der Halo trägt die Farbe der FLÄCHE, nicht die der Seite.
                    Mit dem hellen Seitengrund legte er auf dem gefüllten
                    Primärblau einen weißen Balken quer durch die Schrift; und
                    ganz ohne ihn bricht ein langer Name über den Rand des
                    Polygons hinaus ins Nichts (der Schwerpunkt eines schmalen
                    Stadtteils liegt nun mal nicht mittig unter dem Wort). */}
                <text x={f.cx} y={f.cy} textAnchor="middle" dominantBaseline="middle"
                  className="font-display text-[11px] font-bold"
                  stroke={aktiv ? "hsl(var(--primary))" : "hsl(var(--background))"}
                  strokeWidth="3" strokeLinejoin="round">
                  {f.name}
                </text>
                <text x={f.cx} y={f.cy} textAnchor="middle" dominantBaseline="middle"
                  className={cn("font-display text-[11px] font-bold",
                    aktiv ? "fill-primary-foreground" : "fill-foreground")}>
                  {f.name}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}
