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
