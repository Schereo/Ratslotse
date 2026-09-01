// Die Investitionen des Finanzhaushalts — Typen und Rechenwege für
// /haushalt/investitionen.
//
// Die Seite beantwortet: Was will die Stadt bauen und kaufen, und in welchen
// Bereichen? Alles hier dient dieser Frage.
//
// ZWEI FALLEN, die jeden Rechenweg betreffen:
//
// 1. DIE SUMME KOMMT AUS DER DATEI, NICHT VON UNS. `gesamt` ist die
//    Summenzeile, die das Dokument selbst ausweist — und genau das Ziel der
//    Rechenprobe beim Einlesen. Wer die Teilhaushalte hier noch einmal
//    addiert und das Ergebnis zeigt, zeigt eine zweite Zahl, die dasselbe
//    meint, und muss erklären, warum es zwei gibt.
//
// 2. `finanzhaushalt` IST NICHT DIE SUMME DER INVESTITIONEN, sondern der
//    Gesamtbetrag aller Ein- und Auszahlungen des Jahres — samt Personal,
//    Zuschüssen, Steuern. Er ist rund zehnmal so groß. Er dient als
//    Bezugsgröße („9,5 % aller Auszahlungen sind Investitionen") und trägt als
//    einzige Zahl dieser Seite keine Rechenprobe.

import type { Herkunft } from "@/lib/haushalt-konzern";

export type { Herkunft };

/** Eine Zeile aus `council_investitionen`. */
export type InvestitionsZeile = {
  year: number;
  level: "sub_budget" | "investments" | "financial_budget";
  /** 0 auf den beiden Summenzeilen — sie tragen keine Teilhaushaltsnummer. */
  sub_budget_no: number;
  label: string;
  inflows: number;
  outflows: number;
  herkunft_id: number | null;
};

export type InvestitionenDaten = {
  years: number[];
  sub_budgets: InvestitionsZeile[];
  investments: InvestitionsZeile[];
  financial_budget: InvestitionsZeile[];
  herkunft: Record<string, Herkunft>;
};

export function herkunftVon(
  daten: InvestitionenDaten | null,
  id: number | null | undefined,
): Herkunft | null {
  if (!daten || id == null) return null;
  return daten.herkunft[String(id)] ?? null;
}

/** Die Teilhaushalte eines Jahres, nach Auszahlungen absteigend.
 *
 *  Nach Auszahlungen und nicht nach dem Saldo: „Wofür gibt die Stadt Geld
 *  aus?" ist die Frage der Seite. Der Saldo wäre eine andere (und würde einen
 *  Bereich nach vorn sortieren, der viel ausgibt UND viel zurückbekommt). */
export function teilhaushalte(
  daten: InvestitionenDaten | null,
  year: number,
): InvestitionsZeile[] {
  if (!daten) return [];
  return daten.sub_budgets
    .filter((z) => z.year === year)
    .sort((a, b) => b.outflows - a.outflows);
}

export function gesamtJahr(
  daten: InvestitionenDaten | null,
  year: number,
): InvestitionsZeile | null {
  return daten?.investments.find((z) => z.year === year) ?? null;
}

export function finanzhaushaltJahr(
  daten: InvestitionenDaten | null,
  year: number,
): InvestitionsZeile | null {
  return daten?.financial_budget.find((z) => z.year === year) ?? null;
}

/** Wie viel Prozent aller geplanten Auszahlungen Investitionen sind.
 *
 *  UNSERE Rechnung, nicht die des Dokuments — die Seite schreibt das dazu.
 *  `null`, solange die Bezugsgröße fehlt: Ein Anteil ohne Nenner wäre eine
 *  erfundene Zahl. */
export function investitionsAnteil(
  daten: InvestitionenDaten | null,
  year: number,
): number | null {
  const g = gesamtJahr(daten, year);
  const f = finanzhaushaltJahr(daten, year);
  if (!g || !f || !f.outflows) return null;
  return (g.outflows / f.outflows) * 100;
}

/** Was nach Abzug der Einzahlungen übrig bleibt — die Nettobelastung.
 *
 *  Investitionen sind nicht nur Ausgaben: Zuschüsse von Bund und Land,
 *  Grundstücksverkäufe und Beiträge stehen als Einzahlungen dagegen. Die
 *  Differenz ist der Betrag, den die Stadt selbst aufbringen muss. */
export function netto(row: InvestitionsZeile | null): number | null {
  if (!row) return null;
  return row.outflows - row.inflows;
}

/** Die Zeitreihe der Gesamtinvestitionen, aufsteigend nach Jahr. */
export function series(daten: InvestitionenDaten | null): InvestitionsZeile[] {
  if (!daten) return [];
  return [...daten.investments].sort((a, b) => a.year - b.year);
}
