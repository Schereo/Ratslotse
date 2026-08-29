"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Globe2, Maximize2, Minimize2, RefreshCw } from "lucide-react";
import type {
  GeoJSON as LeafletGeoJSON,
  Map as LeafletMap,
  Marker,
  Path,
  PathOptions,
  TileLayer,
} from "leaflet";
import "leaflet/dist/leaflet.css";
import { basemapUrl } from "@/lib/basemap";
import { MELDE_HAEUFIGKEIT, PROBLEM_SCOPE } from "@/lib/probleme";
import type { ProblemFrequency, PublicProblemSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const TILES = basemapUrl("voyager");

type ShapeEntry = {
  paths: Path[];
  controls: Path[];
  frequency: ProblemFrequency;
  scope: "route" | "area";
};

function shapeStyle(
  frequency: ProblemFrequency,
  scope: "route" | "area",
  selected: boolean,
): PathOptions {
  if (scope === "route") {
    return {
      className: `problem-map-route frequency-${frequency}`,
      weight: selected ? 8 : 5,
      opacity: 0.92,
      lineCap: "round",
      lineJoin: "round",
    };
  }
  return {
    className: `problem-map-area frequency-${frequency}`,
    fillOpacity: selected ? 0.3 : 0.16,
    opacity: 0.9,
    weight: selected ? 4 : 2,
  };
}

function routeHitStyle(frequency: ProblemFrequency): PathOptions {
  return {
    className: `problem-map-route-hit frequency-${frequency}`,
    color: "#000",
    opacity: 0.001,
    weight: 28,
    lineCap: "round",
    lineJoin: "round",
  };
}

function hasCoordinates(problem: PublicProblemSummary): boolean {
  return Number.isFinite(problem.latitude) && Number.isFinite(problem.longitude);
}

function isPosition(value: unknown): value is [number, number] {
  return (
    Array.isArray(value)
    && value.length >= 2
    && value.every((coordinate) => typeof coordinate === "number" && Number.isFinite(coordinate))
    && typeof value[0] === "number"
    && value[0] >= -180
    && value[0] <= 180
    && typeof value[1] === "number"
    && Number.isFinite(value[1])
    && value[1] >= -90
    && value[1] <= 90
  );
}

function isRing(value: unknown): boolean {
  return (
    Array.isArray(value)
    && value.length >= 4
    && value.every(isPosition)
    && value[0][0] === value.at(-1)![0]
    && value[0][1] === value.at(-1)![1]
  );
}

function isPolygon(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0 && value.every(isRing);
}

function hasMatchingGeometry(problem: PublicProblemSummary): boolean {
  if (problem.scope_kind === "route") {
    return (
      problem.geometry?.type === "LineString"
      && Array.isArray(problem.geometry.coordinates)
      && problem.geometry.coordinates.length >= 2
      && problem.geometry.coordinates.every(isPosition)
    );
  }
  if (problem.scope_kind !== "area") return false;
  if (problem.geometry?.type === "Polygon") return isPolygon(problem.geometry.coordinates);
  return (
    problem.geometry?.type === "MultiPolygon"
    && Array.isArray(problem.geometry.coordinates)
    && problem.geometry.coordinates.length > 0
    && problem.geometry.coordinates.every(isPolygon)
  );
}

function isDrawable(problem: PublicProblemSummary): boolean {
  if (problem.scope_kind === "point" || problem.scope_kind === "facility") {
    return hasCoordinates(problem);
  }
  if (problem.scope_kind === "route" || problem.scope_kind === "area") {
    return hasMatchingGeometry(problem);
  }
  return problem.scope_kind === "citywide";
}

export function ProblemMap({
  problems,
  selectedId,
  onSelect,
  className,
}: {
  problems: PublicProblemSummary[];
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
  const [full, setFull] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  selectRef.current = onSelect;
  selectedRef.current = selectedId;
  const citywide = problems.filter((problem) => problem.scope_kind === "citywide");
  const withoutGeometry = problems.filter((problem) => !isDrawable(problem));

  useEffect(() => {
    let cancelled = false;
    setMapError(false);
    let observer: MutationObserver | null = null;
    void (async () => {
      try {
        const L = (await import("leaflet")).default;
        if (cancelled || !ref.current || !ref.current.isConnected || mapRef.current) return;
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
        observer = new MutationObserver(() => tiles.setUrl(TILES));
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

        const bounds = L.latLngBounds([]);
        let hasBounds = false;
        for (const problem of problems) {
          const selected = problem.id === selectedRef.current;
          const frequency = problem.frequency;
          const label = `${problem.title} · ${PROBLEM_SCOPE[problem.scope_kind]} · ${MELDE_HAEUFIGKEIT[frequency]}`;

          if ((problem.scope_kind === "point" || problem.scope_kind === "facility")
              && hasCoordinates(problem)) {
            const facility = problem.scope_kind === "facility";
            const size = facility ? 40 : 34;
            const marker = L.marker([problem.latitude!, problem.longitude!], {
              title: label,
              alt: label,
              keyboard: true,
              icon: L.divIcon({
                className: "problem-map-icon",
                html: `<span class="problem-map-pin problem-map-${problem.scope_kind} frequency-${frequency}${selected ? " is-selected" : ""}" style="--problem-pin-size:${size}px">${facility ? '<span class="problem-map-facility-symbol" aria-hidden="true">⌂</span>' : ""}</span>`,
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

          if ((problem.scope_kind === "route" || problem.scope_kind === "area")
              && hasMatchingGeometry(problem)) {
            const scope = problem.scope_kind;
            const hitShape = scope === "route"
              ? L.geoJSON(problem.geometry!, { style: routeHitStyle(frequency) }).addTo(map)
              : null;
            const shape = L.geoJSON(problem.geometry!, {
              interactive: scope === "area",
              style: shapeStyle(frequency, scope, selected),
            }).addTo(map);
            const paths: Path[] = [];
            shape.eachLayer((layer) => paths.push(layer as Path));
            const controls: Path[] = [];
            const controlsShape = hitShape ?? shape;
            controlsShape.eachLayer((layer) => {
              const path = layer as Path;
              controls.push(path);
              path.on("click", () => selectRef.current(problem.id));
              const tooltip = document.createElement("span");
              tooltip.textContent = problem.title;
              path.bindTooltip(tooltip, { sticky: true });
              const element = path.getElement();
              if (!element) return;
              const interactiveElement = element as HTMLElement;
              interactiveElement.setAttribute("role", "button");
              interactiveElement.setAttribute("tabindex", "0");
              interactiveElement.setAttribute("aria-label", label);
              interactiveElement.setAttribute("aria-pressed", String(selected));
              interactiveElement.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                selectRef.current(problem.id);
              });
            });
            shapesRef.current.set(problem.id, { paths, controls, frequency, scope });
            const shapeBounds = (shape as LeafletGeoJSON).getBounds();
            if (shapeBounds.isValid()) {
              bounds.extend(shapeBounds);
              hasBounds = true;
            }
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
      markersRef.current.clear();
      shapesRef.current.clear();
      try { map?.remove(); } catch { /* verworfener StrictMode-Container */ }
    };
  }, [problems, retryKey]);

  // Auswahl ändert nur die Darstellung, nicht den von der Nutzerin gewählten Ausschnitt.
  useEffect(() => {
    for (const [id, marker] of markersRef.current) {
      marker.getElement()?.querySelector(".problem-map-pin")?.classList.toggle("is-selected", id === selectedId);
    }
    for (const [id, shape] of shapesRef.current) {
      const selected = id === selectedId;
      for (const path of shape.paths) {
        path.setStyle(shapeStyle(shape.frequency, shape.scope, selected));
      }
      for (const control of shape.controls) {
        control.getElement()?.setAttribute("aria-pressed", String(selected));
      }
    }
  }, [selectedId]);

  useEffect(() => {
    mapRef.current?.invalidateSize();
    if (!full) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setFull(false);
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [full]);

  return (
    <div className={cn(
      full
        ? "fixed inset-0 z-[var(--ebene-flaeche)] bg-background p-[env(safe-area-inset-top)]"
        : cn("relative isolate overflow-hidden rounded-xl border border-border bg-card", className),
    )}>
      <div ref={ref} className="h-full w-full" aria-label="Problemkarte von Oldenburg" />
      {mapError && (
        <div className="absolute inset-3 z-[var(--ebene-kartenbedienung)] flex items-center justify-center rounded-lg bg-background/95 p-6 text-center backdrop-blur" role="alert">
          <div>
            <AlertTriangle className="mx-auto h-6 w-6 text-muted-foreground" aria-hidden />
            <p className="mt-2 text-sm font-medium text-foreground">Karte konnte nicht geladen werden</p>
            <button
              type="button"
              onClick={() => setRetryKey((value) => value + 1)}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
            >
              <RefreshCw className="h-4 w-4" aria-hidden /> Nochmal versuchen
            </button>
          </div>
        </div>
      )}
      {citywide.length > 0 && !mapError && (
        <div className="scrollbar-none absolute left-3 top-3 z-[var(--ebene-kartenbedienung)] flex max-w-[calc(100%-4.5rem)] gap-1.5 overflow-x-auto overscroll-x-contain pb-1">
          {citywide.map((problem) => (
            <button
              key={problem.id}
              type="button"
              onClick={() => onSelect(problem.id)}
              aria-label={`${problem.title} · Stadtweit · ${MELDE_HAEUFIGKEIT[problem.frequency]}`}
              aria-pressed={problem.id === selectedId}
              className={cn(
                "problem-map-citywide flex min-h-10 shrink-0 items-center gap-2 rounded-full border bg-background/95 px-3 py-2 text-left text-xs font-medium text-foreground shadow-sm backdrop-blur hover:bg-muted",
                problem.id === selectedId ? "border-primary ring-2 ring-primary/20" : "border-border",
              )}
            >
              <Globe2 className={`problem-map-citywide-icon frequency-${problem.frequency} h-4 w-4 shrink-0`} aria-hidden />
              <span>Stadtweit</span>
            </button>
          ))}
        </div>
      )}
      {withoutGeometry.length > 0 && !mapError && (
        <div className="absolute bottom-7 left-3 z-[var(--ebene-kartenbedienung)] max-h-[min(45%,18rem)] max-w-[min(20rem,calc(100%-1.5rem))] overflow-y-auto overscroll-contain rounded-lg border border-border bg-background/95 p-2 shadow-sm backdrop-blur">
          <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Ohne Geometrie</p>
          <div className="space-y-0.5">
            {withoutGeometry.map((problem) => (
              <button
                key={problem.id}
                type="button"
                onClick={() => onSelect(problem.id)}
                className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs text-foreground hover:bg-muted"
              >
                <span className={`problem-frequency-dot frequency-${problem.frequency}`} aria-hidden />
                <span className="truncate">{problem.title}</span>
                <span className="sr-only"> · {MELDE_HAEUFIGKEIT[problem.frequency]}</span>
                <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">{PROBLEM_SCOPE[problem.scope_kind]}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={() => setFull((value) => !value)}
        className="absolute right-3 top-3 z-[var(--ebene-kartenbedienung)] flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/95 text-foreground shadow-sm backdrop-blur hover:bg-muted"
        aria-label={full ? "Vollbild verlassen" : "Karte im Vollbild anzeigen"}
        title={full ? "Vollbild verlassen (Esc)" : "Vollbild"}
      >
        {full ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
      </button>
    </div>
  );
}
