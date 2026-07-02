"use client";

import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

const OLDENBURG: [number, number] = [8.2146, 53.1389]; // city centre [lng, lat]

// 3D MapLibre map of Oldenburg for the landing hero — tilted, slowly orbiting, with
// extruded buildings. Free, keyless OpenStreetMap vector tiles (OpenFreeMap), loaded
// lazily on the client. Non-interactive (a showcase, not a tool). Calls onError so the
// caller can fall back to the particle network if tiles fail.
export function HeroMap({ onError, className }: { onError?: () => void; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const container = ref.current;
    if (!container) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let map: import("maplibre-gl").Map | null = null;
    let raf = 0;
    let cancelled = false;
    let failed = false;
    const fail = () => { if (!failed) { failed = true; onError?.(); } };

    void (async () => {
      try {
        const maplibregl = (await import("maplibre-gl")).default;
        if (cancelled) return;
        map = new maplibregl.Map({
          container,
          style: "https://tiles.openfreemap.org/styles/positron",
          center: OLDENBURG,
          zoom: 15.1,
          pitch: 55,
          bearing: -18,
          interactive: false,
          attributionControl: false,
        });
        map.on("error", fail);
        map.on("load", () => {
          if (cancelled || !map) return;
          // Extrude 3D buildings on top of the flat style (OpenMapTiles "building" layer).
          const style = map.getStyle();
          const vectorSrc = Object.entries(style.sources || {}).find(([, s]) => s.type === "vector")?.[0];
          const firstSymbol = (style.layers || []).find((l) => l.type === "symbol")?.id;
          if (vectorSrc) {
            try {
              map.addLayer({
                id: "3d-buildings",
                source: vectorSrc,
                "source-layer": "building",
                type: "fill-extrusion",
                minzoom: 13,
                paint: {
                  "fill-extrusion-color": "#aebfdc",
                  "fill-extrusion-height": ["coalesce", ["get", "render_height"], 6],
                  "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
                  "fill-extrusion-opacity": 0.9,
                },
              }, firstSymbol);
            } catch { /* schema without building layer — keep the flat map */ }
          }
          setReady(true);
          if (!reduce) {
            const spin = () => {
              if (cancelled || !map) return;
              map.setBearing(map.getBearing() + 0.05);
              raf = requestAnimationFrame(spin);
            };
            raf = requestAnimationFrame(spin);
          }
        });
      } catch {
        fail();
      }
    })();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      map?.remove();
    };
  }, [onError]);

  return (
    <div
      ref={ref}
      className={className}
      style={{ opacity: ready ? 1 : 0, transition: "opacity 800ms ease" }}
      aria-hidden
    />
  );
}
