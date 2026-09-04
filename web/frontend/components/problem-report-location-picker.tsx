"use client";

import { useEffect, useRef, useState } from "react";
import type { CircleMarker, Map as LeafletMap, TileLayer } from "leaflet";
import { Crosshair } from "lucide-react";
import "leaflet/dist/leaflet.css";
import { basemapUrl } from "@/lib/basemap";
import { Button } from "@/components/ui";

const OLDENBURG_BOUNDS: [[number, number], [number, number]] = [
  [53.05, 8.08],
  [53.24, 8.33],
];
const OLDENBURG_CENTER: [number, number] = [53.1435, 8.2146];
type Position = { latitude: number; longitude: number } | null;

export function ProblemReportLocationPicker({
  value,
  onChange,
}: {
  value: Position;
  onChange: (position: NonNullable<Position>) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markerRef = useRef<CircleMarker | null>(null);
  const drawRef = useRef<(position: Position) => void>(() => undefined);
  const onChangeRef = useRef(onChange);
  const valueRef = useRef(value);
  const [mapError, setMapError] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [attempt, setAttempt] = useState(0);
  onChangeRef.current = onChange;
  valueRef.current = value;

  useEffect(() => {
    let cancelled = false;
    let observer: MutationObserver | null = null;
    void (async () => {
      try {
        const L = (await import("leaflet")).default;
        if (cancelled || !containerRef.current) return;
        const map = L.map(containerRef.current, {
          scrollWheelZoom: false,
          keyboard: true,
          maxBounds: OLDENBURG_BOUNDS,
          maxBoundsViscosity: 1,
          minZoom: 11,
        }).setView(OLDENBURG_CENTER, 13);
        mapRef.current = map;
        setMapReady(true);
        const tiles: TileLayer = L.tileLayer(basemapUrl("voyager"), {
          maxZoom: 19,
          detectRetina: true,
          subdomains: "abcd",
          attribution: "&copy; OpenStreetMap, &copy; CARTO",
        }).addTo(map);
        observer = new MutationObserver(() => tiles.setUrl(basemapUrl("voyager")));
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

        drawRef.current = (position) => {
          markerRef.current?.remove();
          markerRef.current = null;
          if (!position) return;
          markerRef.current = L.circleMarker([position.latitude, position.longitude], {
            radius: 9,
            color: "#ffffff",
            weight: 3,
            fillColor: "hsl(var(--primary))",
            fillOpacity: 1,
          }).addTo(map);
        };
        drawRef.current(valueRef.current);
        map.on("click", ({ latlng }) => {
          const position = { latitude: latlng.lat, longitude: latlng.lng };
          drawRef.current(position);
          onChangeRef.current(position);
        });
      } catch (error) {
        console.error("[ProblemReportLocationPicker] Initialisierung fehlgeschlagen:", error);
        if (!cancelled) setMapError(true);
      }
    })();
    return () => {
      cancelled = true;
      observer?.disconnect();
      drawRef.current = () => undefined;
      markerRef.current = null;
      const map = mapRef.current;
      mapRef.current = null;
      try { map?.remove(); } catch { /* discarded StrictMode container */ }
    };
  }, [attempt]);

  useEffect(() => {
    drawRef.current(value);
  }, [value]);

  const chooseCenter = () => {
    const center = mapRef.current?.getCenter();
    if (!center) return;
    const position = { latitude: center.lat, longitude: center.lng };
    drawRef.current(position);
    onChange(position);
  };

  if (mapError) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground" role="alert">
        <p>Die Ortskarte konnte nicht geladen werden.</p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={() => { setMapError(false); setMapReady(false); setAttempt((value) => value + 1); }}
        >
          Karte erneut laden
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        ref={containerRef}
        className="h-72 overflow-hidden rounded-xl border border-border bg-muted"
        aria-label="Private Lage der Meldung auswählen"
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Karte antippen oder verschieben und die Mitte übernehmen.
        </p>
        <Button type="button" variant="secondary" size="sm" onClick={chooseCenter} disabled={!mapReady}>
          <Crosshair aria-hidden /> Kartenmitte markieren
        </Button>
      </div>
      {value && <p className="text-xs font-medium text-primary" role="status">Lage markiert</p>}
    </div>
  );
}
