/** Oldenburger Stadtteil-Grenzen (31 Stück) für den Karten-Filter.
 *
 * Quelle: OpenStreetMap (admin_level 10, © OpenStreetMap contributors, ODbL),
 * per Douglas-Peucker auf ~25 m vereinfacht — als statisches Asset unter
 * /geo/stadtteile-oldenburg.json (≈18 KB), lazy geladen wenn der Themen-Tab
 * offen ist. Die Punkt-Zuordnung läuft client-seitig per Ray-Casting.
 */

export interface StadtteilFeature {
  type: "Feature";
  properties: { name: string };
  geometry:
    | { type: "Polygon"; coordinates: number[][][] }
    | { type: "MultiPolygon"; coordinates: number[][][][] };
}

let cache: Promise<StadtteilFeature[]> | null = null;

export function loadStadtteile(): Promise<StadtteilFeature[]> {
  cache ??= fetch("/geo/stadtteile-oldenburg.json")
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .then((fc) => fc.features as StadtteilFeature[])
    .catch(() => {
      cache = null; // beim nächsten Aufruf erneut versuchen
      return [];
    });
  return cache;
}

/** Kommunalwahl-Wahlbereiche der Stadt Oldenburg (1–6). Manche Stadtteile liegen
 *  über einer Wahlbereichs-Grenze und gehören zu MEHREREN Bereichen (z. B.
 *  Bürgerfelde → 1+3, Osternburg → 5+2) — die werden in allen gelistet.
 *  Ermittelt aus der Flächen-Überlappung der Stadtteil-Polygone (OSM) mit den
 *  offiziellen Wahlbereich-Polygonen (openGEOdata Stadt Oldenburg, FeatureServer
 *  „Wahlen", Layer 1; Stand 2026-07): ein Stadtteil zählt zu jedem Bereich mit
 *  ≥10 % Flächenanteil (darunter = Grenz-/Simplify-Rauschen). Erster Eintrag =
 *  überwiegender Bereich. Bei Änderungen auch council/geo.py pflegen. */
export const WAHLBEREICH: Record<string, number[]> = {
  "Bürgeresch": [1], "Bürgerfelde": [1, 3], "Donnerschwee": [1, 4], "Ehnernviertel": [1], "Ziegelhof": [1],
  "Bahnhofsviertel": [2], "Dobbenviertel": [2], "Drielake": [2], "Gerichtsviertel": [2],
  "Haarenesch": [2], "Innenstadt": [2], "Neuenwege": [2],
  "Bloherfelde": [3], "Dietrichsfeld": [3], "Fliegerhorst": [3], "Haarentor": [3, 6], "Wechloy": [3],
  "Alexandersfeld": [4], "Bornhorst": [4], "Etzhorn": [4], "Nadorst": [4], "Ofenerdiek": [4], "Ohmstede": [4],
  "Bümmerstede": [5], "Drielaker-Moor": [5, 2], "Kreyenbrück": [5], "Krusenbusch": [5],
  "Osternburg": [5, 2], "Tweelbäke": [5, 2],
  "Eversten": [6], "Nordmoslesfehn": [6],
};

/** Stadtteil-Namen je Wahlbereich [1..6] — inkl. Grenzstadtteile, die auch zu
 *  anderen Bereichen gehören. */
export function stadtteileImWahlbereich(wb: number): string[] {
  return Object.keys(WAHLBEREICH).filter((name) => WAHLBEREICH[name].includes(wb));
}

/** Ray-Casting: liegt (lon, lat) im Ring? */
function inRing(lon: number, lat: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** Stadtteil-Name für einen Punkt — oder null (außerhalb Oldenburgs). Nur der
 *  Außenring zählt (die vereinfachten Grenzen haben keine Löcher). */
export function stadtteilFor(lat: number, lon: number, features: StadtteilFeature[]): string | null {
  for (const f of features) {
    const polys = f.geometry.type === "MultiPolygon" ? f.geometry.coordinates : [f.geometry.coordinates];
    for (const poly of polys) {
      if (poly[0] && inRing(lon, lat, poly[0])) return f.properties.name;
    }
  }
  return null;
}
