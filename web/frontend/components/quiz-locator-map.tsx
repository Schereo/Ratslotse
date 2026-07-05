"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { cn } from "@/lib/utils";

const VOYAGER = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";

/** Kleine, nicht-interaktive Karte für die Auflösung: zeigt entweder einen
 *  Punkt (Einzelort/Gebäude) ODER eine Straßen-Linie (`geojson`), je nachdem was
 *  das Backend verlässlich ermitteln konnte. CircleMarker/Polyline statt
 *  Icon-Bild, damit die CSP img-src eng bleibt. Theme-reaktiv. */
export function LocatorMap({ lat, lon, label, geojson, className }: {
  lat: number;
  lon: number;
  label?: string | null;
  geojson?: object | null;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    let cancelled = false;
    let observer: MutationObserver | null = null;
    void (async () => {
      try {
        const L = (await import("leaflet")).default;
        if (cancelled || !ref.current || !ref.current.isConnected || mapRef.current) return;
        ref.current.innerHTML = "";
        delete (ref.current as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
        const map = L.map(ref.current, {
          scrollWheelZoom: false, dragging: false, zoomControl: false,
          doubleClickZoom: false, attributionControl: true,
        });
        mapRef.current = map;
        map.setView([lat, lon], 15);   // Initial-View vor den Layern (fitBounds crasht sonst)
        const tiles = L.tileLayer(VOYAGER, {
          maxZoom: 18, detectRetina: true, subdomains: "abcd",
          attribution: "&copy; OpenStreetMap, &copy; CARTO",
        }).addTo(map);
        observer = new MutationObserver(() => tiles.setUrl(VOYAGER));
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
        if (geojson) {
          // Entweder eine Straßen-Linie (kompakt & eindeutig) ODER ein ganzes
          // Gebiets-Polygon (Stadtteil) — beide vom Backend geliefert. Fläche
          // wird dezent gefüllt, Linie kräftig gestrichelt.
          const gtype = (geojson as { type?: string }).type;
          const isArea = gtype === "Polygon" || gtype === "MultiPolygon";
          const layer = L.geoJSON(geojson as never, {
            style: isArea
              ? { color: "#0764a6", weight: 2, opacity: 0.9, fillColor: "#0764a6", fillOpacity: 0.12 }
              : { color: "#0764a6", weight: 4, opacity: 0.85, lineCap: "round" },
          }).addTo(map);
          if (isArea && label) layer.bindTooltip(label, { permanent: true, direction: "center" });
          const b = layer.getBounds();
          if (b.isValid()) map.fitBounds(b, { padding: [24, 24], maxZoom: 16 });
        } else {
          const marker = L.circleMarker([lat, lon], {
            radius: 8, color: "#0764a6", weight: 2, fillColor: "#0764a6", fillOpacity: 0.7,
          }).addTo(map);
          if (label) marker.bindTooltip(label, { permanent: true, direction: "top", offset: [0, -8] });
        }
      } catch (err) {
        console.error("[LocatorMap] Initialisierung fehlgeschlagen:", err);
      }
    })();
    return () => {
      cancelled = true;
      observer?.disconnect();
      const m = mapRef.current;
      mapRef.current = null;
      try { m?.remove(); } catch { /* Karte ohnehin weg */ }
    };
  }, [lat, lon, label, geojson]);

  return (
    <div className={cn("relative isolate overflow-hidden rounded-lg border border-border", className)}>
      <div ref={ref} className="h-full w-full" aria-label={label ? `Karte: ${label}` : "Karte"} />
    </div>
  );
}
