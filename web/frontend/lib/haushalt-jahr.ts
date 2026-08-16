// Der Weg eines Haushalts durch den Rat — Typen und die Rechenwege dazu.
//
// Gegenstück zu `GET /api/council/haushalt/weg` (council/store.py:
// `haushalt_weg`). Anders als der Rest des Haushalts-Bereichs kommen die
// Angaben hier nicht aus einem Finanzdokument, sondern aus den Ratsdaten:
// Beratungsfolge, Tagesordnung, Protokoll-Beschluss.
//
// Warum die Auswertung hier und nicht im Endpunkt: Es sind Aussagen ÜBER die
// Jahrgänge („der Entwurf kam siebenmal im Oktober"), keine Daten. Sie hängen
// daran, was die Seite behaupten will, und sie müssen sich mitverändern, wenn
// ein Jahrgang dazukommt — genau das verbietet die Hausregel, jahresabhängige
// Rechenaussagen als festen Text zu schreiben.

export type WegVotum = {
  id: number;
  ksinr: number;
  item_number: string | null;
  outcome: string | null;
  vote: string | null;
  gegenstimmen: number | null;
  enthaltungen: number | null;
};

export type WegStation = {
  kvonr: number;
  datum: string;
  gremium: string;
  /** Rolle laut Beratungsfolge: Kenntnisnahme, Vorberatung, Entscheidung. */
  rolle: string | null;
  is_public: number | null;
  ksinr: number;
  vorlage_nr: string | null;
  vorlage_titel: string;
  /** TOP-Nummer mit Präfix („Ö 6") — ohne Präfix zeigt der Link daneben. */
  top: string | null;
  /** Ergebnis in den Worten der Tagesordnung („geändert beschlossen"). */
  ergebnis: string | null;
  /** Der Beschluss über die Haushaltssatzung in dieser Sitzung, falls es ihn gibt. */
  votum: WegVotum | null;
};

export type WegRunde = {
  jahr: number;
  vorlage_nr: string | null;
  kvonr: number | null;
  einbringung: WegStation | null;
  fachausschuesse: { von: string; bis: string; anzahl: number; gremien: string[] } | null;
  stationen: WegStation[];
};

export type WegDaten = { runden: WegRunde[] };

export const MONATE = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

/** „2026-02-09" → „9. Februar 2026". */
export function deDatum(iso: string): string {
  const [j, m, t] = iso.split("-").map(Number);
  return `${t}. ${MONATE[m - 1]} ${j}`;
}

/** „2026-02-09" → „9. Februar" — wenn das Jahr schon danebensteht. */
export function deTagMonat(iso: string): string {
  const [, m, t] = iso.split("-").map(Number);
  return `${t}. ${MONATE[m - 1]}`;
}

/** Anteil des Jahres, an dem ein Datum liegt (0 = 1. Januar, 1 = Silvester).
 *  Bezugspunkt des Jahreskreises. */
export function jahresAnteil(iso: string): number {
  const [j, m, t] = iso.split("-").map(Number);
  const tag = Date.UTC(j, m - 1, t);
  const start = Date.UTC(j, 0, 1);
  const ende = Date.UTC(j + 1, 0, 1);
  return (tag - start) / (ende - start);
}

/** Die abschließende Station: die letzte im Rat, sonst schlicht die letzte.
 *  In den Ausschüssen wird vorberaten, entschieden wird im Rat. */
export function entscheidung(r: WegRunde): WegStation | null {
  const rat = r.stationen.filter((s) => s.gremium === "Rat");
  return rat[rat.length - 1] ?? r.stationen[r.stationen.length - 1] ?? null;
}

/** Tage zwischen dem Beschluss und dem Beginn des Haushaltsjahres.
 *  Negativ = vorher beschlossen, positiv = das Jahr lief schon. */
export function tageZumJahresbeginn(r: WegRunde): number | null {
  const e = entscheidung(r);
  if (!e) return null;
  const [j, m, t] = e.datum.split("-").map(Number);
  return Math.round((Date.UTC(j, m - 1, t) - Date.UTC(r.jahr, 0, 1)) / 86_400_000);
}

export type Rhythmus = {
  jahrgaenge: number;
  /** Monate, in denen der Entwurf eingebracht wurde — häufigster zuerst. */
  entwurfMonate: { monat: number; anzahl: number }[];
  /** Die beiden Ränder der Streuung, gemessen am Beginn des Haushaltsjahres. */
  frueheste: WegRunde | null;
  spaeteste: WegRunde | null;
  /** Jahrgänge, die erst im laufenden Haushaltsjahr beschlossen wurden. */
  imJahrSelbst: number;
};

/** Was sich über alle Jahrgänge sagen lässt — gerechnet, nicht geschrieben. */
export function rhythmus(runden: WegRunde[]): Rhythmus {
  const zaehler = new Map<number, number>();
  for (const r of runden) {
    if (!r.einbringung) continue;
    const m = Number(r.einbringung.datum.split("-")[1]);
    zaehler.set(m, (zaehler.get(m) ?? 0) + 1);
  }
  const entwurfMonate = [...zaehler.entries()]
    .map(([monat, anzahl]) => ({ monat, anzahl }))
    .sort((a, b) => b.anzahl - a.anzahl || a.monat - b.monat);

  const mitBeschluss = runden.filter((r) => tageZumJahresbeginn(r) !== null);
  const sortiert = [...mitBeschluss].sort(
    (a, b) => tageZumJahresbeginn(a)! - tageZumJahresbeginn(b)!,
  );
  return {
    jahrgaenge: runden.length,
    entwurfMonate,
    frueheste: sortiert[0] ?? null,
    spaeteste: sortiert[sortiert.length - 1] ?? null,
    imJahrSelbst: mitBeschluss.filter((r) => tageZumJahresbeginn(r)! >= 0).length,
  };
}

/** Die Wortwahl des Ratsinformationssystems auf die Ergebnis-Grammatik der App
 *  abbilden — für die Farbe des Abzeichens. Angezeigt wird trotzdem der
 *  Original-Wortlaut: „geändert beschlossen" sagt mehr als „Angenommen", und
 *  es ist die Formulierung, unter der man den Punkt im Original wiederfindet. */
export function ergebnisArt(
  ergebnis: string | null,
): "angenommen" | "abgelehnt" | "vertagt" | "zur_kenntnis" | "kein_beschluss" {
  const e = (ergebnis ?? "").toLowerCase();
  if (!e) return "kein_beschluss";
  if (e.includes("abgelehnt")) return "abgelehnt";
  if (e.includes("beschlossen")) return "angenommen";
  if (e.includes("kenntnis")) return "zur_kenntnis";
  if (e.includes("zurückgestellt") || e.includes("abgesetzt") || e.includes("verwiesen")) {
    return "vertagt";
  }
  return "kein_beschluss";
}
