"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap, GeoJSON as LGeoJSON, Path } from "leaflet";
import "leaflet/dist/leaflet.css";
import { loadStadtteile } from "@/lib/stadtteile";
import { cn } from "@/lib/utils";

// CARTO Voyager — dieselbe Basemap wie die Themen-Karte (dunkel per CSS-Filter,
// globals.css .dark .leaflet-tile). Keine Marker-Bilder → CSP img-src bleibt eng.
const VOYAGER = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";

type Style = { color: string; weight: number; fillColor: string; fillOpacity: number };
const BASE: Style = { color: "#64748b", weight: 1, fillColor: "#64748b", fillOpacity: 0.10 };
const HOVER: Style = { color: "#0764a6", weight: 1.5, fillColor: "#0764a6", fillOpacity: 0.25 };
const SELECTED: Style = { color: "#0764a6", weight: 2.5, fillColor: "#0764a6", fillOpacity: 0.35 };
const CORRECT: Style = { color: "#16a34a", weight: 2.5, fillColor: "#16a34a", fillOpacity: 0.5 };
const WRONG: Style = { color: "#dc2626", weight: 2.5, fillColor: "#dc2626", fillOpacity: 0.45 };
const DIM: Style = { color: "#94a3b8", weight: 0.5, fillColor: "#94a3b8", fillOpacity: 0.04 };

/** Klickbare Stadtteil-Karte für das Karten-Quiz. Init einmalig; Umfärben bei
 *  Auswahl/Auflösung läuft über einen zweiten Effekt, ohne die Karte neu zu
 *  bauen. Bewusst OHNE Beschriftung — sonst wäre die Antwort verraten. */
export function QuizMap({ picked, solution, disabled, onPick, className }: {
  picked: string | null;
  solution: string | null;   // richtige Antwort (nach dem Klick eingefärbt)
  disabled: boolean;         // nach der Antwort keine Auswahl mehr
  onPick: (name: string) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LGeoJSON | null>(null);
  // aktuelle Callbacks/State in Refs, damit der Init-Effekt stabil bleibt.
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;
  const stateRef = useRef({ picked, solution, disabled });
  stateRef.current = { picked, solution, disabled };

  function styleFor(name: string): Style {
    const { picked: p, solution: s } = stateRef.current;
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

        const features = await loadStadtteile();
        if (cancelled || !mapRef.current) return;
        const gj = L.geoJSON(
          { type: "FeatureCollection", features } as never,
          {
            style: () => BASE as never,
            onEachFeature: (feature, layer) => {
              const name = feature?.properties?.name as string | undefined;
              if (!name) return;
              layer.on({
                click: () => { if (!stateRef.current.disabled) onPickRef.current(name); },
                mouseover: () => {
                  const { disabled: d, picked: p } = stateRef.current;
                  if (!d && name !== p) (layer as Path).setStyle(HOVER);
                },
                mouseout: () => (layer as Path).setStyle(styleFor(name)),
              });
            },
          },
        ).addTo(map);
        layerRef.current = gj;
        if (gj.getBounds().isValid()) map.fitBounds(gj.getBounds(), { padding: [12, 12] });
        restyle();
        // Die Kartenhöhe skaliert mit dem Viewport (dvh) — bei Größenänderung
        // (Fenster, mobile Browserleiste) Leaflet nachziehen, sonst bleiben
        // graue Ränder bzw. ein falscher Ausschnitt.
        resize = new ResizeObserver(() => {
          const m = mapRef.current;
          const g = layerRef.current;
          if (!m) return;
          m.invalidateSize();
          if (g?.getBounds().isValid()) m.fitBounds(g.getBounds(), { padding: [12, 12] });
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
      try { m?.remove(); } catch { /* Karte ohnehin weg */ }
    };
  }, []);

  // Umfärben bei Auswahl/Auflösung.
  useEffect(() => { restyle(); }, [picked, solution, disabled]);

  return (
    <div className={cn("relative isolate overflow-hidden rounded-xl border border-border", className)}>
      <div ref={ref} className="h-full w-full" aria-label="Oldenburg-Karte zum Verorten der Stadtteile" />
    </div>
  );
}
