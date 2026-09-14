/** Flächen aus GeoJSON in SVG-Pfade — für jede Karte, die Oldenburg ohne
 *  Kachel-Server zeigt.
 *
 *  **Warum kein Kartengrund.** Die Ortsbereichs-Karte des Einrichtungs-
 *  Assistenten beantwortet „wo wohnst du?", die Wahlbereichs-Karte „wo ist
 *  eigentlich Wahlbereich V?". Für beides braucht es keine Straßen, keine
 *  Kacheln und keinen CARTO-Schlüssel — nur die Umrisse, die als kleines
 *  GeoJSON ohnehin im Repo liegen. Als SVG folgt die Karte außerdem dem
 *  Theme (Tokens statt Bildpixel) und kostet keine Netz-Runde.
 *
 *  Die Projektion ist eine schlichte äquirektanguläre: Bei der Ausdehnung
 *  einer Stadt (≈ 15 km) ist der Fehler gegenüber Mercator nicht sichtbar.
 *  Der Breitengrad-Faktor `cos(φ)` muss aber sein — ohne ihn stünde Oldenburg
 *  um ein Drittel in die Breite gezogen da.
 *
 *  Stand 09/2026 rechnen zwei Karten hiermit (Ortsbereiche, Wahlbereiche und
 *  Wahlbezirke). Vorher stand die Rechnung in `stadtteil-karte.tsx`; eine
 *  zweite Abschrift daneben wäre die Fassung, die als Erste veraltet.
 */

export type GeoGeometrie =
  | { type: "Polygon"; coordinates: number[][][] }
  | { type: "MultiPolygon"; coordinates: number[][][][] };

export type GeoFlaeche<P> = { type: "Feature"; properties: P; geometry: GeoGeometrie };

/** Eine Fläche, fertig als SVG-Pfad, samt Schwerpunkt für die Beschriftung. */
export type Pfad<P> = { eigenschaften: P; d: string; cx: number; cy: number };

type Punkt = [number, number];

/** Nur die Außenringe: Die vereinfachten Grenzen haben keine Löcher, und ein
 *  Innenring würde als eigene Fläche gezeichnet. */
export function ringe<P>(f: GeoFlaeche<P>): Punkt[][] {
  const g = f.geometry;
  const polys = g.type === "MultiPolygon" ? g.coordinates : [g.coordinates];
  return polys.map((poly) => poly[0] as Punkt[]).filter((r) => r && r.length > 2);
}

/**
 * GeoJSON-Flächen auf eine Box der Breite `breite` und höchstens `maxHoehe`
 * legen. Zurück kommen die Pfade und die tatsächlich gebrauchte Höhe — die
 * Karte ist so hoch, wie die Stadt es verlangt, nicht so hoch wie die Box.
 *
 * `rand` hält den Umriss von der Kante weg, damit die Linienbreite nicht
 * abgeschnitten wird.
 */
export function projiziere<P>(
  features: readonly GeoFlaeche<P>[],
  breite: number,
  maxHoehe: number,
  rand = 6,
): { pfade: Pfad<P>[]; hoehe: number } {
  let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
  for (const f of features) {
    for (const ring of ringe(f)) {
      for (const [lon, lat] of ring) {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
    }
  }
  if (!Number.isFinite(minLon)) return { pfade: [], hoehe: maxHoehe };

  const kos = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
  const spanX = (maxLon - minLon) * kos;
  const spanY = maxLat - minLat;
  const skala = Math.min((breite - 2 * rand) / spanX, (maxHoehe - 2 * rand) / spanY);
  const hoehe = spanY * skala + 2 * rand;
  const versatzX = (breite - spanX * skala) / 2;
  const versatzY = rand;

  const x = (lon: number) => versatzX + (lon - minLon) * kos * skala;
  // y invertiert: Norden liegt oben, SVG zählt nach unten.
  const y = (lat: number) => versatzY + (maxLat - lat) * skala;

  const pfade: Pfad<P>[] = [];
  for (const f of features) {
    const rs = ringe(f);
    if (!rs.length) continue;
    const d = rs
      .map((ring) => ring.map(([lo, la], i) =>
        `${i ? "L" : "M"}${x(lo).toFixed(1)} ${y(la).toFixed(1)}`).join("") + "Z")
      .join(" ");
    const groesster = rs.reduce((a, b) => (b.length > a.length ? b : a));
    const cx = groesster.reduce((s, p) => s + x(p[0]), 0) / groesster.length;
    const cy = groesster.reduce((s, p) => s + y(p[1]), 0) / groesster.length;
    pfade.push({ eigenschaften: f.properties, d, cx, cy });
  }
  return { pfade, hoehe };
}

/**
 * Die Deckkraft des Primärtons für einen Wert zwischen 0 und `max`.
 *
 * Die Tönung folgt der WURZEL, nicht dem Wert: Bei 0 bis 14 Vorhaben wären
 * sonst zwei Drittel der Stadt kaum von der leeren Fläche zu unterscheiden.
 * `null`, wo es nichts zu tönen gibt — dort bleibt die neutrale Fläche.
 */
export function toenung(wert: number | null | undefined, max: number,
                        von = 0.12, spanne = 0.5): string | null {
  if (wert === null || wert === undefined || wert <= 0 || max <= 0) return null;
  const a = von + spanne * Math.sqrt(Math.min(1, wert / max));
  return `hsl(var(--primary) / ${a.toFixed(2)})`;
}

/**
 * Dieselbe Tönung, aber über eine SPANNE statt über die Null.
 *
 * Für „wo ist diese Liste stark?" taugt die Null nicht als Anker: Die
 * Anteile der SPD lagen 2026 zwischen 20,5 % und 25,9 % — an der Null
 * gemessen sähen alle sechs Wahlbereiche gleich aus. Zwischen dem
 * schwächsten und dem stärksten gemessen, zeigt die Karte den Unterschied,
 * um den es geht. Der Preis steht daneben in der Rangfolge: die Zahlen.
 *
 * Bei nur einem Wert (oder lauter gleichen) gibt es keine Spanne — dann
 * bekommen alle denselben mittleren Ton, statt dass einer heraussticht.
 */
export function toenungSpanne(wert: number | null | undefined, min: number, max: number,
                              von = 0.18, spanne = 0.44): string | null {
  if (wert === null || wert === undefined) return null;
  const breite = max - min;
  const anteil = breite > 0 ? Math.min(1, Math.max(0, (wert - min) / breite)) : 0.5;
  return `hsl(var(--primary) / ${(von + spanne * anteil).toFixed(2)})`;
}
