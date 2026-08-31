// Typen und Rechenwege für „Was in den Listen stand" — die Inhalts-Ebene
// unter dem Streit-Abschnitt (/haushalt/mitreden#streit).
//
// Die Daten kommen aus `/council/haushalt/aenderungslisten`: je Dokument
// (Verw. I–III, Beschluss-Datei des AFB) die Positionen des
// Haushaltsjahrgangs und die Zusammenstellungen aller Planjahre. Jede
// Positionsliste wurde beim Einlesen gegen ihre eigene Zusammenstellung
// bewiesen (council/aenderungslisten.py) — hier wird nur noch angeordnet.

import type { Herkunft } from "@/lib/herkunft";

export type { Herkunft };

export type AenderungsZeile = {
  budget_year: number;
  list_key: string;
  year: number;
  seq: number;
  /** `null` = die Position gilt pauschal „alle" Teilhaushalte (2019). */
  sub_budget: number | null;
  page_draft: number | null;
  product: string | null;
  label: string;
  /** Euro, negativ = Minderung; `null` = kein Betrag in dieser Spalte. */
  revenue: number | null;
  expense: number | null;
  /** Die Erläuterungs-Spalte des Dokuments — was diese Änderung ist.
   *  `null` = Zelle leer oder Zuordnung nicht eindeutig (dann lieber gar
   *  kein Text als einer von der falschen Zeile). */
  explanation: string | null;
  /** Wer die Position vorgeschlagen hat („Verw. I", „SPD/ BÜNDNIS 90/ DIE
   *  GRÜNEN"). `null` überall dort, wo das Dokument die Spalte „Vorschlag
   *  von" nicht führt — das sind alle Jahrgänge außer 2021. */
  author: string | null;
  document_id: number;
  herkunft_id: number | null;
};

export type AenderungsSumme = {
  budget_year: number;
  list_key: string;
  year: number;
  kind: string; // "entwurf" | "liste" | "endsumme"
  label: string;
  revenues: number;
  expenses: number;
  balance: number;
  /** 1 = die Zeile, die die Positionen dieses Dokuments summiert. */
  own: number;
  document_id: number;
  herkunft_id: number | null;
};

/** Eine Position einer FINANZhaushalts-Änderungsliste.
 *
 *  Andere Form als beim Ergebnishaushalt, und deshalb ein eigener Typ: fünf
 *  Betragsspalten statt zwei, dazu der Investitionscode. Die Namen sind die
 *  des Dokuments — „Soll laut Entwurf", „neues Soll" —, damit sich die Zeile
 *  im PDF wiederfinden lässt. */
export type FhhZeile = {
  budget_year: number;
  list_key: string;
  year: number;
  seq: number;
  sub_budget: number | null;
  /** Auch „neu": Dann steht die Position im Entwurf noch gar nicht. */
  page_draft: string | null;
  /** Der Investitionscode des Programms („I10.089904.500") — über ihn führt
   *  der Weg zum Vorhaben auf `/haushalt/investitionen`. `null`, wo die
   *  Position keinem einzelnen Vorhaben zugeordnet ist. */
  product: string | null;
  label: string;
  /** Euro. `null` = Zelle leer (reine Haushaltsvermerke tragen gar keine
   *  Beträge), `0` = Gedankenstrich, also eine ausdrückliche Null. */
  planned_draft: number | null;
  inflow: number | null;
  outflow: number | null;
  /** Verpflichtungsermächtigungen — zählen NICHT in den Saldo. */
  commitment_authorizations: number | null;
  planned_new: number | null;
  explanation: string | null;
  author: string | null;
  document_id: number;
  herkunft_id: number | null;
};

export type FhhSumme = {
  budget_year: number;
  list_key: string;
  year: number;
  kind: string;
  label: string;
  inflows: number;
  outflows: number;
  balance: number;
  commitment_authorizations: number | null;
  own: number;
  document_id: number;
  herkunft_id: number | null;
};

export type AenderungslistenDaten = {
  zeilen: AenderungsZeile[];
  summen: AenderungsSumme[];
  /** Der Finanzhaushalt — leer, solange sein Ingest nicht gelaufen ist. */
  fhh_zeilen?: FhhZeile[];
  fhh_summen?: FhhSumme[];
  herkunft: Record<string, Herkunft>;
};

export function herkunftVon(
  daten: AenderungslistenDaten | null, id: number | null | undefined,
): Herkunft | null {
  return daten && id != null ? daten.herkunft[String(id)] ?? null : null;
}

/** Anzeige-Namen der Dokumente. Die Schlüssel kommen aus
 *  `council/aenderungslisten.py: liste_aus_label` — wer dort einen neuen
 *  ergänzt, zieht ihn hier nach (eine unbekannte Liste erscheint sonst
 *  gar nicht, s. `listenFuerJahr`). */
export const LISTEN_NAME: Record<string, string> = {
  verwaltung_1: "Änderungsliste der Verwaltung I",
  verwaltung_2: "Änderungsliste der Verwaltung II",
  verwaltung_3: "Änderungsliste der Verwaltung III",
  afb_beschlossen: "Beschlossene Änderungen (Finanzausschuss)",
};

/** Verw. I → II → III → Beschluss: die Reihenfolge des Verfahrens. */
const REIHENFOLGE = ["verwaltung_1", "verwaltung_2", "verwaltung_3", "afb_beschlossen"];

export type ListeImJahr = {
  key: string;
  name: string;
  /** Die Positionen des Haushaltsjahrgangs selbst. */
  zeilen: AenderungsZeile[];
  /** Was die Liste im Haushaltsjahrgang unterm Strich bewegt — die „eigene"
   *  Zeile der Zusammenstellung; bei den Beschluss-Dateien, die mehr
   *  einrechnen als sie ausweisen, Endsumme minus Entwurf. `null`, wenn
   *  beides fehlt (dann trägt die Karte keine Summenzeile statt einer
   *  gerechneten, die das Dokument nicht deckt). */
  balance: { revenues: number; expenses: number; balance: number } | null;
  /** Bis zu welchem Planjahr die Liste außerdem ändert — `null`, wenn sie
   *  nur den Jahrgang selbst betrifft. */
  bisPlanjahr: number | null;
  herkunft: Herkunft | null;
};

export function listenFuerJahr(
  daten: AenderungslistenDaten | null, year: number | null,
): ListeImJahr[] {
  if (!daten || year == null) return [];
  const aus: ListeImJahr[] = [];
  for (const key of REIHENFOLGE) {
    const zeilen = daten.zeilen.filter(
      (z) => z.budget_year === year && z.list_key === key);
    if (!zeilen.length) continue;
    const summen = daten.summen.filter(
      (s) => s.budget_year === year && s.list_key === key);
    const imJahr = summen.filter((s) => s.year === year);
    const eigene = imJahr.find((s) => s.own === 1);
    const entwurf = imJahr.find((s) => s.kind === "entwurf");
    const ende = imJahr.find((s) => s.kind === "endsumme");
    const balance = eigene
      ? { revenues: eigene.revenues, expenses: eigene.expenses, balance: eigene.balance }
      : entwurf && ende
        ? {
            revenues: ende.revenues - entwurf.revenues,
            expenses: ende.expenses - entwurf.expenses,
            balance: ende.balance - entwurf.balance,
          }
        : null;
    const bis = Math.max(...summen.map((s) => s.year));
    aus.push({
      key,
      name: LISTEN_NAME[key] ?? key,
      zeilen,
      balance,
      bisPlanjahr: bis > year ? bis : null,
      herkunft: herkunftVon(daten, zeilen[0].herkunft_id),
    });
  }
  return aus;
}

/** Die politischen Zeilen des Jahrgangs — Summen mit Urheber-Label statt
 *  „Änderungsliste …" davor. Es gibt sie nur in den Beschluss-Dateien, und
 *  sie sind der einzige digitale Beleg der Fraktionslisten (die selbst
 *  Tischvorlagen blieben). */
export function politikZeilen(
  daten: AenderungslistenDaten | null, year: number | null,
): AenderungsSumme[] {
  if (!daten || year == null) return [];
  return daten.summen.filter(
    (s) => s.budget_year === year && s.year === year && s.kind === "liste"
      && !s.label.includes("nderungsliste"));
}

/** Labels ohne Leerzeichen und Groß-/Kleinschreibung vergleichbar machen.
 *  Dasselbe Papier bricht denselben Urheber verschieden um: „SPD/ BÜNDNIS
 *  90/DIE GRÜNEN“ in der Zusammenstellung, „SPD/ BÜNDNIS 90/ DIE GRÜNEN“ in
 *  der Positionsspalte. Der Umbruch ist Satz, nicht Aussage. */
function labelKern(s: string): string {
  return s.replace(/\s+/g, "").toLocaleLowerCase("de-DE");
}

/** Die Positionen, die eine Zusammenstellungs-Zeile ausweist — sofern das
 *  Dokument sie je Position zuordnet.
 *
 *  Das tut genau eine Datei im Bestand: die Beschluss-Datei zum Haushalt
 *  2021 mit ihrer Spalte „Vorschlag von“. Für alle anderen Jahrgänge ist die
 *  Antwort leer, und die Seite sagt dann weiter, dass nur die Summe belegt
 *  ist. Die Zuordnung selbst hat der Ingest bewiesen (Probe
 *  `aenderungsliste_urheber`) — hier wird nur gefiltert. */
export function positionenVon(
  daten: AenderungslistenDaten | null, summe: AenderungsSumme,
): AenderungsZeile[] {
  if (!daten) return [];
  const kern = labelKern(summe.label);
  return daten.zeilen.filter(
    (z) => z.budget_year === summe.budget_year && z.year === summe.year
      && z.list_key === summe.list_key && z.author != null
      && kern.includes(labelKern(z.author)));
}

/** Was das Verfahren zwischen Entwurf und Beschluss bewegt hat — je Jahrgang.
 *
 *  Die Frage, die das Labor braucht, bevor jemand einen Regler anfasst: Wie
 *  viel Spielraum hat der Rat selbst genutzt? Die Zusammenstellung jedes
 *  Dokuments beantwortet sie, weil sie Entwurf und Endsumme nebeneinander
 *  ausweist — dazwischen liegt alles, was das Verfahren geändert hat.
 *
 *  WELCHES DOKUMENT GILT. Je Jahrgang liegen mehrere vor, und sie sind
 *  kumulativ: Die Liste der Verwaltung II führt Verw. I mit, die
 *  Beschluss-Datei des Finanzausschusses zusätzlich die politischen Listen.
 *  Genommen wird deshalb das VOLLSTÄNDIGSTE — die Beschluss-Datei, wo es sie
 *  gibt, sonst die höchste Verwaltungsliste. Gegenprobe an 2026: Verw. III
 *  endet bei −68.957.646, die Beschluss-Datei bei −68.739.348; die Differenz
 *  ist auf den Euro die politische Zeile (218.299).
 *
 *  `beschlossen` sagt, ob das gilt, was der Name verspricht. Ohne
 *  Beschluss-Datei endet der Weg beim letzten Stand der Verwaltung — das ist
 *  NICHT der beschlossene Haushalt, und die Karte muss es anders nennen. */
export type VerfahrensWeg = {
  budget_year: number;
  /** Saldo des Verwaltungsentwurfs — der Ausgangspunkt. */
  entwurf: number;
  /** Saldo am Ende des gelesenen Dokuments. */
  ende: number;
  /** `ende − entwurf`: was das Verfahren insgesamt bewegt hat. */
  bewegt: number;
  /** Anteil der Listen der VERWALTUNG daran. */
  verwaltung: number;
  /** Anteil der politischen Listen (Fraktionen) — 0, wo es keine gibt. */
  politik: number;
  /** Die politischen Zeilen einzeln, für die Urheber-Marken. */
  politikZeilen: AenderungsSumme[];
  /** Endet der Weg beim BESCHLOSSENEN Haushalt (Beschluss-Datei des
   *  Finanzausschusses) — oder nur beim letzten Stand der Verwaltung? */
  beschlossen: boolean;
  herkunft: Herkunft | null;
};

export function verfahrensWeg(
  daten: AenderungslistenDaten | null, budget_year: number | null,
): VerfahrensWeg | null {
  if (!daten || budget_year == null) return null;
  const imJahr = daten.summen.filter(
    (s) => s.budget_year === budget_year && s.year === budget_year);
  if (!imJahr.length) return null;

  // Das vollständigste Dokument: Beschluss zuerst, sonst die höchste
  // Verwaltungsliste (REIHENFOLGE ist die des Verfahrens).
  const kandidaten = [...REIHENFOLGE].reverse();
  const liste = kandidaten.find((k) => imJahr.some((s) => s.list_key === k));
  if (!liste) return null;
  const zeilen = imJahr.filter((s) => s.list_key === liste);

  const entwurf = zeilen.find((s) => s.kind === "entwurf");
  const ende = zeilen.find((s) => s.kind === "endsumme");
  if (!entwurf || !ende) return null;

  const listen = zeilen.filter((s) => s.kind === "liste");
  const politisch = listen.filter((s) => !s.label.includes("nderungsliste"));
  const summeSaldo = (xs: AenderungsSumme[]) => xs.reduce((a, s) => a + s.balance, 0);

  return {
    budget_year,
    entwurf: entwurf.balance,
    ende: ende.balance,
    bewegt: ende.balance - entwurf.balance,
    verwaltung: summeSaldo(listen.filter((s) => s.label.includes("nderungsliste"))),
    politik: summeSaldo(politisch),
    politikZeilen: politisch,
    beschlossen: liste === "afb_beschlossen",
    herkunft: herkunftVon(daten, entwurf.herkunft_id),
  };
}

/** Die Positionen des Finanzhaushalts eines Jahrgangs, nach Dokument geordnet.
 *
 *  Dieselbe Verfahrens-Reihenfolge wie beim Ergebnishaushalt (Verw. I → II →
 *  III → Beschluss). Positionen OHNE jeden Betrag bleiben draußen: Das sind
 *  reine Haushaltsvermerke — Text, den die Verwaltung in den Plan schreibt,
 *  ohne dass sich eine Zahl ändert. Sie in einer Liste „was am Bauen geändert
 *  wurde" zu zeigen, hieße eine Änderung zu behaupten, die es nicht gibt. */
export type FhhListeImJahr = {
  key: string;
  name: string;
  zeilen: FhhZeile[];
  /** Was die Liste im Jahrgang bewegt — die „eigene" Zeile der
   *  Zusammenstellung, sonst `null`. */
  balance: { inflows: number; outflows: number; balance: number } | null;
  herkunft: Herkunft | null;
};

export function fhhListenFuerJahr(
  daten: AenderungslistenDaten | null, year: number | null,
): FhhListeImJahr[] {
  if (!daten || year == null) return [];
  const aus: FhhListeImJahr[] = [];
  for (const key of REIHENFOLGE) {
    const zeilen = (daten.fhh_zeilen ?? []).filter(
      (z) => z.budget_year === year && z.list_key === key
        && (z.inflow != null || z.outflow != null));
    if (!zeilen.length) continue;
    const eigene = (daten.fhh_summen ?? []).find(
      (s) => s.budget_year === year && s.year === year && s.list_key === key
        && s.own === 1);
    aus.push({
      key,
      name: LISTEN_NAME[key] ?? key,
      zeilen,
      balance: eigene
        ? { inflows: eigene.inflows, outflows: eigene.outflows,
            balance: eigene.balance }
        : null,
      herkunft: herkunftVon(daten, zeilen[0].herkunft_id),
    });
  }
  return aus;
}

/** Vorzeichenfester Euro-Betrag fürs Listen-Raster: „+1,73 Mio. €“,
 *  „−218.299 €“, „—“ für „kein Betrag in dieser Spalte“. */
export function deltaBetrag(euro: number | null): string {
  if (euro == null) return "—";
  const abs = Math.abs(euro);
  const zahl = abs >= 1_000_000
    ? `${(abs / 1e6).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} Mio. €`
    : `${Math.round(abs).toLocaleString("de-DE")} €`;
  return `${euro < 0 ? "−" : "+"}${zahl}`;
}
