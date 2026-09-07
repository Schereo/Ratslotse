import type { Map as LeafletMap, Marker, MarkerClusterGroup } from "leaflet";
import type { EntityMapPoint } from "@/lib/types";
import { KIND_COLOR } from "@/components/council-map";

/** Der Zeichner der Ebene „Themen-Orte" auf der Stadtkarte
 *  (STADTKARTE-PLAN.md, Schritt 3) — die Punkte der alten Themen-Karte
 *  (`council-map.tsx`): ein Kreis je verortetem Thema oder Beschlussort,
 *  Größe nach Zahl der Beschlüsse, Farbe nach Art, nahe Punkte im Weitzoom
 *  gebündelt, Namen erst ab Zoom 14 (oder bei wenigen Punkten) direkt am
 *  Punkt, sonst als Hinweis beim Zeigen.
 *
 *  Warum eine Klasse ohne React: wie `ViertelZeichner` — die Ebene bekommt
 *  die Karte und weiß sonst nichts von der Seite. Das Cluster-Plugin muss der
 *  Aufrufer NACH Leaflet laden (`await import("leaflet.markercluster")`),
 *  es erweitert das Browser-Singleton; hier wird nur `L.markerClusterGroup`
 *  benutzt.
 */
const LABEL_ZOOM = 14;
const LABEL_MAX_POINTS = 12;

type Dir = "top" | null | undefined;
type Eintrag = { marker: Marker; label: string; hover: string; n: number; radius: number; dir: Dir };

export class ThemenOrteZeichner {
  private gruppe: MarkerClusterGroup | null = null;
  private eintraege: Eintrag[] = [];
  private readonly nachlegen = () => this.labelsLegen();

  constructor(
    private readonly L: typeof import("leaflet"),
    private readonly map: LeafletMap,
    private onOpen: (p: EntityMapPoint) => void,
  ) {
    map.on("zoomend moveend", this.nachlegen);
  }

  setOnOpen(f: (p: EntityMapPoint) => void) { this.onOpen = f; }

  leeren() {
    this.gruppe?.remove();
    this.gruppe = null;
    this.eintraege = [];
  }

  entfernen() {
    this.leeren();
    this.map.off("zoomend moveend", this.nachlegen);
  }

  zeichnen(points: EntityMapPoint[]) {
    const { L } = this;
    this.leeren();
    if (!points.length) return;
    const gruppe = L.markerClusterGroup({
      maxClusterRadius: (zoom) => (zoom <= 12 ? 55 : 40),
      disableClusteringAtZoom: 15,
      spiderfyOnMaxZoom: true,
      spiderfyDistanceMultiplier: 1.15,
      zoomToBoundsOnClick: true,
      showCoverageOnHover: false,
      removeOutsideVisibleBounds: true,
      chunkedLoading: true,
      iconCreateFunction: (cluster) => {
        const count = cluster.getChildCount();
        const size = count >= 100 ? 48 : count >= 10 ? 42 : 36;
        return L.divIcon({ html: `<span>${count}</span>`, className: "ratslotse-map-cluster", iconSize: [size, size] });
      },
    }).addTo(this.map);
    this.gruppe = gruppe;
    for (const p of points) {
      const color = KIND_COLOR[p.kind] ?? KIND_COLOR.projekt;
      const radius = Math.min(12, 4 + Math.sqrt(p.n));
      const hover = `${p.name} · ${p.n} ${p.n === 1 ? "Beschluss" : "Beschlüsse"}`;
      const marker = L.marker([p.lat, p.lon], {
        icon: L.divIcon({
          className: "ratslotse-map-point",
          html: `<span style="--point-color:${color};--point-size:${radius * 2}px"></span>`,
          iconSize: [radius * 2, radius * 2], iconAnchor: [radius, radius],
        }),
      });
      // Kein `title` — sonst stünde der native Browser-Hinweis als zweiter
      // Kasten unter dem gestalteten (s. `zeigeHover`). Der Name kommt als
      // `aria-label` ans Element, sobald es da ist: Im Bündel gibt es keins,
      // nach dem Aufklappen schon.
      marker.on("add", () => marker.getElement()?.setAttribute("aria-label", hover));
      marker.addTo(gruppe);
      marker.getElement()?.setAttribute("aria-label", hover);
      marker.on("click", () => this.onOpen(p));
      this.eintraege.push({ marker, label: p.name, hover, n: p.n, radius, dir: undefined });
    }
    this.eintraege.sort((a, b) => b.n - a.n);
    this.labelsLegen();
  }

  /** Namen an die Punkte, sobald der Zoom es hergibt — und ohne Überlappung:
   *  Wer mit einem größeren Punkt kollidiert, fällt auf den Hinweis zurück. */
  private labelsLegen() {
    const { map } = this;
    if (!this.eintraege.length) return;
    const zoomedIn = map.getZoom() >= LABEL_ZOOM || this.eintraege.length <= LABEL_MAX_POINTS;
    const size = map.getSize();
    const zeigeLabel = (m: Eintrag) => {
      m.marker.unbindTooltip();
      m.marker.bindTooltip(m.label, { permanent: true, direction: "top", offset: [0, -(m.radius + 4)], className: "themen-map-label", interactive: true });
      m.dir = "top";
    };
    const zeigeHover = (m: Eintrag) => {
      m.marker.unbindTooltip();
      m.marker.bindTooltip(m.hover, {});
      m.dir = null;
    };
    for (const m of this.eintraege) {
      let will = false;
      if (zoomedIn) {
        const pt = map.latLngToContainerPoint(m.marker.getLatLng());
        will = pt.x > -120 && pt.x < size.x + 120 && pt.y > -40 && pt.y < size.y + 60;
      }
      if (will && m.dir !== "top") zeigeLabel(m);
      else if (!will && m.dir !== null) zeigeHover(m);
    }
    if (!zoomedIn) return;
    const GAP = 3;
    type Rect = { x1: number; y1: number; x2: number; y2: number };
    const ueberlappt = (a: Rect, b: Rect) => a.x1 < b.x2 + GAP && b.x1 < a.x2 + GAP && a.y1 < b.y2 + GAP && b.y1 < a.y2 + GAP;
    const gelegt: Rect[] = [];
    for (const m of this.eintraege) {
      if (m.dir !== "top") continue;
      const el = m.marker.getTooltip()?.getElement();
      if (!el) continue;
      const b = el.getBoundingClientRect();
      const rect = { x1: b.left, y1: b.top, x2: b.right, y2: b.bottom };
      if (gelegt.some((g) => ueberlappt(g, rect))) zeigeHover(m);
      else gelegt.push(rect);
    }
  }
}
