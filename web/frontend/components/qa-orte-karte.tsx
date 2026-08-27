"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import { basemapUrl } from "@/lib/basemap";

/** Pin der Mini-Karte unter einer KI-Antwort (5a/I-10): die Fußnoten-Nummer
 *  der zitierten Quelle an ihrem Ort. */
export type QaOrtPin = { id: number; nummer: number; name: string; lat: number; lon: number };

/** Schlanke Leaflet-Karte für den Orts-Baustein — bewusst nicht die große
 *  CouncilMap (View-Persistenz, Stadtteil-Grenzen, Filter braucht hier
 *  niemand). Nummern-Pins im Fußnoten-Look; Klick öffnet das Beleg-Peek.
 *  Nur per next/dynamic (ssr:false) laden — Leaflet kennt kein window nicht. */
export default function QaOrteKarte({ pins, onPin }: {
  pins: QaOrtPin[]; onPin: (id: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const onPinRef = useRef(onPin);
  onPinRef.current = onPin;

  useEffect(() => {
    const el = ref.current;
    if (!el || pins.length === 0) return;
    let map: import("leaflet").Map | null = null;
    let beendet = false;
    let ro: ResizeObserver | null = null;
    const starten = (L: typeof import("leaflet")) => {
      if (beendet || map) return;
      map = L.map(el, {
        zoomControl: false, attributionControl: true, scrollWheelZoom: false,
        dragging: pins.length > 1,
      });
      L.tileLayer(basemapUrl("voyager"), {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
        maxZoom: 18,
      }).addTo(map);
      const bounds = L.latLngBounds(pins.map((p) => [p.lat, p.lon] as [number, number]));
      map.fitBounds(bounds.pad(0.25), { maxZoom: 15 });
      for (const p of pins) {
        L.marker([p.lat, p.lon], {
          title: p.name,
          icon: L.divIcon({
            className: "",
            html: `<div style="display:flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:9999px;background:hsl(var(--primary));color:hsl(var(--primary-foreground));font-size:11px;font-weight:700;box-shadow:0 1px 4px rgba(0,0,0,.35);border:2px solid #fff">${p.nummer}</div>`,
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          }),
        }).addTo(map!).on("click", () => onPinRef.current(p.id));
      }
    };
    void import("leaflet").then((L) => {
      if (beendet) return;
      // Im versteckten Tab (display:none beim Suchen/KI-Umschalter) hat der
      // Container 0×0 — Leaflet rechnete den Zoom auf NaN und blieb nach dem
      // Zurückwechseln grau (Befund F6). Erst initialisieren, wenn wirklich
      // Breite da ist; der ResizeObserver meldet das Sichtbarwerden.
      if (el.clientWidth > 0) {
        starten(L);
      } else if (typeof ResizeObserver !== "undefined") {
        ro = new ResizeObserver(() => {
          if (el.clientWidth > 0) {
            ro?.disconnect();
            starten(L);
          }
        });
        ro.observe(el);
      }
    });
    return () => { beendet = true; ro?.disconnect(); map?.remove(); };
    // Pins ändern sich nur mit einem neuen Turn — dann remountet der Baustein.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pins.map((p) => p.id).join(",")]);

  return <div ref={ref} className="h-44 w-full" aria-label="Karte der zitierten Orte" />;
}
