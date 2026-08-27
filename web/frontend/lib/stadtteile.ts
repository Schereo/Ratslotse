/** Ratslotse-Ortsbereichsgrenzen (31 Stück) für Karten und Filter.
 *
 * Die Namen, IDs, Aliase und Wahlbereiche kommen aus dem zentralen Backend-
 * Katalog. Diese Datei enthält nur die OSM-Geometrie; Oldenburg hat keine
 * amtlich festgelegten Stadtteile.
 *
 * Quelle: OpenStreetMap (admin_level 10, © OpenStreetMap contributors, ODbL),
 * per Douglas-Peucker auf ~25 m vereinfacht — als statisches Asset unter
 * /geo/stadtteile-oldenburg.json (≈18 KB), lazy geladen wenn der Themen-Tab
 * offen ist. Die Punkt-Zuordnung läuft client-seitig per Ray-Casting.
 */

import { api } from "@/lib/api";

export interface OrtsbereichFeature {
  type: "Feature";
  properties: { name: string };
  geometry:
    | { type: "Polygon"; coordinates: number[][][] }
    | { type: "MultiPolygon"; coordinates: number[][][][] };
}

export type StadtteilFeature = OrtsbereichFeature;

export interface OrtsbereichEntry {
  id: string;
  name: string;
  kind: "ortsbereich";
  aliases: string[];
  wahlbereiche: number[];
}

export interface OrtsbereichCatalog {
  schema_version: number;
  id: string;
  label: string;
  singular: string;
  plural: string;
  definition: string;
  sources: { id: string; type: string; title: string; url: string; note?: string; license?: string }[];
  places: OrtsbereichEntry[];
}

let geometryCache: Promise<OrtsbereichFeature[]> | null = null;
let catalogCache: Promise<OrtsbereichCatalog> | null = null;

export function loadOrtsbereiche(): Promise<OrtsbereichFeature[]> {
  geometryCache ??= fetch("/geo/stadtteile-oldenburg.json")
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .then((fc) => fc.features as OrtsbereichFeature[])
    .catch(() => {
      geometryCache = null; // beim nächsten Aufruf erneut versuchen
      return [];
    });
  return geometryCache;
}

export function loadOrtsbereichCatalog(): Promise<OrtsbereichCatalog> {
  catalogCache ??= api.get<OrtsbereichCatalog>("/council/places").catch((error) => {
    catalogCache = null;
    throw error;
  });
  return catalogCache;
}

/** Ortsbereich-Namen je Wahlbereich [1..6] — inkl. Grenzgebiete, die auch zu
 *  anderen Bereichen gehören. */
export function ortsbereicheImWahlbereich(wb: number, places: OrtsbereichEntry[]): string[] {
  return places.filter((place) => place.wahlbereiche.includes(wb)).map((place) => place.name);
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

/** Ortsbereich für einen Punkt — oder null (außerhalb Oldenburgs). Nur der
 *  Außenring zählt (die vereinfachten Grenzen haben keine Löcher). */
export function ortsbereichFor(lat: number, lon: number, features: OrtsbereichFeature[]): string | null {
  for (const f of features) {
    const polys = f.geometry.type === "MultiPolygon" ? f.geometry.coordinates : [f.geometry.coordinates];
    for (const poly of polys) {
      if (poly[0] && inRing(lon, lat, poly[0])) return f.properties.name;
    }
  }
  return null;
}

// Kompatible Namen für bestehende Karten-Komponenten und gespeicherte API-Felder.
export const loadStadtteile = loadOrtsbereiche;
export const stadtteilFor = ortsbereichFor;
