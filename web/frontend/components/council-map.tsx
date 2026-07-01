"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import type { Map as LeafletMap, TileLayer } from "leaflet";
import "leaflet/dist/leaflet.css";
import { EntityMapPoint } from "@/lib/types";
import { themaHref } from "@/lib/routes";

// Minimalist CARTO basemaps, swapped live with the site theme (same as EntityMap).
const TILES = {
  light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};

// Marker colour by entity kind (the legend in the Themen tab mirrors this).
export const KIND_COLOR: Record<string, string> = {
  ort: "#2563eb",
  organisation: "#7c3aed",
  projekt: "#059669",
};

// City-wide map: one clickable circle marker per geocoded entity, sized by how many
// decisions reference it. Plain Leaflet + CARTO tiles, client-only (load via
// next/dynamic ssr:false), theme-reactive like EntityMap. CircleMarkers only — no
// marker-icon images to fetch (CSP img-src stays limited to the tiles).
export function CouncilMap({ points }: { points: EntityMapPoint[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const router = useRouter();

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
      observer = new MutationObserver(() => tiles.setUrl(isDark() ? TILES.dark : TILES.light));
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

      const latlngs: [number, number][] = [];
      for (const p of points) {
        const color = KIND_COLOR[p.kind] ?? KIND_COLOR.projekt;
        const marker = L.circleMarker([p.lat, p.lon], {
          radius: Math.min(12, 4 + Math.sqrt(p.n)),
          color,
          weight: 1.5,
          fillColor: color,
          fillOpacity: 0.55,
        }).addTo(map);
        marker.bindTooltip(`${p.name} · ${p.n} ${p.n === 1 ? "Beschluss" : "Beschlüsse"}`);
        marker.on("click", () => router.push(themaHref(p.slug)));
        latlngs.push([p.lat, p.lon]);
      }
      if (latlngs.length >= 8) {
        // Frame the dense Oldenburg core, not the scattered far points (Berne, Hude, Bad
        // Zwischenahn …): centre on the median point and fit to everything within ~7 km of
        // it, so a handful of distant outliers don't shrink the whole city to a tiny blob.
        const median = (xs: number[]) => xs.slice().sort((a, b) => a - b)[xs.length >> 1];
        const cLat = median(latlngs.map((p) => p[0]));
        const cLon = median(latlngs.map((p) => p[1]));
        const core = latlngs.filter(([la, lo]) => Math.hypot((la - cLat) * 111, (lo - cLon) * 67) < 7);
        map.fitBounds(core.length >= 5 ? core : latlngs, { padding: [24, 24], maxZoom: 15 });
      } else if (latlngs.length) {
        map.fitBounds(latlngs, { padding: [30, 30], maxZoom: 14 });
      } else {
        map.setView([53.1435, 8.2146], 12); // Oldenburg centre fallback
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
  }, [points, router]);

  return (
    <div
      ref={ref}
      className="h-[72vh] min-h-[30rem] w-full overflow-hidden rounded-lg border border-border"
      aria-label="Stadtweite Themen-Karte"
    />
  );
}
