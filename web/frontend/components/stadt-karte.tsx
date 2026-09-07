"use client";

import { useEffect, useRef } from "react";
import type { GeoJSON as GeoJSONLayer, LayerGroup, Map as LeafletMap, Path } from "leaflet";
import "leaflet/dist/leaflet.css";
import { loadOrtsbereiche, type OrtsbereichFeature } from "@/lib/districts";
import { basemapUrl } from "@/lib/basemap";
import { cn } from "@/lib/utils";
import { ViertelZeichner, escapeHtml, type KartenSperrung, type KartenVorhaben } from "@/components/viertel-zeichner";
import type { EbenenId } from "@/lib/karten-ebenen";

/** Die vereinte Stadtkarte — EINE Leaflet-Karte mit zwei Stufen
 *  (`STADTKARTE-PLAN.md`, Richtung A „Karte als Bühne").
 *
 *  - **Stadt:** die 31 Ortsbereiche als Flächen, getönt nach Zahl der
 *    Vorhaben (Wurzel-Skala, wie die SVG-Wärmekarte der Auswahl). Zeigen
 *    hebt die Fläche und nennt Name und Zahl, ein Tipp meldet den Ortsbereich
 *    nach außen — die Seite zoomt dann hinein.
 *  - **Viertel:** der gewählte Ortsbereich als Umriss, darin Pins, Linien,
 *    Planflächen und Sperrungen — gezeichnet vom selben `ViertelZeichner`
 *    wie auf `/viertel`.
 *
 *  Die Karte bleibt beim Stufenwechsel dieselbe Instanz (Kacheln, Zoom-
 *  Animation, Attribution): Genau das unterscheidet die Bühne von zwei
 *  Seiten. Zwei Leaflet-Karten auf einer Seite gehen ohnehin nicht gut
 *  (`_leaflet_id`, StrictMode-Doppelmount — s. `council-map.tsx`).
 */
export type KartenStufe = { art: "city" } | { art: "district"; name: string };

const VOYAGER = basemapUrl("voyager");
const PRIMAER = "#0a63a8";
const STADT_MITTE: [number, number] = [53.1435, 8.2146];

export function StadtKarte({ stufe, ebenen, orte, gewaehlt, schwebtOrt, onOrt, vorhaben, sperrungen, aktiv, gedimmt, schwebt, onSelect, onHover, className }: {
  stufe: KartenStufe;
  /** Die eingeschalteten Ebenen (`lib/karten-ebenen.ts`). Ohne die Vorhaben-
   *  Ebene bleibt die Stadt-Stufe eine flache Umrisskarte. */
  ebenen: ReadonlySet<EbenenId>;
  /** Zahl der Vorhaben je Ortsbereich (Name → Zahl) — die Tönung der Stadt-Stufe. */
  orte: Map<string, number>;
  /** Die eigenen Stadtteile: auf der Stadt-Stufe mit kräftigem Rand. */
  gewaehlt?: Set<string>;
  /** Der Ortsbereich, über dem der Zeiger in der Rangliste steht. */
  schwebtOrt?: string | null;
  onOrt: (name: string) => void;
  vorhaben: KartenVorhaben[];
  sperrungen?: KartenSperrung[];
  aktiv: number | null;
  gedimmt: Set<number>;
  schwebt?: number | null;
  onSelect: (id: number) => void;
  onHover?: (id: number | null) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const featuresRef = useRef<OrtsbereichFeature[]>([]);
  const stadtRef = useRef<GeoJSONLayer | null>(null);
  const grenzeRef = useRef<LayerGroup | null>(null);
  const zeichnerRef = useRef<ViertelZeichner | null>(null);
  const bereitRef = useRef(false);
  const rueckrufe = useRef({ onSelect, onHover, onOrt });
  rueckrufe.current = { onSelect, onHover, onOrt };
  // Der jüngste Zustand für die Effekte, die nach dem Laden nachziehen.
  const standRef = useRef({ stufe, ebenen, orte, gewaehlt, vorhaben, sperrungen, aktiv, gedimmt });
  standRef.current = { stufe, ebenen, orte, gewaehlt, vorhaben, sperrungen, aktiv, gedimmt };

  // Karte einmal aufbauen.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current || !ref.current.isConnected) return;
      delete (ref.current as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
      leafletRef.current = L;
      const map = L.map(ref.current, { zoomControl: false, scrollWheelZoom: true, attributionControl: true });
      mapRef.current = map;
      L.control.zoom({ position: "topright" }).addTo(map);
      L.tileLayer(VOYAGER, { maxZoom: 19, subdomains: "abcd", attribution: "&copy; OpenStreetMap, &copy; CARTO" }).addTo(map);
      map.setView(STADT_MITTE, 12);
      try {
        featuresRef.current = await loadOrtsbereiche();
      } catch { /* ohne Umrisse bleibt die Karte trotzdem eine Karte */ }
      if (cancelled) return;
      grenzeRef.current = L.layerGroup().addTo(map);
      zeichnerRef.current = new ViertelZeichner(L, map, L.layerGroup().addTo(map), {
        onSelect: (id) => rueckrufe.current.onSelect(id),
        onHover: (id) => rueckrufe.current.onHover?.(id),
      });
      bereitRef.current = true;
      stufeSetzen(true);
      viertelZeichnen();
    })();
    return () => {
      cancelled = true;
      bereitRef.current = false;
      mapRef.current?.remove();
      mapRef.current = null;
      stadtRef.current = null;
      grenzeRef.current = null;
      zeichnerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Tönung einer Fläche nach Zahl — dieselbe Wurzel-Skala wie die SVG-Karte. */
  function toenung(name: string): number {
    if (!standRef.current.ebenen.has("vorhaben")) return 0.04;
    const o = standRef.current.orte;
    const max = Math.max(0, ...o.values());
    const n = o.get(name) ?? 0;
    return n > 0 && max > 0 ? 0.12 + 0.5 * Math.sqrt(n / max) : 0.03;
  }

  function stadtStil(name: string, hell: boolean) {
    const eigen = standRef.current.gewaehlt?.has(name);
    return {
      color: eigen ? PRIMAER : "#fff", weight: eigen ? 2.5 : 1, opacity: 0.9,
      fillColor: PRIMAER, fillOpacity: hell ? Math.min(0.75, toenung(name) + 0.2) : toenung(name),
    };
  }

  /** Die Stufe auf der Karte herstellen: Stadt-Flächen ODER Viertel-Umriss + Ausschnitt. */
  function stufeSetzen(sofort = false) {
    const L = leafletRef.current, map = mapRef.current;
    if (!L || !map || !bereitRef.current) return;
    const { stufe } = standRef.current;
    const features = featuresRef.current;
    stadtRef.current?.remove();
    stadtRef.current = null;
    grenzeRef.current?.clearLayers();
    if (stufe.art === "city") {
      zeichnerRef.current?.leeren();
      const stadt = L.geoJSON({ type: "FeatureCollection", features } as never, {
        style: (f) => stadtStil((f as OrtsbereichFeature).properties.name, false),
        onEachFeature: (f, layer) => {
          const name = (f as OrtsbereichFeature).properties.name;
          const n = standRef.current.orte.get(name) ?? 0;
          layer.bindTooltip(`<b>${escapeHtml(name)}</b><span class="wann">${n} Vorhaben</span>`, { sticky: true, direction: "top", offset: [0, -6], className: "viertel-tip", opacity: 1 });
          layer.on("mouseover", () => (layer as Path).setStyle(stadtStil(name, true)));
          layer.on("mouseout", () => (layer as Path).setStyle(stadtStil(name, false)));
          layer.on("click", () => rueckrufe.current.onOrt(name));
        },
      }).addTo(map);
      stadtRef.current = stadt;
      if (features.length) {
        if (sofort) map.fitBounds(stadt.getBounds(), { padding: [8, 8] });
        else map.flyToBounds(stadt.getBounds(), { padding: [8, 8], duration: 0.6 });
      }
    } else {
      const grenze = features.find((f) => f.properties.name === stufe.name);
      if (grenze) {
        const layer = L.geoJSON(grenze as never, {
          style: { color: PRIMAER, weight: 2, opacity: 0.8, fillColor: PRIMAER, fillOpacity: 0.05 },
          interactive: false,
        });
        grenzeRef.current?.addLayer(layer);
        if (sofort) map.fitBounds(layer.getBounds(), { padding: [16, 16] });
        else map.flyToBounds(layer.getBounds(), { padding: [16, 16], duration: 0.7 });
      }
    }
  }

  function viertelZeichnen() {
    const z = zeichnerRef.current, map = mapRef.current;
    if (!z || !map || !bereitRef.current) return;
    const { stufe, ebenen, vorhaben, sperrungen, aktiv, gedimmt } = standRef.current;
    if (stufe.art !== "district") { z.leeren(); return; }
    z.zeichnen({ vorhaben, sperrungen, aktiv, gedimmt,
      ebenen: { vorhaben: ebenen.has("vorhaben"), plaene: ebenen.has("plaene"), sperrungen: ebenen.has("sperrungen") } });
    if (z.aktivBounds) map.flyToBounds(z.aktivBounds.pad(0.6), { maxZoom: 16, duration: 0.5 });
  }

  // Stufe oder Ortsbereich gewechselt → Karte umbauen.
  const stufeSchluessel = stufe.art === "district" ? `district:${stufe.name}` : "city";
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { stufeSetzen(); viertelZeichnen(); }, [stufeSchluessel]);
  // Tönung oder eigene Stadtteile neu → Stadt-Flächen nachfärben.
  useEffect(() => {
    if (standRef.current.stufe.art !== "city") return;
    stadtRef.current?.eachLayer((layer) => {
      const f = (layer as unknown as { feature?: OrtsbereichFeature }).feature;
      if (f) (layer as Path).setStyle(stadtStil(f.properties.name, false));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orte, gewaehlt, ebenen]);
  // Vorhaben, Auswahl, Filter, Ebenen → Viertel neu zeichnen.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { viertelZeichnen(); }, [vorhaben, sperrungen, aktiv, gedimmt, ebenen]);
  // Zeiger in der Liste → Pin hebt sich.
  useEffect(() => {
    if (schwebt != null) zeichnerRef.current?.heben(schwebt, true);
    return () => { if (schwebt != null) zeichnerRef.current?.heben(schwebt, false); };
  }, [schwebt]);
  // Zeiger in der Rangliste → Fläche hebt sich.
  useEffect(() => {
    if (!schwebtOrt) return;
    let getroffen: Path | null = null;
    stadtRef.current?.eachLayer((layer) => {
      const f = (layer as unknown as { feature?: OrtsbereichFeature }).feature;
      if (f?.properties.name === schwebtOrt) { getroffen = layer as Path; getroffen.setStyle(stadtStil(schwebtOrt, true)); }
    });
    return () => { getroffen?.setStyle(stadtStil(schwebtOrt, false)); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schwebtOrt]);

  const label = stufe.art === "district" ? `Karte von ${stufe.name} mit den Vorhaben` : "Karte von Oldenburg mit den Vorhaben je Ortsbereich";
  return (
    <div className={cn("relative overflow-hidden bg-muted", className)}>
      <div ref={ref} className="h-full w-full" aria-label={label} role="region" />
    </div>
  );
}
