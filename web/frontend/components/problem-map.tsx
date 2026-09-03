"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import type { GeoJSON as LeafletGeoJSON, Map as LeafletMap, Marker, Path, PathOptions, TileLayer } from "leaflet";
import "leaflet/dist/leaflet.css";
import { basemapUrl } from "@/lib/basemap";
import { isProblemMappable, MELDE_HAEUFIGKEIT, PROBLEM_SCOPE, type ProblemFrequency, type PublicProblem } from "@/lib/probleme";
import { cn } from "@/lib/utils";

const TILES = basemapUrl("voyager");

type ShapeEntry = { paths: Path[]; controls: Path[]; frequency: ProblemFrequency; scope: "route" | "area" };

function shapeStyle(frequency: ProblemFrequency, scope: "route" | "area", selected: boolean): PathOptions {
  if (scope === "route") {
    return { className: `problem-map-route frequency-${frequency}`, weight: selected ? 8 : 5, opacity: 0.92, lineCap: "round", lineJoin: "round" };
  }
  return { className: `problem-map-area frequency-${frequency}`, fillOpacity: selected ? 0.3 : 0.16, opacity: 0.9, weight: selected ? 4 : 2 };
}

export function ProblemMap({ problems, selectedId, onSelect, className }: {
  problems: PublicProblem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef(new Map<number, Marker>());
  const shapesRef = useRef(new Map<number, ShapeEntry>());
  const selectRef = useRef(onSelect);
  const selectedRef = useRef(selectedId);
  const [mapError, setMapError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  selectRef.current = onSelect;
  selectedRef.current = selectedId;

  useEffect(() => {
    let cancelled = false;
    let observer: MutationObserver | null = null;
    const markers = markersRef.current;
    const shapes = shapesRef.current;
    setMapError(false);
    void (async () => {
      try {
        const L = (await import("leaflet")).default;
        if (cancelled || !ref.current || mapRef.current) return;
        ref.current.innerHTML = "";
        delete (ref.current as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
        const map = L.map(ref.current, { scrollWheelZoom: false, zoomSnap: 0.25 });
        mapRef.current = map;
        map.setView([53.1435, 8.2146], 12);
        const tiles: TileLayer = L.tileLayer(TILES, {
          maxZoom: 19,
          detectRetina: true,
          subdomains: "abcd",
          attribution: "&copy; OpenStreetMap, &copy; CARTO",
        }).addTo(map);
        tiles.once("tileerror", () => {
          if (!cancelled) setMapError(true);
        });
        observer = new MutationObserver(() => tiles.setUrl(TILES));
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

        const bounds = L.latLngBounds([]);
        let hasBounds = false;
        for (const problem of problems) {
          if (!isProblemMappable(problem)) continue;
          const selected = problem.id === selectedRef.current;
          const label = `${problem.title} · ${PROBLEM_SCOPE[problem.scope_kind]} · ${MELDE_HAEUFIGKEIT[problem.frequency]}`;
          if (problem.scope_kind === "point" || problem.scope_kind === "facility") {
            const size = problem.scope_kind === "facility" ? 40 : 34;
            const marker = L.marker([problem.latitude!, problem.longitude!], {
              title: label,
              alt: label,
              keyboard: true,
              icon: L.divIcon({
                className: "problem-map-icon",
                html: `<span class="problem-map-pin problem-map-${problem.scope_kind} frequency-${problem.frequency}${selected ? " is-selected" : ""}" style="--problem-pin-size:${size}px"></span>`,
                iconSize: [size, size],
                iconAnchor: [size / 2, size / 2],
              }),
            }).addTo(map);
            marker.on("click", () => selectRef.current(problem.id));
            const tooltip = document.createElement("span");
            tooltip.textContent = problem.title;
            marker.bindTooltip(tooltip, { direction: "top", offset: [0, -(size / 2)] });
            markersRef.current.set(problem.id, marker);
            bounds.extend([problem.latitude!, problem.longitude!]);
            hasBounds = true;
            continue;
          }

          const scope = problem.scope_kind;
          if (scope !== "route" && scope !== "area") continue;
          const hitShape = scope === "route"
            ? L.geoJSON(problem.geometry!, { style: { color: "#000", opacity: 0.001, weight: 28 } }).addTo(map)
            : null;
          const shape = L.geoJSON(problem.geometry!, { interactive: scope === "area", style: shapeStyle(problem.frequency, scope, selected) }).addTo(map);
          const paths: Path[] = [];
          shape.eachLayer((layer) => paths.push(layer as Path));
          const controls: Path[] = [];
          (hitShape ?? shape).eachLayer((layer) => {
            const path = layer as Path;
            controls.push(path);
            path.on("click", () => selectRef.current(problem.id));
            const tooltip = document.createElement("span");
            tooltip.textContent = problem.title;
            path.bindTooltip(tooltip, { sticky: true });
            const element = path.getElement();
            if (!element) return;
            element.classList.add("problem-map-control", `problem-map-${scope}-control`);
            element.setAttribute("role", "button");
            element.setAttribute("tabindex", "0");
            element.setAttribute("aria-label", label);
            element.setAttribute("aria-pressed", String(selected));
            element.addEventListener("keydown", (event) => {
              const key = (event as KeyboardEvent).key;
              if (key !== "Enter" && key !== " ") return;
              event.preventDefault();
              selectRef.current(problem.id);
            });
          });
          shapesRef.current.set(problem.id, { paths, controls, frequency: problem.frequency, scope });
          const shapeBounds = (shape as LeafletGeoJSON).getBounds();
          if (shapeBounds.isValid()) {
            bounds.extend(shapeBounds);
            hasBounds = true;
          }
        }
        if (hasBounds) map.fitBounds(bounds, { padding: [36, 36], maxZoom: 14 });
      } catch (error) {
        console.error("[ProblemMap] Initialisierung fehlgeschlagen:", error);
        if (!cancelled) setMapError(true);
      }
    })();
    return () => {
      cancelled = true;
      observer?.disconnect();
      const map = mapRef.current;
      mapRef.current = null;
      markers.clear();
      shapes.clear();
      try { map?.remove(); } catch { /* StrictMode-Container ist bereits verworfen. */ }
    };
  }, [problems, retryKey]);

  useEffect(() => {
    for (const [id, marker] of markersRef.current) {
      marker.getElement()?.querySelector(".problem-map-pin")?.classList.toggle("is-selected", id === selectedId);
    }
    for (const [id, shape] of shapesRef.current) {
      const selected = id === selectedId;
      shape.paths.forEach((path) => path.setStyle(shapeStyle(shape.frequency, shape.scope, selected)));
      shape.controls.forEach((control) => control.getElement()?.setAttribute("aria-pressed", String(selected)));
    }
  }, [selectedId]);

  return (
    <div className={cn("relative overflow-hidden rounded-xl border border-border bg-card", className)}>
      <div ref={ref} className="h-full w-full" aria-label="Problemkarte von Oldenburg" />
      {mapError && (
        <div className="absolute inset-3 z-10 flex items-center justify-center rounded-lg bg-background/95 p-6 text-center backdrop-blur" role="alert">
          <div>
            <AlertTriangle className="mx-auto h-6 w-6 text-muted-foreground" aria-hidden />
            <p className="mt-2 text-sm font-medium text-foreground">Karte konnte nicht geladen werden</p>
            <button type="button" onClick={() => setRetryKey((value) => value + 1)} className="mt-3 inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted">
              <RefreshCw className="h-4 w-4" aria-hidden /> Nochmal versuchen
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
