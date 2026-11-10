/**
 * Pläne der Stadt (Schalter `plaene`, docs/plan-ziele-plaene.md): die
 * Typen aus dem Vertrag und das bisschen Darstellungslogik, das nicht im
 * Backend steht. Gruppen, Kicker, Zeitbänder (als Anteile einer Achse),
 * „letzter Bericht“ und die Sätze, wenn der Bestand schweigt, kommen fertig
 * aus `council/plan_pages.py`.
 */
import type { ApiAntwort } from "./vertrag";

export type PlanOverview = ApiAntwort<"/council/plans">;
export type PlanGroup = PlanOverview["groups"][number];
export type PlanCard = PlanGroup["plans"][number];
export type PlanAxis = PlanOverview["axis"];
export type PlanLane = PlanCard["lane"];
export type PlanBand = NonNullable<PlanLane["band"]>;
export type PlanDetail = ApiAntwort<"/council/plan/{key}">;
export type PlanStation = PlanDetail["timeline"]["stations"][number];
export type PlanLogEntry = PlanDetail["timeline"]["log"][number];
export type PlanRunway = NonNullable<PlanDetail["runway"]>;
export type PlanDecisionGroup = PlanDetail["decision_groups"][number];
export type PlanMeasures = NonNullable<PlanDetail["measures"]>;
export type PlanMeasureField = PlanMeasures["groups"][number];
export type PlanMeasure = PlanMeasureField["measures"][number];
export type PlanStatusBrief = NonNullable<PlanCard["status_brief"]>;
export type PlanCityStatus = NonNullable<PlanDetail["city_status"]>;
export type PlanIndicator = PlanDetail["indicators"][number];
export type PlanContent = NonNullable<PlanDetail["content"]>;
export type PlanContentStatement = PlanContent["purpose"];
export type PlanContentGroup = PlanContent["groups"][number];
export type PlanSection = PlanDetail["sections"][number];
export type PlanView = PlanOverview["views"][number];
export type PlanSnapshot = PlanCityStatus["series"][number];
export type PlanDue = PlanRunway["dues"][number];
export type PlanNews = NonNullable<PlanDetail["news"]>;
export type PlanPlain = NonNullable<PlanDetail["plain"]>;
export type PlanStatusNorm = PlanStatusBrief["counts"][number]["status_norm"];

/** „19.12.2022“ aus dem ISO-Datum — ohne `new Date`, das rutscht je nach
 *  Zeitzone auf den Vortag (wie in `akte-zeitleiste.tsx`). */
export function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  if (day && month && year) return `${day}.${month}.${year}`;
  if (month && year) return `${month}/${year}`;
  return iso;
}

/** Was eine Station im Zeitstrahl ist, in einem Wort. Mündliche Berichte
 *  sagen dazu, dass es keinen Text gibt (Plan § 3.2). */
export function stationKind(station: Pick<PlanStation, "kind" | "oral">): string {
  switch (station.kind) {
    case "adoption": return "Beschluss des Plans";
    case "amendment": return "Beschluss zum Plan";
    case "evaluation": return "Auswertung";
    case "preparation": return station.oral ? "Vor dem Beschluss · mündlich, ohne Text" : "Vor dem Beschluss";
    default: return station.oral ? "Mündlicher Bericht, ohne Text" : "Bericht";
  }
}

/** Die Gremien einer Station in der Reihenfolge der Beratung: Ausschüsse
 *  vorn, „Rat“ zuletzt. */
export function committeeList(committees: readonly string[]): string {
  const others = committees.filter((c) => c !== "Rat");
  return committees.includes("Rat") ? [...others, "Rat"].join(" · ") : others.join(" · ");
}

/** Tönung des Status-Abzeichens. Kein Rot, kein Fehler-Ton (§ 3.4 Regel 5):
 *  Abgelaufen und abgelöst ist neutral, „in Arbeit“ trägt den Primär-Tint. */
export function statusTone(status: PlanCard["status"]): "neutral" | "primary" | "none" {
  if (status === "running") return "none";
  if (status === "preparing") return "primary";
  return "neutral";
}

/** Ein Anteil der Zeitachse (0–1) als CSS-Länge. */
export function percent(x: number): string {
  return `${Math.round(Math.min(1, Math.max(0, x)) * 10000) / 100}%`;
}

/** „12 Berichte“, „1 Bericht“ — die Null schreibt die Seite als Satz, nicht als Zahl. */
export function reportCount(n: number): string {
  return n === 1 ? "1 Bericht" : `${n} Berichte`;
}

/** Die Jahre eines Zeitstrahl-Abschnitts: „2025“ oder „2020–2026“. */
export function yearSpan(entry: Pick<PlanLogEntry, "year" | "year_to">): string {
  return entry.year === entry.year_to ? `${entry.year}` : `${entry.year}–${entry.year_to}`;
}

/** Die Pläne einer Gruppe nach Themenfeld. Die Reihenfolge kommt aus dem
 *  Backend (nach Feld, darin der jüngste Bericht zuerst) und bleibt stehen —
 *  hier wird nur an den Feldgrenzen geschnitten. */
export function byField(plans: readonly PlanCard[]): { key: string; label: string; plans: PlanCard[] }[] {
  const out: { key: string; label: string; plans: PlanCard[] }[] = [];
  for (const plan of plans) {
    const last = out[out.length - 1];
    if (last && last.key === plan.policy_field) last.plans.push(plan);
    else out.push({ key: plan.policy_field, label: plan.field_label, plans: [plan] });
  }
  return out;
}

/** Klein, ohne Akzente, „ß“ als „ss“ — damit „strasse“ die „Straße“ findet. */
function fold(text: string): string {
  return text.toLocaleLowerCase("de").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");
}

/** Die Maßnahmen, die zur Suche passen — in Kennung, Titel, Paket oder Feld;
 *  jedes Wort muss vorkommen. Umlaute und Großschreibung zählen nicht. Felder
 *  ohne Treffer fallen heraus. */
export function filterMeasures(fields: readonly PlanMeasureField[], query: string): PlanMeasureField[] {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return [...fields];
  return fields
    .map((field) => ({
      ...field,
      measures: field.measures.filter((m) => {
        const haystack = fold(`${m.code} ${m.title} ${m.package ?? ""} ${field.field ?? ""}`);
        return words.every((w) => haystack.includes(w));
      }),
    }))
    .filter((field) => field.measures.length > 0);
}

/** Die Maßnahmen eines Feldes, an den Paketgrenzen geschnitten (Reihenfolge
 *  der Quelle). Ein Feld ohne Pakete ist ein einziges Stück. */
export function byPackage(measures: readonly PlanMeasure[]): { name: string | null; measures: PlanMeasure[] }[] {
  const out: { name: string | null; measures: PlanMeasure[] }[] = [];
  for (const m of measures) {
    const name = m.package ?? null;
    const last = out[out.length - 1];
    if (last && last.name === name) last.measures.push(m);
    else out.push({ name, measures: [m] });
  }
  return out;
}

/** Die Verteilung laut Stadt in einer Zeile, in ihren Worten: „34 In Umsetzung
 *  · 20 Realisiert“. Stufen ohne Maßnahme entfallen. Ordnet die Stadt nur
 *  einen Teil ein, steht die Zählbasis dabei („6 von 18 in Umsetzung“) —
 *  sonst läse sich der Rest als „nichts geschehen“. */
export function statusLine(brief: Pick<PlanStatusBrief, "counts" | "total" | "complete">): string {
  return brief.counts
    .filter((c) => c.count > 0)
    .map((c) => (brief.complete ? `${c.count} ${c.status_raw}` : `${c.count} von ${brief.total} ${c.status_raw}`))
    .join(" · ");
}

/** Die Statuszeile der Übersicht. Kurze Verteilungen stehen ausgeschrieben da;
 *  wo die Wörter der Stadt lang sind (fünf Stufen der Ernährungsstrategie),
 *  sagt die Zeile nur, dass und wie fein die Stadt einordnet — die Verteilung
 *  selbst steht auf der Planseite. Gekürzt oder ausgewählt wird nichts. */
export function statusSummary(brief: Pick<PlanStatusBrief, "counts" | "total" | "complete">, maxLength = 90): string {
  const line = statusLine(brief);
  if (line.length <= maxLength) return line;
  const stages = brief.counts.filter((c) => c.count > 0).length;
  const counted = brief.counts.reduce((n, c) => n + c.count, 0);
  return brief.complete
    ? `${brief.total} Maßnahmen, von der Stadt in ${stages} Stufen eingeordnet`
    : `${counted} von ${brief.total} Maßnahmen von der Stadt eingeordnet`;
}

/** „+9“, „−2“ — mit echtem Minuszeichen. */
export function signed(n: number): string {
  return n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "±0";
}

/** Die Stufen einer Reihe in der Reihenfolge des jüngsten Stands; was die
 *  Stadt früher anders nannte, hängt hinten an. */
export function statusLabels(series: readonly { counts: readonly { status_raw: string }[] }[]): string[] {
  const out: string[] = [];
  for (const snapshot of [...series].reverse()) {
    for (const c of snapshot.counts) if (!out.includes(c.status_raw)) out.push(c.status_raw);
  }
  return out;
}

/** „935.792“ — ganze Zahlen mit Tausenderpunkt. */
export function formatAmount(value: number): string {
  return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** Eine Änderung als Anteil (−0,1791 …) in Prozent mit einer Nachkommastelle:
 *  „−17,9 %“. Gerundet wird genau hier, einmal — das Backend liefert exakt. */
export function formatChange(ratio: number): string {
  const tenths = Math.round(ratio * 1000);
  const sign = tenths > 0 ? "+" : tenths < 0 ? "−" : "±";
  const abs = Math.abs(tenths);
  return `${sign}${Math.floor(abs / 10)},${abs % 10} %`;
}

/** Ein Kästchen im „Stand laut Stadt“: dieselbe Kennung über alle Stände, damit es beim Wechsel des
 *  Jahres von seiner Stufe zur nächsten wandern kann. */
export type SquareToken = { id: number; label: string };

/** Die Kästchen je Stand — so verteilt, dass von Stand zu Stand möglichst wenige die Stufe wechseln.
 *
 *  Die Stadt meldet je Stand nur SUMMEN je Stufe, nicht den Weg einzelner Maßnahmen. Die Kennungen
 *  hier sind deshalb gerechnet, nicht gemeldet: Was in einer Stufe bleibt, bleibt; der Überschuss
 *  einer Stufe füllt die Lücken der anderen, in der Reihenfolge der Stufen. Wächst die Zählbasis,
 *  kommen Kästchen dazu, schrumpft sie, fallen welche weg. Die Bewegung zeigt so die Verschiebung
 *  der Zahlen — die Seite sagt dazu, dass sie nicht zeigt, WELCHE Maßnahme gewechselt ist. */
export function squareTokens(
  series: readonly { counts: readonly { status_raw: string; count: number }[] }[],
): SquareToken[][] {
  const out: SquareToken[][] = [];
  let next = 0;
  let current: SquareToken[] = [];
  for (const snapshot of series) {
    const want = new Map(snapshot.counts.map((c) => [c.status_raw, c.count]));
    const kept: SquareToken[] = [];
    const free: SquareToken[] = [];
    const seen = new Map<string, number>();
    for (const token of current) {
      const n = seen.get(token.label) ?? 0;
      seen.set(token.label, n + 1);
      (n < (want.get(token.label) ?? 0) ? kept : free).push(token);
    }
    for (const c of snapshot.counts) {
      for (let i = Math.min(seen.get(c.status_raw) ?? 0, c.count); i < c.count; i++) {
        const moved = free.shift();
        kept.push({ id: moved ? moved.id : next++, label: c.status_raw });
      }
    }
    current = kept.sort((a, b) => a.id - b.id);
    out.push(current);
  }
  return out;
}
