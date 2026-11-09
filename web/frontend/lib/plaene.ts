/**
 * Pläne der Stadt (Schalter `plaene`, docs/plan-ziele-plaene.md): die
 * Typen aus dem Vertrag und das bisschen Darstellungslogik, das nicht im
 * Backend steht. Gruppen, Kicker, „letzter Bericht“ und die Sätze, wenn der
 * Bestand schweigt, kommen fertig aus `council/plan_pages.py`.
 */
import type { ApiAntwort } from "./vertrag";

export type PlanUebersicht = ApiAntwort<"/council/plans">;
export type PlanKarte = PlanUebersicht["groups"][number]["plans"][number];
export type PlanDetail = ApiAntwort<"/council/plan/{key}">;
export type PlanStation = PlanDetail["timeline"]["stations"][number];
export type PlanBeschlussGruppe = PlanDetail["decision_groups"][number];

/** „19.12.2022“ aus dem ISO-Datum — ohne `new Date`, das rutscht je nach
 *  Zeitzone auf den Vortag (wie in `akte-zeitleiste.tsx`). */
export function datum(iso: string): string {
  const [j, m, t] = iso.split("-");
  if (t && m && j) return `${t}.${m}.${j}`;
  if (m && j) return `${m}/${j}`;
  return iso;
}

/** Was eine Station im Zeitstrahl ist, in einem Wort. Mündliche Berichte
 *  sagen dazu, dass es keinen Text gibt (Plan § 3.2). */
export function stationsArt(s: Pick<PlanStation, "kind" | "oral">): string {
  switch (s.kind) {
    case "adoption": return "Beschluss des Plans";
    case "amendment": return "Beschluss zum Plan";
    case "evaluation": return "Auswertung";
    case "preparation": return s.oral ? "Vor dem Beschluss · mündlich, ohne Text" : "Vor dem Beschluss";
    default: return s.oral ? "Mündlicher Bericht, ohne Text" : "Bericht";
  }
}

/** Die Gremien einer Station in der Reihenfolge der Beratung: Ausschüsse
 *  vorn, „Rat“ zuletzt. */
export function gremien(committees: readonly string[]): string {
  const ohneRat = committees.filter((c) => c !== "Rat");
  return committees.includes("Rat") ? [...ohneRat, "Rat"].join(" · ") : ohneRat.join(" · ");
}

/** Tönung des Status-Abzeichens. Kein Rot, kein Fehler-Ton (§ 3.4 Regel 5):
 *  Abgelaufen und abgelöst ist neutral, „in Arbeit“ trägt den Primär-Tint. */
export function statusTon(status: PlanKarte["status"]): "neutral" | "primary" | "none" {
  if (status === "running") return "none";
  if (status === "preparing") return "primary";
  return "neutral";
}
