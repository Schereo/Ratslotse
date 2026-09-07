import type { LayerGroup, Map as LeafletMap, Marker, Path } from "leaflet";

/** Der Zeichner der Viertel-Stufe: Pins, Straßenlinien, Planflächen und
 *  Sperrungen auf einer Leaflet-Karte — mit Hover, Namensschild und der
 *  Kopplung zur Liste.
 *
 *  **Warum eine Klasse ohne React.** Bis 07.09.2026 lebte das alles in
 *  `viertel-karte.tsx`. Die vereinte Stadtkarte (`STADTKARTE-PLAN.md`,
 *  Richtung A) zeichnet auf ihrer Viertel-Stufe genau dasselbe, nur auf
 *  einer Karte, die vorher die ganze Stadt zeigte. Zwei Komponenten mit
 *  demselben Zeichencode wären zwei Wahrheiten; der Zeichner ist deshalb
 *  eine Klasse, die eine Karte und eine Ebenengruppe bekommt und sonst
 *  nichts von der Seite weiß. `ViertelKarte` (die alte Seite) und
 *  `StadtKarte` (die neue Bühne) benutzen dieselbe Instanz.
 *
 *  Die Punkte bleiben HTML-Kreise, es werden keine Marker-Bilder
 *  nachgeladen (CSP bleibt auf die Kacheln begrenzt).
 */
export type KartenVorhaben = {
  id: number;
  name: string;
  stage: string;
  when: string | null;
  locations: { slug: string; name: string; kind: string; lat: number; lon: number; geometry: unknown; role?: string; plan?: { status: string } }[];
};

/** Eine laufende Sperrung der Stadt — Linie in Warnfarbe, nicht wählbar. */
export type KartenSperrung = {
  id: number; street: string; reason: string | null; kind_label: string | null;
  valid_until: string | null; geometry: unknown; lat: number | null; lon: number | null;
};

/** Stand → Farbe. Dieselben Töne wie die Badges der Liste, damit Pin und
 *  Karte dasselbe sagen. */
export const STAND_FARBE: Record<string, string> = {
  building: "#f0641c", decided: "#15803d", planning: "#0a63a8", idea: "#64748b", done: "#94a3b8", rejected: "#b91c1c",
};
export const STAND_LABEL: Record<string, string> = {
  building: "Im Bau", decided: "Beschlossen", planning: "In Planung", idea: "Idee", done: "Fertig", rejected: "Abgelehnt",
};
export const SPERRUNG_FARBE = "#b45309";
export const BETEILIGUNG_FARBE = "#e8590c";
/** Leaflet-Ebene der Beteiligungen, über den übrigen Überlagerungen (400), unter den Pins (600). */
const MITREDEN_PANE = "mitreden";

/** Eine laufende Beteiligung mit Fläche — der Geltungsbereich des Plans;
 *  ein Tipp öffnet die Beteiligung bei der Stadt. */
export type KartenBeteiligung = {
  title: string | null; step: string | null; valid_until: string | null; url: string | null;
  geometry: unknown; plan_nr: string | null;
};
/** Quellenzeile der Stadt-Ebenen — nur, was gerade wirklich auf der Karte
 *  liegt, wird genannt. (Die Ebenen selbst stehen in `lib/karten-ebenen.ts`.) */
export const PLAN_ATTRIBUTION = "Bebauungspläne: Stadt Oldenburg (Geoportal)";
export const SPERRUNG_ATTRIBUTION = "Sperrungen: Stadt Oldenburg (Geoportal)";

/** Welche Ebenen der Zeichner malt. Fehlt das Feld, gilt: alles. */
export type ZeichnerEbenen = { vorhaben?: boolean; plaene?: boolean; sperrungen?: boolean; beteiligungen?: boolean };

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] ?? c));
}

type Ebenen = { pins: Marker[]; pfade: Path[]; farbe: string; aktiv: boolean };

export type ZeichnerRueckrufe = {
  onSelect: (id: number) => void;
  onHover?: (id: number | null) => void;
};

export type ZeichnerStand = {
  vorhaben: KartenVorhaben[];
  sperrungen?: KartenSperrung[];
  beteiligungen?: KartenBeteiligung[];
  aktiv: number | null;
  gedimmt: Set<number>;
  ebenen?: ZeichnerEbenen;
};

export class ViertelZeichner {
  private ebenen = new Map<number, Ebenen>();

  constructor(
    private readonly L: typeof import("leaflet"),
    private readonly map: LeafletMap,
    private readonly gruppe: LayerGroup,
    private rueckrufe: ZeichnerRueckrufe,
  ) {}

  /** Die Rückrufe wechseln mit jedem Render der Seite — hier stets die jüngsten. */
  setRueckrufe(r: ZeichnerRueckrufe) { this.rueckrufe = r; }

  /** Ein Vorhaben heben oder senken — Pin-Klasse und Strichstärke, ohne
   *  Neuzeichnen (ein Neuzeichnen bei jedem Zeigerwechsel ließe offene
   *  Hinweise zuklappen). Das aktive bleibt, wie es ist: Es steht ohnehin vorn. */
  heben(id: number, an: boolean) {
    const e = this.ebenen.get(id);
    if (!e) return;
    for (const pin of e.pins) pin.getElement()?.classList.toggle("ist-schwebt", an);
    if (e.aktiv) return;
    for (const pfad of e.pfade) {
      if (an) {
        // Die Ruhe-Werte EINMAL merken, bevor gehoben wird: Leaflets
        // `setStyle` schreibt in `options` — wer die Basis von dort liest,
        // liest beim zweiten Zeigen schon die gehobene Stärke, und die Linie
        // wird mit jedem Hover dicker (Tims Befund 07.09.2026). Das Senken
        // stellt die gemerkten Werte wieder her, auch die Deckkraft einer
        // blassen Linie.
        if (!this.ruhe.has(pfad)) this.ruhe.set(pfad, { weight: pfad.options.weight, opacity: pfad.options.opacity });
        const ruhe = this.ruhe.get(pfad)!;
        pfad.setStyle({ weight: (ruhe.weight ?? 5) + 2, opacity: 1 });
        pfad.bringToFront();
      } else {
        const ruhe = this.ruhe.get(pfad);
        if (!ruhe) continue;
        pfad.setStyle({ weight: ruhe.weight ?? 5, opacity: ruhe.opacity ?? 0.75 });
        this.ruhe.delete(pfad);
      }
    }
  }

  /** Strichstärke und Deckkraft eines Pfads vor dem Heben — je gehobenem Pfad,
   *  bis er gesenkt ist. Neu gezeichnete Pfade sind neue Objekte, alte Einträge
   *  fallen mit ihnen weg. */
  private ruhe = new WeakMap<Path, { weight?: number; opacity?: number }>();

  /** Grenzen des aktiven Vorhabens nach dem letzten Zeichnen — die Karte
   *  fährt dorthin (wer das will). */
  aktivBounds: ReturnType<typeof import("leaflet").latLngBounds> | null = null;

  leeren() {
    this.gruppe.clearLayers();
    this.ebenen = new Map();
    this.aktivBounds = null;
    this.map.attributionControl?.removeAttribution(PLAN_ATTRIBUTION);
    this.map.attributionControl?.removeAttribution(SPERRUNG_ATTRIBUTION);
  }

  /** Alles neu zeichnen — je nach `ebenen` nur einen Teil. Gibt zurück, ob
   *  eine Planfläche der Stadt liegt (für die Quellenzeile). */
  zeichnen({ vorhaben, sperrungen, beteiligungen, aktiv, gedimmt, ebenen }: ZeichnerStand): boolean {
    const { L, gruppe } = this;
    this.leeren();
    const zeigeVorhaben = ebenen?.vorhaben ?? true;
    const zeigePlaene = ebenen?.plaene ?? true;
    const zeigeSperrungen = ebenen?.sperrungen ?? true;
    const zeigeBeteiligungen = ebenen?.beteiligungen ?? true;
    let aktivBounds: ReturnType<typeof L.latLngBounds> | null = null;
    let planQuelle = false;
    // Ohne die Vorhaben-Ebene bleiben Pins und Linien weg — die Planflächen
    // hängen aber an den Vorhaben und dürfen allein stehen (ein Plan ohne
    // Pin ist immer noch eine Fläche, die etwas sagt).
    for (const v of vorhaben) {
      if (!zeigeVorhaben && !zeigePlaene) break;
      const farbe = STAND_FARBE[v.stage] ?? STAND_FARBE.planning;
      const istAktiv = v.id === aktiv;
      // Blass, was der Stand-Filter ausblendet — und alles andere, sobald ein
      // Vorhaben ausgewählt ist: Dessen Linie soll allein stehen.
      const blass = (gedimmt.has(v.id) || aktiv != null) && !istAktiv;
      // Alles, was aus der Datenbank kommt, wird maskiert — auch „wann" und
      // der Stand stammen aus einer Modellantwort, nicht aus dem Code.
      const hinweis = `<span class="stand" style="--c:${escapeHtml(farbe)}">${escapeHtml(STAND_LABEL[v.stage] ?? v.stage)}</span>${v.when ? `<span class="wann">${escapeHtml(v.when)}</span>` : ""}<b>${escapeHtml(v.name)}</b>`;
      const eintrag: Ebenen = { pins: [], pfade: [], farbe, aktiv: istAktiv };
      this.ebenen.set(v.id, eintrag);
      // Ein Tipp WÄHLT das Vorhaben (Detail in Seitenspalte bzw. Sheet); der
      // Hinweis mit Name und Stand steht beim Zeigen (Tooltip), das gewählte
      // Vorhaben trägt sein Namensschild dauerhaft (s. u.).
      const anklicken = (layer: import("leaflet").Layer) => {
        if (!istAktiv) layer.bindTooltip(hinweis, { sticky: true, direction: "top", offset: [0, -8], className: "viertel-tip", opacity: 1 });
        layer.on("click", () => this.rueckrufe.onSelect(v.id));
        layer.on("mouseover", () => { this.heben(v.id, true); this.rueckrufe.onHover?.(v.id); });
        layer.on("mouseout", () => { this.heben(v.id, false); this.rueckrufe.onHover?.(null); });
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
        // `kind = bplan`): rechtsverbindlich durchgezogen, in Aufstellung
        // gestrichelt und blasser — die Fläche, auf der etwas entsteht, das
        // OSM noch nicht kennt.
        if (zeigePlaene && linie && loc.kind === "bplan" && (linie.type === "Polygon" || linie.type === "MultiPolygon")) {
          const inVerfahren = loc.plan?.status === "in_procedure";
          const layer = L.geoJSON(linie as never, {
            style: { color: farbe, weight: istAktiv ? 3 : 2, dashArray: inVerfahren ? "6 4" : undefined,
              opacity: blass ? 0.2 : 0.85,
              fillColor: farbe, fillOpacity: blass ? 0.04 : istAktiv ? (inVerfahren ? 0.14 : 0.22) : (inVerfahren ? 0.08 : 0.14) },
          });
          anklicken(layer);
          gruppe.addLayer(layer);
          layer.eachLayer((l) => eintrag.pfade.push(l as Path));
          planQuelle = true;
          if (istAktiv) aktivBounds = aktivBounds ? aktivBounds.extend(layer.getBounds()) : layer.getBounds();
        }
        if (!zeigeVorhaben) continue;
        if (linie && (linie.type === "LineString" || linie.type === "MultiLineString")) {
          const layer = L.geoJSON(linie as never, {
            style: { color: farbe, weight: istAktiv ? 7 : 5, opacity: blass ? 0.18 : 0.75, lineCap: "round" },
          });
          anklicken(layer);
          gruppe.addLayer(layer);
          layer.eachLayer((l) => eintrag.pfade.push(l as Path));
          if (istAktiv) aktivBounds = aktivBounds ? aktivBounds.extend(layer.getBounds()) : layer.getBounds();
        }
        const radius = grenze ? 6 : istAktiv ? 11 : 8;
        const klassen = ["ratslotse-map-point", "viertel-pin", istAktiv && "ist-aktiv", blass && "ist-blass", grenze && "ist-grenze"].filter(Boolean).join(" ");
        const marker = L.marker([loc.lat, loc.lon], {
          icon: L.divIcon({
            className: klassen,
            html: `<span style="--point-color:${farbe};--point-size:${radius * 2}px"></span>`,
            iconSize: [radius * 2, radius * 2], iconAnchor: [radius, radius],
          }),
          zIndexOffset: istAktiv ? 1000 : 0,
        });
        // KEIN `title`: Der Pin trägt schon den gestalteten Hinweis (s.
        // `anklicken`), und der native Browser-Hinweis stand als zweiter,
        // dunkler Kasten darunter (Tims Befund 07.09.2026). Der Name muss
        // trotzdem dran — Leaflet macht aus dem Pin ein `role="button"` mit
        // `tabindex`, und ein Knopf ohne Namen ist für die Sprachausgabe
        // stumm. `alt` hilft nicht: Das setzt Leaflet als JS-Eigenschaft, und
        // an einem `div` ist sie wirkungslos (im DOM nachgesehen).
        const name = grenze ? `${v.name} — Grenze: ${loc.name}` : v.name;
        const benennen = () => marker.getElement()?.setAttribute("aria-label", name);
        marker.on("add", benennen);
        anklicken(marker);
        gruppe.addLayer(marker);
        benennen();
        eintrag.pins.push(marker);
        if (istAktiv) {
          // Das gewählte Vorhaben trägt sein Namensschild — EIN Schild je
          // Vorhaben, bei zwei Orten nebeneinander lagen sonst zwei übereinander.
          if (!grenze && !schildGesetzt) {
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
    let sperrQuelle = false;
    for (const sp of zeigeSperrungen ? sperrungen ?? [] : []) {
      const g = sp.geometry as { type?: string } | null;
      if (!g || (g.type !== "LineString" && g.type !== "MultiLineString")) continue;
      sperrQuelle = true;
      const blass = aktiv != null;
      const saum = L.geoJSON(g as never, { style: { color: "#fff", weight: 7, opacity: blass ? 0.3 : 0.9, lineCap: "round" }, interactive: false });
      const linie = L.geoJSON(g as never, { style: { color: SPERRUNG_FARBE, weight: 4, opacity: blass ? 0.3 : 0.9, dashArray: "8 6", lineCap: "round" } });
      const bis = sp.valid_until ? ` · bis ${escapeHtml(new Date(sp.valid_until).toLocaleDateString("de-DE"))}` : "";
      linie.bindTooltip(`<span class="stand" style="--c:${SPERRUNG_FARBE}">${escapeHtml(sp.kind_label ?? "Sperrung")}</span><b>${escapeHtml(sp.street)}</b><span class="wann">${escapeHtml(sp.reason ?? "")}${bis}</span>`,
        { sticky: true, direction: "top", offset: [0, -8], className: "viertel-tip", opacity: 1 });
      gruppe.addLayer(saum);
      gruppe.addLayer(linie);
    }
    // Beteiligungen: der Geltungsbereich des Plans, punktiert in Signal-Orange
    // mit leichter Füllung, darunter der Plan der Stadt. Ein Tipp öffnet die
    // Beteiligung bei der Stadt — das ist die Handlung, um die es hier geht.
    // Sie liegen in einer eigenen Ebene ÜBER den Vorhaben-Flächen: Das
    // Zeigen auf ein Vorhaben holt dessen Pfad nach vorn (`heben`) und
    // ließe die Beteiligung sonst dauerhaft darunter verschwinden — der
    // Geltungsbereich ist meist derselbe Umriss wie der Plan des Vorhabens.
    if (zeigeBeteiligungen && beteiligungen?.length && !this.map.getPane(MITREDEN_PANE)) {
      this.map.createPane(MITREDEN_PANE).style.zIndex = "450";
    }
    for (const b of zeigeBeteiligungen ? beteiligungen ?? [] : []) {
      const g = b.geometry as { type?: string } | null;
      if (!g || (g.type !== "Polygon" && g.type !== "MultiPolygon")) continue;
      const blass = aktiv != null;
      // Ein weißer Saum unter der Punktlinie, wie bei den Sperrungen: Der
      // Geltungsbereich liegt meist genau auf dem Umriss des Plans (grün,
      // zwei Pixel) — ohne Saum gehen die Punkte darin unter (Donnerschwee,
      // Plan 831 gemessen).
      const saum = L.geoJSON(g as never, { pane: MITREDEN_PANE, style: { color: "#fff", weight: 7, opacity: blass ? 0.3 : 0.9, lineCap: "round", fill: false }, interactive: false });
      gruppe.addLayer(saum);
      const layer = L.geoJSON(g as never, {
        pane: MITREDEN_PANE,
        style: { color: BETEILIGUNG_FARBE, weight: 4, dashArray: "1 8", lineCap: "round", opacity: blass ? 0.3 : 0.95,
          fillColor: BETEILIGUNG_FARBE, fillOpacity: blass ? 0.03 : 0.1 },
      });
      const bis = b.valid_until ? `bis ${escapeHtml(new Date(b.valid_until).toLocaleDateString("de-DE"))}` : "";
      layer.bindTooltip(`<span class="stand" style="--c:${BETEILIGUNG_FARBE}">Mitreden</span>${bis ? `<span class="wann">${bis}</span>` : ""}<b>${escapeHtml(b.title ?? "Beteiligung")}</b>${b.step ? `<span class="wann" style="color:inherit;font-weight:400">${escapeHtml(b.step)}</span>` : ""}`,
        { sticky: true, direction: "top", offset: [0, -8], className: "viertel-tip", opacity: 1 });
      if (b.url) layer.on("click", () => window.open(b.url ?? "", "_blank", "noopener"));
      gruppe.addLayer(layer);
      planQuelle = true;
    }
    this.aktivBounds = aktivBounds;
    // Die Stadt als Quelle nennen, sobald eine ihrer Ebenen auf der Karte liegt.
    if (planQuelle) this.map.attributionControl?.addAttribution(PLAN_ATTRIBUTION);
    if (sperrQuelle) this.map.attributionControl?.addAttribution(SPERRUNG_ATTRIBUTION);
    return planQuelle;
  }
}
