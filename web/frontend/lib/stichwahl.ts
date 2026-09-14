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
export { datumLang } from "./wahlabend";

export type Stichwahl = ApiAntwort<"/wahlabend/stichwahl">;
export type StichwahlKandidat = Stichwahl["candidates"][number];
/** Die Hochrechnung des Backends (`runoff_model`) — da, sobald ein Bezirk
 *  gemeldet hat. Eine Modellrechnung; die Seite nennt sie so. */
export type StichwahlHochrechnung = NonNullable<Stichwahl["projection"]>;

/** Der Satz zur Chance — oder warum es noch keinen gibt. `null`, wenn die
 *  Seite lieber nichts sagt (rechnerisch entschieden hat einen eigenen Satz). */
export function chanceText(p: StichwahlHochrechnung, name: string | undefined): string | null {
  if (p.decided) return null;
  const bezirke = p.counted_ballot + p.counted_postal;
  if (p.chance_pct === null) {
    return `Erst ${bezirke} ${bezirke === 1 ? "Bezirk" : "Bezirke"} gezählt — zu früh für eine Wahrscheinlichkeit. Ab 15 nennt das Modell eine.`;
  }
  return `Chance: ${name ?? p.leader} ${p.chance_pct} %`;
}

/** Wie das Modell die Bezirke gesehen hat: „nach 47 von 133 Bezirken · Urne 41, Brief 6". */
export function bezirkeText(p: StichwahlHochrechnung): string {
  const gezaehlt = p.counted_ballot + p.counted_postal;
  const gesamt = gezaehlt + p.open_ballot + p.open_postal;
  return `nach ${gezaehlt} von ${gesamt} Bezirken · Urne ${p.counted_ballot}, Brief ${p.counted_postal}`;
}

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

export function abfragePfad(probe: string | null, counted: string | null): string {
  const q = new URLSearchParams();
  if (probe) q.set("probe", probe);
  if (counted && /^\d+$/.test(counted)) q.set("counted", counted);
  const s = q.toString();
  return s ? `/wahlabend/stichwahl?${s}` : "/wahlabend/stichwahl";
}

/* ── Momente (docs/plan-stichwahl-spannung.md S4) ──────────────────────────
 * Alles aus der Historie des Backends, nicht aus dem Browser-Zustand — ein
 * frisch geladener Tab soll dasselbe sehen wie einer, der seit 18 Uhr offen ist. */

export type Meldung = {
  at: string;
  /** Wie viele Bezirke seit dem vorigen Stand dazukamen. */
  bezirke: number;
  /** Slug → Stimmen, die seit dem vorigen Stand dazukamen. */
  zuwachs: Record<string, number>;
};

/** Die jüngste Meldung: der letzte Stand gegen den davor. Beim allerersten
 *  Stand ist alles Zuwachs. `null` ohne Verlauf. */
export function letzteMeldung(daten: Stichwahl): Meldung | null {
  const h = daten.history ?? [];
  if (h.length === 0) return null;
  const p = h[h.length - 1];
  const q = [...h].reverse().find((x) => x.reports_received < p.reports_received) ?? null;
  const zuwachs: Record<string, number> = {};
  for (const [slug, v] of Object.entries(p.votes)) zuwachs[slug] = v - (q?.votes[slug] ?? 0);
  return { at: p.at, bezirke: p.reports_received - (q?.reports_received ?? 0), zuwachs };
}

/** Der jüngste Führungswechsel — oder `null`. */
export function letzterWechsel(daten: Stichwahl): Stichwahl["lead_changes"][number] | null {
  const w = daten.lead_changes ?? [];
  return w.length ? w[w.length - 1] : null;
}

/** Nachname — für den Fenstertitel und die Zeile der Meldung. */
export function nachname(k: StichwahlKandidat): string {
  const teile = k.name.trim().split(/\s+/);
  return teile[teile.length - 1] ?? k.name;
}

/** Der Fenstertitel: die billigste Meldung, die es gibt — wer den Tab im
 *  Hintergrund hat, sieht den Stand trotzdem. */
export function fensterTitel(daten: Stichwahl): string {
  if (daten.phase === "before") return "Stichwahl · Ratslotse";
  const stand = nachStimmen(daten.candidates)
    .map((k) => `${nachname(k)} ${prozentKurz(k.share_pct)}`)
    .join(" · ");
  return `${stand} — ${daten.reports_received}/${daten.reports_expected} · Stichwahl`;
}

function prozentKurz(v: number | null): string {
  return v === null ? "–" : `${v.toFixed(1).replace(".", ",")}`;
}

/* ── Die Karte der Stichwahl (docs/plan-stichwahl-spannung.md S5) ───────── */

export type StichwahlBezirke = ApiAntwort<"/wahlabend/stichwahl/bezirke">;
export type StichwahlBezirk = StichwahlBezirke["districts"][number];

export function stichwahlBezirkePfad(probe: string | null, counted: string | null): string {
  const q = new URLSearchParams();
  if (probe) q.set("probe", probe);
  if (counted && /^\d+$/.test(counted)) q.set("counted", counted);
  const s = q.toString();
  return s ? `/wahlabend/stichwahl/bezirke?${s}` : "/wahlabend/stichwahl/bezirke";
}

/** Der Anteil einer Kandidatur an den Stimmen der beiden in einem Bezirk —
 *  im ersten Wahlgang (`first_round`) oder in der Stichwahl (`votes`).
 *  `null`, solange die Zahlen fehlen. */
export function bezirkAnteil(d: StichwahlBezirk, slug: string, quelle: "votes" | "first_round"): number | null {
  const stimmen = d[quelle];
  const mein = stimmen[slug];
  if (mein === null || mein === undefined) return null;
  let summe = 0;
  for (const v of Object.values(stimmen)) {
    if (v === null || v === undefined) return null;
    summe += v;
  }
  return summe > 0 ? Math.round((1000 * mein) / summe) / 10 : null;
}
