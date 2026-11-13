/* Der Kasten „Im Haushalt“ auf der Punkt-Seite: nur noch Anzeige. Welche
   Zahlenreihen zu einem Punkt gehören, entscheidet der Server
   (`council/punkt_haushalt.py`); die Werte kommen exakt, gerundet wird hier
   genau einmal. */

import type { ApiAntwort } from "@/lib/vertrag";
import { amount } from "@/lib/haushalt";

export type HaushaltKontext = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["budget_context"]>;
export type HaushaltBlock = HaushaltKontext["blocks"][number];

/** Ein Wert in seiner Einheit — hinter jedem Euro-Wert steht das €-Zeichen. */
export function wert(v: number | null | undefined, unit: string): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (unit === "percent") return `${v.toLocaleString("de-DE", { maximumFractionDigits: 1 })}\u00a0%`;
  if (unit === "EUR") {
    const a = amount(v);
    return `${a.value}\u00a0${a.unit}`;
  }
  return Math.round(v).toLocaleString("de-DE");
}

/** Ein Anteil, einmal gerundet. Unter einem Zehntelprozent stünde „0,0 %“ —
 *  eine Zahl, die nichts sagt, obwohl wir sie genau kennen. */
export function anteil(percent: number): string {
  if (percent > 0 && percent < 0.1) return "weniger als 0,1\u00a0%";
  return `${percent.toLocaleString("de-DE", { maximumFractionDigits: percent < 10 ? 1 : 0 })}\u00a0%`;
}

/** „481.300 € sind 0,8 % der geplanten Aufwendungen 2025 dieses Teilhaushalts.“ */
export function anteilSatz(share: NonNullable<HaushaltBlock["share"]>): string {
  const betrag = `${Math.round(share.amount).toLocaleString("de-DE")}\u00a0€`;
  return `${betrag} sind ${anteil(share.percent)} der geplanten Aufwendungen ${share.year} dieses Teilhaushalts.`;
}

/** Wohin der Kasten in den Haushalts-Bereich führt — nur für Konten mit dem
 *  Recht dazu (`lib/rechte.ts`); der Server nennt die Seite, nicht den Pfad. */
const SEITEN: Record<string, string> = {
  sub_budgets: "/haushalt/bereich", products: "/haushalt/produkte", enterprises: "/haushalt/konzern",
  taxes: "/haushalt/steuer", debt: "/haushalt/schulden", plan_actual: "/haushalt/plan-ist",
};
export function haushaltSeite(page: string | null | undefined): string | null {
  return page ? SEITEN[page] ?? null : null;
}

/** Die Jahresspalte: Ein Satz „gilt ab“ dem Jahr, eine Summe gehört zu ihm. */
export function jahrSpalte(basis: string): string {
  return basis === "rate" ? "Ab" : "Jahr";
}
