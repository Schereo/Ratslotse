"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap, TileLayer } from "leaflet";
import "leaflet/dist/leaflet.css";
import { EntityGeo } from "@/lib/types";

// Minimalist CARTO basemaps that match the clean look of the site — light "Positron"
// and dark "Dark Matter", swapped live with the site theme. (Replaces the busy default
// OpenStreetMap raster tiles.)
const TILES = {
  light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};

// Plain Leaflet (no react-leaflet) — client-only (needs `window`), loaded via
// next/dynamic with ssr:false. No marker-icon images (CircleMarker), so nothing to
// fetch beyond the tiles (allowed in the CSP img-src).
export function EntityMap({ geo, name }: { geo: EntityGeo; name: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    let cancelled = false;
    let observer: MutationObserver | null = null;
    void (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current || mapRef.current) return;
      const map = L.map(ref.current, { scrollWheelZoom: false });
      mapRef.current = map;

      const isDark = () => document.documentElement.classList.contains("dark");
      const tiles: TileLayer = L.tileLayer(isDark() ? TILES.dark : TILES.light, {
        maxZoom: 19,
        detectRetina: true,
        subdomains: "abcd",
        attribution: "&copy; OpenStreetMap, &copy; CARTO",
      }).addTo(map);
      // Swap light/dark tiles when the site theme toggles.
      observer = new MutationObserver(() => tiles.setUrl(isDark() ? TILES.dark : TILES.light));
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

      const primary = getComputedStyle(document.documentElement).getPropertyValue("--primary").trim();
      const color = primary ? `hsl(${primary})` : "#3b82f6";
      const dot = { radius: 7, color, weight: 2, fillColor: color, fillOpacity: 0.5 };

      if (geo.geojson) {
        const layer = L.geoJSON(geo.geojson as never, {
          style: { color, weight: 4, opacity: 0.9, fillColor: color, fillOpacity: 0.12 },
          pointToLayer: (_f, latlng) => L.circleMarker(latlng, dot),
        }).addTo(map);
        try {
          // maxZoom 15 keeps a short street/area from zooming in too far (more context).
          map.fitBounds(layer.getBounds(), { padding: [30, 30], maxZoom: 15 });
        } catch {
          map.setView([geo.lat, geo.lon], 14);
        }
      } else {
        L.circleMarker([geo.lat, geo.lon], dot).addTo(map).bindTooltip(name);
        map.setView([geo.lat, geo.lon], 14);
      }
    })();
    return () => {
      cancelled = true;
      observer?.disconnect();
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
