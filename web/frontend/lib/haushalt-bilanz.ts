// Die Bilanz der Stadt (/haushalt/schulden, unterer Teil) — Typen und Rechenwege.
//
// ZWEI ZAHLEN HEISSEN „DIE PENSIONSRÜCKSTELLUNGEN", und sie unterscheiden
// sich um 45 Mio. €. Die Bilanz führt untereinander:
//
//   3.1    Pensionsrückstellungen und ähnliche Verpflichtungen  311.789.660,00
//   3.1.1  Pensionsrückstellungen                               266.259.316,00
//   3.1.2  Beihilferückstellungen                                45.530.344,00
//
// Beide stimmen, sie messen nur Verschiedenes: 3.1 schließt die Beihilfe ein,
// 3.1.1 nicht. Deshalb heißen die Rollen hier `pensionen_gesamt` und
// `pensionsrueckstellungen` und nicht etwa beide „pension" — wer sie
// verwechselt, schreibt eine falsche Schlagzeile.

import type { Herkunft } from "@/lib/herkunft";

export type { Herkunft };

/** Die Rollen, die `council/bilanz.py` vergibt. Stabil über alle drei
 *  Layouts der Bilanz hinweg — anders als die Gliederungsnummer, die bis
 *  2020 römisch ist und ab 2021 auf beiden Seiten dieselbe. */
export type BilanzRolle =
  | "intangible_assets" | "tangible_assets" | "infrastructure_assets"
  | "financial_assets" | "cash_and_equivalents" | "prepaid_expenses"
  | "net_position" | "reserves_total" | "ordinary_surplus_reserve"
  | "annual_result_balance_sheet" | "special_items" | "liabilities" | "financial_liabilities"
  | "provisions" | "pension_and_similar_provisions" | "pension_provisions"
  | "healthcare_allowance_provisions" | "deferred_income";

export type BilanzPosten = {
  year: number;
  role: BilanzRolle;
  page: "aktiva" | "passiva";
  /** 1 = Hauptposten; nur diese ergeben zusammen die Bilanzsumme. */
  level: number;
  /** Gliederungsnummer des Dokuments — für die Anzeige, nicht als Schlüssel. */
  nr: string | null;
  /** Wortlaut des Dokuments. */
  label: string;
  value: number;
  herkunft_id: number | null;
};

/** Was die Verwaltung zu einem Hauptposten schreibt (Anhang 6.2.1–6.2.9).
 *
 *  Für `schulden` ist das keine Zugabe, sondern die Bedingung, unter der die
 *  Zahl überhaupt gezeigt werden darf — s. `cashPoolingHinweis`. */
export type BilanzErlaeuterung = {
  year: number;
  role: BilanzRolle;
  nr: number;
  heading: string;
  text: string;
  herkunft_id: number | null;
};

export type BilanzDaten = {
  years: number[];
  items: BilanzPosten[];
  explanations: BilanzErlaeuterung[];
  provenance: Record<string, Herkunft>;
};

/** Ein Bilanzstichtag, nach Rolle nachschlagbar. */
export type Stichtag = {
  year: number;
  posten: Partial<Record<BilanzRolle, BilanzPosten>>;
  /** Summe der Hauptposten — beide Seiten ergeben sie, das ist die Probe. */
  bilanzsumme: number;
  herkunft_id: number | null;
};

/** Die neun Hauptposten in Bilanzreihenfolge: erst was die Stadt hat, dann
 *  wem es zusteht. Dieselbe Reihenfolge wie `bilanz.PFLICHT_ROLLEN` im
 *  Backend — und dieselbe, in der der Anhang sie erläutert. */
export const AKTIVA_HAUPT: BilanzRolle[] = [
  "intangible_assets", "tangible_assets", "financial_assets",
  "cash_and_equivalents", "prepaid_expenses",
];
export const PASSIVA_HAUPT: BilanzRolle[] = [
  "net_position", "liabilities", "provisions", "deferred_income",
];

/** Kurznamen für die Legende. Der Wortlaut des Dokuments („Aktive
 *  Rechnungsabgrenzung") ist korrekt, aber in einer Balkenlegende unlesbar;
 *  er steht deshalb weiter in `label` und wird in der Tabelle
 *  darunter gezeigt. */
export const KURZ: Partial<Record<BilanzRolle, string>> = {
  intangible_assets: "Immaterielles",
  tangible_assets: "Gebäude, Straßen, Grundstücke",
  financial_assets: "Beteiligungen und Forderungen",
  cash_and_equivalents: "Kasse",
  prepaid_expenses: "Abgrenzung",
  net_position: "Eigenkapital",
  liabilities: "Schulden",
  provisions: "Rückstellungen",
  deferred_income: "Abgrenzung",
};

/** Den jüngsten Stichtag herausziehen — oder `null`, wenn keiner vollständig
 *  ist. Unvollständig heißt hier: Ein Hauptposten fehlt, dann geht die
 *  Bilanzsumme nicht auf und es gibt nichts zu zeigen. */
export function juengsterStichtag(daten: BilanzDaten | null): Stichtag | null {
  if (!daten?.years?.length) return null;
  const year = daten.years[daten.years.length - 1];
  return as_of_date(daten, year);
}

export function as_of_date(daten: BilanzDaten | null, year: number): Stichtag | null {
  if (!daten) return null;
  const posten: Partial<Record<BilanzRolle, BilanzPosten>> = {};
  for (const p of daten.items) {
    if (p.year === year) posten[p.role] = p;
  }
  const haupt = [...AKTIVA_HAUPT, ...PASSIVA_HAUPT];
  if (haupt.some((r) => posten[r] === undefined)) return null;
  const bilanzsumme = AKTIVA_HAUPT.reduce((n, r) => n + (posten[r]?.value ?? 0), 0);
  return {
    year, posten, bilanzsumme,
    herkunft_id: posten.tangible_assets?.herkunft_id ?? null,
  };
}

/** Die Segmente einer Bilanzseite, absteigend nach Betrag — in Mio. €.
 *
 *  Absteigend und nicht in Dokumentreihenfolge: Der <Gegenbalken> verteilt
 *  seine Rampe dunkel nach hell in der übergebenen Reihenfolge, und ein
 *  0,6-%-Posten als dunkelstes Segment ganz links wäre eine Betonung, die
 *  der Betrag nicht trägt. */
export function segmente(s: Stichtag, page: "aktiva" | "passiva") {
  const roles = page === "aktiva" ? AKTIVA_HAUPT : PASSIVA_HAUPT;
  return roles
    .map((r) => ({
      label: KURZ[r] ?? s.posten[r]?.label ?? r,
      kurz: KURZ[r],
      value: (s.posten[r]?.value ?? 0) / 1e6,
      role: r,
    }))
    .filter((x) => x.value > 0)
    .sort((a, b) => b.value - a.value);
}

/** Wie oft die Pensionsrückstellungen in die Kreditschulden passen.
 *
 *  Gerechnet und nicht geschrieben: „das Siebenfache" wird mit dem nächsten
 *  Jahrgang still falsch. Gibt `null`, wenn eine der beiden Zahlen fehlt
 *  oder die Geldschulden null sind. */
export function vielfaches(s: Stichtag): number | null {
  const pension = s.posten.pension_and_similar_provisions?.value;
  const kredite = s.posten.financial_liabilities?.value;
  if (!pension || !kredite) return null;
  return pension / kredite;
}

/** Die Erläuterung des Anhangs zu einem Hauptposten. */
export function explanation(
  daten: BilanzDaten | null, year: number, role: BilanzRolle,
): BilanzErlaeuterung | null {
  if (!daten) return null;
  return daten.explanations.find((e) => e.year === year && e.role === role) ?? null;
}

/** Ist der Schuldensprung dieses Jahrgangs ein Buchungsartefakt?
 *
 *  DIE WICHTIGSTE FUNKTION IN DIESER DATEI. Die Bilanz 2024 weist Schulden
 *  von 207,1 Mio. € aus nach 84,4 Mio. € im Vorjahr. Wer das als Zahl
 *  hinschreibt, behauptet eine Verdreifachung der Schulden — und die hat es
 *  nicht gegeben: Die Stadt muss dieselben Cash-Pooling-Mittel seit 2024 auf
 *  **beiden** Bilanzseiten ausweisen, mit einem Gegenposten im
 *  Finanzvermögen. Der Anhang erklärt es selbst (6.2.7).
 *
 *  Deshalb sucht diese Funktion nicht nach dem Wort „Cash-Pooling", sondern
 *  liefert den Erläuterungstext — und die Seite zeigt den Schuldenwert nur,
 *  wenn sie ihn hat. Kein Text, keine Zahl. */
export function cashPoolingHinweis(
  daten: BilanzDaten | null, year: number,
): BilanzErlaeuterung | null {
  return explanation(daten, year, "liabilities");
}

export function herkunftVon(daten: BilanzDaten | null, id: number | null): Herkunft | null {
  if (!daten || id == null) return null;
  return daten.provenance[String(id)] ?? null;
}
