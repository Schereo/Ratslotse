/**
 * Stichwahl: reine Helfer für die Seite `/wahlabend/stichwahl`.
 *
 * Eine Stichwahl ist kein kleiner Wahlabend, sondern ein anderer: zwei Namen,
 * eine Zahl je Name, und die eine Frage, wer vorn liegt. Keine Sitze, keine
 * Wahlbereiche, keine Hochrechnung — der Vergleich läuft gegen den ERSTEN
 * Wahlgang, dessen Zahlen das Backend mitschickt (`first_round_pct`).
 *
 * Wie überall: Gerechnet wird im Backend, hier steht nur, was die Anzeige
 * daraus macht (web/frontend/CLAUDE.md).
 */
import type { ApiAntwort } from "./vertrag";

export type Stichwahl = ApiAntwort<"/wahlabend/stichwahl">;
export type StichwahlKandidat = Stichwahl["candidates"][number];

/** Nach Stimmen, die meisten zuerst.
 *
 *  Solange nichts ausgezählt ist, zählt das Ergebnis des ersten Wahlgangs —
 *  das ist die Reihenfolge, in der Leute die beiden im Kopf haben. Fehlt auch
 *  die, bleibt die der Antwort (sie ist die des Stimmzettels). */
export function nachStimmen(kandidaten: readonly StichwahlKandidat[]): StichwahlKandidat[] {
  if (kandidaten.some((k) => k.votes !== null)) {
    return [...kandidaten].sort((a, b) => (b.votes ?? 0) - (a.votes ?? 0));
  }
  if (kandidaten.some((k) => k.first_round_pct !== null)) {
    return [...kandidaten].sort((a, b) => (b.first_round_pct ?? 0) - (a.first_round_pct ?? 0));
  }
  return [...kandidaten];
}

/** Wer vorn liegt — `null` bei Gleichstand oder solange nichts ausgezählt ist.
 *
 *  Gleichstand ist kein Randfall zum Wegdenken: Bei einer Stichwahl mit zwei
 *  Namen entscheidet dann das Los (§ 45c Abs. 2 NKWG). Die Seite behauptet in
 *  dem Fall lieber nichts. */
export function fuehrend(kandidaten: readonly StichwahlKandidat[]): string | null {
  const mitZahlen = kandidaten.filter((k) => (k.votes ?? 0) > 0);
  if (mitZahlen.length === 0) return null;
  const sortiert = nachStimmen(mitZahlen);
  if (sortiert.length > 1 && (sortiert[0].votes ?? 0) === (sortiert[1].votes ?? 0)) return null;
  return sortiert[0].slug;
}

/** Der Abstand zwischen den beiden ersten in Prozentpunkten — `null`, solange
 *  es nichts zu vergleichen gibt. */
export function vorsprung(kandidaten: readonly StichwahlKandidat[]): number | null {
  const sortiert = nachStimmen(kandidaten).filter((k) => k.share_pct !== null);
  if (sortiert.length < 2) return null;
  return Math.round(((sortiert[0].share_pct ?? 0) - (sortiert[1].share_pct ?? 0)) * 100) / 100;
}

/** Wie viele Stimmen zwischen den beiden ersten liegen — die Zahl, die am
 *  Abend wirklich interessiert. */
export function abstandStimmen(kandidaten: readonly StichwahlKandidat[]): number | null {
  const sortiert = nachStimmen(kandidaten).filter((k) => k.votes !== null);
  if (sortiert.length < 2) return null;
  return (sortiert[0].votes ?? 0) - (sortiert[1].votes ?? 0);
}

/** Der Zugewinn gegenüber dem ersten Wahlgang in Prozentpunkten — `null`,
 *  wenn eine der beiden Zahlen fehlt. */
export function verschiebung(k: StichwahlKandidat): number | null {
  if (k.share_pct === null || k.first_round_pct === null) return null;
  return Math.round((k.share_pct - k.first_round_pct) * 100) / 100;
}

export type Zeitlage = {
  phase: "vorher" | "laeuft";
  /** Kalendertage bis zum Wahltag in deutscher Zeit; 0 am Wahltag selbst. */
  tage: number;
  /** Kurz, für den Mono-Kicker: „Noch 6 Tage", „Heute ab 18 Uhr", „Live". */
  kicker: string;
};

function berlinerTag(d: Date): number {
  const t = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  const [j, m, tag] = t.split("-").map(Number);
  return Date.UTC(j, m - 1, tag);
}

/** Dieselbe Regel wie `wahlabendZeit`, aber für einen Termin, der aus der
 *  Antwort kommt statt aus einer Konstante — die nächste Wahl hat ein anderes
 *  Datum, und niemand soll es in den Code schreiben müssen. */
export function zeitlage(pollsClose: string, jetzt: Date = new Date()): Zeitlage {
  const schluss = new Date(pollsClose).getTime();
  if (!Number.isFinite(schluss)) return { phase: "laeuft", tage: 0, kicker: "Live" };
  if (jetzt.getTime() >= schluss) return { phase: "laeuft", tage: 0, kicker: "Live" };
  const tage = Math.max(0, Math.round((berlinerTag(new Date(schluss)) - berlinerTag(jetzt)) / 86_400_000));
  if (tage === 0) return { phase: "vorher", tage, kicker: "Heute ab 18 Uhr" };
  if (tage === 1) return { phase: "vorher", tage, kicker: "Morgen ab 18 Uhr" };
  return { phase: "vorher", tage, kicker: `Noch ${tage} Tage` };
}

/** Tag und Monat ausgeschrieben: „27. September 2026". */
export function datumLang(iso: string): string {
  const d = new Date(`${iso}T12:00:00Z`);
  if (!Number.isFinite(d.getTime())) return iso;
  return new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Berlin" }).format(d);
}

export function abfragePfad(probe: string | null, counted: string | null): string {
  const q = new URLSearchParams();
  if (probe) q.set("probe", probe);
  if (counted && /^\d+$/.test(counted)) q.set("counted", counted);
  const s = q.toString();
  return s ? `/wahlabend/stichwahl?${s}` : "/wahlabend/stichwahl";
}
