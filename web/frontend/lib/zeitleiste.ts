/**
 * Die Rechnung hinter der Zeitleiste einer Bewegung — ohne React.
 *
 * **Die Achse kommt vom Server** (`axis` in `/council/cities/movements`), vom
 * Jahresanfang der frühesten bis zum Jahresende der spätesten Vorlage im
 * GANZEN Bestand. Gerechnet wird hier nur, wo ein Datum darauf liegt. Würde
 * jede Karte ihre eigene Achse bilden, stünde „2024" auf der einen links und
 * auf der nächsten in der Mitte — und niemand könnte zwei Ideen vergleichen.
 *
 * Dieselbe Rechnung steht in der App (`Zeitleiste` in `MovementViews.swift`);
 * wer hier etwas ändert, ändert es dort mit.
 */

export type Achse = { start: string | null; end: string | null };
export type Punkt = {
  paper_id: string;
  city: string;
  date: string | null;
  outcome: string;
  kind: string;
};

/** Fünf Stufen, nicht acht: Wer eine Leiste überfliegt, unterscheidet
 *  „beschlossen", „abgelehnt", „hängt", „zur Kenntnis" und „offen" — ob
 *  vertagt oder verwiesen, sagt der Titel des Punktes. */
export type Stufe = "ok" | "no" | "wait" | "neu" | "open";

const STUFEN: Record<string, Stufe> = {
  accepted: "ok",
  amended: "ok",
  rejected: "no",
  postponed: "wait",
  referred: "wait",
  noted: "neu",
  withdrawn: "open",
  none: "open",
};

export function stufe(outcome: string | null | undefined): Stufe {
  return STUFEN[outcome ?? "none"] ?? "open";
}

export const STUFE_TEXT: Record<Stufe, string> = {
  ok: "beschlossen",
  no: "abgelehnt",
  wait: "vertagt oder verwiesen",
  neu: "zur Kenntnis",
  open: "ohne Ergebnis",
};

/** Die Reihenfolge der Legende — vom Klaren zum Offenen. */
export const STUFEN_REIHE: Stufe[] = ["ok", "no", "wait", "neu", "open"];

function tage(iso: string): number {
  return Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7) || "1") - 1,
                  Number(iso.slice(8, 10) || "1")) / 86_400_000;
}

/** Wo ein Datum auf der Achse liegt, als Anteil 0…1 — `null` ohne Datum.
 *
 *  Außerhalb der Achse wird geklemmt, nicht verworfen: Eine Vorlage vom
 *  31.12. darf nicht verschwinden, weil die Achse am 01.01. endet. */
export function anteil(datum: string | null | undefined, achse: Achse): number | null {
  if (!datum || !achse.start || !achse.end) return null;
  const a = tage(achse.start);
  const b = tage(achse.end);
  if (!(b > a)) return 0.5;
  return Math.min(1, Math.max(0, (tage(datum) - a) / (b - a)));
}

/** Die Jahresmarken — je Jahreswechsel innerhalb der Achse eine. */
export function jahresmarken(achse: Achse): { jahr: number; anteil: number }[] {
  if (!achse.start || !achse.end) return [];
  const von = Number(achse.start.slice(0, 4));
  const bis = Number(achse.end.slice(0, 4));
  const marken: { jahr: number; anteil: number }[] = [];
  for (let jahr = von; jahr <= bis; jahr++) {
    const a = anteil(`${jahr}-01-01`, achse);
    if (a !== null) marken.push({ jahr, anteil: a });
  }
  return marken;
}

const ZAHLWORT = ["", "einmal", "zweimal", "dreimal", "viermal", "fünfmal"];
function mal(n: number): string {
  return ZAHLWORT[n] ?? `${n}-mal`;
}

/** Die Leiste als Satz — für Vorlesesoftware, die keine Punkte sieht.
 *
 *  „6 Städte, 2023 bis 2026: dreimal beschlossen, zweimal abgelehnt, einmal
 *  ohne Ergebnis." */
export function satz(punkte: Punkt[]): string {
  if (punkte.length === 0) return "Keine Vorlagen.";
  const staedte = new Set(punkte.map((p) => p.city)).size;
  const jahre = punkte.map((p) => p.date?.slice(0, 4)).filter(Boolean) as string[];
  const von = jahre.length ? jahre.reduce((a, b) => (a < b ? a : b)) : null;
  const bis = jahre.length ? jahre.reduce((a, b) => (a > b ? a : b)) : null;
  const zeitraum = von && bis ? (von === bis ? ` ${von}` : ` ${von} bis ${bis}`) : "";
  const zaehler = new Map<Stufe, number>();
  for (const p of punkte) zaehler.set(stufe(p.outcome), (zaehler.get(stufe(p.outcome)) ?? 0) + 1);
  const teile = STUFEN_REIHE.filter((s) => zaehler.get(s))
    .map((s) => `${mal(zaehler.get(s)!)} ${STUFE_TEXT[s]}`);
  const kopf = staedte === 1 ? "1 Stadt" : `${staedte} Städte`;
  return `${kopf},${zeitraum}: ${teile.join(", ")}.`;
}

/** Punkte, die auf dieselbe Stelle fallen würden, in Spuren legen.
 *
 *  Zwei Vorlagen derselben Woche lägen sonst übereinander — bei der
 *  Wärmeplanung (27 Vorlagen) wurden daraus Ketten aus halben Ringen.
 *  Die erste Fassung schob solche Punkte nach RECHTS; bei dichten Gruppen
 *  summierte sich das, und ein Punkt stand Monate neben seinem Datum. Jetzt
 *  bleibt jeder Punkt an seinem Datum und weicht nach oben oder unten aus:
 *  Spur 0 ist die Linie, dann +1, −1, … bis `spuren` Stück. Ist keine frei,
 *  überlappt er in Spur 0 — lieber übereinander als am falschen Tag.
 *
 *  `abstand` ist der kleinste Abstand als Anteil der Breite: 11 px Punkt auf
 *  rund 340 px Kartenbreite sind gut 0,03. */
export function spuren(anteile: number[], abstand = 0.032, spuren = 3): number[] {
  const reihe = [0, 1, -1, 2, -2].slice(0, spuren);
  const letzte = new Map<number, number>();
  return anteile.map((a) => {
    const frei = reihe.find((s) => a - (letzte.get(s) ?? -Infinity) >= abstand) ?? 0;
    letzte.set(frei, a);
    return frei;
  });
}
