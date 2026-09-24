"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap, CircleMarker, GeoJSON as LGeoJSON } from "leaflet";
import "leaflet/dist/leaflet.css";
import { cn } from "@/lib/utils";
import { basemapUrl } from "@/lib/basemap";

const VOYAGER = basemapUrl("voyager");
const CENTER: [number, number] = [53.1435, 8.2146];

/** Karte für „Wo liegt das?": Ein Tipp setzt (oder versetzt) den Pin; mit
 *  `solution` erscheint die Geometrie des Orts, und der Ausschnitt nimmt Pin
 *  und Ort zusammen. Punkte als CircleMarker statt Icon-Bild (CSP img-src). */
export function PinMap({ pin, solution, onPin, className }: {
  pin: { lat: number; lon: number } | null;
  solution: object | null;           // GeoJSON-Geometrie nach dem Auflösen
  onPin: (p: { lat: number; lon: number }) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const pinRef = useRef<CircleMarker | null>(null);
  const solRef = useRef<LGeoJSON | null>(null);
  const LRef = useRef<typeof import("leaflet") | null>(null);
  const onPinRef = useRef(onPin);
  onPinRef.current = onPin;
  const lockedRef = useRef(false);
  lockedRef.current = solution !== null;

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current || mapRef.current) return;
      LRef.current = L;
      const map = L.map(ref.current, { scrollWheelZoom: false, zoomSnap: 0.5 });
      mapRef.current = map;
      map.setView(CENTER, 12.5);
      L.tileLayer(VOYAGER, { maxZoom: 18, detectRetina: true, subdomains: "abcd",
        attribution: "&copy; OpenStreetMap, &copy; CARTO" }).addTo(map);
      map.on("click", (e) => {
        if (lockedRef.current) return;
        onPinRef.current({ lat: e.latlng.lat, lon: e.latlng.lng });
      });
    })();
    return () => {
      cancelled = true;
      const m = mapRef.current;
      mapRef.current = null;
      try { m?.stop(); m?.remove(); } catch { /* weg */ }
    };
  }, []);

  // Pin setzen/versetzen.
  useEffect(() => {
    const L = LRef.current, map = mapRef.current;
    if (!L || !map) return;
    pinRef.current?.remove();
    pinRef.current = pin
      ? L.circleMarker([pin.lat, pin.lon], { radius: 8, color: "#fff", weight: 2.5, fillColor: "#ea580c", fillOpacity: 1 }).addTo(map)
      : null;
  }, [pin]);

  // Auflösung: Geometrie zeigen, Ausschnitt auf Pin + Ort.
  useEffect(() => {
    const L = LRef.current, map = mapRef.current;
    if (!L || !map) return;
    solRef.current?.remove();
    solRef.current = null;
    if (!solution) return;  // je Frage eine neue Karte (key im Aufrufer)
    const t = (solution as { type?: string }).type ?? "";
    const layer = L.geoJSON(solution as never, {
      style: t.includes("Polygon")
        ? { color: "#15803d", weight: 2, fillColor: "#16a34a", fillOpacity: 0.25 }
        : { color: "#15803d", weight: 5, opacity: 0.9, lineCap: "round" },
      pointToLayer: (_f, latlng) => L.circleMarker(latlng, { radius: 8, color: "#15803d", fillColor: "#16a34a", fillOpacity: 0.9 }),
    }).addTo(map);
    solRef.current = layer;
    const bounds = layer.getBounds();
    if (pin) bounds.extend([pin.lat, pin.lon]);
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [36, 36], maxZoom: 16, animate: false });
    pinRef.current?.bringToFront();
  }, [solution, pin]);

  return (
    <div className={cn("relative isolate overflow-hidden rounded-xl border border-border", className)}>
      <div ref={ref} className="h-full w-full" aria-label="Oldenburg-Karte: Tippe, wo der Ort liegt" />
    </div>
  );
}
