"use client";

import { useEffect, useRef, useState } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import type { Map as LeafletMap, Marker, TileLayer } from "leaflet";
import "leaflet/dist/leaflet.css";
import { basemapUrl } from "@/lib/basemap";
import { meldeHaeufigkeit, PROBLEM_SCOPE } from "@/lib/probleme";
import type { PublicProblem } from "@/lib/types";
import { cn } from "@/lib/utils";

const TILES = basemapUrl("voyager");

export function ProblemMap({
  problems,
  selectedId,
  onSelect,
  className,
}: {
  problems: PublicProblem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef(new Map<number, Marker>());
  const selectRef = useRef(onSelect);
  const selectedRef = useRef(selectedId);
  const [full, setFull] = useState(false);
  selectRef.current = onSelect;
  selectedRef.current = selectedId;
  const withoutPoint = problems.filter((problem) => problem.latitude == null || problem.longitude == null);

  useEffect(() => {
    let cancelled = false;
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

        const positions: [number, number][] = [];
        for (const problem of problems) {
          if (problem.latitude == null || problem.longitude == null) continue;
          const selected = problem.id === selectedRef.current;
          const frequency = meldeHaeufigkeit(problem.unique_reporters);
          const size = 36;
          const label = `${problem.title} · ${frequency.label}`;
          const marker = L.marker([problem.latitude, problem.longitude], {
            title: label,
            alt: label,
            keyboard: true,
            icon: L.divIcon({
              className: "problem-map-icon",
              html: `<span class="problem-map-pin frequency-${frequency.key}${selected ? " is-selected" : ""}" style="--problem-pin-size:${size}px"></span>`,
              iconSize: [size, size],
              iconAnchor: [size / 2, size / 2],
            }),
          }).addTo(map);
          marker.on("click", () => selectRef.current(problem.id));
          marker.bindTooltip(problem.title, { direction: "top", offset: [0, -(size / 2)] });
          markersRef.current.set(problem.id, marker);
          positions.push([problem.latitude, problem.longitude]);
        }

        if (positions.length > 1) map.fitBounds(positions, { padding: [36, 36], maxZoom: 14 });
        else if (positions.length === 1) map.setView(positions[0], 14);
      } catch (error) {
        console.error("[ProblemMap] Initialisierung fehlgeschlagen:", error);
      }
    })();
    return () => {
      cancelled = true;
      observer?.disconnect();
      const map = mapRef.current;
      mapRef.current = null;
      markersRef.current.clear();
      try { map?.remove(); } catch { /* verworfener StrictMode-Container */ }
    };
  }, [problems]);

  // Auswahl ändert nur den Marker, nicht die Karte. Ein vollständiger Leaflet-
  // Neubau würde den von der Nutzerin gewählten Ausschnitt bei jedem Klick
  // wieder auf ganz Oldenburg zurücksetzen.
  useEffect(() => {
    for (const [id, marker] of markersRef.current) {
      marker.getElement()?.querySelector(".problem-map-pin")?.classList.toggle("is-selected", id === selectedId);
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
      {withoutPoint.length > 0 && (
        <div className="absolute bottom-7 left-3 z-[1000] max-w-[min(20rem,calc(100%-1.5rem))] rounded-lg border border-border bg-background/95 p-2 shadow-sm backdrop-blur">
          <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Ohne einzelnen Kartenpunkt</p>
          <div className="space-y-0.5">
            {withoutPoint.map((problem) => {
              const frequency = meldeHaeufigkeit(problem.unique_reporters);
              return (
                <button
                  key={problem.id}
                  type="button"
                  onClick={() => onSelect(problem.id)}
                  className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs text-foreground hover:bg-muted"
                >
                  <span className={`problem-frequency-dot frequency-${frequency.key}`} aria-hidden />
                  <span className="truncate">{problem.title}</span>
                  <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">{PROBLEM_SCOPE[problem.scope_kind]}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={() => setFull((value) => !value)}
        className="absolute right-3 top-3 z-[1000] flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/95 text-foreground shadow-sm backdrop-blur hover:bg-muted"
        aria-label={full ? "Vollbild verlassen" : "Karte im Vollbild anzeigen"}
        title={full ? "Vollbild verlassen (Esc)" : "Vollbild"}
      >
        {full ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
      </button>
    </div>
  );
}
