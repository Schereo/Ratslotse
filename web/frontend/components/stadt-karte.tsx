"use client";

import { useEffect, useRef } from "react";
import type { GeoJSON as GeoJSONLayer, LayerGroup, Map as LeafletMap, Path } from "leaflet";
import "leaflet/dist/leaflet.css";
// Das Cluster-Plugin bringt Übergänge für seine Marker mit; das Aussehen der
// Bündel steht in globals.css (.ratslotse-map-cluster).
import "leaflet.markercluster/dist/MarkerCluster.css";
import { loadOrtsbereiche, ortsbereichFor, type OrtsbereichFeature } from "@/lib/districts";
import { basemapUrl } from "@/lib/basemap";
import { cn } from "@/lib/utils";
import { ViertelZeichner, escapeHtml, type KartenBeteiligung, type KartenSperrung, type KartenVorhaben } from "@/components/viertel-zeichner";
import { ThemenOrteZeichner } from "@/components/themen-orte-zeichner";
import type { EbenenId } from "@/lib/karten-ebenen";
import { prozent, toenungNachStaerke, type WahlFlaeche } from "@/lib/wahl-flaechen";
import type { EntityMapPoint } from "@/lib/types";

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

export function StadtKarte({ stufe, ebenen, orte, gewaehlt, schwebtOrt, onOrt, onStadt, vorhaben, sperrungen, beteiligungen, themenOrte, onThemenOrt, wahl, aktiv, gedimmt, schwebt, onSelect, onHover, className }: {
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
  /** Zurück auf die Stadt-Stufe — die Karte ruft es, wenn jemand aus dem
   *  Viertel herauszoomt (Tims Wunsch 07.09.2026: Zoom wechselt die Stufe). */
  onStadt?: () => void;
  /** Die Ebene „Wahlergebnis": je Ortsbereich die Fläche seines Wahlbereichs
   *  (lib/wahl-flaechen.ts) — die Stadt-Stufe tönt danach und sagt im Hinweis,
   *  wer vorn liegt. Fehlt sie oder ist die Ebene aus, färbt die Zahl der Vorhaben. */
  wahl?: ReadonlyMap<string, WahlFlaeche>;
  vorhaben: KartenVorhaben[];
  sperrungen?: KartenSperrung[];
  beteiligungen?: KartenBeteiligung[];
  /** Die Ebene „Themen-Orte": schon gefiltert (Art, Ortsbereich) — leer, wenn aus. */
  themenOrte?: EntityMapPoint[];
  onThemenOrt?: (p: EntityMapPoint) => void;
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
  const themenRef = useRef<ThemenOrteZeichner | null>(null);
  const bereitRef = useRef(false);
  // Zoom wechselt die Stufe (Tim, 07.09.2026): Wer auf der Stadt-Stufe zwei
  // Stufen über die Stadtansicht hinein zoomt, landet im Ortsbereich unter der
  // Kartenmitte; wer im Viertel anderthalb Stufen unter den Einstiegs-Zoom
  // fällt, ist wieder in der Stadt. Die eigenen Flüge (fitBounds, flyTo)
  // zählen nicht — sonst würde der Einstieg ins Viertel gleich wieder
  // herausführen. Der Zoom des Einstiegs je Stufe ist der Maßstab, nicht eine
  // feste Zahl: Osternburg passt bei 13, ein kleines Viertel erst bei 15.
  const stufenZoomRef = useRef<{ stadt: number | null; viertel: number | null }>({ stadt: null, viertel: null });
  const eigenerFlugRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Vor jedem eigenen Flug: Die nächste Zoom-Änderung ist unsere, nicht die der Nutzerin. */
  function eigenerFlug() {
    if (eigenerFlugRef.current) clearTimeout(eigenerFlugRef.current);
    // Falls der Flug gar nichts bewegt (kein zoomend/moveend), darf die
    // Sperre nicht hängen bleiben — sonst schluckte sie den nächsten echten Zoom.
    eigenerFlugRef.current = setTimeout(() => { eigenerFlugRef.current = null; }, 1500);
  }
  const rueckrufe = useRef({ onSelect, onHover, onOrt, onStadt, onThemenOrt });
  rueckrufe.current = { onSelect, onHover, onOrt, onStadt, onThemenOrt };
  // Der jüngste Zustand für die Effekte, die nach dem Laden nachziehen.
  const standRef = useRef({ stufe, ebenen, orte, gewaehlt, vorhaben, sperrungen, beteiligungen, themenOrte, wahl, aktiv, gedimmt });
  standRef.current = { stufe, ebenen, orte, gewaehlt, vorhaben, sperrungen, beteiligungen, themenOrte, wahl, aktiv, gedimmt };

  // Karte einmal aufbauen.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const L = (await import("leaflet")).default;
      // Das Cluster-Plugin erweitert Leaflet zur Laufzeit um markerClusterGroup.
      // Erst nach Leaflet selbst laden, damit beide dasselbe Browser-Singleton nutzen.
      await import("leaflet.markercluster");
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
      themenRef.current = new ThemenOrteZeichner(L, map, (p) => rueckrufe.current.onThemenOrt?.(p));
      map.on("zoomend", () => {
        if (eigenerFlugRef.current) return;
        const zoom = map.getZoom();
        const { stufe } = standRef.current;
        const { stadt, viertel } = stufenZoomRef.current;
        if (stufe.art === "city" && stadt != null && zoom >= stadt + 2) {
          const mitte = map.getCenter();
          const name = ortsbereichFor(mitte.lat, mitte.lng, featuresRef.current);
          if (name) rueckrufe.current.onOrt(name);
        } else if (stufe.art === "district" && viertel != null && zoom <= viertel - 1.5) {
          rueckrufe.current.onStadt?.();
        }
      });
      map.on("moveend", () => {
        if (eigenerFlugRef.current) { clearTimeout(eigenerFlugRef.current); eigenerFlugRef.current = null; }
      });
      bereitRef.current = true;
      stufeSetzen(true);
      viertelZeichnen();
      themenZeichnen();
    })();
    return () => {
      cancelled = true;
      bereitRef.current = false;
      themenRef.current?.entfernen();
      themenRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
      stadtRef.current = null;
      grenzeRef.current = null;
      zeichnerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Die Wahl-Fläche eines Ortsbereichs, wenn die Ebene an ist und Daten da sind. */
  function wahlVon(name: string): WahlFlaeche | undefined {
    const { ebenen, wahl } = standRef.current;
    return ebenen.has("wahlergebnis") ? wahl?.get(name) : undefined;
  }

  /** Der Hinweis beim Zeigen: Vorhaben — und mit der Wahl-Ebene, wer im
   *  Wahlbereich vorn liegt (Parteifarbe nur als Punkt, Designsprache). */
  function hinweisHtml(name: string): string {
    const n = standRef.current.orte.get(name) ?? 0;
    const w = wahlVon(name);
    let html = `<b>${escapeHtml(name)}</b><span class="wann">${n} Vorhaben</span>`;
    if (w) {
      const listen = w.listen.slice(0, 3).map((l) =>
        `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:8px"><span style="display:inline-block;width:8px;height:8px;border-radius:9999px;background:${l.color}"></span>${escapeHtml(l.short)} ${escapeHtml(prozent(l.share))}</span>`).join("");
      html += `<span class="wann" style="display:block;margin-top:5px">Wahlbereich ${escapeHtml(w.roman)} · ${w.counted > 0 ? `${w.counted} von ${w.total} Bezirken` : "noch nichts ausgezählt"}</span>`
        + (w.counted > 0 ? `<span style="display:block;margin-top:2px">${listen}</span>` : "");
    }
    return html;
  }

  /** Tönung einer Fläche: mit der Wahl-Ebene nach Stärke der stärksten
   *  Liste im Wahlbereich, sonst nach Zahl der Vorhaben — dieselbe
   *  Wurzel-Skala wie die SVG-Karte. */
  function toenung(name: string): number {
    const w = wahlVon(name);
    if (w) return toenungNachStaerke(w.staerke);
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
          layer.bindTooltip(hinweisHtml(name), { sticky: true, direction: "top", offset: [0, -6], className: "viertel-tip", opacity: 1 });
          layer.on("mouseover", () => (layer as Path).setStyle(stadtStil(name, true)));
          layer.on("mouseout", () => (layer as Path).setStyle(stadtStil(name, false)));
          layer.on("click", () => rueckrufe.current.onOrt(name));
        },
      }).addTo(map);
      stadtRef.current = stadt;
      if (features.length) {
        eigenerFlug();
        if (sofort) map.fitBounds(stadt.getBounds(), { padding: [8, 8] });
        else map.flyToBounds(stadt.getBounds(), { padding: [8, 8], duration: 0.6 });
        stufenZoomRef.current.stadt = map.getBoundsZoom(stadt.getBounds(), false, L.point(8, 8));
      }
    } else {
      const grenze = features.find((f) => f.properties.name === stufe.name);
      if (grenze) {
        const layer = L.geoJSON(grenze as never, {
          style: { color: PRIMAER, weight: 2, opacity: 0.8, fillColor: PRIMAER, fillOpacity: 0.05 },
          interactive: false,
        });
        grenzeRef.current?.addLayer(layer);
        eigenerFlug();
        if (sofort) map.fitBounds(layer.getBounds(), { padding: [16, 16] });
        else map.flyToBounds(layer.getBounds(), { padding: [16, 16], duration: 0.7 });
        stufenZoomRef.current.viertel = map.getBoundsZoom(layer.getBounds(), false, L.point(16, 16));
      }
    }
  }

  function viertelZeichnen() {
    const z = zeichnerRef.current, map = mapRef.current;
    if (!z || !map || !bereitRef.current) return;
    const { stufe, ebenen, vorhaben, sperrungen, beteiligungen, aktiv, gedimmt } = standRef.current;
    if (stufe.art !== "district") { z.leeren(); return; }
    z.zeichnen({ vorhaben, sperrungen, beteiligungen, aktiv, gedimmt,
      ebenen: { vorhaben: ebenen.has("vorhaben"), plaene: ebenen.has("plaene"), sperrungen: ebenen.has("sperrungen"), beteiligungen: ebenen.has("mitreden") } });
    if (z.aktivBounds) { eigenerFlug(); map.flyToBounds(z.aktivBounds.pad(0.6), { maxZoom: 16, duration: 0.5 }); }
  }

  function themenZeichnen() {
    if (!bereitRef.current) return;
    themenRef.current?.zeichnen(standRef.current.themenOrte ?? []);
  }
  // Themen-Orte (schon gefiltert) → Ebene neu zeichnen.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { themenZeichnen(); }, [themenOrte]);

  // Stufe oder Ortsbereich gewechselt → Karte umbauen.
  const stufeSchluessel = stufe.art === "district" ? `district:${stufe.name}` : "city";
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { stufeSetzen(); viertelZeichnen(); }, [stufeSchluessel]);
  // Tönung, eigene Stadtteile oder Wahl-Ebene neu → Stadt-Flächen nachfärben
  // und den Hinweis neu setzen (er nennt die Zahlen der Ebene).
  useEffect(() => {
    if (standRef.current.stufe.art !== "city") return;
    stadtRef.current?.eachLayer((layer) => {
      const f = (layer as unknown as { feature?: OrtsbereichFeature }).feature;
      if (!f) return;
      (layer as Path).setStyle(stadtStil(f.properties.name, false));
      (layer as Path).setTooltipContent(hinweisHtml(f.properties.name));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orte, gewaehlt, ebenen, wahl]);
  // Vorhaben, Auswahl, Filter, Ebenen → Viertel neu zeichnen.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { viertelZeichnen(); }, [vorhaben, sperrungen, beteiligungen, aktiv, gedimmt, ebenen]);
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
