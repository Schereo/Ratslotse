"use client";

// Die Karte zum Plan — schlankes Leaflet ohne react-leaflet, nur clientseitig
// (per next/dynamic mit ssr:false laden). Straßen aus der Maßnahmenliste als
// Linie, Orte aus Beschlüssen als Punkt; die Kachel-URL kommt aus
// lib/basemap.ts (der Key-Parameter heißt `key`, nicht `api_key`).
//
// Neutral gefärbt: Die Karte zeigt, WO etwas vorgesehen oder beschlossen ist,
// nicht wie weit es ist (Plan § 3.4). Der Stand steht in der Liste darunter.

import { useEffect, useRef } from "react";
import type { Layer, Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { basemapUrl } from "@/lib/basemap";
import type { PlanPlace } from "@/lib/plans";

function color(name: string, fallback: string): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return raw ? `hsl(${raw})` : fallback;
}

function escape(text: string): string {
  return text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] ?? c);
}

export default function PlanMap({ places, focus, onPick }: {
  places: readonly PlanPlace[];
  /** Der Ort, auf den die Liste zeigt — die Karte fährt hin und hebt ihn hervor. */
  focus: string | null;
  onPick: (slug: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layers = useRef(new Map<string, Layer>());
  const pick = useRef(onPick);
  pick.current = onPick;

  useEffect(() => {
    const el = ref.current;
    if (!el || places.length === 0) return;
    let done = false;
    let ro: ResizeObserver | null = null;
    const start = (L: typeof import("leaflet")) => {
      if (done || mapRef.current) return;
      const map = L.map(el, { zoomControl: true, scrollWheelZoom: false, attributionControl: true });
      mapRef.current = map;
      L.tileLayer(basemapUrl("voyager"), {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
        maxZoom: 18, subdomains: "abcd", detectRetina: true,
      }).addTo(map);
      const line = color("--primary", "#0764a6");
      const dot = color("--signal", "#e8590c");
      const bounds = L.latLngBounds([]);
      const pending: Layer[] = [];
      for (const place of places) {
        const label = `<strong>${escape(place.name)}</strong>${place.areas[0] ? `<br>${escape(place.areas[0].area_ha.toLocaleString("de-DE", { maximumFractionDigits: 1 }))} ha` : place.sections[0] ? `<br>${escape(place.sections[0].code)} · ${escape(place.sections[0].stretch)}` : place.measures[0] ? `<br>${escape(place.measures[0].code)} · ${escape(place.measures[0].title)}` : place.decisions[0] ? `<br>${escape(place.decisions[0].title)}` : ""}`;
        let layer: Layer;
        if (place.geometry) {
          // Gebiete als Fläche (dünner Rand, leichte Füllung), Straßen als kräftige Linie.
          const style = place.areas.length
            ? { color: line, weight: 2, opacity: 0.9, fillColor: line, fillOpacity: 0.18 }
            : { color: line, weight: 5, opacity: 0.85, lineCap: "round" as const };
          const shape = L.geoJSON(place.geometry as import("geojson").GeoJsonObject, { style });
          layer = shape;
          bounds.extend(shape.getBounds());
        } else {
          layer = L.circleMarker([place.lat, place.lon], {
            radius: 6, color: "#fff", weight: 2, fillColor: place.measures.length ? line : dot, fillOpacity: 0.95,
          });
          bounds.extend([place.lat, place.lon]);
        }
        layer.bindTooltip(label, { sticky: true, direction: "top" }).on("click", () => pick.current(place.slug));
        layers.current.set(place.slug, layer);
        pending.push(layer);
      }
      // Erst den Ausschnitt setzen, dann die Linien hinzufügen: Ohne Ansicht hat der Zeichner noch
      // keine Grenzen, und Leaflet bricht beim Zuschneiden der Linien ab.
      if (bounds.isValid()) map.fitBounds(bounds.pad(0.08), { maxZoom: 15, animate: false });
      else map.setView([53.1435, 8.2146], 12);
      for (const layer of pending) layer.addTo(map);
    };
    void import("leaflet").then((mod) => {
      const L = mod.default ?? mod;
      if (done) return;
      // In einem eben erst aufgeklappten oder versteckten Bereich ist der Kasten 0 breit —
      // Leaflet rechnete den Zoom dann auf NaN. Erst starten, wenn Breite da ist.
      if (el.getBoundingClientRect().width > 0) start(L);
      else if (typeof ResizeObserver !== "undefined") {
        ro = new ResizeObserver(() => {
          if (el.getBoundingClientRect().width > 0) { ro?.disconnect(); start(L); }
        });
        ro.observe(el);
      }
    });
    const registry = layers.current;
    return () => { done = true; ro?.disconnect(); mapRef.current?.remove(); mapRef.current = null; registry.clear(); };
  }, [places]);

  useEffect(() => {
    const map = mapRef.current;
    const layer = focus ? layers.current.get(focus) : null;
    if (!map || !layer) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const target = layer as Layer & { getBounds?: () => import("leaflet").LatLngBounds; getLatLng?: () => import("leaflet").LatLng };
    if (target.getBounds) map.flyToBounds(target.getBounds().pad(0.4), { maxZoom: 16, animate: !reduced, duration: 0.6 });
    else if (target.getLatLng) map.flyTo(target.getLatLng(), Math.max(map.getZoom(), 15), { animate: !reduced, duration: 0.6 });
    layer.openTooltip();
  }, [focus]);

  return <div ref={ref} className="h-72 w-full overflow-hidden rounded-xl border border-border sm:h-96" aria-label="Karte der Orte zum Plan" />;
}
