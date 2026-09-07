/**
 * Wahlabend: reine Helfer für die Seite `/wahlabend`.
 *
 * Die Zahlen kommen fertig gerechnet vom Backend (`GET /api/wahlabend`,
 * Sitzzuteilung nach NKWG §§ 36, 37 in `web/backend/app/election/`). Hier
 * steht nur, was die Anzeige daraus macht: Formate, Sortierung, der Status
 * einer Kandidatur in Worten.
 */
import type { ApiAntwort } from "./vertrag";

export type Wahlabend = ApiAntwort<"/wahlabend">;
export type WahlabendPartei = Wahlabend["parties"][number];
export type WahlabendBereich = Wahlabend["areas"][number];
export type WahlabendBereichPartei = WahlabendBereich["parties"][number];
export type WahlabendKandidat = WahlabendBereichPartei["candidates"][number];
export type WahlabendMandat = Wahlabend["mandates"][number];

/** Schlüssel im localStorage: die zuletzt gewählte Liste. */
export const LISTE_SPEICHER = "wahlabend.liste";

const ZAHL = new Intl.NumberFormat("de-DE");

export function zahl(n: number | null | undefined): string {
  return n === null || n === undefined ? "–" : ZAHL.format(n);
}

export function prozent(n: number | null | undefined, stellen = 1): string {
  if (n === null || n === undefined) return "–";
  return `${n.toFixed(stellen).replace(".", ",")} %`;
}

/** Abstand in Prozentpunkten, mit Vorzeichen: „+2,4" / „−1,0"; null ohne Vergleich. */
export function delta(jetzt: number | null | undefined, vorher: number | null | undefined): string | null {
  if (jetzt === null || jetzt === undefined || vorher === null || vorher === undefined) return null;
  const d = jetzt - vorher;
  const text = Math.abs(d).toFixed(1).replace(".", ",");
  if (Math.abs(d) < 0.05) return "±0,0";
  return d > 0 ? `+${text}` : `−${text}`;
}

/** Uhrzeit eines ISO-Zeitstempels in deutscher Zeit, „20:14". */
export function uhrzeit(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
}

/** „21:26 Uhr" am selben Tag, sonst „31.08., 12:54 Uhr" — ein alter
 *  Stand soll nicht wie ein frischer aussehen. */
export function standText(iso: string | null | undefined, jetzt: Date = new Date()): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const tag = (x: Date) => x.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", timeZone: "Europe/Berlin" });
  const zeit = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
  return tag(d) === tag(jetzt) ? `${zeit} Uhr` : `${tag(d)}, ${zeit} Uhr`;
}

export function fortschritt(gezaehlt: number, gesamt: number): number {
  if (gesamt <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((100 * gezaehlt) / gesamt)));
}

/** Nach Stimmen absteigend; ohne Zahl nach hinten, dort Stimmzettel-Reihenfolge. */
export function nachStimmen<T extends { votes: number | null; index: number }>(parteien: readonly T[]): T[] {
  return [...parteien].sort((a, b) => {
    if (a.votes === null && b.votes === null) return a.index - b.index;
    if (a.votes === null) return 1;
    if (b.votes === null) return -1;
    return b.votes - a.votes || a.index - b.index;
  });
}

export type StatusTon = "seated" | "shaky" | "projected" | "close" | "open" | "out" | "unknown";

/** Ab wie vielen fehlenden Stimmen es „knapp" heißt — in einem Wahlbereich
 *  mit rund 6.000 Wähler*innen je Liste sind 250 Personenstimmen ein Abend. */
export const KNAPP_BIS = 250;

function art(kind: string | null): string {
  if (kind === "direct") return "direkt";
  if (kind === "list") return "über die Liste";
  if (kind === "transfer") return "aus einem anderen Wahlbereich";
  return "";
}

/**
 * Der Status einer Kandidatur in Worten. `phase` und `personen` kommen vom
 * Backend: Vor der Auszählung gibt es nichts zu sagen, und ohne
 * Personenstimmen kennt niemand die Namen — dann sagt der Status genau das.
 */
export function kandidatenStatus(
  k: Pick<WahlabendKandidat, "votes" | "elected" | "projected_elected" | "votes_to_seat">,
  phase: string,
  personen: boolean,
  bereichGezaehlt = true,
): { ton: StatusTon; text: string } {
  if (phase === "before" || !bereichGezaehlt) return { ton: "unknown", text: "noch nichts ausgezählt" };
  if (!personen || k.votes === null) return { ton: "unknown", text: "Personenstimmen fehlen noch" };
  if (k.elected) {
    if (phase === "counting" && k.projected_elected === null) {
      return { ton: "shaky", text: `drin · ${art(k.elected)} · Hochrechnung: raus` };
    }
    return { ton: "seated", text: `drin · ${art(k.elected)}` };
  }
  if (k.projected_elected) return { ton: "projected", text: `Hochrechnung: drin · ${art(k.projected_elected)}` };
  if (k.votes_to_seat !== null && k.votes_to_seat > 0) {
    const text = `${zahl(k.votes_to_seat)} Stimmen bis zum Sitz`;
    return { ton: k.votes_to_seat <= KNAPP_BIS ? "close" : "open", text };
  }
  return { ton: "out", text: "außer Reichweite" };
}

/** Die Punkte des Sitzbands: je Sitz einer, in Stimmzettel-Reihenfolge der Listen. */
export function sitzband(
  parteien: readonly WahlabendPartei[],
  feld: "seats" | "projected_seats",
): { slug: string; short: string; color: string; color_dark: string; n: number }[] {
  return parteien
    .map((p) => ({ slug: p.slug, short: p.short, color: p.color, color_dark: p.color_dark, n: p[feld] ?? 0 }))
    .filter((p) => p.n > 0);
}

/** Query-String für den Abruf: Generalprobe und Auszählungsstand durchreichen. */
export function abfragePfad(probe: string | null, counted: string | null): string {
  const q = new URLSearchParams();
  if (probe) q.set("probe", probe);
  if (counted && /^\d+$/.test(counted)) q.set("counted", counted);
  const s = q.toString();
  return s ? `/wahlabend?${s}` : "/wahlabend";
}

/* ── Sitze, Mehrheiten, Halbkreis ───────────────────────────────────────── */

/** Absolute Mehrheit: mehr als die Hälfte der Sitze — bei 52 also 27. */
export function mehrheit(sitze: number): number {
  return Math.floor(sitze / 2) + 1;
}

export type Koalition = { slugs: string[]; seats: number };

/**
 * Rechnerisch mögliche Mehrheitsbündnisse: jede Gruppe von Listen, die
 * zusammen die Mehrheit hat und aus der KEIN Partner entfallen könnte, ohne
 * sie zu verlieren (minimal). Nur Rechnung, keine Politik — wer mit wem
 * kann, sagt die Liste nicht. Höchstens `maxPartner` Partner, sonst wird die
 * Aufzählung lang und sagt nichts mehr.
 */
export function koalitionen(
  parteien: readonly { slug: string; seats: number | null }[],
  gesamt: number,
  maxPartner = 3,
): Koalition[] {
  const noetig = mehrheit(gesamt);
  const mit = parteien
    .map((p) => ({ slug: p.slug, seats: p.seats ?? 0 }))
    .filter((p) => p.seats > 0)
    .sort((a, b) => b.seats - a.seats);
  const out: Koalition[] = [];
  const n = mit.length;
  for (let maske = 1; maske < 1 << n; maske++) {
    const glieder = mit.filter((_, i) => maske & (1 << i));
    if (glieder.length > maxPartner) continue;
    const summe = glieder.reduce((s, g) => s + g.seats, 0);
    if (summe < noetig) continue;
    if (!glieder.every((g) => summe - g.seats < noetig)) continue;
    out.push({ slugs: glieder.map((g) => g.slug), seats: summe });
  }
  return out.sort((a, b) => a.slugs.length - b.slugs.length || b.seats - a.seats);
}

export type HalbkreisPunkt = { x: number; y: number; r: number; reihe: number };

/**
 * Die Plätze eines Halbkreis-Parlaments, links nach rechts, in einem Kasten
 * von 2 × 1 (Mittelpunkt unten bei 1|1). Die Reihen bekommen Plätze im
 * Verhältnis ihres Umfangs, damit die Abstände überall gleich aussehen; die
 * Rückgabe ist nach Winkel sortiert, die Listen füllen sie der Reihe nach.
 */
export function halbkreis(n: number, reihen = 3, innen = 0.48): HalbkreisPunkt[] {
  if (n <= 0) return [];
  const radien = Array.from({ length: reihen }, (_, i) => (reihen === 1 ? 1 : innen + (i * (1 - innen)) / (reihen - 1)));
  const summe = radien.reduce((s, r) => s + r, 0);
  const jeReihe = radien.map((r) => Math.floor((n * r) / summe));
  let rest = n - jeReihe.reduce((s, k) => s + k, 0);
  for (let i = reihen - 1; rest > 0; i = (i - 1 + reihen) % reihen, rest--) jeReihe[i] += 1;
  const lueckeReihe = reihen > 1 ? (1 - innen) / (reihen - 1) : 0.3;
  const punkte: (HalbkreisPunkt & { winkel: number })[] = [];
  radien.forEach((r, i) => {
    const m = jeReihe[i];
    const bogen = (Math.PI * r) / Math.max(m, 1);
    const radius = Math.min(lueckeReihe, bogen) * 0.34;
    for (let j = 0; j < m; j++) {
      const winkel = Math.PI * (1 - (j + 0.5) / m);
      punkte.push({ x: 1 + r * Math.cos(winkel), y: 1 - r * Math.sin(winkel), r: radius, reihe: i, winkel });
    }
  });
  return punkte
    .sort((a, b) => b.winkel - a.winkel || a.reihe - b.reihe)
    .map(({ x, y, r, reihe }) => ({ x, y, r, reihe }));
}

/* ── Kandidatenrennen und Bild ──────────────────────────────────────────── */

/** Die Sitzgrenze einer Liste im Wahlbereich: die Stimmen des schwächsten
 *  Personensitzes. Ohne Personensitz gibt es keine Grenze (null) — ein
 *  Listensitz hängt an der Reihenfolge, nicht an einer Stimmenzahl. */
export function sitzgrenze(kandidaten: readonly Pick<WahlabendKandidat, "votes" | "elected">[]): number | null {
  const direkt = kandidaten.filter((k) => k.elected === "direct" && k.votes !== null).map((k) => k.votes as number);
  return direkt.length ? Math.min(...direkt) : null;
}

/** Pfad des teilbaren Bilds (ohne `/api`, wie bei `api.get`). */
export function bildPfad(feld: "seats" | "projected_seats", probe: string | null, counted: string | null): string {
  const q = new URLSearchParams({ feld });
  if (probe) q.set("probe", probe);
  if (counted && /^\d+$/.test(counted)) q.set("counted", counted);
  return `/wahlabend/bild.png?${q.toString()}`;
}

/* ── Wann ist Wahlabend? ────────────────────────────────────────────────── */

/** 13.09.2026, 18:00 Uhr in Oldenburg (MESZ = UTC+2): Die Wahllokale schließen,
 *  ab hier „läuft" der Wahlabend. */
export const WAHLABEND_BEGINN_UTC = Date.UTC(2026, 8, 13, 16, 0, 0);

export type WahlabendZeit = {
  phase: "vorher" | "laeuft";
  /** Kalendertage bis zum Wahltag in deutscher Zeit; 0 am Wahltag selbst. */
  tage: number;
  /** Kurz, für den Mono-Kicker: „NOCH 6 TAGE", „HEUTE AB 18 UHR", „LIVE". */
  kicker: string;
  /** Ein Satzanfang für Überschriften: „Am Sonntag ab 18 Uhr", „Heute ab 18 Uhr". */
  wann: string;
};

function berlinerTag(d: Date): number {
  const t = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  const [j, m, tag] = t.split("-").map(Number);
  return Date.UTC(j, m - 1, tag);
}

/** Vor dem Wahlabend zählt die Seite herunter, danach „läuft" sie — dieselbe
 *  Regel für Landing, Heute-Seite und die Tafel. */
export function wahlabendZeit(jetzt: Date = new Date()): WahlabendZeit {
  if (jetzt.getTime() >= WAHLABEND_BEGINN_UTC) return { phase: "laeuft", tage: 0, kicker: "Live", wann: "Jetzt" };
  const tage = Math.max(0, Math.round((Date.UTC(2026, 8, 13) - berlinerTag(jetzt)) / 86_400_000));
  if (tage === 0) return { phase: "vorher", tage, kicker: "Heute ab 18 Uhr", wann: "Heute ab 18 Uhr" };
  if (tage === 1) return { phase: "vorher", tage, kicker: "Morgen ab 18 Uhr", wann: "Morgen ab 18 Uhr" };
  return { phase: "vorher", tage, kicker: `Noch ${tage} Tage`, wann: "Am Sonntag ab 18 Uhr" };
}
