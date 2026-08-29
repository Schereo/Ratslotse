"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Maximize2, Minimize2, RefreshCw } from "lucide-react";
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
import { isProblemMappable, MELDE_HAEUFIGKEIT, PROBLEM_SCOPE } from "@/lib/probleme";
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

export function ProblemMap({
  problems,
  selectedId,
  onSelect,
  interactive = true,
  className,
}: {
  problems: PublicProblemSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  interactive?: boolean;
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
              && isProblemMappable(problem)) {
            const facility = problem.scope_kind === "facility";
            const size = facility ? 40 : 34;
            const marker = L.marker([problem.latitude!, problem.longitude!], {
              title: label,
              alt: label,
              interactive,
              keyboard: interactive,
              icon: L.divIcon({
                className: "problem-map-icon",
                html: `<span class="problem-map-pin problem-map-${problem.scope_kind} frequency-${frequency}${selected ? " is-selected" : ""}" style="--problem-pin-size:${size}px">${facility ? '<span class="problem-map-facility-symbol" aria-hidden="true">⌂</span>' : ""}</span>`,
                iconSize: [size, size],
                iconAnchor: [size / 2, size / 2],
              }),
            }).addTo(map);
            if (interactive) marker.on("click", () => selectRef.current(problem.id));
            const tooltip = document.createElement("span");
            tooltip.textContent = problem.title;
            marker.bindTooltip(tooltip, { direction: "top", offset: [0, -(size / 2)] });
            markersRef.current.set(problem.id, marker);
            bounds.extend([problem.latitude!, problem.longitude!]);
            hasBounds = true;
            continue;
          }

          if ((problem.scope_kind === "route" || problem.scope_kind === "area")
              && isProblemMappable(problem)) {
            const scope = problem.scope_kind;
            const hitShape = scope === "route" && interactive
              ? L.geoJSON(problem.geometry!, { style: routeHitStyle(frequency) }).addTo(map)
              : null;
            const shape = L.geoJSON(problem.geometry!, {
              interactive: interactive && scope === "area",
              style: shapeStyle(frequency, scope, selected),
            }).addTo(map);
            const paths: Path[] = [];
            shape.eachLayer((layer) => paths.push(layer as Path));
            const controls: Path[] = [];
            const controlsShape = interactive ? (hitShape ?? shape) : null;
            controlsShape?.eachLayer((layer) => {
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
  }, [problems, interactive, retryKey]);

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
