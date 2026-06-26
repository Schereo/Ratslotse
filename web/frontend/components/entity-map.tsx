"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { EntityGeo } from "@/lib/types";

// Plain Leaflet (no react-leaflet dependency) so we fully control the single-shape
// render. Client-only — Leaflet needs `window`, so the page imports this via
// next/dynamic with ssr:false. Tiles come from OpenStreetMap (allowed in the CSP
// img-src); no marker-icon images are used (CircleMarker), avoiding icon-path issues.
export function EntityMap({ geo, name }: { geo: EntityGeo; name: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current || mapRef.current) return;
      const map = L.map(ref.current, { scrollWheelZoom: false });
      mapRef.current = map;
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap-Mitwirkende",
      }).addTo(map);
      const primary = getComputedStyle(document.documentElement).getPropertyValue("--primary").trim();
      const color = primary ? `hsl(${primary})` : "#3b82f6";
      const dot = { radius: 9, color, weight: 2, fillColor: color, fillOpacity: 0.5 };

      if (geo.geojson) {
        const layer = L.geoJSON(geo.geojson as never, {
          style: { color, weight: 4, opacity: 0.9, fillColor: color, fillOpacity: 0.15 },
          pointToLayer: (_f, latlng) => L.circleMarker(latlng, dot),
        }).addTo(map);
        try {
          map.fitBounds(layer.getBounds(), { padding: [26, 26], maxZoom: 16 });
        } catch {
          map.setView([geo.lat, geo.lon], 15);
        }
      } else {
        L.circleMarker([geo.lat, geo.lon], dot).addTo(map).bindTooltip(name);
        map.setView([geo.lat, geo.lon], 15);
      }
    })();
    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [geo, name]);

  return (
    <div
      ref={ref}
      className="h-64 w-full overflow-hidden rounded-lg border border-border"
      aria-label={`Karte: ${name}`}
    />
  );
}
