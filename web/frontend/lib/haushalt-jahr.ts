// Der Weg eines Haushalts durch den Rat — Typen und die Rechenwege dazu.
//
// Gegenstück zu `GET /api/council/budget/journey` (council/store.py:
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
  no_votes: number | null;
  abstentions: number | null;
};

export type WegStation = {
  kvonr: number;
  date: string;
  committee: string;
  /** Rolle laut Beratungsfolge: Kenntnisnahme, Vorberatung, Entscheidung. */
  role: string | null;
  is_public: number | null;
  ksinr: number;
  template_number: string | null;
  template_title: string;
  /** TOP-Nummer mit Präfix („Ö 6") — ohne Präfix zeigt der Link daneben. */
  top: string | null;
  /** Ergebnis in den Worten der Tagesordnung („geändert beschlossen"). */
  result: string | null;
  /** Der Beschluss über die Haushaltssatzung in dieser Sitzung, falls es ihn gibt. */
  votum: WegVotum | null;
};

export type WegRunde = {
  year: number;
  template_number: string | null;
  kvonr: number | null;
  einbringung: WegStation | null;
  fachausschuesse: { von: string; bis: string; count: number; committees: string[] } | null;
  stationen: WegStation[];
};

export type WegDaten = { rounds: WegRunde[] };

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

/** Die abschließende Station: die letzte im Rat, sonst schlicht die letzte.
 *  In den Ausschüssen wird vorberaten, entschieden wird im Rat. */
export function entscheidung(r: WegRunde): WegStation | null {
  const rat = r.stationen.filter((s) => s.committee === "Rat");
  return rat[rat.length - 1] ?? r.stationen[r.stationen.length - 1] ?? null;
}

/** Tage zwischen dem Beschluss und dem Beginn des Haushaltsjahres.
 *  Negativ = vorher beschlossen, positiv = das Jahr lief schon. */
export function tageZumJahresbeginn(r: WegRunde): number | null {
  const e = entscheidung(r);
  if (!e) return null;
  const [j, m, t] = e.date.split("-").map(Number);
  return Math.round((Date.UTC(j, m - 1, t) - Date.UTC(r.year, 0, 1)) / 86_400_000);
}

export type Rhythmus = {
  jahrgaenge: number;
  /** Monate, in denen der Entwurf eingebracht wurde — häufigster zuerst. */
  entwurfMonate: { monat: number; count: number }[];
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
    const m = Number(r.einbringung.date.split("-")[1]);
    zaehler.set(m, (zaehler.get(m) ?? 0) + 1);
  }
  const entwurfMonate = [...zaehler.entries()]
    .map(([monat, count]) => ({ monat, count }))
    .sort((a, b) => b.count - a.count || a.monat - b.monat);

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

/** Die Runde, auf der der Zeitstrahl steht: das Haushaltsjahr, in dem
 *  „heute" liegt — das ist das Jahr, in dem das Geld gerade ausgegeben wird.
 *  Gibt es (noch) keine Runde zu diesem Jahr, trägt die jüngste. */
export function strahlRunde(runden: WegRunde[], heute: Date): WegRunde | null {
  return runden.find((r) => r.year === heute.getFullYear())
    ?? runden[runden.length - 1] ?? null;
}

/** Volle Monate zwischen zwei ISO-Daten (Monatsgrenzen, Tag ignoriert). */
export function monateZwischen(von: string, bis: string): number {
  const [vj, vm] = von.split("-").map(Number);
  const [bj, bm] = bis.split("-").map(Number);
  return (bj - vj) * 12 + (bm - vm);
}

/** Ein Jahresabschluss-Dokument, wie `/council/budget/documents` es
 *  liefert — gebraucht werden nur Jahr und das Datum der Sitzung, in der
 *  der Rat den Abschluss festgestellt hat. */
export type AbschlussDok = {
  year: number | null;
  official_text: { date: string | null } | null;
};

export type AbschlussMass = {
  /** Jahrgänge, deren Feststellungs-Datum im Bestand steht. */
  gezaehlt: number;
  /** Der häufigste Jahres-Versatz (1 = im Jahr darauf, 2 = im übernächsten). */
  versatz: number;
  /** Wie viele der gezählten Jahrgänge genau diesen Versatz haben. */
  mitVersatz: number;
  /** Median der Monate zwischen dem 1. Januar des Haushaltsjahres und der
   *  Feststellung — die Lage der Station auf dem Strahl. */
  medianMonate: number;
};

/** Wann der Rat Jahresabschlüsse festgestellt hat — gemessen an den
 *  Jahrgängen im Bestand, nicht behauptet. `null`, solange kein Abschluss
 *  einen Ratsvorgang mit Datum trägt: Dann bekommt der Strahl KEINE
 *  Abschluss-Station, statt eine zu raten (GB-11: `gemessen` ist Pflicht). */
export function jahresabschlussMass(doks: AbschlussDok[] | undefined): AbschlussMass | null {
  const monate: number[] = [];
  const versaetze = new Map<number, number>();
  for (const d of doks ?? []) {
    const date = d.official_text?.date;
    if (d.year == null || !date) continue;
    const [bj, bm] = date.split("-").map(Number);
    if (!bj || !bm) continue;
    monate.push((bj - d.year) * 12 + bm);
    versaetze.set(bj - d.year, (versaetze.get(bj - d.year) ?? 0) + 1);
  }
  if (!monate.length) return null;
  monate.sort((a, b) => a - b);
  const [versatz, mitVersatz] = [...versaetze.entries()]
    .sort((a, b) => b[1] - a[1] || a[0] - b[0])[0];
  return {
    gezaehlt: monate.length,
    versatz,
    mitVersatz,
    medianMonate: monate[Math.floor(monate.length / 2)],
  };
}

/** „im Jahr darauf" / „im übernächsten Jahr" / „drei Jahre später" — die
 *  Wortform des gemessenen Versatzes. */
export function versatzWort(versatz: number): string {
  if (versatz <= 0) return "noch im selben Jahr";
  if (versatz === 1) return "im Jahr darauf";
  if (versatz === 2) return "im übernächsten Jahr";
  return `${versatz} Jahre später`;
}

/** Eine kommende Sitzung aus `/council/sessions?scope=upcoming`. */
export type KommendeSitzung = {
  ksinr: number | null;
  committee: string;
  session_date: string;
  session_time: string | null;
  location: string | null;
};

/** Der nächste echte Termin der Gremien, in denen über den Haushalt
 *  abgestimmt wird (Finanzausschuss und Rat) — aus dem Ratskalender.
 *  MEHR sagt die Auswahl nicht: Ob dort der Haushalt aufgerufen wird, weiß
 *  erst die Tagesordnung, und die erscheint kurz vor dem Termin. Deshalb
 *  wird hier nach dem GREMIUM gefiltert, nie nach einem geratenen Inhalt. */
export function naechsterHaushaltsTermin(sitzungen: KommendeSitzung[] | undefined): KommendeSitzung | null {
  return (sitzungen ?? []).find(
    (s) => s.committee === "Rat" || s.committee.includes("Finanzen und Beteiligungen"),
  ) ?? null;
}

/** Die Wortwahl des Ratsinformationssystems auf die Ergebnis-Grammatik der App
 *  abbilden — für die Farbe des Abzeichens. Angezeigt wird trotzdem der
 *  Original-Wortlaut: „geändert beschlossen" sagt mehr als „Angenommen", und
 *  es ist die Formulierung, unter der man den Punkt im Original wiederfindet. */
export function ergebnisArt(
  result: string | null,
): "accepted" | "rejected" | "postponed" | "noted" | "no_decision" {
  const e = (result ?? "").toLowerCase();
  if (!e) return "no_decision";
  if (e.includes("abgelehnt")) return "rejected";
  if (e.includes("beschlossen")) return "accepted";
  if (e.includes("kenntnis")) return "noted";
  if (e.includes("zurückgestellt") || e.includes("abgesetzt") || e.includes("verwiesen")) {
    return "postponed";
  }
  return "no_decision";
}
