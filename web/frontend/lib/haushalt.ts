// Datenschicht des Haushalts-Bereichs (Design-Serie „Haushalt" H-01…H-09).
// Quelle ist GET /api/council/haushalt: Ergebnishaushalt je Planjahr
// (Teilhaushalte + Summenzeile), dazu Ist-Steuereinnahmen und Steuerkraft —
// hier stehen nur Ableitungen, keine erfundenen Zahlen (Designprinzip:
// fehlende Daten heißen sichtbar „[folgt]", nie interpoliert).

export type HaushaltZeile = {
  bereich: string;
  ertraege: number | null;
  aufwendungen: number | null;
  ergebnis: number | null;
  is_summe: 0 | 1;
  source_url: string | null;
};

/** Bezugsgröße, gegen die der Jahresabschluss seine Abweichung rechnet.
 *  Sie wechselt über die Jahrgänge — deshalb steht sie an jeder Zeile. */
export type PlanArt = "ansatz" | "ansatz_nachtrag" | "gesamtermaechtigung";

/** Wie die Bezugsgröße auf der Seite genannt wird. Ohne diese Angabe wäre
 *  eine Mehrjahres-Kurve still falsch: 2018 vergleicht gegen die
 *  Gesamtermächtigung, 2020 gegen den Ansatz samt Nachtrag (27 Mio. €
 *  Unterschied), alle übrigen Jahrgänge gegen den nackten Ansatz. */
export const PLAN_ART_LABEL: Record<PlanArt, string> = {
  ansatz: "Haushaltsansatz",
  ansatz_nachtrag: "Ansatz einschließlich Nachtragshaushalt",
  gesamtermaechtigung: "Gesamtermächtigung (Ansatz, Nachtrag, Übertragungen)",
};

/** Ein Posten der Ergebnisrechnung aus dem Jahresabschluss (#500):
 *  `plan` = die Bezugsgröße der Abweichung, `ansatz` = der ursprüngliche
 *  Haushaltsansatz, `ergebnis` = was es tatsächlich wurde. In den meisten
 *  Jahrgängen sind `plan` und `ansatz` derselbe Wert. */
export type ErgebnisPosten = {
  jahr: number; nr: number; bezeichnung: string;
  /** null = Kernverwaltung gesamt, sonst der Teilhaushalt (1–13). */
  thh_nr: number | null; thh_name: string | null;
  vorjahr: number | null; ansatz: number | null;
  plan: number | null; plan_art: PlanArt | null;
  ergebnis: number | null; abweichung: number | null;
  ist_summe: 0 | 1;
  quelle_label: string | null; quelle_url: string | null;
};

/** Warum ein Posten vom Plan abwich — Abschnitt 6.3.1 des Jahresabschlusses,
 *  in den Worten der Verwaltung. Übernommen wird nur, was die Rechenprobe
 *  besteht: Betrag UND Prozentsatz der Überschrift müssen zur Tabellenzeile
 *  passen. */
export type Abweichungsgrund = {
  jahr: number; nr: number; bezeichnung: string;
  delta_mio: number | null; prozent: number | null;
  text: string;
  quelle_label: string | null; quelle_url: string | null;
};

/** Fundstelle des Schlussberichts des Rechnungsprüfungsamts. `lesbar === 0`
 *  heißt: Das PDF liegt vor, sein Textextrakt ist aber unbrauchbar (2024). */
export type Pruefbericht = {
  jahr: number; label: string | null; url: string | null;
  n_pages: number | null; lesbar: 0 | 1;
};

/** Produktebene aus den Teilhaushalts-Plänen (#500) — was einzelne Aufgaben
 *  kosten. `ergebnis` ist negativ = Zuschussbedarf. */
export type Produkt = {
  jahr: number; produkt_nr: string; produkt_name: string;
  thh_nr: number | null; thh_name: string | null; amt: string | null;
  ertraege: number | null; aufwendungen: number | null; ergebnis: number | null;
  quelle_label: string | null; quelle_url: string | null;
};

export type ProdukteAntwort = {
  jahr: number; produkte: Produkt[];
  abdeckung_prozent: number | null; plan_aufwendungen: number | null;
};

export type HaushaltDaten = {
  jahre: Record<string, HaushaltZeile[]>;
  steuern: { jahr: number; art: string; betrag: number | null }[];
  steuerkraft: {
    jahr: number; messzahl: number | null; messzahl_je_ew: number | null;
    zuweisungen: number | null; zuweisungen_je_ew: number | null;
  }[];
  /** Jüngste Einwohnerzahl — Bezugsgröße für Pro-Kopf-Einordnungen. */
  einwohner: { jahr: number; einwohner: number } | null;
  /** Ansatz, Plan und Ergebnis je Posten aus den Jahresabschlüssen. */
  ergebnisrechnung?: ErgebnisPosten[];
  /** Warum ein Posten vom Plan abwich (Abschnitt 6.3.1). */
  abweichungsgruende?: Abweichungsgrund[];
  /** Schlussberichte des Rechnungsprüfungsamts je Jahrgang. */
  pruefbericht_quellen?: Pruefbericht[];
  /** Jahre, für die die Produktebene vorliegt. */
  produkt_jahre?: number[];
  /** Jahre mit „geplant gegen tatsächlich" je Teilhaushalt. */
  plan_ist_jahre?: number[];
};

/** „Geplant gegen tatsächlich" je abgeschlossenem Jahr, in Mio.
 *
 *  Verglichen wird das **Jahresergebnis**: ordentliches (Posten 21) plus
 *  außerordentliches Ergebnis (24). Nur das ordentliche zu nehmen schmeichelte
 *  der Stadt — die außerordentlichen Posten waren zuletzt durchweg negativ.
 *  Jahre, in denen ein Posten fehlt, fallen raus statt halb gerechnet zu
 *  werden.
 *
 *  Als Plan gilt `plan`, also die Bezugsgröße, gegen die der Jahresabschluss
 *  selbst rechnet — nicht durchweg der nackte Ansatz. `planArt` gibt sie je
 *  Jahr mit heraus, damit die Kurve sie anschreiben kann: 2018 ist es die
 *  Gesamtermächtigung, 2020 der Ansatz samt Nachtrag. Eine Reihe, die das
 *  vermischt, ohne es zu sagen, wäre still falsch. */
export function planGegenIst(
  daten: HaushaltDaten,
): { jahr: number; plan: number; ist: number; delta: number; planArt: PlanArt }[] {
  const posten = daten.ergebnisrechnung ?? [];
  const jahre = [...new Set(posten.map((p) => p.jahr))].sort((a, b) => a - b);
  return jahre
    .map((jahr) => {
      const teile = [21, 24].map((nr) =>
        posten.find((p) => p.jahr === jahr && p.nr === nr && p.thh_nr == null));
      if (teile.some((t) => !t || t.plan == null || t.ergebnis == null)) return null;
      const plan = teile.reduce((s, t) => s + (t!.plan as number), 0) / 1e6;
      const ist = teile.reduce((s, t) => s + (t!.ergebnis as number), 0) / 1e6;
      return {
        jahr,
        plan: Math.round(plan * 10) / 10,
        ist: Math.round(ist * 10) / 10,
        delta: Math.round((ist - plan) * 10) / 10,
        planArt: (teile[0]!.plan_art ?? "ansatz") as PlanArt,
      };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null);
}

/** Die Erläuterung zu einem Posten eines Jahres — oder nichts. */
export function grundZuPosten(
  daten: HaushaltDaten, jahr: number, nr: number,
): Abweichungsgrund | null {
  return (daten.abweichungsgruende ?? []).find((g) => g.jahr === jahr && g.nr === nr) ?? null;
}

/** Der Schlussbericht des Rechnungsprüfungsamts zu einem Jahrgang. */
export function pruefberichtZuJahr(
  daten: HaushaltDaten, jahr: number,
): Pruefbericht | null {
  return (daten.pruefbericht_quellen ?? []).find((p) => p.jahr === jahr) ?? null;
}

/** Erläuterungen, die einen bestimmten Teilhaushalt ausdrücklich nennen.
 *
 *  Abschnitt 6.3.1 erläutert die Posten der **Gesamtrechnung**, nicht die
 *  Bereiche — eine Zuordnung je Teilhaushalt gibt es dort nicht. Die Texte
 *  benennen den Bereich aber regelmäßig selbst („Im Teilhaushalt 10 sind
 *  Mehrerträge …"). Genau darauf, und nur darauf, stützt sich diese Auswahl;
 *  sie wird auf der Seite auch so angeschrieben statt als Aufteilung
 *  ausgegeben, die das Dokument nicht hergibt. */
export function gruendeFuerBereich(
  daten: HaushaltDaten, jahr: number, thhNr: number,
): Abweichungsgrund[] {
  // „Teilhaushalt 10", „THH 10", „THH10" — mit und ohne führende Null.
  const n = String(thhNr);
  const muster = new RegExp(
    `(?:Teilhaushalt|THH)\\s?0?${n}(?!\\d)`, "i");
  return (daten.abweichungsgruende ?? [])
    .filter((g) => g.jahr === jahr && muster.test(g.text))
    .sort((a, b) => Math.abs(b.delta_mio ?? 0) - Math.abs(a.delta_mio ?? 0));
}

/** Das Produkt, dessen Zuschussbedarf einem Betrag am nächsten kommt — die
 *  Übersetzung von „4,0 Mio." in etwas, das man kennt.
 *
 *  `thhName` grenzt bewusst auf denselben Teilhaushalt ein: Eine Kürzung bei
 *  Kultur mit einer Sozialleistung zu vergleichen legt nahe, man könne die
 *  stattdessen streichen. Wo für den Bereich keine Produkte vorliegen, gibt es
 *  lieber keinen Vergleich als einen schiefen. */
export function naechstesProdukt(
  produkte: Produkt[], mioBetrag: number, thhName?: string,
): Produkt | null {
  if (mioBetrag < 0.2) return null;
  const passend = produkte.filter((p) =>
    p.ergebnis != null && p.ergebnis < 0 && (!thhName || p.thh_name === thhName));
  if (!passend.length) return null;
  return passend.reduce((best, p) =>
    Math.abs(-(p.ergebnis as number) / 1e6 - mioBetrag)
      < Math.abs(-(best.ergebnis as number) / 1e6 - mioBetrag) ? p : best);
}

/** Redaktionell gepflegte Konstanten — NICHT aus der DB. Quelle: Genehmigung
 *  des Haushalts 2026 durch das Nds. Innenministerium (04/2026), oldenburg.de.
 *  Beim nächsten Haushaltsjahr prüfen und nachziehen. */
export const RUECKLAGE_MIO = 195;
export const RUECKLAGE_STAND = "Stand: Genehmigung Haushalt 2026 (04/2026)";

export function mio(euro: number | null | undefined): number | null {
  if (euro == null) return null;
  return Math.round(euro / 100_000) / 10; // eine Nachkommastelle, in Mio.
}

/** Deutsche Anzeige „283,1" — Zahlen kommen bereits als Mio.-Wert. */
export function deMio(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export function jahreSortiert(daten: HaushaltDaten): number[] {
  return Object.keys(daten.jahre).map(Number).sort((a, b) => a - b);
}

/** Lücken zwischen erstem und letztem vorhandenen Jahr — die Zeitreihe zeigt
 *  sie als schraffierte Kästen (Lücken-Konvention H-07), nie interpoliert. */
export function fehlendeJahre(vorhanden: number[]): number[] {
  if (vorhanden.length < 2) return [];
  const out: number[] = [];
  for (let y = vorhanden[0]; y <= vorhanden[vorhanden.length - 1]; y++) {
    if (!vorhanden.includes(y)) out.push(y);
  }
  return out;
}

export function summe(zeilen: HaushaltZeile[]): HaushaltZeile | undefined {
  return zeilen.find((z) => z.is_summe === 1);
}

export function bereiche(zeilen: HaushaltZeile[]): HaushaltZeile[] {
  return zeilen.filter((z) => z.is_summe !== 1);
}

/** Kostendeckungsgrad in Prozent (eigene Erträge / Aufwendungen), 0–100. */
export function deckung(z: HaushaltZeile): number | null {
  if (!z.aufwendungen || z.aufwendungen <= 0 || z.ertraege == null) return null;
  return Math.round((z.ertraege / z.aufwendungen) * 100);
}

/** URL-Slug eines Bereichsnamens („Jugend und Familie" → jugend-und-familie). */
export function bereichSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Zeitreihe eines Bereichs über alle Jahre — nur exakt namensgleiche Zeilen.
 *  Die Teilhaushalts-Zuschnitte ändern sich über die Jahre; eine kurze Reihe
 *  ist dann die ehrliche Antwort, keine fehlende. */
export function bereichsReihe(
  daten: HaushaltDaten, name: string,
): { jahr: number; zeile: HaushaltZeile }[] {
  return jahreSortiert(daten)
    .map((jahr) => {
      const z = daten.jahre[String(jahr)]?.find((r) => r.bereich === name);
      return z ? { jahr, zeile: z } : null;
    })
    .filter((x): x is { jahr: number; zeile: HaushaltZeile } => x !== null);
}

/** Quelle einer Jahres-Scheibe menschenlesbar (PDF vs. Open-Data-CSV). */
export function quellenLabel(zeilen: HaushaltZeile[], jahr: number): { text: string; url: string | null } {
  const url = zeilen[0]?.source_url ?? null;
  const csv = url?.includes("opendata.oldenburg.de");
  return {
    text: csv
      ? `Haushaltsplan ${jahr}, Stadt Oldenburg — Open-Data-Portal (CSV, Lizenz dl-de/by-2.0)`
      : `Beschlossener Haushaltsplan ${jahr}, Stadt Oldenburg (PDF)`,
    url,
  };
}

/** Kuratierte Kurzbeschreibungen der Teilhaushalte — redaktionell, nach dem
 *  Vorbericht des Haushaltsplans (Spiegel zu council/haushalt.py); bei neuen
 *  Jahrgängen prüfen. Bereiche ohne Eintrag zeigen den Block nicht. */
export const BEREICH_INFO: Record<string, string> = {
  "Jugend und Familie":
    "Der größte Brocken sind die Kindertagesstätten — die Stadt betreibt eigene, " +
    "bezuschusst freie Träger und zahlt für Plätze in der Kindertagespflege. Dazu " +
    "kommt die Jugendhilfe: Hilfen zur Erziehung, Pflegefamilien, Heimunterbringung, " +
    "Jugendarbeit und der Allgemeine Soziale Dienst. Vieles davon ist gesetzliche " +
    "Pflicht — wie gut es ausgestattet ist, entscheidet der Rat.",
  "Soziales und Gesundheit":
    "Vor allem gesetzliche Sozialleistungen, Hilfen zur Pflege und der öffentliche " +
    "Gesundheitsdienst. Ein großer Teil der Ausgaben wird durch Erstattungen von " +
    "Bund und Land gedeckt — deshalb ist der Bereich brutto der größte, unterm " +
    "Strich aber nicht der teuerste.",
  "Schule und Bildung":
    "Schulgebäude, Ausstattung und Ganztagsangebote der Stadt als Schulträgerin — " +
    "die Lehrkräfte selbst bezahlt das Land.",
  "Finanzmanagement und Recht":
    "Die zentrale Finanzwirtschaft: Hier werden Steuern und Zuweisungen für die " +
    "ganze Stadt verbucht. Die hohen Einnahmen sind kein Gewinn der Kämmerei — " +
    "sie werden von hier auf alle Aufgaben verteilt.",
  "Kultur, Museen, Sport":
    "Museen, Bibliotheken sowie Kultur- und Sportförderung — überwiegend " +
    "freiwillige Leistungen, über deren Umfang der Rat frei entscheidet.",
  "Verkehr und Straßenbau": "Straßen, Radwege, Brücken und der Nahverkehr.",
  "Sicherheit und Ordnung": "Feuerwehr, Rettungsdienst und Ordnungsverwaltung.",
  Stadtplanung: "Bauleitplanung und Stadtentwicklung.",
};
