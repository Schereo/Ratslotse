"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { loadOrtsbereiche, type OrtsbereichFeature } from "@/lib/districts";
import { basemapUrl } from "@/lib/basemap";
import { cn } from "@/lib/utils";
import { ViertelZeichner, type KartenSperrung, type KartenVorhaben } from "@/components/viertel-zeichner";

export { STAND_FARBE, type KartenSperrung, type KartenVorhaben } from "@/components/viertel-zeichner";

/** Die Karte als Bühne von „Mein Viertel" (die Seite `/viertel`).
 *
 *  Das Viertel als Umriss auf echtem Kartengrund, jedes Vorhaben als Pin in
 *  seiner Stand-Farbe — und wo der Ort eine Straße ist, als Linie: Ein Pin am
 *  Mittelpunkt einer Straße, die um die Ecke geht, läge NEBEN ihr (dieselbe
 *  Falle wie in `geo.ortsbereiche_der_geometrie`). Ein Tipp wählt das
 *  Vorhaben, die Seite zeigt es unter der Karte bzw. in der Seitenspalte.
 *
 *  Gezeichnet wird über `ViertelZeichner` — denselben, den die vereinte
 *  Stadtkarte (`stadt-karte.tsx`) auf ihrer Viertel-Stufe benutzt. Hier
 *  bleibt nur die Hülle: Leaflet laden, Grenze setzen, Zustand durchreichen.
 *
 *  Leaflet wird erst im Effekt geladen (kein SSR, kein Export-Bruch), wie in
 *  `council-map.tsx`.
 */
const VOYAGER = basemapUrl("voyager");

export function ViertelKarte({ ortsbereich, vorhaben, sperrungen, aktiv, gedimmt, schwebt, onSelect, onHover, className }: {
  /** Name des Ortsbereichs — die Grenze kommt aus dem statischen GeoJSON. */
  ortsbereich: string;
  vorhaben: KartenVorhaben[];
  /** Laufende Sperrungen der Stadt im Viertel — Linien in Warnfarbe mit
   *  Hinweis, aber ohne Auswahl: Sie sind Kontext, kein Vorhaben. */
  sperrungen?: KartenSperrung[];
  /** Das ausgewählte Vorhaben (Pin wird groß, Karte fährt hin). */
  aktiv: number | null;
  /** Vorhaben, die der Stufen-Filter ausblendet — bleiben blass sichtbar. */
  gedimmt: Set<number>;
  /** Das Vorhaben, über dem der Zeiger gerade in der LISTE steht — sein Pin
   *  hebt sich auf der Karte, damit Liste und Karte eine Sache sind. */
  schwebt?: number | null;
  onSelect: (id: number) => void;
  /** Zeiger über einem Pin (bzw. weg davon) — die Liste hebt ihre Zeile. */
  onHover?: (id: number | null) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const zeichnerRef = useRef<ViertelZeichner | null>(null);
  const rueckrufe = useRef({ onSelect, onHover });
  rueckrufe.current = { onSelect, onHover };

  // Karte einmal aufbauen: Kacheln, Grenze, Ausschnitt.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current || !ref.current.isConnected) return;
      delete (ref.current as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
      const map = L.map(ref.current, { zoomControl: true, scrollWheelZoom: false, attributionControl: true });
      mapRef.current = map;
      L.tileLayer(VOYAGER, { maxZoom: 19, subdomains: "abcd", attribution: "&copy; OpenStreetMap, &copy; CARTO" }).addTo(map);
      map.setView([53.1435, 8.2146], 12);
      let grenze: OrtsbereichFeature | undefined;
      try {
        grenze = (await loadOrtsbereiche()).find((f) => f.properties.name === ortsbereich);
      } catch { /* ohne Grenze bleibt die Karte trotzdem brauchbar */ }
      if (cancelled) return;
      if (grenze) {
        const layer = L.geoJSON(grenze as never, {
          style: { color: "#0a63a8", weight: 2, opacity: 0.8, fillColor: "#0a63a8", fillOpacity: 0.05 },
          interactive: false,
        }).addTo(map);
        map.fitBounds(layer.getBounds(), { padding: [12, 12] });
      }
      zeichnerRef.current = new ViertelZeichner(L, map, L.layerGroup().addTo(map), {
        onSelect: (id) => rueckrufe.current.onSelect(id),
        onHover: (id) => rueckrufe.current.onHover?.(id),
      });
      zeichnen();
    })();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      zeichnerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ortsbereich]);

  // Zeiger in der Liste → Pin hebt sich, ohne Neuzeichnen.
  useEffect(() => {
    if (schwebt != null) zeichnerRef.current?.heben(schwebt, true);
    return () => { if (schwebt != null) zeichnerRef.current?.heben(schwebt, false); };
  }, [schwebt]);

  function zeichnen() {
    const z = zeichnerRef.current, map = mapRef.current;
    if (!z || !map) return;
    z.zeichnen({ vorhaben, sperrungen, aktiv, gedimmt });
    if (z.aktivBounds) map.flyToBounds(z.aktivBounds.pad(0.6), { maxZoom: 16, duration: 0.5 });
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { zeichnen(); }, [vorhaben, sperrungen, aktiv, gedimmt]);

  return (
    <div className={cn("relative overflow-hidden rounded-2xl border border-border bg-muted", className)}>
      <div ref={ref} className="h-full w-full" aria-label={`Karte von ${ortsbereich} mit den Vorhaben`} role="region" />
    </div>
  );
}
