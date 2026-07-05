"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { cn } from "@/lib/utils";

const VOYAGER = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";

/** Kleine, nicht-interaktive Karte mit EINEM Marker — zeigt in der Auflösung,
 *  wo ein Ort/eine Straße/ein Gebäude liegt. CircleMarker statt Icon-Bild, damit
 *  die CSP img-src eng bleibt. Theme-reaktiv wie die Themen-Karte. */
export function LocatorMap({ lat, lon, label, className }: {
  lat: number;
  lon: number;
  label?: string | null;
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
        map.setView([lat, lon], 15);
        const tiles = L.tileLayer(VOYAGER, {
          maxZoom: 18, detectRetina: true, subdomains: "abcd",
          attribution: "&copy; OpenStreetMap, &copy; CARTO",
        }).addTo(map);
        observer = new MutationObserver(() => tiles.setUrl(VOYAGER));
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
        const marker = L.circleMarker([lat, lon], {
          radius: 8, color: "#0764a6", weight: 2, fillColor: "#0764a6", fillOpacity: 0.7,
        }).addTo(map);
        if (label) marker.bindTooltip(label, { permanent: true, direction: "top", offset: [0, -8] });
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
  }, [lat, lon, label]);

  return (
    <div className={cn("relative isolate overflow-hidden rounded-lg border border-border", className)}>
      <div ref={ref} className="h-full w-full" aria-label={label ? `Karte: ${label}` : "Karte"} />
    </div>
  );
}
