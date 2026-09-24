"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap, GeoJSON as LGeoJSON, Path } from "leaflet";
import "leaflet/dist/leaflet.css";
import { loadOrtsbereiche } from "@/lib/districts";
import { cn } from "@/lib/utils";
import { basemapUrl } from "@/lib/basemap";

// CARTO Voyager — dieselbe Basemap wie die Themen-Karte (dunkel per CSS-Filter,
// globals.css .dark .leaflet-tile). Keine Marker-Bilder → CSP img-src bleibt eng.
const VOYAGER = basemapUrl("voyager");

type Style = { color: string; weight: number; fillColor: string; fillOpacity: number };
const BASE: Style = { color: "#64748b", weight: 1, fillColor: "#64748b", fillOpacity: 0.10 };
const HOVER: Style = { color: "#0764a6", weight: 1.5, fillColor: "#0764a6", fillOpacity: 0.25 };
const SELECTED: Style = { color: "#0764a6", weight: 2.5, fillColor: "#0764a6", fillOpacity: 0.35 };
const CORRECT: Style = { color: "#16a34a", weight: 2.5, fillColor: "#16a34a", fillOpacity: 0.5 };
const WRONG: Style = { color: "#dc2626", weight: 2.5, fillColor: "#dc2626", fillOpacity: 0.45 };
const DIM: Style = { color: "#94a3b8", weight: 0.5, fillColor: "#94a3b8", fillOpacity: 0.04 };

// Fortschrittskarte: eine Farbe (Hafenblau), die Deckkraft trägt die Stufe —
// unentdeckt kaum, gemeistert kräftig. Stufen und Wörter kommen vom Server.
const LEVEL: Style[] = [
  { color: "#94a3b8", weight: 0.75, fillColor: "#94a3b8", fillOpacity: 0.06 },
  { color: "#0764a6", weight: 1, fillColor: "#0764a6", fillOpacity: 0.16 },
  { color: "#0764a6", weight: 1.25, fillColor: "#0764a6", fillOpacity: 0.34 },
  { color: "#0764a6", weight: 1.5, fillColor: "#0764a6", fillOpacity: 0.62 },
];

export type DistrictLevel = { level: number; label: string; answered: number; correct: number };

/** Klickbare Ortsbereich-Karte für das Karten-Quiz. Init einmalig; Umfärben bei
 *  Auswahl/Auflösung läuft über einen zweiten Effekt, ohne die Karte neu zu
 *  bauen. Bewusst OHNE Beschriftung — sonst wäre die Antwort verraten.
 *
 *  Mit `progress` wird sie zur Fortschrittskarte: jede Fläche nach ihrer Stufe
 *  getönt, Name und Stand im Tooltip, ein Klick startet eine Runde dort. */
export function QuizMap({ picked, solution, disabled, onPick, progress, className, label }: {
  picked: string | null;
  solution: string | null;   // richtige Antwort (nach dem Klick eingefärbt)
  disabled: boolean;         // nach der Antwort keine Auswahl mehr
  onPick: (name: string) => void;
  progress?: Record<string, DistrictLevel>;
  className?: string;
  label?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LGeoJSON | null>(null);
  // aktuelle Callbacks/State in Refs, damit der Init-Effekt stabil bleibt.
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;
  const stateRef = useRef({ picked, solution, disabled, progress });
  stateRef.current = { picked, solution, disabled, progress };

  function styleFor(name: string): Style {
    const { picked: p, solution: s, progress: pr } = stateRef.current;
    if (pr) return LEVEL[pr[name]?.level ?? 0] ?? LEVEL[0];
    if (s) {
      if (name === s) return CORRECT;
      if (name === p) return WRONG;
      return DIM;
    }
    return name === p ? SELECTED : BASE;
  }

  function restyle() {
    layerRef.current?.eachLayer((l) => {
      const name = (l as unknown as { feature?: { properties?: { name?: string } } }).feature?.properties?.name;
      if (name) (l as Path).setStyle(styleFor(name));
    });
  }

  // Init einmalig.
  useEffect(() => {
    let cancelled = false;
    let observer: MutationObserver | null = null;
    let resize: ResizeObserver | null = null;
    void (async () => {
      try {
        const L = (await import("leaflet")).default;
        if (cancelled || !ref.current || !ref.current.isConnected || mapRef.current) return;
        const el = ref.current;
        el.innerHTML = "";
        delete (el as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
        // zoomSnap 0.5: fitBounds darf auf halbe Stufen einrasten — das
        // Stadtgebiet füllt die (jetzt viewport-skalierte) Fläche besser aus.
        const map = L.map(el, { scrollWheelZoom: false, attributionControl: true, zoomSnap: 0.5 });
        mapRef.current = map;
        map.setView([53.1435, 8.2146], 11);

        const isDark = () => document.documentElement.classList.contains("dark");
        const tiles = L.tileLayer(VOYAGER, {
          maxZoom: 18, detectRetina: true, subdomains: "abcd",
          attribution: "&copy; OpenStreetMap, &copy; CARTO",
        }).addTo(map);
        observer = new MutationObserver(() => tiles.setUrl(VOYAGER));
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
        void isDark; // Dark-Mode kommt per CSS-Filter, kein URL-Wechsel nötig

        const features = await loadOrtsbereiche();
        if (cancelled || !mapRef.current) return;
        const gj = L.geoJSON(
          { type: "FeatureCollection", features } as never,
          {
            style: () => BASE as never,
            onEachFeature: (feature, layer) => {
              const name = feature?.properties?.name as string | undefined;
              if (!name) return;
              if (stateRef.current.progress) {
                // Tooltip liest den Stand beim Öffnen, nicht beim Bauen —
                // die Karte wird nur einmal gebaut.
                layer.bindTooltip(() => {
                  const d = stateRef.current.progress?.[name];
                  const stand = d && d.answered ? ` · ${d.correct} von ${d.answered} richtig` : "";
                  return `<strong>${name}</strong><br>${d?.label ?? "unentdeckt"}${stand}`;
                }, { sticky: true, direction: "top", className: "text-xs" });
              }
              layer.on({
                click: () => { if (!stateRef.current.disabled) onPickRef.current(name); },
                mouseover: () => {
                  const { disabled: d, picked: p, progress: pr } = stateRef.current;
                  if (pr) (layer as Path).setStyle({ ...styleFor(name), weight: 2.5, color: "#0764a6" });
                  else if (!d && name !== p) (layer as Path).setStyle(HOVER);
                },
                mouseout: () => (layer as Path).setStyle(styleFor(name)),
              });
            },
          },
        ).addTo(map);
        layerRef.current = gj;
        if (gj.getBounds().isValid()) map.fitBounds(gj.getBounds(), { padding: [12, 12], animate: false });
        restyle();
        // Die Kartenhöhe skaliert mit dem Viewport (dvh) — bei Größenänderung
        // (Fenster, mobile Browserleiste) Leaflet nachziehen, sonst bleiben
        // graue Ränder bzw. ein falscher Ausschnitt.
        resize = new ResizeObserver(() => {
          const m = mapRef.current;
          const g = layerRef.current;
          if (!m) return;
          m.invalidateSize();
          // Ohne Animation: Wird die Karte während eines Zoom-Übergangs
          // abgebaut (Rundenstart von der Fortschrittskarte), greift Leaflet
          // danach ins Leere („_leaflet_pos of undefined“).
          if (g?.getBounds().isValid()) m.fitBounds(g.getBounds(), { padding: [12, 12], animate: false });
        });
        resize.observe(el);
      } catch (err) {
        console.error("[QuizMap] Initialisierung fehlgeschlagen:", err);
      }
    })();
    return () => {
      cancelled = true;
      observer?.disconnect();
      resize?.disconnect();
      const m = mapRef.current;
      mapRef.current = null;
      layerRef.current = null;
      try { m?.stop(); m?.remove(); } catch { /* Karte ohnehin weg */ }
    };
  }, []);

  // Umfärben bei Auswahl/Auflösung.
  useEffect(() => { restyle(); }, [picked, solution, disabled, progress]);

  return (
    <div className={cn("relative isolate overflow-hidden rounded-xl border border-border", className)}>
      <div ref={ref} className="h-full w-full" aria-label={label ?? "Oldenburg-Karte zum Verorten der Ortsbereiche"} />
    </div>
  );
}
