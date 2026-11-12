/* Die neue Sitzungsseite (Plan `docs/plan-sitzungsseite-kurs.md`, Schritt 3):
   was rechnet, steht hier und ist getestet; die Komponenten in
   `components/session/` zeichnen nur. */

import { isLiveNow, localTodayISO, type LiveSession } from "@/lib/live";
import type { DecisionOutcome } from "@/lib/types";

/** Vier Zustände derselben Sitzung (Plan § 4.3). */
export type SessionPhase = "before" | "live" | "past" | "protocol";

export function sessionPhase(
  s: { session_date: string; has_protocol?: boolean } & LiveSession,
  now: Date = new Date(),
): SessionPhase {
  if (s.has_protocol) return "protocol";
  if (isLiveNow(s, now)) return "live";
  return String(s.session_date).slice(0, 10) >= localTodayISO(now) ? "before" : "past";
}

/** „Heute", „Morgen" oder der Wochentag — der Anfang des Kickers. */
export function dayWord(sessionDate: string, now: Date = new Date()): string {
  const heute = localTodayISO(now);
  const morgen = localTodayISO(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 12));
  const tag = String(sessionDate).slice(0, 10);
  if (tag === heute) return "Heute";
  if (tag === morgen) return "Morgen";
  return new Date(`${tag}T12:00:00`).toLocaleDateString("de-DE", { weekday: "long" });
}

/** Der Ort ohne Straße für den Kicker: „Alte Fleiwa, Industriestraße 1d,
 *  Sitzungssaal 1/2" → „Alte Fleiwa, Sitzungssaal 1/2". Die volle Adresse
 *  steht in der Karte „Ort und Zeit". */
export function shortLocation(location: string | null | undefined): string | null {
  const teile = (location ?? "").split(",").map((t) => t.trim()).filter(Boolean);
  if (!teile.length) return null;
  const ohne = teile.filter((t, i) => i === 0 || !/\D\s\d+\s?[a-z]?$/i.test(t));
  return ohne.join(", ");
}

/** „Mo · 21.09.2026"-artig: der ganze Kicker in einer Zeile. */
export function sessionKicker(
  s: { session_date: string; session_time?: string | null; location?: string | null },
  now: Date = new Date(),
): string {
  const tag = String(s.session_date).slice(0, 10);
  const [j, m, d] = tag.split("-");
  const teile = [dayWord(tag, now), `${d}.${m}.${j}`];
  if (s.session_time) teile.push(`${s.session_time.slice(0, 5)} Uhr`);
  const ort = shortLocation(s.location);
  if (ort) teile.push(ort);
  return teile.join(" · ");
}

export const OUTCOME_ORDER: DecisionOutcome[] = ["accepted", "noted", "postponed", "rejected", "settled", "no_decision"];

/** Zählung der Ergebnisse unter dem Kurs („7 Angenommen · 4 Zur Kenntnis …")
 *  — Ergebnisse von PUNKTEN, keine Abstimmungsgrafik (Plan 3.13). Null
 *  entfällt; `withResult` ist die Zahl der Punkte mit einem Ergebnis. */
export function outcomeCounts(
  itemNumbers: string[], outcomeByItem: Record<string, DecisionOutcome | null>,
): { counts: [DecisionOutcome, number][]; withResult: number } {
  const zahl = new Map<DecisionOutcome, number>();
  let mit = 0;
  for (const nr of itemNumbers) {
    const o = outcomeByItem[nr.replace(/^\p{L}+\s+/u, "").trim()];
    if (!o) continue;
    mit += 1;
    zahl.set(o, (zahl.get(o) ?? 0) + 1);
  }
  return { counts: OUTCOME_ORDER.filter((o) => zahl.get(o)).map((o) => [o, zahl.get(o)!]), withResult: mit };
}

/** Aufeinanderfolgende Formalakte (Widmung, Einziehung, Umstufung) teilen
 *  sich eine Karte (Plan § 4.2). Gibt Gruppen von Nummern zurück — eine
 *  Gruppe mit einem Punkt ist eine gewöhnliche Karte. */
export function groupFormalActs(items: string[], isFormalAct: (nr: string) => boolean): string[][] {
  const out: string[][] = [];
  for (const nr of items) {
    const last = out[out.length - 1];
    if (last && isFormalAct(nr) && isFormalAct(last[last.length - 1])) last.push(nr);
    else out.push([nr]);
  }
  return out;
}

const ZAHLWORT = ["Null", "Ein", "Zwei", "Drei", "Vier", "Fünf", "Sechs", "Sieben", "Acht", "Neun", "Zehn", "Elf", "Zwölf"];

/** „Drei Widmungen" — der Titel einer Formalakt-Karte. */
export function formalActTitle(titles: string[]): string {
  const n = titles.length;
  const zahl = n < ZAHLWORT.length ? ZAHLWORT[n] : String(n);
  const alle = (re: RegExp) => titles.every((t) => re.test(t));
  const art = alle(/widmung/i) && !titles.some((t) => /einziehung/i.test(t)) ? "Widmungen"
    : alle(/einziehung/i) ? "Einziehungen"
    : alle(/umstufung/i) ? "Umstufungen"
    : "straßenrechtliche Formalakte";
  return `${zahl} ${art}`;
}

/** „Ö 11.1" → „11.1" für die große Nummer; das „Ö" steht davor in Muted. */
export function splitNumber(nr: string): { prefix: string; rest: string } {
  const m = nr.match(/^(\p{L}+)\s+(.*)$/u);
  return m ? { prefix: m[1], rest: m[2] } : { prefix: "", rest: nr };
}

/** Die Station dieser Sitzung im Weg der Vorlage und die davor. */
export function priorStations<T extends { ksinr: number; session_date: string }>(journey: T[], ksinr: number, date: string): T[] {
  return journey.filter((s) => s.ksinr !== ksinr && s.session_date < date);
}

/** Wie weit ein erwartetes Datum entfernt ist, grob: „in den nächsten
 *  Tagen", „in etwa einer Woche", „in etwa 5 Wochen" — eine Schätzung
 *  soll nicht genauer klingen, als sie ist. `null`, wenn es schon vorbei ist. */
export function roughlyIn(isoDate: string, now: Date = new Date()): string | null {
  const ziel = new Date(`${isoDate.slice(0, 10)}T12:00:00`);
  const heute = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
  const tage = Math.round((ziel.getTime() - heute.getTime()) / 86_400_000);
  if (tage < 0) return null;
  if (tage <= 4) return "in den nächsten Tagen";
  const wochen = Math.round(tage / 7);
  return wochen <= 1 ? "in etwa einer Woche" : `in etwa ${wochen} Wochen`;
}
