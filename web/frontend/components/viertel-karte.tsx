"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import "leaflet/dist/leaflet.css";
import { loadOrtsbereiche, type OrtsbereichFeature } from "@/lib/districts";
import { basemapUrl } from "@/lib/basemap";
import { cn } from "@/lib/utils";

/** Die Karte als Bühne von „Mein Viertel".
 *
 *  Das Viertel als Umriss auf echtem Kartengrund, jedes Vorhaben als Pin in
 *  seiner Stand-Farbe — und wo der Ort eine Straße ist, als Linie: Ein Pin am
 *  Mittelpunkt einer Straße, die um die Ecke geht, läge NEBEN ihr (dieselbe
 *  Falle wie in `geo.ortsbereiche_der_geometrie`). Ein Tipp öffnet ein
 *  Popover mit Name und Stand; „Details" gibt das Vorhaben nach außen, die
 *  Seite zeigt es dann unter der Karte bzw. in der Seitenspalte.
 *
 *  Leaflet wird erst im Effekt geladen (kein SSR, kein Export-Bruch), wie in
 *  `council-map.tsx`; die Punkte bleiben HTML-Kreise, es werden keine
 *  Marker-Bilder nachgeladen (CSP bleibt auf die Kacheln begrenzt).
 */
export type KartenVorhaben = {
  id: number;
  name: string;
  stage: string;
  when: string | null;
  locations: { slug: string; name: string; kind: string; lat: number; lon: number; geometry: unknown }[];
};

/** Stand → Farbe. Dieselben Töne wie die Badges der Liste, damit Pin und
 *  Karte dasselbe sagen. */
export const STAND_FARBE: Record<string, string> = {
  building: "#f0641c", decided: "#15803d", planning: "#0a63a8", idea: "#64748b", done: "#94a3b8", rejected: "#b91c1c",
};
const STAND_LABEL: Record<string, string> = {
  building: "Im Bau", decided: "Beschlossen", planning: "In Planung", idea: "Idee", done: "Fertig", rejected: "Abgelehnt",
};

const VOYAGER = basemapUrl("voyager");

export function ViertelKarte({ ortsbereich, vorhaben, aktiv, gedimmt, onSelect, className }: {
  /** Name des Ortsbereichs — die Grenze kommt aus dem statischen GeoJSON. */
  ortsbereich: string;
  vorhaben: KartenVorhaben[];
  /** Das ausgewählte Vorhaben (Pin wird groß, Karte fährt hin). */
  aktiv: number | null;
  /** Vorhaben, die der Stufen-Filter ausblendet — bleiben blass sichtbar. */
  gedimmt: Set<number>;
  onSelect: (id: number) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Karte einmal aufbauen: Kacheln, Grenze, Ausschnitt.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current || !ref.current.isConnected) return;
      delete (ref.current as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
      leafletRef.current = L;
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
      layerRef.current = L.layerGroup().addTo(map);
      zeichnen();
    })();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ortsbereich]);

  // Pins und Linien neu zeichnen, wenn Auswahl oder Filter wechseln.
  function zeichnen() {
    const L = leafletRef.current, map = mapRef.current, gruppe = layerRef.current;
    if (!L || !map || !gruppe) return;
    gruppe.clearLayers();
    let aktivBounds: ReturnType<typeof L.latLngBounds> | null = null;
    for (const v of vorhaben) {
      const farbe = STAND_FARBE[v.stage] ?? STAND_FARBE.planning;
      const istAktiv = v.id === aktiv;
      const blass = gedimmt.has(v.id) && !istAktiv;
      const popup = `<div class="viertel-popup"><span class="stand" style="--c:${farbe}">${STAND_LABEL[v.stage] ?? v.stage}</span>${v.when ? `<span class="wann">${v.when}</span>` : ""}<b>${escapeHtml(v.name)}</b><button type="button" data-id="${v.id}">Details</button></div>`;
      const anklicken = (layer: import("leaflet").Layer) => {
        layer.bindPopup(popup, { closeButton: false, offset: [0, -6], className: "viertel-popup-huelle" });
        layer.on("popupopen", (e) => {
          const el = (e as unknown as { popup: { getElement: () => HTMLElement | undefined } }).popup.getElement();
          el?.querySelector("button")?.addEventListener("click", () => { map.closePopup(); onSelectRef.current(v.id); });
        });
      };
      for (const loc of v.locations) {
        const linie = loc.geometry as { type?: string } | null;
        if (linie && (linie.type === "LineString" || linie.type === "MultiLineString")) {
          const layer = L.geoJSON(linie as never, {
            style: { color: farbe, weight: istAktiv ? 7 : 5, opacity: blass ? 0.18 : 0.75, lineCap: "round" },
          });
          anklicken(layer);
          gruppe.addLayer(layer);
          if (istAktiv) aktivBounds = aktivBounds ? aktivBounds.extend(layer.getBounds()) : layer.getBounds();
        }
        const radius = istAktiv ? 11 : 8;
        const marker = L.marker([loc.lat, loc.lon], {
          title: v.name, alt: v.name,
          icon: L.divIcon({
            className: cn("ratslotse-map-point viertel-pin", istAktiv && "ist-aktiv", blass && "ist-blass"),
            html: `<span style="--point-color:${farbe};--point-size:${radius * 2}px"></span>`,
            iconSize: [radius * 2, radius * 2], iconAnchor: [radius, radius],
          }),
          zIndexOffset: istAktiv ? 1000 : 0,
        });
        anklicken(marker);
        gruppe.addLayer(marker);
        if (istAktiv) {
          const b = L.latLngBounds([loc.lat, loc.lon], [loc.lat, loc.lon]);
          aktivBounds = aktivBounds ? aktivBounds.extend(b) : b;
        }
      }
    }
    if (aktivBounds) map.flyToBounds(aktivBounds.pad(0.6), { maxZoom: 16, duration: 0.5 });
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { zeichnen(); }, [vorhaben, aktiv, gedimmt]);

  return (
    <div className={cn("relative overflow-hidden rounded-2xl border border-border bg-muted", className)}>
      <div ref={ref} className="h-full w-full" aria-label={`Karte von ${ortsbereich} mit den Vorhaben`} role="region" />
    </div>
  );
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] ?? c));
}
