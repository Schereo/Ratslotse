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

/** Wer in einem Bezirk vorn liegt und wie deutlich — für die Karte. Gezählt
 *  zählt die Stichwahl, sonst der erste Wahlgang. `null` ohne Zahlen oder
 *  bei Gleichstand. */
export function bezirkFuehrung(d: StichwahlBezirk, slugs: readonly string[]): { slug: string; share: number; live: boolean } | null {
  const quelle = d.counted ? "votes" : "first_round";
  let best: { slug: string; share: number } | null = null;
  let gleich = false;
  for (const slug of slugs) {
    const share = bezirkAnteil(d, slug, quelle);
    if (share === null) return null;
    if (!best || share > best.share) { best = { slug, share }; gleich = false; }
    else if (share === best.share) gleich = true;
  }
  return best && !gleich ? { ...best, live: d.counted } : null;
}

/** Die Deckkraft einer Fläche: 50 % ist Gleichstand (kaum Farbe), `max` der
 *  deutlichste Vorsprung auf der Karte (volle Farbe). Offene Bezirke
 *  halb so kräftig — sie zeigen den ERSTEN Wahlgang. */
export function flaechenAlpha(share: number, max: number, live: boolean): number {
  const spanne = Math.max(5, max - 50);
  const anteil = Math.min(1, Math.max(0, (share - 50) / spanne));
  const a = 0.22 + 0.68 * anteil;
  return live ? a : a * 0.5;
}

/* ── Neue Zahlen sichtbar machen (Tims Wunsch 23.09.2026) ───────────────── */

/** Wer die jüngste Meldung gewonnen hat: die Kandidatur mit dem größten
 *  Zuwachs an Stimmen in den gerade dazugekommenen Bezirken. `null` bei
 *  Gleichstand oder ohne Zuwachs — dann leuchtet nichts auf.
 *
 *  Bewusst der Zuwachs und nicht die Veränderung des Anteils: Wer mit 45 %
 *  zurückliegt, gewinnt an Anteil schon mit einer 48-%-Meldung, obwohl der
 *  andere darin mehr Stimmen holte. „Wer hat diese Bezirke gewonnen" ist die
 *  Frage, die man beim Aufleuchten im Kopf hat. */
export function meldungsGewinner(m: Meldung | null): string | null {
  if (!m || m.bezirke <= 0) return null;
  const reihe = Object.entries(m.zuwachs).sort((a, b) => b[1] - a[1]);
  if (reihe.length === 0 || reihe[0][1] <= 0) return null;
  if (reihe.length > 1 && reihe[0][1] === reihe[1][1]) return null;
  return reihe[0][0];
}

/** Wie oft die Seite nachfragt: ab Wahlschluss alle 15 Sekunden, bis alles
 *  gezählt ist; sonst jede Minute. Schneller hilft nicht — das Backend holt
 *  selbst alle 15 s, und das CDN des Votemanagers hält jede Datei bis zu
 *  60 s (`election/mayor.py`, `TTL_LIVE`). */
export const TAKT_LIVE_MS = 15_000;
export const TAKT_RUHE_MS = 60_000;

export function abrufTakt(daten: Pick<Stichwahl, "phase" | "election" | "dataset"> | undefined, jetzt: Date = new Date()): number {
  if (!daten) return TAKT_RUHE_MS;
  if (daten.dataset === "probe") return TAKT_RUHE_MS;
  if (daten.phase === "complete") return TAKT_RUHE_MS;
  return zeitlage(daten.election.polls_close, jetzt).phase === "laeuft" ? TAKT_LIVE_MS : TAKT_RUHE_MS;
}

/* ── Mitfiebern: wem man die Daumen drückt ─────────────────────────────── */

/** Nur im eigenen Browser: Wem jemand die Daumen drückt, geht niemanden
 *  etwas an, und der Server erfährt es nie. Ein gesperrter Speicher
 *  (privates Fenster) heißt „niemand" — nie ein Absturz. */
const FAVORIT_SCHLUESSEL = "ratslotse:stichwahl-favorit";

export function ladeFavorit(wahl: string, erlaubt: readonly string[]): string | null {
  try {
    const roh = localStorage.getItem(FAVORIT_SCHLUESSEL);
    if (!roh) return null;
    const { wahl: w, slug } = JSON.parse(roh) as { wahl?: unknown; slug?: unknown };
    return w === wahl && typeof slug === "string" && erlaubt.includes(slug) ? slug : null;
  } catch {
    return null;
  }
}

export function speichereFavorit(wahl: string, slug: string | null): void {
  try {
    if (slug === null) localStorage.removeItem(FAVORIT_SCHLUESSEL);
    else localStorage.setItem(FAVORIT_SCHLUESSEL, JSON.stringify({ wahl, slug }));
  } catch {
    // Privates Fenster: Die Wahl gilt dann eben nur bis zum Neuladen.
  }
}

/* ── Countdown bis 18 Uhr (Tims Wunsch 23.09.2026) ─────────────────────── */

/** Wie lange noch bis Wahlschluss, als Text — `null`, sobald die Wahllokale
 *  zu sind. Am Wahltag selbst sekundengenau („2:14:07“), davor in Tagen und
 *  Stunden: Wer eine Woche vorher die Seite aufruft, braucht keine Sekunden. */
export function countdown(pollsClose: string, jetzt: Date = new Date()): { rest: number; text: string; sekundengenau: boolean } | null {
  const schluss = new Date(pollsClose).getTime();
  if (!Number.isFinite(schluss)) return null;
  const rest = schluss - jetzt.getTime();
  if (rest <= 0) return null;
  const s = Math.floor(rest / 1000);
  const tage = Math.floor(s / 86_400);
  const std = Math.floor((s % 86_400) / 3600);
  const min = Math.floor((s % 3600) / 60);
  const sek = s % 60;
  if (rest < 86_400_000) {
    const zwei = (n: number) => String(n).padStart(2, "0");
    return { rest, text: `${std}:${zwei(min)}:${zwei(sek)}`, sekundengenau: true };
  }
  return { rest, text: `${tage} ${tage === 1 ? "Tag" : "Tage"}, ${std} ${std === 1 ? "Stunde" : "Stunden"}`, sekundengenau: false };
}

/* ── Die Aufholrechnung ─────────────────────────────────────────────────── */

/** „Rohr bräuchte 51,1 % der noch offenen Stimmen — das Modell erwartet dort
 *  47,4 %.“ Die Zahlen rechnet das Backend (`runoff_model`); hier steht nur
 *  der Satz. `null`, wenn es nichts aufzuholen gibt. */
export function aufholText(p: StichwahlHochrechnung, kandidaten: readonly StichwahlKandidat[]): string | null {
  if (p.decided || !p.trailing || p.needed_share_pct === null) return null;
  const k = kandidaten.find((x) => x.slug === p.trailing);
  const wer = k ? nachname(k) : p.trailing;
  const zahl = (v: number) => `${v.toFixed(1).replace(".", ",")} %`;
  if (p.needed_share_pct > 100) {
    return `${wer} bräuchte mehr als alle Stimmen, die das Modell in den offenen Bezirken erwartet.`;
  }
  const erwartet = p.trailing_expected_share_pct;
  return erwartet === null
    ? `${wer} bräuchte ${zahl(p.needed_share_pct)} der noch offenen Stimmen.`
    : `${wer} bräuchte ${zahl(p.needed_share_pct)} der noch offenen Stimmen — das Modell erwartet dort ${zahl(erwartet)}.`;
}

/* ── Das Bild zum Teilen ────────────────────────────────────────────────── */

export type BildFormat = "beitrag" | "story" | "quer";

export function stichwahlBildPfad(format: BildFormat, probe: string | null, counted: string | null): string {
  const q = new URLSearchParams({ format });
  if (probe) q.set("probe", probe);
  if (counted && /^\d+$/.test(counted)) q.set("counted", counted);
  return `/wahlabend/stichwahl/bild.png?${q.toString()}`;
}
