"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import "leaflet/dist/leaflet.css";
import { loadOrtsbereiche, type OrtsbereichFeature } from "@/lib/districts";
import { basemapUrl } from "@/lib/basemap";
import { cn } from "@/lib/utils";

/** Die Karte als Bühne von „Mein Viertel".
 *
 *  Das Viertel als Umriss auf echtem Kartengrund, jedes Vorhaben als Pin in
 *  seiner Stand-Farbe — und wo der Ort eine Straße ist, als Linie: Ein Pin am
 *  Mittelpunkt einer Straße, die um die Ecke geht, läge NEBEN ihr (dieselbe
 *  Falle wie in `geo.ortsbereiche_der_geometrie`). Ein Tipp öffnet ein
 *  Popover mit Name und Stand; „Details" gibt das Vorhaben nach außen, die
 *  Seite zeigt es dann unter der Karte bzw. in der Seitenspalte.
 *
 *  Leaflet wird erst im Effekt geladen (kein SSR, kein Export-Bruch), wie in
 *  `council-map.tsx`; die Punkte bleiben HTML-Kreise, es werden keine
 *  Marker-Bilder nachgeladen (CSP bleibt auf die Kacheln begrenzt).
 */
export type KartenVorhaben = {
  id: number;
  name: string;
  stage: string;
  when: string | null;
  locations: { slug: string; name: string; kind: string; lat: number; lon: number; geometry: unknown; role?: string; plan?: { status: string } }[];
};

/** Stand → Farbe. Dieselben Töne wie die Badges der Liste, damit Pin und
 *  Karte dasselbe sagen. */
export const STAND_FARBE: Record<string, string> = {
  building: "#f0641c", decided: "#15803d", planning: "#0a63a8", idea: "#64748b", done: "#94a3b8", rejected: "#b91c1c",
};
const STAND_LABEL: Record<string, string> = {
  building: "Im Bau", decided: "Beschlossen", planning: "In Planung", idea: "Idee", done: "Fertig", rejected: "Abgelehnt",
};

const VOYAGER = basemapUrl("voyager");
const PLAN_ATTRIBUTION = "Bebauungspläne: Stadt Oldenburg (Geoportal)";

/** Eine laufende Sperrung der Stadt — Linie in Warnfarbe, nicht wählbar. */
export type KartenSperrung = {
  id: number; street: string; reason: string | null; kind_label: string | null;
  valid_until: string | null; geometry: unknown; lat: number | null; lon: number | null;
};
const SPERRUNG_FARBE = "#b45309";

export function ViertelKarte({ ortsbereich, vorhaben, sperrungen, aktiv, gedimmt, schwebt, onSelect, onHover, className }: {
  /** Name des Ortsbereichs — die Grenze kommt aus dem statischen GeoJSON. */
  ortsbereich: string;
  vorhaben: KartenVorhaben[];
  /** Laufende Sperrungen der Stadt im Viertel — Linien in Warnfarbe mit
   *  Hinweis, aber ohne Auswahl: Sie sind Kontext, kein Vorhaben. */
  sperrungen?: KartenSperrung[];
  /** Das ausgewählte Vorhaben (Pin wird groß, Karte fährt hin). */
  aktiv: number | null;
  /** Vorhaben, die der Stufen-Filter ausblendet — bleiben blass sichtbar. */
  gedimmt: Set<number>;
  /** Das Vorhaben, über dem der Zeiger gerade in der LISTE steht — sein Pin
   *  hebt sich auf der Karte, damit Liste und Karte eine Sache sind. */
  schwebt?: number | null;
  onSelect: (id: number) => void;
  /** Zeiger über einem Pin (bzw. weg davon) — die Liste hebt ihre Zeile. */
  onHover?: (id: number | null) => void;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const onHoverRef = useRef(onHover);
  onHoverRef.current = onHover;
  // Je Vorhaben seine Ebenen, damit Hover sie hebt, ohne alles neu zu zeichnen
  // (ein Neuzeichnen bei jedem Zeigerwechsel ließe offene Popups zuklappen).
  const ebenenRef = useRef<Map<number, { pins: import("leaflet").Marker[]; pfade: import("leaflet").Path[]; farbe: string; aktiv: boolean }>>(new Map());

  // Karte einmal aufbauen: Kacheln, Grenze, Ausschnitt.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current || !ref.current.isConnected) return;
      delete (ref.current as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
      leafletRef.current = L;
      const map = L.map(ref.current, { zoomControl: true, scrollWheelZoom: false, attributionControl: true });
      mapRef.current = map;
      L.tileLayer(VOYAGER, { maxZoom: 19, subdomains: "abcd", attribution: "&copy; OpenStreetMap, &copy; CARTO" }).addTo(map);
      map.setView([53.1435, 8.2146], 12);
      let grenze: OrtsbereichFeature | undefined;
      try {
        grenze = (await loadOrtsbereiche()).find((f) => f.properties.name === ortsbereich);
      } catch { /* ohne Grenze bleibt die Karte trotzdem brauchbar */ }
      if (cancelled) return;
      if (grenze) {
        const layer = L.geoJSON(grenze as never, {
          style: { color: "#0a63a8", weight: 2, opacity: 0.8, fillColor: "#0a63a8", fillOpacity: 0.05 },
          interactive: false,
        }).addTo(map);
        map.fitBounds(layer.getBounds(), { padding: [12, 12] });
      }
      layerRef.current = L.layerGroup().addTo(map);
      zeichnen();
    })();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ortsbereich]);

  /** Ein Vorhaben heben oder senken — Pin-Klasse und Strichstärke, ohne
   *  Neuzeichnen. Das aktive bleibt, wie es ist: Es steht ohnehin vorn. */
  function heben(id: number, an: boolean) {
    const e = ebenenRef.current.get(id);
    if (!e) return;
    for (const pin of e.pins) pin.getElement()?.classList.toggle("ist-schwebt", an);
    if (e.aktiv) return;
    for (const pfad of e.pfade) {
      const basis = pfad.options.weight ?? 5;
      pfad.setStyle({ weight: an ? basis + 2 : basis, opacity: an ? 1 : (pfad.options.opacity ?? 0.75) });
      if (an) pfad.bringToFront();
    }
  }

  // Zeiger in der Liste → Pin hebt sich. Der Effekt läuft, ohne die Karte
  // neu zu zeichnen (s. ebenenRef).
  useEffect(() => {
    if (schwebt != null) heben(schwebt, true);
    return () => { if (schwebt != null) heben(schwebt, false); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schwebt]);

  // Pins und Linien neu zeichnen, wenn Auswahl oder Filter wechseln.
  function zeichnen() {
    const L = leafletRef.current, map = mapRef.current, gruppe = layerRef.current;
    if (!L || !map || !gruppe) return;
    gruppe.clearLayers();
    ebenenRef.current = new Map();
    let aktivBounds: ReturnType<typeof L.latLngBounds> | null = null;
    let planQuelle = false;
    for (const v of vorhaben) {
      const farbe = STAND_FARBE[v.stage] ?? STAND_FARBE.planning;
      const istAktiv = v.id === aktiv;
      // Blass, was der Stand-Filter ausblendet — und alles andere, sobald ein
      // Vorhaben ausgewählt ist: Dessen Linie soll allein stehen.
      const blass = (gedimmt.has(v.id) || aktiv != null) && !istAktiv;
      // Alles, was aus der Datenbank kommt, wird maskiert — auch „wann" und
      // der Stand stammen aus einer Modellantwort, nicht aus dem Code.
      const hinweis = `<span class="stand" style="--c:${escapeHtml(farbe)}">${escapeHtml(STAND_LABEL[v.stage] ?? v.stage)}</span>${v.when ? `<span class="wann">${escapeHtml(v.when)}</span>` : ""}<b>${escapeHtml(v.name)}</b>`;
      const eintrag = { pins: [] as import("leaflet").Marker[], pfade: [] as import("leaflet").Path[], farbe, aktiv: istAktiv };
      ebenenRef.current.set(v.id, eintrag);
      // Ein Tipp WÄHLT das Vorhaben (Detail in Seitenspalte bzw. Sheet) —
      // bis 06.09.2026 öffnete er erst ein Popup mit einem „Details"-Knopf,
      // zwei Tipps für eine Sache. Der Hinweis mit Name und Stand steht
      // stattdessen beim Zeigen (Tooltip); das gewählte Vorhaben trägt sein
      // Namensschild dauerhaft (s. u.).
      const anklicken = (layer: import("leaflet").Layer) => {
        if (!istAktiv) layer.bindTooltip(hinweis, { sticky: true, direction: "top", offset: [0, -8], className: "viertel-tip", opacity: 1 });
        layer.on("click", () => onSelectRef.current(v.id));
        layer.on("mouseover", () => { heben(v.id, true); onHoverRef.current?.(v.id); });
        layer.on("mouseout", () => { heben(v.id, false); onHoverRef.current?.(null); });
      };
      // Abschnittsgrenzen („Am Schmeel bis Brahmweg") und Bezugsstraßen
      // („Quartier Am Schmeel") sind nicht betroffen: keine Linie, kein Pin,
      // solange das Vorhaben einen Gegenstand hat. Nur ohne (ein Bebauungsplan
      // „zwischen A und B") stehen sie als hohle Punkte, damit das Vorhaben
      // überhaupt eine Stelle hat.
      const hatGegenstand = v.locations.some((l) => l.role === "subject");
      let schildGesetzt = false;
      for (const loc of v.locations) {
        const grenze = loc.role !== "subject";
        if (grenze && hatGegenstand) continue;
        const linie = grenze ? null : (loc.geometry as { type?: string } | null);
        // Ein Bebauungsplan bringt seinen Geltungsbereich mit (Stadt-Geodaten,
        // `kind = bplan`): gestrichelter Rand und leichte Füllung in der Farbe
        // des Stands — die Fläche, auf der etwas entsteht, das OSM noch nicht
        // kennt. Straßen-Polygone anderer Art bleiben beim Pin.
        if (linie && loc.kind === "bplan" && (linie.type === "Polygon" || linie.type === "MultiPolygon")) {
          // Rechtsverbindlich = durchgezogen; in Aufstellung = gestrichelt und
          // blasser. Der Unterschied ist die Aussage der Fläche: das eine gilt,
          // das andere ist ein Vorhaben der Verwaltung.
          const inVerfahren = loc.plan?.status === "in_procedure";
          const layer = L.geoJSON(linie as never, {
            style: { color: farbe, weight: istAktiv ? 3 : 2, dashArray: inVerfahren ? "6 4" : undefined,
              opacity: blass ? 0.2 : 0.85,
              fillColor: farbe, fillOpacity: blass ? 0.04 : istAktiv ? (inVerfahren ? 0.14 : 0.22) : (inVerfahren ? 0.08 : 0.14) },
          });
          anklicken(layer);
          gruppe.addLayer(layer);
          layer.eachLayer((l) => eintrag.pfade.push(l as import("leaflet").Path));
          planQuelle = true;
          if (istAktiv) aktivBounds = aktivBounds ? aktivBounds.extend(layer.getBounds()) : layer.getBounds();
        }
        if (linie && (linie.type === "LineString" || linie.type === "MultiLineString")) {
          const layer = L.geoJSON(linie as never, {
            style: { color: farbe, weight: istAktiv ? 7 : 5, opacity: blass ? 0.18 : 0.75, lineCap: "round" },
          });
          anklicken(layer);
          gruppe.addLayer(layer);
          layer.eachLayer((l) => eintrag.pfade.push(l as import("leaflet").Path));
          if (istAktiv) aktivBounds = aktivBounds ? aktivBounds.extend(layer.getBounds()) : layer.getBounds();
        }
        const radius = grenze ? 6 : istAktiv ? 11 : 8;
        const marker = L.marker([loc.lat, loc.lon], {
          title: grenze ? `${v.name} — Grenze: ${loc.name}` : v.name, alt: v.name,
          icon: L.divIcon({
            className: cn("ratslotse-map-point viertel-pin", istAktiv && "ist-aktiv", blass && "ist-blass", grenze && "ist-grenze"),
            html: `<span style="--point-color:${farbe};--point-size:${radius * 2}px"></span>`,
            iconSize: [radius * 2, radius * 2], iconAnchor: [radius, radius],
          }),
          zIndexOffset: istAktiv ? 1000 : 0,
        });
        anklicken(marker);
        gruppe.addLayer(marker);
        eintrag.pins.push(marker);
        if (istAktiv) {
          // Das gewählte Vorhaben trägt sein Namensschild, damit man auf der
          // Karte sieht, WAS man angeklickt hat — nicht nur, dass.
          if (!grenze && !schildGesetzt) {
            // EIN Schild je Vorhaben — bei zwei Orten nebeneinander lagen sonst
            // zwei gleiche Schilder übereinander.
            marker.bindTooltip(escapeHtml(v.name), { permanent: true, direction: "top", offset: [0, -radius - 2], className: "viertel-schild" });
            schildGesetzt = true;
          }
          const b = L.latLngBounds([loc.lat, loc.lon], [loc.lat, loc.lon]);
          aktivBounds = aktivBounds ? aktivBounds.extend(b) : b;
        }
      }
    }
    // Sperrungen der Stadt: gestrichelte Linie in Warnfarbe, darunter zur
    // Lesbarkeit ein heller Saum; ein Hinweis beim Zeigen. Blass, sobald ein
    // Vorhaben gewählt ist — dann steht dessen Linie allein.
    for (const sp of sperrungen ?? []) {
      const g = sp.geometry as { type?: string } | null;
      if (!g || (g.type !== "LineString" && g.type !== "MultiLineString")) continue;
      const blass = aktiv != null;
      const saum = L.geoJSON(g as never, { style: { color: "#fff", weight: 7, opacity: blass ? 0.3 : 0.9, lineCap: "round" }, interactive: false });
      const linie = L.geoJSON(g as never, { style: { color: SPERRUNG_FARBE, weight: 4, opacity: blass ? 0.3 : 0.9, dashArray: "8 6", lineCap: "round" } });
      const bis = sp.valid_until ? ` · bis ${escapeHtml(new Date(sp.valid_until).toLocaleDateString("de-DE"))}` : "";
      linie.bindTooltip(`<span class="stand" style="--c:${SPERRUNG_FARBE}">${escapeHtml(sp.kind_label ?? "Sperrung")}</span><b>${escapeHtml(sp.street)}</b><span class="wann">${escapeHtml(sp.reason ?? "")}${bis}</span>`,
        { sticky: true, direction: "top", offset: [0, -8], className: "viertel-tip", opacity: 1 });
      gruppe.addLayer(saum);
      gruppe.addLayer(linie);
    }
    if (aktivBounds) map.flyToBounds(aktivBounds.pad(0.6), { maxZoom: 16, duration: 0.5 });
    // Die Stadt als Quelle nennen, sobald eine ihrer Flächen auf der Karte liegt
    // (dl-de/zero verlangt keine Nennung; wir nennen sie trotzdem, weil die
    // Fläche sonst wie unsere eigene Rechnung aussähe).
    const attribution = map.attributionControl;
    if (attribution) {
      attribution.removeAttribution(PLAN_ATTRIBUTION);
      if (planQuelle) attribution.addAttribution(PLAN_ATTRIBUTION);
    }
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { zeichnen(); }, [vorhaben, sperrungen, aktiv, gedimmt]);

  return (
    <div className={cn("relative overflow-hidden rounded-2xl border border-border bg-muted", className)}>
      <div ref={ref} className="h-full w-full" aria-label={`Karte von ${ortsbereich} mit den Vorhaben`} role="region" />
    </div>
  );
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] ?? c));
}
