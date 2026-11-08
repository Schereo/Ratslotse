"use client";

import { useEffect, useRef } from "react";
import type { GeoJSON as LGeoJSON, Layer, Map as LeafletMap, Path } from "leaflet";
import "leaflet/dist/leaflet.css";

import { basemapUrl } from "@/lib/basemap";
import { loadOrtsbereiche } from "@/lib/districts";
import { cn } from "@/lib/utils";

/** Die Stadtteil-Auswahl des Einrichtungs-Assistenten — auf echtem Stadtplan.
 *
 *  **Warum nicht die SVG-Karte** (`stadtteil-karte.tsx`). Die zeigt nur die
 *  Umrisse, „weiß und blau", und war im Assistenten genau das: „ein bisschen
 *  langweilig" (Tim, 08.11.2026). Wer den eigenen Stadtteil sucht, erkennt ihn
 *  am Fluss, an der Hauptstraße, am Park — nicht an einer Fläche. Deshalb hier
 *  CARTO Voyager darunter, derselbe Kartengrund wie auf `/karte` und im Quiz,
 *  und die Ortsbereiche als halbdurchsichtige Flächen darüber. Die SVG-Karte
 *  bleibt, wo sie als Wärmekarte dient (`/karte`).
 *
 *  **Satellit gibt es nicht:** Keine der Quellen, die wir nutzen dürfen, liefert
 *  Luftbilder (CARTO hat keine; Esri und Google verbieten das freie Einbetten,
 *  Sentinel-2-Mosaike stehen unter nicht-kommerziellen Lizenzen).
 *
 *  **Tastatur und Screenreader** gehen über die Liste der Stadtteile daneben —
 *  die Karte ist die Zeige-Geste und deshalb `aria-hidden` und ohne Tab-Stopp.
 *  Gebaut wird einmal; Auswahl und Hover färben nur um (Muster aus
 *  `quiz-map.tsx`). Leaflet lädt erst im Browser — im statischen Export gibt
 *  es kein `window`. */

// Hafenblau, wie die Primärfarbe — Leaflet braucht eine echte Farbe, kein Token.
const BLAU = "#0764a6";
type Stil = { color: string; weight: number; opacity: number; fillColor: string; fillOpacity: number };
/** Wählbar, aber nicht gewählt: dünner Rand, kaum Füllung — der Stadtplan
 *  darunter soll lesbar bleiben, sonst wäre er nur Tapete. */
const OFFEN: Stil = { color: BLAU, weight: 1, opacity: 0.55, fillColor: BLAU, fillOpacity: 0.05 };
const HOVER: Stil = { color: BLAU, weight: 2, opacity: 0.9, fillColor: BLAU, fillOpacity: 0.2 };
const AN: Stil = { color: BLAU, weight: 2.5, opacity: 1, fillColor: BLAU, fillOpacity: 0.4 };
/** Ohne Beschlüsse: sichtbar, damit die Stadt vollständig aussieht, aber stumm. */
const STUMM: Stil = { color: "#94a3b8", weight: 0.75, opacity: 0.5, fillColor: "#94a3b8", fillOpacity: 0.02 };

export function StadtteilKarteGrund({ gewaehlt, auswaehlbar, onWaehlen, className }: {
  /** Namen der gewählten Ortsbereiche (mehrere erlaubt). */
  gewaehlt: Set<string>;
  /** Namen, zu denen es Beschlüsse gibt — nur sie sind anklickbar. */
  auswaehlbar: Set<string>;
  onWaehlen: (name: string) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LGeoJSON | null>(null);
  // Aktuelle Werte in Refs: Der Bau-Effekt läuft nur einmal und darf keine
  // veralteten Sets festhalten.
  const zustand = useRef({ gewaehlt, auswaehlbar, onWaehlen });
  zustand.current = { gewaehlt, auswaehlbar, onWaehlen };

  function stilFuer(name: string): Stil {
    const { gewaehlt: g, auswaehlbar: a } = zustand.current;
    return g.has(name) ? AN : a.has(name) ? OFFEN : STUMM;
  }

  /** Gewählt = festes Namensschild, sonst nur der Name beim Überfahren. */
  function beschriften(layer: Layer, name: string) {
    const an = zustand.current.gewaehlt.has(name);
    const tip = layer.getTooltip();
    const istFest = !!tip?.options.permanent;
    if (tip && istFest === an) return;
    layer.unbindTooltip();
    layer.bindTooltip(name, an
      ? { permanent: true, direction: "center", className: "stadtteil-schild" }
      : { sticky: true, direction: "top", className: "stadtteil-tip" });
  }

  function umfaerben() {
    layerRef.current?.eachLayer((l) => {
      const name = (l as unknown as { feature?: { properties?: { name?: string } } }).feature?.properties?.name;
      if (!name) return;
      (l as Path).setStyle(stilFuer(name));
      beschriften(l, name);
    });
  }

  useEffect(() => {
    let abgebrochen = false;
    let groesse: ResizeObserver | null = null;
    void (async () => {
      try {
        const L = (await import("leaflet")).default;
        const el = ref.current;
        if (abgebrochen || !el || !el.isConnected || mapRef.current) return;
        el.innerHTML = "";
        delete (el as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
        const map = L.map(el, {
          scrollWheelZoom: false, keyboard: false, attributionControl: true, zoomSnap: 0.5,
        });
        mapRef.current = map;
        map.setView([53.1435, 8.2146], 11);
        // Dunkelmodus kommt per CSS-Filter auf die Kacheln (globals.css).
        L.tileLayer(basemapUrl("voyager"), {
          maxZoom: 18, detectRetina: true, subdomains: "abcd",
          attribution: "&copy; OpenStreetMap, &copy; CARTO",
        }).addTo(map);

        const features = await loadOrtsbereiche();
        if (abgebrochen || !mapRef.current) return;
        const gj = L.geoJSON({ type: "FeatureCollection", features } as never, {
          style: (f) => stilFuer((f?.properties as { name?: string } | undefined)?.name ?? "") as never,
          onEachFeature: (feature, layer) => {
            const name = feature?.properties?.name as string | undefined;
            if (!name) return;
            layer.on({
              click: () => {
                if (zustand.current.auswaehlbar.has(name)) zustand.current.onWaehlen(name);
              },
              mouseover: () => {
                const { gewaehlt: g, auswaehlbar: a } = zustand.current;
                if (a.has(name) && !g.has(name)) (layer as Path).setStyle(HOVER);
              },
              mouseout: () => (layer as Path).setStyle(stilFuer(name)),
            });
          },
        }).addTo(map);
        layerRef.current = gj;
        if (gj.getBounds().isValid()) map.fitBounds(gj.getBounds(), { padding: [8, 8], animate: false });
        umfaerben();
        groesse = new ResizeObserver(() => {
          const m = mapRef.current;
          const g = layerRef.current;
          if (!m) return;
          m.invalidateSize();
          if (g?.getBounds().isValid()) m.fitBounds(g.getBounds(), { padding: [8, 8], animate: false });
        });
        groesse.observe(el);
      } catch (err) {
        console.error("[StadtteilKarteGrund] Initialisierung fehlgeschlagen:", err);
      }
    })();
    return () => {
      abgebrochen = true;
      groesse?.disconnect();
      const m = mapRef.current;
      mapRef.current = null;
      layerRef.current = null;
      try { m?.stop(); m?.remove(); } catch { /* Karte ohnehin weg */ }
    };
    // Einmal bauen — Auswahl färbt der Effekt darunter um.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { umfaerben(); }, [gewaehlt, auswaehlbar]);

  return (
    <div className={cn("relative overflow-hidden rounded-2xl border border-border bg-muted/30", className)}>
      <div ref={ref} aria-hidden="true" className="h-full w-full" />
    </div>
  );
}
