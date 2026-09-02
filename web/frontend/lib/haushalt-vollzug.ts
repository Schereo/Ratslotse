// Der Haushaltsvollzug — wie das laufende Jahr gegen seinen Plan läuft.
//
// Quelle: GET /api/council/budget/execution?budget_year=<jahr> (council/
// budget_execution.py). Die Verwaltung berichtet dem Finanzausschuss
// vierteljährlich, was sie zum 31. Dezember erwartet — je Teilhaushalt und
// als Summe, für Ergebnis- und Finanzhaushalt getrennt. Das schließt die
// Lücke zwischen dem Plan (Schritt 0) und dem Jahresabschluss (Schritt 6),
// der erst zwei Jahre später kommt.
//
// Zwei Dinge, die jede Anzeige mitführen muss (Docstring des Endpunkts):
//   * `forecast` ist eine ERWARTUNG, kein Ist. „Zum 30. Juni" ist der Tag,
//     an dem die Ämter ihre Prognose abgegeben haben — nicht ein
//     Halbjahresergebnis. Deshalb heißt die Hantel hier „geplant → erwartet",
//     nie „tatsächlich".
//   * `plan_basis` sagt, was in der Ansatz-Spalte steht: bis 2020 der Ansatz
//     samt Ermächtigungsübertragungen, ab 2021 der nackte Ansatz. Wer beides
//     nebeneinanderstellt, sagt es dazu — `plan_basis_note` liefert den Satz.

import type { Herkunft } from "@/lib/herkunft";

export type VollzugHaushalt = "result" | "cash";
export type VollzugArt = "revenue" | "expense" | "inflow" | "outflow" | "result";
export type PlanBasis = "budget" | "budget_plus_carryover";

export type VollzugZeile = {
  budget_year: number;
  /** Stichtag, ISO (2025-06-30). */
  as_of: string;
  budget: VollzugHaushalt;
  /** 1–13; 0 ist die gedruckte Summenzeile. */
  sub_budget: number;
  kind: VollzugArt;
  label: string;
  budgeted: number | null;
  forecast: number | null;
  deviation: number | null;
  /** Ermächtigungsübertragungen — nur an der Aufwands-/Auszahlungszeile. */
  carryover: number | null;
  plan_basis: PlanBasis;
  is_total: 0 | 1;
  probes: string;
  herkunft_id: number | null;
};

export type VollzugStichtag = {
  budget_year: number;
  as_of: string;
  /** Welche Haushalte an diesem Stichtag vorliegen — ein halbes Quartal
   *  steht hier, statt in einer Lücke zu verschwinden. */
  budgets: VollzugHaushalt[];
  plan_basis: PlanBasis;
};

export type VollzugDaten = {
  scope_note: string;
  plan_basis_note: Record<PlanBasis, string>;
  budget_names: Record<VollzugHaushalt, string>;
  kind_names: Record<VollzugArt, string>;
  editions: number[];
  reporting_dates: VollzugStichtag[];
  /** Summenzeilen ALLER Jahrgänge — die Zeitreihe. */
  totals: VollzugZeile[];
  /** Die dreizehn Teilhaushalte, nur für das angefragte Jahr. */
  rows: VollzugZeile[];
  /** Je `herkunft_id` das Papier — dieselbe Form wie überall im Bereich. */
  provenance: Record<string, Herkunft>;
};

/** Das Papier, auf dem eine Zeile ruht — oder null, wo keines vermerkt ist. */
export function herkunftVon(d: VollzugDaten, id: number | null): Herkunft | null {
  return id == null ? null : d.provenance[String(id)] ?? null;
}

/** Die Adressen der Berichte eines Jahrgangs, je Stichtag eine, in
 *  Stichtags-Reihenfolge. Ergebnis- und Finanzhaushalt stehen im SELBEN
 *  PDF (zwei Abschnitte), deshalb je Stichtag eine Adresse, nicht zwei.
 *
 *  Das ist die Liste für `jeDokument` (s. `components/haushalt/source.tsx`):
 *  Die Seite „Geplant und geworden" zeigt den Abschluss von 2024 und den
 *  Vollzug von 2026 — würde das Quellenverzeichnis die Berichte über den
 *  Jahrgang der Seite suchen, stünden unter einer 2026er-Zahl die Papiere
 *  von 2024. Genau das war der Fehler, den Tim am 02.09.2026 gemeldet hat. */
export function berichteUrls(d: VollzugDaten, year: number): string[] {
  const aus: string[] = [];
  for (const s of stichtageDesJahres(d, year)) {
    const zeile = d.totals.find((z) => z.budget_year === year && z.as_of === s.as_of && z.is_total === 1);
    const url = zeile ? herkunftVon(d, zeile.herkunft_id)?.url : null;
    if (url && !aus.includes(url)) aus.push(url);
  }
  return aus;
}

/** „30.06.2025" aus „2025-06-30". */
export function deStichtag(iso: string): string {
  const [j, m, t] = iso.split("-");
  return `${t}.${m}.${j}`;
}

/** „30. Juni" — der Stichtag ohne Jahr, für Umschalter innerhalb eines Jahrgangs. */
export function deStichtagKurz(iso: string): string {
  const monate = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
    "August", "September", "Oktober", "November", "Dezember"];
  const [, m, t] = iso.split("-");
  return `${Number(t)}. ${monate[Number(m) - 1]}`;
}

export function stichtageDesJahres(d: VollzugDaten, year: number): VollzugStichtag[] {
  return d.reporting_dates.filter((s) => s.budget_year === year);
}

/** Die Summenzeile eines Stichtags — oder null, wo der Bericht sie nicht führt. */
export function summe(
  d: VollzugDaten, year: number, as_of: string, budget: VollzugHaushalt, kind: VollzugArt,
): VollzugZeile | null {
  return d.totals.find((z) => z.budget_year === year && z.as_of === as_of
    && z.budget === budget && z.kind === kind && z.is_total === 1) ?? null;
}

/** Der jüngste Stichtag im Bestand — das, was „jetzt" am nächsten kommt. */
export function juengster(d: VollzugDaten): VollzugStichtag | null {
  return d.reporting_dates.length ? d.reporting_dates[d.reporting_dates.length - 1] : null;
}

/** Der Verlauf der Erwartung innerhalb eines Jahrgangs: je Stichtag der
 *  Ansatz (gleich, außer der Plan wurde nachgetragen) und die Prognose. */
export function verlauf(d: VollzugDaten, year: number, budget: VollzugHaushalt) {
  return stichtageDesJahres(d, year)
    .map((s) => summe(d, year, s.as_of, budget, "result"))
    .filter((z): z is VollzugZeile => z !== null && z.budgeted != null && z.forecast != null);
}

/** Die Teilhaushalte eines Stichtags, eine Zeile je Bereich. */
export function bereiche(
  d: VollzugDaten, year: number, as_of: string, budget: VollzugHaushalt, kind: VollzugArt,
): VollzugZeile[] {
  return d.rows
    .filter((z) => z.budget_year === year && z.as_of === as_of && z.budget === budget
      && z.kind === kind && z.is_total === 0)
    .sort((a, b) => a.sub_budget - b.sub_budget);
}

/** Der Name des Ergebnisses je Haushalt: Im Ergebnishaushalt heißt es
 *  Jahresergebnis, im Finanzhaushalt Saldo der Investitionstätigkeit. */
export function ergebnisWort(budget: VollzugHaushalt): string {
  return budget === "cash" ? "Saldo aus Investitionen" : "Jahresergebnis";
}

/** Mio. € mit Vorzeichen, eine Nachkommastelle — für die Sätze. */
export function deMioSigned(euro: number): string {
  const v = euro / 1e6;
  const s = Math.abs(v).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${v < 0 ? "−" : v > 0 ? "+" : ""}${s}`;
}
