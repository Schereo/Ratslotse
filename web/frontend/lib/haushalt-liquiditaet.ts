// Der Liquiditätsstand — wie viel Geld die Stadt am Monatsende auf dem Konto
// hat. Quelle: GET /api/council/budget/liquidity (council/liquidity.py).
//
// Ein KONTOSTAND, kein Vermögen und kein Haushaltsergebnis: Er schwankt im
// Jahr um Dutzende Millionen (Steuertermine, Zuweisungen), ein einzelner
// Monat sagt wenig — deshalb nennt die Anzeige immer das Datum, die Spanne
// der letzten zwölf Monate und die Dezember-Stände über die Jahre.

import type { Herkunft } from "@/lib/herkunft";

export type LiquiditaetsMonat = {
  month: string;          // YYYY-MM
  year: number;
  amount: number;         // Euro
  as_of: string;
  confirmations: number;
  /** Der Wert, den eine spätere Grafik der Verwaltung ersetzt hat. */
  revised_from: number | null;
  document_id: number | null;
  url: string | null;
  template_number: string | null;
  herkunft_id: number | null;
};

export type LiquiditaetsDaten = {
  scope_note: string;
  series: LiquiditaetsMonat[];
  latest: LiquiditaetsMonat | null;
  last_12: { months: number; min: LiquiditaetsMonat | null; max: LiquiditaetsMonat | null };
  year_ends: LiquiditaetsMonat[];
  coverage: { from: string | null; to: string | null; missing: string[]; months: number };
  provenance: Record<string, Herkunft>;
};

const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
  "September", "Oktober", "November", "Dezember"];

/** „Mai 2026" aus „2026-05". */
export function deMonat(ym: string | null | undefined): string {
  if (!ym) return "–";
  return `${MONATE[Number(ym.slice(5, 7)) - 1]} ${ym.slice(0, 4)}`;
}

/** Die letzten N Monate der Reihe — für die Verlaufsskizze. */
export function letzteMonate(d: LiquiditaetsDaten | null, n = 36): LiquiditaetsMonat[] {
  return (d?.series ?? []).slice(-n);
}
