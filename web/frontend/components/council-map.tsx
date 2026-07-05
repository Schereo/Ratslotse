"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Maximize2, Minimize2 } from "lucide-react";
import type { Map as LeafletMap, TileLayer } from "leaflet";
import "leaflet/dist/leaflet.css";
import { EntityMapPoint } from "@/lib/types";
import type { StadtteilFeature } from "@/lib/stadtteile";
import { themaHref } from "@/lib/routes";
import { cn } from "@/lib/utils";

// CARTO-Basemaps, live mit dem Site-Theme getauscht. Hell: Voyager statt
// light_all — light_all ist fast konturlos; Voyager zeigt Straßennetz,
// Grünflächen und Wasser deutlich, bleibt aber ruhig genug fürs Design.
// Dunkel: dark_all + dezenter CSS-Boost (globals.css, .leaflet-tile).
const TILES = {
  light: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};

// Marker colour by entity kind (the legend in the Themen tab mirrors this).
export const KIND_COLOR: Record<string, string> = {
  ort: "#0764a6",
  organisation: "#7c3aed",
  projekt: "#059669",
};

// Ab diesem Zoom stehen die Themen-Namen direkt an den Punkten — auf dem
// Touchscreen sieht man so, worum es geht, ohne jeden Punkt anzutippen.
// Sind ohnehin nur wenige Punkte auf der Karte (Stadtteil-/Art-Filter aktiv),
// kommen die Labels unabhängig vom Zoom.
const LABEL_ZOOM = 14;
const LABEL_MAX_POINTS = 12;

// Kartenausschnitt überlebt die Navigation (Thema öffnen → zurück) — pro Tab,
// deshalb sessionStorage statt localStorage.
const VIEW_KEY = "ratslotse:themen-karte-view";

type SavedView = { lat: number; lng: number; zoom: number };

function loadView(): SavedView | null {
  try {
    const raw = sessionStorage.getItem(VIEW_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    return Number.isFinite(v.lat) && Number.isFinite(v.lng) && Number.isFinite(v.zoom) ? v : null;
  } catch {
    return null;
  }
}

// City-wide map: one clickable circle marker per geocoded entity, sized by how many
// decisions reference it. Plain Leaflet + CARTO tiles, client-only (load via
// next/dynamic ssr:false), theme-reactive like EntityMap. CircleMarkers only — no
// marker-icon images to fetch (CSP img-src stays limited to the tiles).
export function CouncilMap({ points, outlines, className }: {
  points: EntityMapPoint[];
  /** Grenzen der ausgewählten Stadtteile — dezent eingezeichnet zur Orientierung. */
  outlines?: StadtteilFeature[];
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const [full, setFull] = useState(false);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    let observer: MutationObserver | null = null;
    void (async () => {
      try {
      const L = (await import("leaflet")).default;
      // isConnected: im StrictMode-Doppelmount läuft dieser async-Teil auch für
      // bereits verworfene Bäume — dort keine Karte auf den toten Div bauen.
      if (cancelled || !ref.current || !ref.current.isConnected || mapRef.current) return;
      // Container säubern: schlug das remove() der Vorgänger-Karte fehl
      // (StrictMode-Ghost), bleibt Leaflets _leaflet_id am Div hängen und
      // L.map() verweigert die Wiederverwendung („container is being reused").
      ref.current.innerHTML = "";
      delete (ref.current as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
      const map = L.map(ref.current, { scrollWheelZoom: false });
      mapRef.current = map;
      // Initial-View VOR den Vektor-Layern: Polygone (der Stadtteil-Umriss)
      // crashen sonst beim ersten fitBounds in Leaflets _clipPoints, weil der
      // Renderer einer viewlosen Karte noch keine Bounds hat. Die eigentliche
      // Ausschnitts-Logik unten ist danach ein normaler View-Wechsel.
      map.setView([53.1435, 8.2146], 12);

      const isDark = () => document.documentElement.classList.contains("dark");
      const tiles: TileLayer = L.tileLayer(isDark() ? TILES.dark : TILES.light, {
        maxZoom: 19,
        detectRetina: true,
        subdomains: "abcd",
        attribution: "&copy; OpenStreetMap, &copy; CARTO",
      }).addTo(map);
      observer = new MutationObserver(() => tiles.setUrl(isDark() ? TILES.dark : TILES.light));
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

      // Ausgewählte Stadtteil-Grenzen unter den Punkten (nicht klickbar).
      let outlineLayer: ReturnType<typeof L.geoJSON> | null = null;
      if (outlines?.length) {
        outlineLayer = L.geoJSON(
          { type: "FeatureCollection", features: outlines } as never,
          { style: { color: "#0764a6", weight: 1.5, opacity: 0.6, fillColor: "#0764a6", fillOpacity: 0.06 }, interactive: false },
        ).addTo(map);
      }

      const latlngs: [number, number][] = [];
      const markers: { marker: ReturnType<typeof L.circleMarker>; label: string; hover: string }[] = [];
      for (const p of points) {
        const color = KIND_COLOR[p.kind] ?? KIND_COLOR.projekt;
        const marker = L.circleMarker([p.lat, p.lon], {
          radius: Math.min(12, 4 + Math.sqrt(p.n)),
          color,
          weight: 1.5,
          fillColor: color,
          fillOpacity: 0.55,
        }).addTo(map);
        const hover = `${p.name} · ${p.n} ${p.n === 1 ? "Beschluss" : "Beschlüsse"}`;
        marker.on("click", () => router.push(themaHref(p.slug)));
        latlngs.push([p.lat, p.lon]);
        markers.push({ marker, label: p.name, hover });
      }

      // Nah dran: Namen permanent an den Punkten; weiter draußen: Hover-Tooltip.
      let labelled: boolean | null = null;
      const applyLabels = () => {
        const want = map.getZoom() >= LABEL_ZOOM || markers.length <= LABEL_MAX_POINTS;
        if (want === labelled) return;
        labelled = want;
        for (const { marker, label, hover } of markers) {
          marker.unbindTooltip();
          marker.bindTooltip(want ? label : hover, want
            ? { permanent: true, direction: "top", offset: [0, -6], className: "themen-map-label" }
            : {});
        }
      };
      map.on("zoomend", applyLabels);

      // Letzten Ausschnitt wiederherstellen (Zurück-Navigation, Filterwechsel) —
      // sonst zoomt die Karte bei jedem Mount wieder auf die Gesamtansicht raus.
      // Ausnahme: Stadtteil-Filter aktiv → auf die Auswahl zoomen, sonst zeigt
      // die Karte womöglich einen Ausschnitt ganz woanders.
      const saved = loadView();
      if (outlineLayer && outlineLayer.getBounds().isValid()) {
        map.fitBounds(outlineLayer.getBounds(), { padding: [24, 24], maxZoom: 15 });
      } else if (saved) {
        map.setView([saved.lat, saved.lng], saved.zoom);
      } else if (latlngs.length >= 8) {
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
      applyLabels();
      map.on("moveend", () => {
        const c = map.getCenter();
        try {
          sessionStorage.setItem(VIEW_KEY, JSON.stringify({ lat: c.lat, lng: c.lng, zoom: map.getZoom() }));
        } catch { /* voller/gesperrter Storage — egal */ }
      });
      } catch (err) {
        // Karte kaputt ist besser als Seite kaputt — Fehler nur loggen.
        console.error("[CouncilMap] Initialisierung fehlgeschlagen:", err);
      }
    })();
    return () => {
      cancelled = true;
      observer?.disconnect();
      // Ref ZUERST nullen, dann abgesichert entfernen: remove() kann werfen,
      // wenn Vektor-Layer nie gerendert wurden (StrictMode-Doppelmount auf
      // detachtem Container) — bliebe der Ref stehen, bailt jeder folgende
      // Effect-Lauf und die Karte wäre dauerhaft ein Tiles-Zombie.
      const m = mapRef.current;
      mapRef.current = null;
      try {
        m?.remove();
      } catch { /* Layer ohne DOM-Pfad — Karte ist ohnehin weg */ }
    };
  }, [points, outlines, router]);

  // Vollbild ist ein CSS-Overlay (kein Fullscreen-API — das zickt in iOS/Capacitor):
  // Container wird fixed, die Karte rechnet ihre Größe neu.
  useEffect(() => {
    mapRef.current?.invalidateSize();
    if (!full) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setFull(false);
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [full]);

  return (
    // Rundung/Border liegen am Wrapper: die className des Map-Divs darf sich
    // nach der Initialisierung NIE ändern — React setzt className als Ganzes
    // und würde Leaflets eigene Laufzeit-Klassen (.leaflet-container …) wegwischen.
    <div
      className={cn(
        full
          ? "fixed inset-0 z-[100] bg-background"
          : cn("relative overflow-hidden border border-border", className),
      )}
    >
      <div ref={ref} className="h-full w-full" aria-label="Stadtweite Themen-Karte" />
      <button
        type="button"
        onClick={() => setFull((f) => !f)}
        aria-label={full ? "Vollbild verlassen" : "Karte im Vollbild anzeigen"}
        title={full ? "Vollbild verlassen (Esc)" : "Vollbild"}
        className={cn(
          "absolute right-3 z-[1000] flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background/90 text-foreground shadow-sm backdrop-blur transition-colors hover:bg-muted",
          full ? "top-[calc(env(safe-area-inset-top)+0.75rem)]" : "top-3",
        )}
      >
        {full ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
      </button>
    </div>
  );
}
