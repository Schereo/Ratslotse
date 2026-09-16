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
  /** Castur und Stille — die Bezirksdatei führt sie nur als „Sonstige“. */
  others: Paar;
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
  { slug: "others", name: "Sonstige (Castur, Stille)", kurz: "Sonstige" },
];

/** Die Vorgaben aus dem Plan §2.1 — Tims Einschätzung in Zahlen, keine Messung. */
export const VORGABE: Regler = {
  boldt: { rohr: 55, prange: 15 },
  kuessner: { rohr: 45, prange: 15 },
  butzin: { rohr: 40, prange: 20 },
  froehlich: { rohr: 20, prange: 35 },
  wilkens: { rohr: 15, prange: 30 },
  others: { rohr: 30, prange: 30 },
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

/** Die Einstufung je Bezirk, wie das Backend sie nennt — und ihr Wort dazu. */
export const STRATEGIE: Record<string, { title: string; sentence: string }> = {
  hold: { title: "Halten", sentence: "Rohr lag hier im ersten Wahlgang vorn. Entscheidend ist, ob seine bisherigen Wählenden erneut abstimmen. Briefwahl anbieten." },
  persuade: { title: "Überzeugen", sentence: "Hier gab es viele Stimmen für Boldt, Butzin und Küßner. Gespräche stehen im Vordergrund." },
  both: { title: "Beides", sentence: "Hier kommen viele Rohr-Stimmen und Stimmen für andere Kandidaturen zusammen." },
  skip: { title: "Liegenlassen", sentence: "Der berechnete Wert ist niedrig. Diesen Bezirk zuletzt einplanen, wenn überhaupt." },
  postal: { title: "Briefwahl", sentence: "Die Briefwahlbezirke lassen sich keinem einzelnen Wohngebiet auf der Karte zuordnen." },
};

/** Tönungs-Modi der Karte: Feld, Beschriftung, Legende. */
export const TOENUNG = [
  { key: "yield_per_1000", title: "Ertrag je Tür", legend: "netto je 1.000 Wahlberechtigte" },
  { key: "rohr_pct_of_two", title: "Rohr-Anteil", legend: "Rohrs Anteil an den Stimmen für beide Kandidaten im ersten Wahlgang" },
  { key: "pool_pct", title: "Weitere Kandidaturen", legend: "Anteil der Stimmen für ausgeschiedene Kandidaturen an allen gültigen Stimmen" },
  { key: "cdu_council", title: "CDU", legend: "CDU-Stimmen bei der Ratswahl je 100 Wahlberechtigte" },
  { key: "non_voters", title: "Nichtwählende", legend: "Geschätzter Anteil der Nichtwählenden an den Wahlberechtigten" },
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
 *  gilt; „skip“ bleibt neutral. Token statt Hex, damit die Fläche in
 *  beiden Themes zu ihrem Grund passt. */
export const STRATEGIE_FARBE: Record<string, string | null> = {
  hold: "hsl(var(--signal) / 0.5)",
  both: "hsl(var(--signal) / 0.9)",
  persuade: "hsl(var(--primary) / 0.5)",
  skip: null,
  postal: null,
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
