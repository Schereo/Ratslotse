/**
 * Das Wähler*innen-Potenzial für die Stichwahl — Helfer für die Seite
 * `/stichwahl/potenzial?k=<token>` (docs/plan-stichwahl-potenzial.md, P2).
 *
 * Gerechnet wird im Backend (`potential.py`); hier stehen nur der Pfad mit
 * den Reglern, ihre Vorgaben und die Worte für die Anzeige. Die Seite hängt an
 * einem Token aus der `.env`; ohne ihn antwortet der Server 404, und die
 * Seite zeigt dasselbe wie für eine Adresse, die es nicht gibt.
 */
import type { ApiAntwort } from "./vertrag";

export type Potenzial = ApiAntwort<"/wahlabend/stichwahl/potenzial">;
export type PotenzialBezirk = Potenzial["districts"][number];
export type PotenzialBuendel = Potenzial["bundles"][number];

/** Ein Reglerpaar: Anteil zu Rohr, Anteil zu Prange, in Prozent. */
export type Paar = { rohr: number; prange: number };

export type Regler = {
  boldt: Paar;
  kuessner: Paar;
  butzin: Paar;
  froehlich: Paar;
  wilkens: Paar;
  cdu: Paar;
  /** Beteiligung in Prozent der Erstrunden-Wählenden je Lager. */
  turnoutRohr: number;
  turnoutPrange: number;
  turnoutPool: number;
};

export const KANDIDATUREN: { slug: keyof Omit<Regler, "cdu" | "turnoutRohr" | "turnoutPrange" | "turnoutPool">; name: string; kurz: string }[] = [
  { slug: "boldt", name: "Heike Boldt (Linke)", kurz: "Boldt" },
  { slug: "kuessner", name: "Byanca Küßner", kurz: "Küßner" },
  { slug: "butzin", name: "Ralf Butzin", kurz: "Butzin" },
  { slug: "froehlich", name: "Sebastian Fröhlich (FDP)", kurz: "Fröhlich" },
  { slug: "wilkens", name: "Holger Martin Wilkens (BB-OL)", kurz: "Wilkens" },
];

/** Die Vorgaben aus dem Plan §2.1 — Tims Einschätzung in Zahlen, keine Messung. */
export const VORGABE: Regler = {
  boldt: { rohr: 55, prange: 15 },
  kuessner: { rohr: 45, prange: 15 },
  butzin: { rohr: 40, prange: 20 },
  froehlich: { rohr: 20, prange: 35 },
  wilkens: { rohr: 15, prange: 30 },
  cdu: { rohr: 25, prange: 25 },
  turnoutRohr: 100,
  turnoutPrange: 100,
  turnoutPool: 100,
};

/** Der Pfad zum Endpunkt — nur Regler, die von der Vorgabe abweichen, stehen
 *  drin, damit die Adresse lesbar bleibt. */
export function potenzialPfad(token: string, r: Regler): string {
  const q = new URLSearchParams();
  q.set("token", token);
  for (const k of KANDIDATUREN) {
    if (r[k.slug].rohr !== VORGABE[k.slug].rohr || r[k.slug].prange !== VORGABE[k.slug].prange) {
      q.set(k.slug, `${Math.round(r[k.slug].rohr)},${Math.round(r[k.slug].prange)}`);
    }
  }
  if (r.cdu.rohr !== VORGABE.cdu.rohr || r.cdu.prange !== VORGABE.cdu.prange) q.set("cdu", `${Math.round(r.cdu.rohr)},${Math.round(r.cdu.prange)}`);
  if (r.turnoutRohr !== 100) q.set("turnout_rohr", String(r.turnoutRohr));
  if (r.turnoutPrange !== 100) q.set("turnout_prange", String(r.turnoutPrange));
  if (r.turnoutPool !== 100) q.set("turnout_pool", String(r.turnoutPool));
  return `/wahlabend/stichwahl/potenzial?${q.toString()}`;
}

/** Ein Paar so setzen, dass beide zusammen nie über 100 gehen — wer den einen
 *  Regler hochzieht, drückt den anderen. */
export function paarSetzen(p: Paar, seite: keyof Paar, wert: number): Paar {
  const w = Math.max(0, Math.min(100, Math.round(wert)));
  const andere = seite === "rohr" ? "prange" : "rohr";
  return { ...p, [seite]: w, [andere]: Math.min(p[andere], 100 - w) };
}

export const STRATEGIE: Record<string, { titel: string; satz: string }> = {
  halten: { titel: "Halten", satz: "Rohr liegt hier vorn — die Basis muss am 27.09. kommen. Briefwahl anbieten." },
  ueberzeugen: { titel: "Überzeugen", satz: "Hier wohnen die Umworbenen — Linke, Butzin, Küßner. Ansprechen, nicht bekräftigen." },
  beides: { titel: "Beides", satz: "Starke Basis und großer Pool — hier lohnt jede Tür doppelt." },
  liegenlassen: { titel: "Liegenlassen", satz: "Wenig zu holen je Tür. Zuletzt, wenn überhaupt." },
  brief: { titel: "Briefwahl", satz: "Keine Fläche, keine Türen — die Stimmen kommen von überall." },
};

/** Tönungs-Modi der Karte: Feld, Beschriftung, Legende. */
export const TOENUNG = [
  { key: "yield_per_1000", titel: "Ertrag je Tür", legende: "netto je 1.000 Wahlberechtigte" },
  { key: "rohr_pct_of_two", titel: "Rohr-Anteil", legende: "Rohr an den Stimmen der beiden, 1. Wahlgang" },
  { key: "pool_pct", titel: "Umworbene", legende: "Stimmen der Ausgeschiedenen, Anteil an den gültigen" },
  { key: "cdu_council", titel: "CDU", legende: "CDU-Zweitstimmen der Ratswahl" },
  { key: "non_voters", titel: "Nichtwählende", legende: "Wahlberechtigte, die nicht kamen" },
] as const;
export type ToenungKey = (typeof TOENUNG)[number]["key"];

/** Der Saldo als Satz. */
export function saldoSatz(balance: number): string {
  if (balance > 0) return `Rohr läge ${balance.toLocaleString("de-DE")} Stimmen vorn.`;
  if (balance < 0) return `Prange läge ${Math.abs(balance).toLocaleString("de-DE")} Stimmen vorn.`;
  return "Gleichstand — dann entscheidet das Los.";
}

/** Welche Zahl je Bezirk die Karte tönt — die Brief-Bezirke haben keine
 *  Fläche und deshalb keinen Wert. CDU und Nichtwählende werden auf die
 *  Wahlberechtigten bezogen, sonst tönt die Karte nur die Bezirksgröße. */
export type ToenbarerBezirk = Pick<PotenzialBezirk, "eligible" | "non_voters" | "rohr_pct_of_two" | "pool_pct" | "cdu_council" | "yield_per_1000" | "postal">;

export function toenungWert(z: ToenbarerBezirk, key: ToenungKey): number | null {
  if (z.postal) return null;
  switch (key) {
    case "yield_per_1000": return z.yield_per_1000;
    case "rohr_pct_of_two": return z.rohr_pct_of_two;
    case "pool_pct": return z.pool_pct;
    case "cdu_council": return z.eligible > 0 ? Math.round((1000 * z.cdu_council) / z.eligible) / 10 : null;
    case "non_voters": return z.eligible > 0 ? Math.round((1000 * z.non_voters) / z.eligible) / 10 : null;
  }
}

/** Die Kartenfarbe je Strategie — Rohr-Orange (`--signal`) für die Basis,
 *  Hafenblau (`--primary`) für die Umworbenen, beides kräftig, wo beides
 *  gilt; „liegenlassen" bleibt neutral. Token statt Hex, damit die Fläche in
 *  beiden Themes zu ihrem Grund passt. */
export const STRATEGIE_FARBE: Record<string, string | null> = {
  halten: "hsl(var(--signal) / 0.5)",
  beides: "hsl(var(--signal) / 0.9)",
  ueberzeugen: "hsl(var(--primary) / 0.5)",
  liegenlassen: null,
  brief: null,
};

/** Die Haken der Einsatzliste — nur in diesem Browser, nie auf dem Server:
 *  die Seite hat kein Konto, und wer sie sieht, hat den Link. */
export const UEBERNOMMEN_KEY = "stichwahl-potenzial-uebernommen";

export function uebernommenLesen(speicher: Storage): Set<number> {
  try {
    const roh = speicher.getItem(UEBERNOMMEN_KEY);
    const liste: unknown = roh ? JSON.parse(roh) : [];
    return new Set(Array.isArray(liste) ? liste.filter((n): n is number => typeof n === "number") : []);
  } catch {
    return new Set();
  }
}

export function uebernommenSchreiben(speicher: Storage, nummern: Set<number>): void {
  try {
    speicher.setItem(UEBERNOMMEN_KEY, JSON.stringify([...nummern]));
  } catch {
    // Privates Fenster oder voller Speicher — der Haken gilt dann nur bis zum Neuladen.
  }
}
