"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { loadOrtsbereiche, type OrtsbereichFeature } from "@/lib/districts";

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
 *  Die Projektion ist eine schlichte äquirektanguläre: Bei der Ausdehnung
 *  einer Stadt (≈ 15 km) ist der Fehler gegenüber Mercator nicht sichtbar.
 *  Der Breitengrad-Faktor `cos(φ)` muss aber sein — ohne ihn stünde Oldenburg
 *  um ein Drittel in die Breite gezogen da.
 */

type Punkt = [number, number];

/** Ein Ortsbereich, fertig als SVG-Pfad. */
type Flaeche = { name: string; d: string; cx: number; cy: number };

const HOEHE = 460;

function ringeVon(feature: OrtsbereichFeature): Punkt[][] {
  const g = feature.geometry;
  const polys = g.type === "MultiPolygon" ? g.coordinates : [g.coordinates];
  // Nur der Außenring: Die vereinfachten Grenzen haben keine Löcher, und ein
  // Innenring würde als eigene Fläche gezeichnet.
  return polys.map((poly) => poly[0] as Punkt[]).filter((r) => r && r.length > 2);
}

/** GeoJSON → SVG-Pfade, gemeinsam auf eine Box skaliert. */
function projizieren(features: OrtsbereichFeature[], breite: number): { flaechen: Flaeche[]; hoehe: number } {
  let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
  for (const f of features) {
    for (const ring of ringeVon(f)) {
      for (const [lon, lat] of ring) {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
    }
  }
  if (!Number.isFinite(minLon)) return { flaechen: [], hoehe: HOEHE };

  // Ohne cos(φ) wäre die Stadt in die Breite gezogen: Ein Längengrad ist auf
  // 53° Nord nur noch gut 0,6 Breitengrade breit.
  const kos = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
  const spanX = (maxLon - minLon) * kos;
  const spanY = maxLat - minLat;
  const rand = 6;
  const skala = Math.min((breite - 2 * rand) / spanX, (HOEHE - 2 * rand) / spanY);
  const hoehe = spanY * skala + 2 * rand;
  const versatzX = (breite - spanX * skala) / 2;
  const versatzY = rand;

  const x = (lon: number) => versatzX + (lon - minLon) * kos * skala;
  // y invertiert: Norden liegt oben, SVG zählt nach unten.
  const y = (lat: number) => versatzY + (maxLat - lat) * skala;

  const flaechen: Flaeche[] = [];
  for (const f of features) {
    const ringe = ringeVon(f);
    if (!ringe.length) continue;
    const d = ringe
      .map((ring) => ring.map(([lo, la], i) =>
        `${i ? "L" : "M"}${x(lo).toFixed(1)} ${y(la).toFixed(1)}`).join("") + "Z")
      .join(" ");
    // Schwerpunkt des größten Rings — trägt später den Namen bzw. den Punkt.
    const groesster = ringe.reduce((a, b) => (b.length > a.length ? b : a));
    const cx = groesster.reduce((s, p) => s + x(p[0]), 0) / groesster.length;
    const cy = groesster.reduce((s, p) => s + y(p[1]), 0) / groesster.length;
    flaechen.push({ name: f.properties.name, d, cx, cy });
  }
  return { flaechen, hoehe };
}

export function StadtteilKarte({ gewaehlt, auswaehlbar, onWaehlen, className }: {
  /** Namen der gewählten Ortsbereiche. Mehrere sind erlaubt: Man interessiert
   *  sich für den eigenen Stadtteil und für den, in dem gerade gebaut wird. */
  gewaehlt: Set<string>;
  /** Namen, zu denen es überhaupt Beschlüsse gibt. Alle anderen bleiben
   *  sichtbar, aber stumm: Die Stadt soll vollständig aussehen, und ein
   *  fehlendes Stück wäre erklärungsbedürftiger als ein blasses. */
  auswaehlbar: Set<string>;
  onWaehlen: (name: string) => void;
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
            return (
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
                strokeWidth={aktiv ? 2 : 1}
                onMouseEnter={() => setSchwebt(f.name)}
                onMouseLeave={() => setSchwebt((n) => (n === f.name ? null : n))}
                onClick={() => offen && onWaehlen(f.name)}
              />
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
