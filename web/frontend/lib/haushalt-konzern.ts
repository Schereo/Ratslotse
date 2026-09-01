// Der Konzern Stadt Oldenburg — Typen und Rechenwege für /haushalt/konzern.
//
// Die Seite beantwortet eine einzige Frage: Was der Haushalts-Bereich zeigt,
// ist die Kernverwaltung — wie groß ist der Teil, der fehlt? Alles hier dient
// dieser Differenz.
//
// EINE FALLE VORWEG, die jeden Rechenweg betrifft: Die Summe der
// Aufgabenträger ist NICHT die Konzernsumme. Dazwischen steht die
// Konsolidierung — die Verrechnung der Geschäfte, die die Träger
// untereinander machen (die Stadt zahlt dem Klinikum einen Zuschuss, der
// Eigenbetrieb vermietet der Stadt ein Schulgebäude). Diese Beträge stünden
// sonst doppelt in der Rechnung. Sie ist deshalb immer eine eigene Zeile mit
// negativem Vorzeichen, nie ein stiller Abzug irgendwo.

/** Woher eine Zeile kommt — das gemeinsame Format aller Finanz-Schichten.
 *  Nachgeschlagen wird über die `herkunft_id` der Datenzeile. Definition und
 *  Begründung, warum sie NICHT je Bereich ausgeschrieben wird, in
 *  `lib/herkunft.ts`. */
import type { Herkunft } from "@/lib/herkunft";

export type { Herkunft };

export type KonzernJahr = {
  year: number;
  revenues_total?: number;
  expenses_total?: number;
  ordinary_result?: number;
  total_result?: number;
  interest_expenses?: number;
  personnel_expenses?: number;
  taxes?: number;
  herkunft_id: number | null;
};

export type KonzernTraeger = {
  year: number;
  art: "revenues" | "expenses";
  entity_key: string;
  entity: string;
  /** Euro — aus TEUR hochgerechnet, deshalb auf Tausend glatt. */
  amount: number;
  prior_year: number | null;
  herkunft_id: number | null;
};

export type KonzernPosten = {
  year: number;
  nr: number;
  label: string;
  role: string | null;
  amount: number;
  prior_year: number | null;
  herkunft_id: number | null;
};

export type Gegenprobe = {
  year: number;
  art: "revenues" | "expenses";
  konzern: number;
  jahresabschluss: number;
  ok: boolean;
};

export type KonzernDaten = {
  years: number[];
  konzern: KonzernJahr[];
  entity: KonzernTraeger[];
  posten: KonzernPosten[];
  gegenprobe: Gegenprobe[];
  /** Nach `herkunft_id`. Die beiden Ebenen eines Jahrgangs tragen
   *  verschiedene IDs — verschiedene Abschnitte, verschiedene Proben. */
  herkunft: Record<string, Herkunft>;
};

export function herkunftVon(daten: KonzernDaten,
                            id: number | null | undefined): Herkunft | null {
  return id == null ? null : daten.herkunft[String(id)] ?? null;
}

/** Die Zeile „Konsolidierung" ist kein Aufgabenträger, sondern der Abzug.
 *  Sie gehört in jede Rechnung, aber in keine Rangliste. */
export const KONSOLIDIERUNG = "konsolidierung";

/** Kurznamen für die Balkenbeschriftung. Der Bericht schreibt „Klinikum
 *  Oldenburg AöR -Teilkonzern-"; auf 320 px Breite bleibt davon nichts übrig. */
export const KURZ: Record<string, string> = {
  stadt: "Kernverwaltung",
  klinikum: "Klinikum",
  vwg: "Verkehr und Wasser",
  egh: "Gebäudewirtschaft",
  awb: "Abfallwirtschaft",
  bbo: "Bäderbetrieb",
  bbgo: "Bäderbetriebsgesellschaft",
  weh: "Weser-Ems Halle",
  konsolidierung: "Verrechnung untereinander",
};

/** Was die Träger jeweils sind — die Antwort auf „wieso zählt das mit?". */
export const ART: Record<string, string> = {
  stadt: "Die Stadtverwaltung selbst — das, was der Haushalt abbildet.",
  klinikum: "Anstalt des öffentlichen Rechts, der Stadt gehörend.",
  vwg: "Stadtwerke-Tochter: Busse und Wasserversorgung.",
  egh: "Eigenbetrieb: Schulen, Rathäuser, städtische Gebäude.",
  awb: "Eigenbetrieb: Müllabfuhr und Entsorgung.",
  bbo: "Eigenbetrieb: die städtischen Bäder.",
  bbgo: "Gesellschaft, die den Betrieb der Bäder führt.",
  weh: "Veranstaltungshallen, städtische Beteiligung.",
};

export function jahrDaten(daten: KonzernDaten, year: number): KonzernJahr | null {
  return daten.konzern.find((k) => k.year === year) ?? null;
}

/** Träger eines Jahres und einer Aufstellung, größter zuerst — ohne die
 *  Konsolidierungszeile, die separat danebensteht. */
export function traegerListe(
  daten: KonzernDaten, year: number, art: "revenues" | "expenses",
): KonzernTraeger[] {
  return daten.entity
    .filter((t) => t.year === year && t.art === art && t.entity_key !== KONSOLIDIERUNG)
    .sort((a, b) => b.amount - a.amount);
}

export function konsolidierung(
  daten: KonzernDaten, year: number, art: "revenues" | "expenses",
): KonzernTraeger | null {
  return daten.entity.find(
    (t) => t.year === year && t.art === art && t.entity_key === KONSOLIDIERUNG) ?? null;
}

/** Jahre, für die die Trägeraufstellung vorliegt — nicht dieselben wie
 *  `daten.years`: Die Berichte bis 2016 führen den Abschnitt noch nicht, und
 *  2018 ist die Aufwendungsseite an ihrer eigenen Probe gescheitert. */
export function traegerJahre(daten: KonzernDaten,
                             art?: "revenues" | "expenses"): number[] {
  const years = daten.entity
    .filter((t) => !art || t.art === art)
    .map((t) => t.year);
  return [...new Set(years)].sort((a, b) => a - b);
}

/** Der Anteil, den der Kernhaushalt am Konzern hat — die Zahl, um die es auf
 *  dieser Seite geht. `null`, wo die Trägeraufstellung fehlt: Ohne die
 *  Kernverwaltungs-Zeile ist der Anteil nicht bestimmbar, und ein geschätzter
 *  wäre hier das Gegenteil des Zwecks. */
export function kernAnteil(
  daten: KonzernDaten, year: number, art: "revenues" | "expenses" = "revenues",
): { kern: number; konzern: number; anteil: number } | null {
  const jd = jahrDaten(daten, year);
  const konzern = art === "revenues" ? jd?.revenues_total : jd?.expenses_total;
  const kern = daten.entity.find(
    (t) => t.year === year && t.art === art && t.entity_key === "stadt");
  if (!konzern || !kern) return null;
  return { kern: kern.amount, konzern, anteil: kern.amount / konzern };
}

/** Das jüngste Jahr, für das sich der Anteil überhaupt bilden lässt. */
export function juengstesVergleichsjahr(daten: KonzernDaten): number | null {
  const years = traegerJahre(daten, "revenues");
  return years.length ? years[years.length - 1] : null;
}
