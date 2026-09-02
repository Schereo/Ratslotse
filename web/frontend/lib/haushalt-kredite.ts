// Kredite und Zinsen — was die Stadt und ihre Betriebe für geliehenes Geld
// zahlen. Quelle: GET /api/council/budget/loans (council/loans.py).
//
// Die Schulden-Seite kannte bis 09/2026 den Stand (Jahrbuch) und die Zinslast
// des Jahres (Jahresabschluss, Posten 17). Was hier dazukommt, sind die
// EINZELNEN Vorgänge, über die die Verwaltung den Rat nach der Kreditrichtlinie
// unterrichtet: Kreditaufnahmen mit ihrem Zinssatz, Umschuldungen mit ihrem
// Volumen und — wo die Vorlage sie beziffert — der Zinsersparnis.
//
// Zwei Grenzen, die jede Anzeige mitführt (Docstring des Endpunkts):
//   * Die Konditionen je Darlehen (Bank, Marge, Laufzeit) stehen in den
//     Anlagen, nicht im Vorlagentext — sie sind nicht im Bestand.
//   * `borrower` ist null bei den Umschuldungen der Grundgeschäfte, die
//     Kernverwaltung und Betriebe zugleich betreffen — die Vorlage nennt dort
//     keinen Schuldner, und wir raten keinen.

import type { Herkunft } from "@/lib/herkunft";

export type KreditArt = "loan" | "refinancing" | "prolongation" | "disbursement" | "lending" | "other";

export type KreditPosten = {
  template_number: string;
  seq: number;
  year: number;
  kind: KreditArt;
  borrower: string | null;
  heading: string;
  amount: number | null;
  rate_pct: number | null;
  fixed_years: number | null;
  fixed_until: string | null;
  decided_at: string | null;
  summary: string | null;
  herkunft_id: number | null;
  period_from: string;
  period_to: string;
};

export type KreditUnterrichtung = {
  template_number: string;
  year: number;
  period_from: string;
  period_to: string;
  document_date: string | null;
  none_reported: number;
  items: number;
  interest_saving: number | null;
  saving_from: string | null;
  saving_to: string | null;
  document_url: string | null;
  herkunft_id: number | null;
};

export type KrediteDaten = {
  scope_note: string;
  kind_names: Record<KreditArt, string>;
  notices: KreditUnterrichtung[];
  items: KreditPosten[];
  coverage: { from: string | null; to: string | null; gaps: { from: number; to: number }[];
              notices: number; none_reported: number };
  rates: KreditPosten[];
  refinancing_by_year: { year: number; amount: number; count: number; saving: number;
                         saving_notices: number }[];
  /** Der jüngste Umschuldungs-Posten — die Zahl, die man nennt. Die
   *  Jahressummen zählen die rollierenden Grundgeschäfte viermal. */
  latest_refinancing: KreditPosten | null;
  provenance: Record<string, Herkunft>;
};

const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
  "September", "Oktober", "November", "Dezember"];

/** „Juni 2026" aus „2026-06". */
export function deMonat(ym: string | null): string {
  if (!ym) return "–";
  const [j, m] = ym.split("-");
  return `${MONATE[Number(m) - 1]} ${j}`;
}

/** „Juni bis August 2026" bzw. „Mai 2026". */
export function deZeitraum(von: string, bis: string): string {
  if (von === bis) return deMonat(von);
  const [j1, m1] = von.split("-"); const [j2, m2] = bis.split("-");
  if (j1 === j2) return `${MONATE[Number(m1) - 1]} bis ${MONATE[Number(m2) - 1]} ${j1}`;
  return `${deMonat(von)} bis ${deMonat(bis)}`;
}

/** „3,46 %" — Prozent mit Dezimalkomma, zwei Stellen wie im Dokument. */
export function deProzent(v: number | null): string {
  if (v == null) return "–";
  return `${v.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`;
}

/** Die jüngsten Kreditaufnahmen mit Zinssatz — die Zeile „zu welchem Zins?". */
export function juengsteZinssaetze(d: KrediteDaten | null, n = 4): KreditPosten[] {
  return (d?.rates ?? []).filter((p) => p.kind === "loan" || p.kind === "prolongation").slice(0, n);
}

/** Innenfinanzierung: 0,00 % zwischen Kernverwaltung und Betrieb ist echt,
 *  aber kein Marktzins — die Zeile sagt es. */
export function istInnenfinanzierung(p: KreditPosten): boolean {
  return p.rate_pct === 0 && /innenfinanz/i.test(p.heading + " " + (p.summary ?? ""));
}
