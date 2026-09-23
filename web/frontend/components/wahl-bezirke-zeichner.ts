import type { GeoJSON as GeoJSONLayer, LayerGroup, Map as LeafletMap, Path } from "leaflet";
import type { GeoFlaeche } from "@/lib/gebiete";
import { escapeHtml } from "@/components/viertel-zeichner";
import {
  anteilIn, deckkraft, farbe, fuehrungText, lageSatz, prozent, punkte, werNachSlug,
  type Wahlkarte, type WahlkarteBezirk,
} from "@/lib/wahlkarte";

/** Die Ebene „Wahlergebnis" auf der Leaflet-Stadtkarte
 *  (docs/plan-viertel-wahlkarte.md): die 91 Urnenbezirke in der Farbe dessen,
 *  der dort vorn lag, die Deckkraft nach dem Vorsprung.
 *
 *  - **Stadt:** alle Bezirke. Ein Tipp öffnet den Ortsbereich unter dem
 *    Finger (nicht den Bezirk) — so will es der Wunsch, und so arbeitet die
 *    Stadt-Stufe ohnehin. Der Hinweis beim Zeigen nennt den Bezirk.
 *  - **Ortsbereich:** die Bezirke, die ihn berühren, in VOLLER Form — nicht
 *    auf den Ortsbereich zugeschnitten: Ein beschnittener Bezirk 204 sähe aus
 *    wie „so hat die Innenstadt gewählt", obwohl 71 % seiner Fläche in
 *    Eversten und im Dobbenviertel liegen. Außerhalb dimmt eine Maske, die
 *    Nummer steht in der Fläche, ein Tipp wählt den Bezirk.
 *
 *  Parteifarbe als Fläche ist hier die zweite Ausnahme der Designsprache
 *  (§ 2 „Parteifarben", Tims Wunsch 23.09.2026). Sie gilt nur für die
 *  Fläche; in Tafeln und Legenden bleibt die Farbe ein Punkt.
 */
type BezirkProps = { nr: number; wb: number; name: string };
type BezirkFlaeche = GeoFlaeche<BezirkProps>;

export const WAHL_PANE = "wahlbezirke";

let geometrie: Promise<BezirkFlaeche[]> | null = null;
export function ladeWahlbezirke(): Promise<BezirkFlaeche[]> {
  geometrie ??= fetch("/geo/wahlbezirke-oldenburg.json")
    .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
    .then((j: { features: BezirkFlaeche[] }) => j.features)
    .catch((e) => { geometrie = null; throw e; });
  return geometrie;
}

export type WahlZeichnung = {
  daten: Wahlkarte;
  /** `null` = Stadt-Stufe. */
  ort: string | null;
  /** Der Umriss des Ortsbereichs für die Maske. */
  ortGeometrie?: GeoJSON.Geometry | null;
  gewaehlt: number | null;
  dunkel: boolean;
};

export class WahlBezirkeZeichner {
  private flaechen: BezirkFlaeche[] = [];
  private schicht: GeoJSONLayer | null = null;
  private stand: WahlZeichnung | null = null;

  constructor(
    private readonly L: typeof import("leaflet"),
    private readonly map: LeafletMap,
    private readonly gruppe: LayerGroup,
    private readonly rueck: { onOrtBei: (lat: number, lng: number) => void; onBezirk: (nr: number) => void },
  ) {
    if (!map.getPane(WAHL_PANE)) {
      // Unter den Pins und Linien des Viertels (overlayPane = 400), über den Kacheln.
      map.createPane(WAHL_PANE).style.zIndex = "390";
    }
  }

  async laden(): Promise<void> {
    if (!this.flaechen.length) this.flaechen = await ladeWahlbezirke();
  }

  leeren() {
    this.gruppe.clearLayers();
    this.schicht = null;
    this.stand = null;
  }

  zeichnen(z: WahlZeichnung) {
    const { L } = this;
    this.leeren();
    this.stand = z;
    if (!this.flaechen.length) return;
    const nachNr = new Map(z.daten.districts.map((d) => [d.number, d]));
    const imOrt = z.ort ? new Set(z.daten.districts.filter((d) => anteilIn(d, z.ort!) > 0).map((d) => d.number)) : null;
    const features = this.flaechen.filter((f) => !imOrt || imOrt.has(f.properties.nr));

    if (z.ort && z.ortGeometrie) {
      // Die Maske: die ganze Welt mit dem Ortsbereich als Loch — dimmt, was
      // außerhalb liegt, auch die Teile der Bezirke jenseits der Grenze.
      const welt = [[-90, -180], [-90, 180], [90, 180], [90, -180], [-90, -180]];
      const loecher = (z.ortGeometrie.type === "Polygon" ? [z.ortGeometrie.coordinates]
        : z.ortGeometrie.type === "MultiPolygon" ? z.ortGeometrie.coordinates : []).map((p) => p[0]);
      L.geoJSON({ type: "Polygon", coordinates: [welt.map(([a, b]) => [b, a]), ...loecher] } as never, {
        pane: WAHL_PANE, interactive: false,
        style: { stroke: false, fillColor: z.dunkel ? "#0b1220" : "#ffffff", fillOpacity: 0.55 },
      }).addTo(this.gruppe);
    }

    const schicht = L.geoJSON({ type: "FeatureCollection", features } as never, {
      pane: WAHL_PANE,
      style: (f) => this.stil((f as BezirkFlaeche).properties.nr, nachNr, false),
      onEachFeature: (f, layer) => {
        const nr = (f as BezirkFlaeche).properties.nr;
        const d = nachNr.get(nr);
        layer.bindTooltip(this.hinweis(d, nr, z), { sticky: true, direction: "top", offset: [0, -6], className: "viertel-tip", opacity: 1 });
        layer.on("mouseover", () => (layer as Path).setStyle(this.stil(nr, nachNr, true)));
        layer.on("mouseout", () => (layer as Path).setStyle(this.stil(nr, nachNr, false)));
        layer.on("click", (e: { latlng: { lat: number; lng: number } }) => {
          if (z.ort) this.rueck.onBezirk(nr);
          else this.rueck.onOrtBei(e.latlng.lat, e.latlng.lng);
        });
      },
    }).addTo(this.gruppe);
    this.schicht = schicht;

    if (z.ort) {
      // Die Nummer in der Fläche — mit ≤ 16 Bezirken je Ortsbereich lesbar.
      schicht.eachLayer((layer) => {
        const nr = (layer as unknown as { feature: BezirkFlaeche }).feature.properties.nr;
        const mitte = (layer as unknown as { getBounds(): { getCenter(): import("leaflet").LatLng } }).getBounds().getCenter();
        L.marker(mitte, {
          pane: WAHL_PANE, interactive: false, keyboard: false,
          icon: L.divIcon({ className: "wahl-nr", html: `<span${z.gewaehlt === nr ? ' class="an"' : ""}>${nr}</span>`, iconSize: [0, 0] }),
        }).addTo(this.gruppe);
      });
    }
  }

  private stil(nr: number, nachNr: Map<number, WahlkarteBezirk>, hell: boolean) {
    const z = this.stand!;
    const d = nachNr.get(nr);
    const wer = d?.leader ? z.daten.contestants.find((c) => c.slug === d.leader) : undefined;
    const gewaehlt = z.gewaehlt === nr;
    const blass = z.gewaehlt != null && !gewaehlt;
    let fuell = d?.counted && d.leader ? deckkraft(d.margin_pct) : 0.04;
    if (blass) fuell *= 0.35;
    if (hell) fuell = Math.min(0.9, fuell + 0.15);
    const offen = !d?.counted;
    const gleich = d?.counted && !d.leader;
    return {
      color: gewaehlt ? (z.dunkel ? "#f8fafc" : "#0f172a") : (z.dunkel ? "#0b1220" : "#ffffff"),
      weight: gewaehlt ? 2.5 : 0.8,
      opacity: 0.9,
      dashArray: offen || gleich ? "3 3" : undefined,
      fillColor: farbe(wer, z.dunkel),
      fillOpacity: fuell,
    };
  }

  private hinweis(d: WahlkarteBezirk | undefined, nr: number, z: WahlZeichnung): string {
    if (!d) return `<b>Wahlbezirk ${nr}</b>`;
    const wer = werNachSlug(z.daten);
    const listen = d.counted ? d.parties.slice(0, 3).map((p) => {
      const c = wer.get(p.slug);
      return `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:8px"><span style="display:inline-block;width:8px;height:8px;border-radius:9999px;background:${farbe(c, z.dunkel)}"></span>${escapeHtml(c?.short ?? p.slug)} ${escapeHtml(prozent(p.share_pct))}</span>`;
    }).join("") : "";
    const lage = lageSatz(d, z.ort);
    return `<b>Wahlbezirk ${nr} · ${escapeHtml(d.name)}</b>`
      + `<span class="wann" style="display:block">${escapeHtml(fuehrungText(d, wer))}${d.leader ? ` · ${escapeHtml(punkte(d.margin_pct))} Vorsprung` : ""}</span>`
      + (listen ? `<span style="display:block;margin-top:3px">${listen}</span>` : "")
      + (lage ? `<span class="leise" style="display:block;margin-top:3px">${escapeHtml(lage)}</span>` : "")
      + (z.ort ? "" : `<span class="leise" style="display:block;margin-top:3px">Tippen öffnet den Ortsbereich</span>`);
  }
}
