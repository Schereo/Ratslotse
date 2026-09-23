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
import { WahlBezirkeZeichner } from "@/components/wahl-bezirke-zeichner";
import type { Wahlkarte } from "@/lib/wahlkarte";
import { isDarkNow, THEME_EVENT } from "@/lib/theme";
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

export function StadtKarte({ stufe, ebenen, orte, gewaehlt, schwebtOrt, onOrt, onStadt, vorhaben, sperrungen, beteiligungen, themenOrte, onThemenOrt, wahl, wahlBezirk, onWahlBezirk, aktiv, gedimmt, schwebt, onSelect, onHover, className }: {
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
  /** Die Ebene „Wahlergebnis": das Ergebnis je Urnenbezirk
   *  (`/api/wahlabend/karte`). Mit ihr zeichnet die Karte die Wahlbezirke in
   *  der Farbe dessen, der vorn lag (components/wahl-bezirke-zeichner.ts);
   *  die Ortsbereiche bleiben als Linien darüber. */
  wahl?: Wahlkarte;
  /** Der gewählte Wahlbezirk auf der Viertel-Stufe. */
  wahlBezirk?: number | null;
  onWahlBezirk?: (nr: number | null) => void;
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
  const wahlRef = useRef<WahlBezirkeZeichner | null>(null);
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
  const rueckrufe = useRef({ onSelect, onHover, onOrt, onStadt, onThemenOrt, onWahlBezirk });
  rueckrufe.current = { onSelect, onHover, onOrt, onStadt, onThemenOrt, onWahlBezirk };
  // Der jüngste Zustand für die Effekte, die nach dem Laden nachziehen.
  const standRef = useRef({ stufe, ebenen, orte, gewaehlt, vorhaben, sperrungen, beteiligungen, themenOrte, wahl, wahlBezirk, aktiv, gedimmt });
  standRef.current = { stufe, ebenen, orte, gewaehlt, vorhaben, sperrungen, beteiligungen, themenOrte, wahl, wahlBezirk, aktiv, gedimmt };

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
      wahlRef.current = new WahlBezirkeZeichner(L, map, L.layerGroup().addTo(map), {
        onOrtBei: (lat, lng) => {
          const name = ortsbereichFor(lat, lng, featuresRef.current);
          if (name) rueckrufe.current.onOrt(name);
        },
        onBezirk: (nr) => rueckrufe.current.onWahlBezirk?.(nr),
      });
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
      void wahlZeichnen();
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
      wahlRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Liegt die Wahl-Ebene auf der Karte? Dann tragen die Bezirke die Farbe,
   *  und die Ortsbereiche sind nur noch Linien zur Orientierung. */
  function wahlAn(): boolean {
    const { ebenen, wahl } = standRef.current;
    return ebenen.has("wahlergebnis") && !!wahl;
  }

  /** Der Hinweis beim Zeigen: Name und Zahl der Vorhaben. */
  function hinweisHtml(name: string): string {
    const n = standRef.current.orte.get(name) ?? 0;
    return `<b>${escapeHtml(name)}</b><span class="wann">${n} Vorhaben</span>`;
  }

  /** Tönung einer Fläche nach Zahl der Vorhaben — dieselbe Wurzel-Skala
   *  wie die SVG-Karte. */
  function toenung(name: string): number {
    if (!standRef.current.ebenen.has("vorhaben")) return 0.04;
    const o = standRef.current.orte;
    const max = Math.max(0, ...o.values());
    const n = o.get(name) ?? 0;
    return n > 0 && max > 0 ? 0.12 + 0.5 * Math.sqrt(n / max) : 0.03;
  }

  function stadtStil(name: string, hell: boolean) {
    const eigen = standRef.current.gewaehlt?.has(name);
    if (wahlAn()) {
      // Nur die Grenze: Die Farbe gehört den Wahlbezirken darunter.
      // Dunkler und kräftiger als die weißen Bezirksgrenzen darunter, sonst
      // verschwimmen Stadtteil und Wahlbezirk zu einem Netz.
      return { color: eigen ? PRIMAER : isDarkNow() ? "#e2e8f0" : "#1e293b", weight: eigen ? 2.5 : 1.6, opacity: eigen ? 0.95 : 0.6,
        fillColor: PRIMAER, fillOpacity: 0 };
    }
    return {
      color: eigen ? PRIMAER : "#fff", weight: eigen ? 2.5 : 1, opacity: 0.9,
      fillColor: PRIMAER, fillOpacity: hell ? Math.min(0.75, toenung(name) + 0.2) : toenung(name),
    };
  }

  /** Die Stufe auf der Karte herstellen: Stadt-Flächen ODER Viertel-Umriss + Ausschnitt. */
  function stufeSetzen(sofort = false, fliegen = true) {
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
        // Mit der Wahl-Ebene fangen die Bezirke darunter Zeiger und Tipp —
        // sie wissen, welcher Bezirk gemeint ist, und öffnen trotzdem den
        // Ortsbereich unter dem Finger.
        interactive: !wahlAn(),
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
      if (features.length && fliegen) {
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
        if (fliegen) {
          eigenerFlug();
          if (sofort) map.fitBounds(layer.getBounds(), { padding: [16, 16] });
          else map.flyToBounds(layer.getBounds(), { padding: [16, 16], duration: 0.7 });
          stufenZoomRef.current.viertel = map.getBoundsZoom(layer.getBounds(), false, L.point(16, 16));
        }
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

  async function wahlZeichnen() {
    const w = wahlRef.current;
    if (!w || !bereitRef.current) return;
    const { stufe, wahl, wahlBezirk } = standRef.current;
    if (!wahlAn() || !wahl) { w.leeren(); return; }
    try { await w.laden(); } catch { return; }
    if (!bereitRef.current || wahlRef.current !== w) return;
    const ort = stufe.art === "district" ? stufe.name : null;
    const grenze = ort ? featuresRef.current.find((f) => f.properties.name === ort) : undefined;
    w.zeichnen({ daten: wahl, ort, ortGeometrie: grenze?.geometry as GeoJSON.Geometry | undefined, gewaehlt: ort ? wahlBezirk ?? null : null, dunkel: isDarkNow() });
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
  useEffect(() => { stufeSetzen(); viertelZeichnen(); void wahlZeichnen(); }, [stufeSchluessel]);
  // Wahl-Ebene an/aus: Die Stadt-Flächen tauschen Interaktion und Stil
  // (ohne Flug — die Karte bleibt, wo sie ist).
  const wahlSchluessel = ebenen.has("wahlergebnis") && !!wahl;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (bereitRef.current && standRef.current.stufe.art === "city") stufeSetzen(false, false); }, [wahlSchluessel]);
  // Daten, Auswahl, Ebene → Bezirke neu zeichnen; auch beim Wechsel hell/dunkel.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void wahlZeichnen(); }, [wahl, wahlBezirk, wahlSchluessel]);
  useEffect(() => {
    const h = () => { void wahlZeichnen(); if (standRef.current.stufe.art === "city") stadtRef.current?.eachLayer((l) => {
      const f = (l as unknown as { feature?: OrtsbereichFeature }).feature;
      if (f) (l as Path).setStyle(stadtStil(f.properties.name, false));
    }); };
    window.addEventListener(THEME_EVENT, h);
    return () => window.removeEventListener(THEME_EVENT, h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
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
  }, [orte, gewaehlt, ebenen]);
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

  const label = wahlSchluessel
    ? (stufe.art === "district" ? `Karte von ${stufe.name} mit dem Wahlergebnis je Wahlbezirk` : "Karte von Oldenburg mit dem Wahlergebnis je Wahlbezirk")
    : stufe.art === "district" ? `Karte von ${stufe.name} mit den Vorhaben` : "Karte von Oldenburg mit den Vorhaben je Ortsbereich";
  return (
    <div className={cn("relative overflow-hidden bg-muted", className)}>
      <div ref={ref} className="h-full w-full" aria-label={label} role="region" />
    </div>
  );
}
