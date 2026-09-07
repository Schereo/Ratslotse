// Die Ebenen der vereinten Stadtkarte — EINE Liste, aus der Chips, Legende,
// Zeichner und Adresse kommen (STADTKARTE-PLAN.md, Schritt 2).
//
// Eine Ebene ist etwas, das auf der Karte liegt und das man einzeln aus- und
// anschalten kann: die Vorhaben (Pins, Linien, auf der Stadt-Stufe die
// Tönung), die Bebauungspläne (Flächen), die Sperrungen (Linien). Die Karten
// der Tafel-Spalte hängen NICHT daran: Wer die Sperrungs-Linien ausschaltet,
// liest die Sperrungen weiter in der Tafel — die Ebene sagt, was die Karte
// zeigt, nicht, was es gibt.
//
// Der Stand der Chips lebt an zwei Stellen, in dieser Reihenfolge: in der
// Adresse (`?ebenen=vorhaben,plaene` — ein geteilter Link zeigt, was der
// Absender sah) und sonst im localStorage (wer die Sperrungen einmal
// ausgeschaltet hat, sieht sie beim nächsten Besuch wieder aus). Steht in der
// Adresse nichts und im Speicher nichts, gilt die Vorgabe: alles an.
//
// Spätere Ebenen (Themen-Orte, Beteiligungen, Wahlergebnis) sind je ein
// Eintrag hier — die Chips, die Adresse und der Speicher kennen sie dann.

export type EbenenId = "vorhaben" | "plaene" | "sperrungen" | "themen-orte";

export type Ebene = {
  id: EbenenId;
  label: string;
  /** Farbe des Chip-Punkts. Vorhaben tragen Stand-Farben, der Chip nimmt Hafenblau. */
  farbe: string;
  /** Punkt mit gestricheltem Ring (Planflächen sind Umrisse, keine Punkte). */
  gestrichelt?: boolean;
  /** Auf welchen Stufen die Ebene etwas zeichnet. */
  stufen: ("city" | "district")[];
  /** Woher die Daten kommen — steht im Tooltip des Chips. */
  quelle: string;
};

export const EBENEN: readonly Ebene[] = [
  { id: "vorhaben", label: "Vorhaben", farbe: "#0a63a8", stufen: ["city", "district"], quelle: "aus den Beschlüssen des Rats, letzte zwei Jahre" },
  { id: "plaene", label: "Bebauungspläne", farbe: "#15803d", gestrichelt: true, stufen: ["district"], quelle: "Geltungsbereiche, Stadt Oldenburg (Geoportal)" },
  { id: "sperrungen", label: "Sperrungen", farbe: "#b45309", stufen: ["district"], quelle: "Verkehrsbehörde, Stadt Oldenburg (Geoportal), täglich" },
  // Die Punkte der alten Themen-Karte: verortete Themen und Beschlussorte
  // über ALLE Jahre. In der Vorgabe aus — sie sind das andere Vokabular
  // (Themen statt Vorhaben) und lägen sonst über den Pins des Viertels.
  { id: "themen-orte", label: "Themen-Orte", farbe: "#7c3aed", stufen: ["city", "district"], quelle: "Orte und Themen aus allen Beschlüssen, nach Zahl gewichtet" },
] as const;

export const ALLE_EBENEN: readonly EbenenId[] = EBENEN.map((e) => e.id);
/** Was ohne Adresse und Speicher an ist: die Ebenen des Viertels. Die
 *  Themen-Orte schaltet man dazu. */
export const VORGABE: ReadonlySet<EbenenId> = new Set<EbenenId>(["vorhaben", "plaene", "sperrungen"]);

const SCHLUESSEL = "karte.ebenen";

export function istEbene(x: string): x is EbenenId {
  return (ALLE_EBENEN as readonly string[]).includes(x);
}

/** `?ebenen=vorhaben,plaene` → Set. Unbekannte Namen fallen weg, ein leerer
 *  Parameter (`?ebenen=`) heißt „keine". Ohne Parameter: `null` (= nicht gesetzt). */
export function ebenenAusUrl(param: string | null): Set<EbenenId> | null {
  if (param == null) return null;
  return new Set(param.split(",").map((s) => s.trim()).filter(istEbene));
}

/** Set → Parameter-Wert; `null`, wenn die Vorgabe gilt (dann bleibt die
 *  Adresse sauber). Die Reihenfolge ist die der Registry, nicht die des Klicks. */
export function ebenenZuUrl(ebenen: ReadonlySet<EbenenId>): string | null {
  if (ebenen.size === VORGABE.size && [...VORGABE].every((e) => ebenen.has(e))) return null;
  return ALLE_EBENEN.filter((e) => ebenen.has(e)).join(",");
}

/** Der gemerkte Stand — oder `null`, wenn nichts gemerkt ist (oder der
 *  Speicher gesperrt ist: privates Fenster, voll). */
export function ebenenAusSpeicher(): Set<EbenenId> | null {
  if (typeof window === "undefined") return null;
  try {
    const roh = window.localStorage.getItem(SCHLUESSEL);
    if (roh == null) return null;
    const liste = JSON.parse(roh) as unknown;
    return new Set(Array.isArray(liste) ? liste.filter((x): x is EbenenId => typeof x === "string" && istEbene(x)) : []);
  } catch {
    return null;
  }
}

export function ebenenMerken(ebenen: ReadonlySet<EbenenId>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SCHLUESSEL, JSON.stringify(ALLE_EBENEN.filter((e) => ebenen.has(e))));
  } catch {
    /* kein Gedächtnis ist kein Fehler */
  }
}

/** Der Anfangsstand: Adresse vor Speicher vor Vorgabe. */
export function ebenenStart(param: string | null): Set<EbenenId> {
  return ebenenAusUrl(param) ?? ebenenAusSpeicher() ?? new Set(VORGABE);
}

export function ebeneUmschalten(ebenen: ReadonlySet<EbenenId>, id: EbenenId): Set<EbenenId> {
  const neu = new Set(ebenen);
  if (neu.has(id)) neu.delete(id); else neu.add(id);
  return neu;
}
