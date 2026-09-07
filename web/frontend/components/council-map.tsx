import { EntityMapPoint } from "@/lib/types";
import { ortHref, themaHref } from "@/lib/routes";

// Bis 09/2026 stand hier die Leaflet-Karte des Themen-Tabs (`CouncilMap`:
// Cluster, Labels ab Zoom 14, Vollbild, gemerkter Ausschnitt). Sie ist als
// Ebene „Themen-Orte" in die vereinte Stadtkarte gewandert — der Zeichner
// heißt `themen-orte-zeichner.ts`, die Bühne `stadt-karte.tsx`
// (STADTKARTE-PLAN.md, Schritte 3 und 5). Geblieben ist das Vokabular der
// Punkte: wohin ein Punkt führt, was ein Beschlussort ist, welche Farbe eine
// Art trägt. Die Datei heißt weiter so, weil `KIND_COLOR` aus vielen Stellen
// importiert wird.

// Marker colour by entity kind (the legend in the Themen tab mirrors this).
/** Wohin ein Kartenpunkt führt — Thema, Ortsseite oder die Beschluss-Suche
 *  nach einem Beschlussort. Hier (und nicht in der Stadtkarte), weil die
 *  `target`-Werte ein eigenes Vokabular sind, das nur diese Datei liest. */
export function punktHref(p: EntityMapPoint): string {
  if (p.target === "ort" && p.place_id) return ortHref(p.place_id);
  if (p.target === "location") {
    const query = new URLSearchParams({ tab: "decisions", cat: "all", location: p.location_slug ?? p.slug, location_name: p.name });
    return `/council?${query.toString()}`;
  }
  return themaHref(p.slug);
}

/** Ein konkreter Beschlussort (Straße, Platz, Gebäude aus der Orts-Pipeline)
 *  — im Unterschied zu einem Thema mit Koordinate. */
export function istBeschlussort(p: EntityMapPoint): boolean {
  return p.target === "location";
}

export const KIND_COLOR: Record<string, string> = {
  place: "#0764a6",
  organisation: "#7c3aed",
  project: "#059669",
  beschlussort: "#dc6b19",
};
