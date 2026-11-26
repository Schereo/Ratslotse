/**
 * Anzeige des Benchmark-Bereichs im Admin-Panel — nur Formatieren.
 *
 * Was ein Lauf bedeutet, ob er überholt ist und warum, rechnet das Backend
 * (`kern/benchmarks.py::assess`); hier wird es nur in Worte gefasst. Werte
 * kommen exakt (0–1 für Anteile) und werden genau einmal gerundet.
 */
import type { ApiAntwort } from "./vertrag";

export type BenchmarkUebersicht = ApiAntwort<"/admin/benchmarks">;
export type Benchmark = BenchmarkUebersicht["benchmarks"][number];
export type Pipeline = BenchmarkUebersicht["pipelines"][number];
export type LaufZeile = Benchmark["runs"][number];
export type Kennzahl = Benchmark["metric"];

const zahl = (v: number, stellen = 0) =>
  v.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen });

/** Ein Wert in seiner Einheit. `null` heißt „keine Aussage" — nie „0 %". */
export function wertText(v: number | null | undefined, einheit: string): string {
  if (einheit === "none") return "zum Lesen";
  if (v == null || !Number.isFinite(v)) return "–";
  switch (einheit) {
    case "share": return `${zahl(v * 100)} %`;
    case "seconds": return `${zahl(v, v < 10 ? 1 : 0)} s`;
    case "ratio": return zahl(v, 2);
    default: return zahl(v);
  }
}

export function kostenText(usd: number | null | undefined): string {
  if (usd == null) return "–";
  if (usd === 0) return "0 $";
  if (usd < 0.01) return "< 0,01 $";
  return `${zahl(usd, 2)} $`;
}

export const UMGEBUNG: Record<string, string> = {
  prod: "Prod", dev: "dev", local: "lokal", ci: "CI", unknown: "nicht erfasst",
};

/** Nebenkennzahlen ohne Eintrag im Katalog — sonst stünde der Schlüssel da. */
export const KENNZAHL_NAMEN: Record<string, string> = {
  hard_findings: "harte Befunde", precision: "Precision", recall: "Recall", f1: "F1",
  kontextfehler: "Kontextfehler", modellfehler: "Modellfehler", erfunden: "erfunden",
  evidence_in_prompt: "Belege im Prompt", evidence_total: "Belege gesamt", violations: "Verstöße",
  retrieval_hit_rate: "Suche: Treffer", mrr: "Suche: MRR", rho: "Spearman ρ",
};

export const LAEUFT: Record<string, string> = {
  local: "lokal mit dem Abzug", server: "auf dem Server", both: "lokal oder auf dem Server",
};

/** „openai/gpt-6-luna" → „gpt-6-luna": Der Anbieter steht im Tooltip. */
export function modellKurz(id: string | null | undefined): string {
  if (!id) return "–";
  return id.includes("/") ? id.slice(id.indexOf("/") + 1) : id;
}

export function datumText(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export type Grund = Benchmark["reasons"][number];

/** Warum die jüngste Messung nicht mehr für heute spricht — ein Satzteil je Grund. */
export function grundText(g: Grund, stufe: (key: string) => string): string {
  switch (g.kind) {
    case "model":
      return `${stufe(String(g.step))}: heute ${modellKurz(String(g.now))}, gemessen mit ${modellKurz(String(g.then))}`;
    case "cases": return "Fälle seither geändert";
    case "age": return `zuletzt vor ${g.days} Tagen gemessen`;
    case "variant": return `nur als Variante gemessen (${g.variant})`;
    case "not_comparable": return "nur Teilläufe oder ältere Fälle";
    default: return String(g.kind);
  }
}

export const STATUS: Record<Benchmark["status"], { text: string; ton: "gruen" | "gelb" | "leer" }> = {
  ok: { text: "Aktuell", ton: "gruen" },
  stale: { text: "Überholt", ton: "gelb" },
  none: { text: "Ungemessen", ton: "leer" },
};

/** Ein Rohergebnis im Repo verlinkt GitHub; eines auf einem Server nicht. */
export function rohLink(raw: string | null | undefined, github: string, ref = "dev"): string | null {
  if (!raw || raw.startsWith("server:")) return null;
  return `${github}/blob/${ref}/${raw}`;
}

export function commitLink(commit: string | null | undefined, github: string): string | null {
  return commit && /^[0-9a-f]{7,40}$/.test(commit) ? `${github}/commit/${commit}` : null;
}

/** Der Ausschnitt der y-Achse: so eng wie die Werte, damit kleine Schwankungen
 *  sichtbar werden (Tim, 26.11.2026) — mit etwas Luft und einer Mindestspanne,
 *  sonst bläst ein Unterschied von einem Punkt die ganze Fläche auf.
 *
 *  Anteile und Verhältnisse bleiben zwischen 0 und 1, Zahlen über 0. Die Achse
 *  beginnt damit oft NICHT bei null; ihre Beschriftung sagt, wo sie beginnt. */
export function achse(werte: number[], einheit: string): [number, number] {
  const anteil = einheit === "share" || einheit === "ratio";
  if (werte.length === 0) return anteil ? [0, 1] : [0, 1];
  const lo = Math.min(...werte);
  const hi = Math.max(...werte);
  const mindest = anteil ? 0.06 : Math.max(1, Math.abs(hi) * 0.1);
  const spanne = Math.max(hi - lo, mindest);
  const mitte = (lo + hi) / 2;
  let von = mitte - spanne * 0.65;
  let bis = mitte + spanne * 0.65;
  const unten = 0;
  const oben = anteil ? 1 : Infinity;
  if (von < unten) { bis += unten - von; von = unten; }
  if (bis > oben) { von = Math.max(unten, von - (bis - oben)); bis = oben; }
  return [von, bis];
}
