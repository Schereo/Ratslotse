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
