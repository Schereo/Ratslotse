// Datenschicht des Haushalts-Bereichs (Design-Serie „Haushalt" H-01…H-09).
// Quelle ist GET /api/council/haushalt: Ergebnishaushalt je Planjahr
// (Teilhaushalte + Summenzeile), dazu Ist-Steuereinnahmen und Steuerkraft —
// hier stehen nur Ableitungen, keine erfundenen Zahlen (Designprinzip:
// fehlende Daten heißen sichtbar „[folgt]", nie interpoliert).
//
// Bereichsnamen werden hier NICHT als Schlüssel benutzt — sie wechseln je
// Jahrgang. Das Wörterbuch dazu steht in `lib/haushalt-bereiche.ts`.

import {
  BEREICHE, bereichSchluessel, type BereichSchluessel,
} from "@/lib/haushalt-bereiche";

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

/** Die Zeilen der Finanzrechnung, auf die es ankommt. **An der Rolle hängen,
 *  nicht an der Nummer:** Die Tabelle hat 2017–2020 eine Zeile mehr als ab
 *  2021 (eine Einzahlungsart fiel weg), wodurch sich jede Nummer ab 08 um eins
 *  verschiebt — der Finanzmittelsaldo ist 2019 die Zeile 33 und 2024 die 32. */
export type FinanzRolle =
  | "summe_ein_verwaltung" | "summe_aus_verwaltung" | "saldo_verwaltung"
  | "summe_ein_investition" | "summe_aus_investition" | "saldo_investition"
  | "finanzmittel" | "saldo_finanzierung" | "finanzmittelveraenderung"
  | "saldo_haushaltsunwirksam" | "anfangsbestand" | "endbestand";

/** Eine Zeile der Finanzrechnung der Kernverwaltung (Abschnitt 4.1 desselben
 *  Jahresabschlusses): nicht was gebucht, sondern was **gezahlt** wurde.
 *
 *  `ermaechtigung` ist die Spalte „Ermächtigungen aus Haushaltsvorjahren" —
 *  Geld aus früheren Jahren, das in diesem Jahr noch ausgegeben werden durfte.
 *  Sie ist `null`, wo der Jahrgang die Spalte nicht führt.
 *
 *  Die Bestandszeilen (`anfangsbestand`, `endbestand`,
 *  `saldo_haushaltsunwirksam`) tragen **keinen** `plan`: Ein Kassenbestand
 *  wird nicht veranschlagt, und das Dokument lässt die Spalte dort leer. */
export type FinanzZeile = {
  jahr: number;
  /** Zeilennummer des Dokuments — nur für die Fundstelle, nie zum Suchen. */
  nr: number;
  rolle: FinanzRolle | null;
  bezeichnung: string;
  vorjahr: number | null; ansatz: number | null;
  plan: number | null; plan_art: PlanArt | null;
  ergebnis: number | null; abweichung: number | null;
  ermaechtigung: number | null;
  ist_summe: 0 | 1;
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
 *  kosten. `ergebnis` ist negativ = Zuschussbedarf.
 *
 *  Dazu der Steckbrief, den die Pläne zu jedem Produkt führen: was die Aufgabe
 *  umfasst, worauf sie beruht, wie viel Spielraum die Stadt bei ihr hat. Alle
 *  Steckbrief-Felder sind optional — nicht jedes Produkt trägt jedes Feld, und
 *  eine Lücke wird gezeigt, nicht gefüllt. */
export type Spielraum = "niedrig" | "mittel" | "hoch";

export type Produkt = {
  jahr: number; produkt_nr: string; produkt_name: string;
  thh_nr: number | null; thh_name: string | null; amt: string | null;
  ertraege: number | null; aufwendungen: number | null; ergebnis: number | null;
  kurzbeschreibung?: string | null;
  /** Die Rechtsgrundlagen, im Wortlaut des Plans. */
  auftragsgrundlage?: string | null;
  /** Normalisiert. Der Plan schreibt mal „niedrig", mal „gering". */
  beeinflussbarkeit?: Spielraum | null;
  /** Der Wortlaut des Plans — steht neben der normalisierten Stufe, damit
   *  Mischformen („niedrig/mittel bei Prävention") nicht verschwinden. */
  beeinflussbarkeit_roh?: string | null;
  wirkungskreis?: string | null;
  zielgruppe?: string | null;
  quelle_label: string | null; quelle_url: string | null;
  /** Jahrgänge, in denen dieses Produkt im Bestand steht — gegen
   *  `alle_jahre` gehalten wird daraus das Abdeckungs-Badge (H4-04). */
  jahre?: number[];
};

export type ProdukteAntwort = {
  jahr: number; produkte: Produkt[]; treffer?: number;
  abdeckung_prozent: number | null; plan_aufwendungen: number | null;
  /** Alle Jahrgänge mit Produktebene — die Bezugsreihe der `jahre` je
   *  Produkt. */
  alle_jahre?: number[];
  /** Filterwerte mit Anzahl + wie viele Produkte welches Feld tragen. */
  facetten?: {
    aemter: { amt: string; anzahl: number }[];
    spielraum: Partial<Record<Spielraum, number>>;
    mit_feld: Record<string, number>;
  };
  /** Das per `?nr=` angeforderte Produkt — auch wenn ein Filter es aus der
   *  Liste nähme. */
  produkt?: Produkt | null;
};

/** Wie die Stadt den Spielraum selbst benennt, in Alltagssprache übersetzt.
 *  „Grad der Beeinflussbarkeit: niedrig" heißt: Die Stadt kann hier kaum etwas
 *  ändern — nicht, dass die Aufgabe unwichtig wäre. */
export const SPIELRAUM_TEXT: Record<Spielraum, { kurz: string; lang: string }> = {
  niedrig: {
    kurz: "kaum Spielraum",
    lang: "Die Stadt sieht bei dieser Aufgabe kaum Spielraum: Was sie kostet, "
      + "bestimmen im Wesentlichen Gesetze und Fallzahlen, nicht der Rat.",
  },
  mittel: {
    kurz: "etwas Spielraum",
    lang: "Die Stadt sieht hier einen mittleren Spielraum — über das Wie lässt "
      + "sich entscheiden, über das Ob meist nicht.",
  },
  hoch: {
    kurz: "viel Spielraum",
    lang: "Die Stadt sieht hier viel Spielraum: Umfang und Zuschnitt dieser "
      + "Aufgabe kann der Rat weitgehend selbst bestimmen.",
  },
};

/** Ein Ausgleichsjahr aus Blatt „9a" der KFA-Tabellen des Landes.
 *
 *  Alle Beträge in **Tausend Euro**. Die Jahresangabe ist die des Landes
 *  (Ausgleichsjahr) — dieselbe, auf die `steuerkraft` seit der
 *  Jahres-Korrektur am Datensatz 1106 gerückt ist. */
export type FinanzausgleichJahr = {
  jahr: number;
  zuweisungen_gemeindeaufgaben?: number | null;
  zuweisungen_kreisaufgaben?: number | null;
  zuweisungen_uebertragener_wirkungskreis?: number | null;
  finanzausgleichsumlage?: number | null;
  nettobetrag?: number | null;
};

export type HaushaltDaten = {
  jahre: Record<string, HaushaltZeile[]>;
  steuern: { jahr: number; art: string; betrag: number | null }[];
  steuerkraft: {
    jahr: number; messzahl: number | null; messzahl_je_ew: number | null;
    zuweisungen: number | null; zuweisungen_je_ew: number | null;
  }[];
  /** Die drei Komponenten der Landeszuweisung je Ausgleichsjahr, in **Tausend
   *  Euro** (so führt das Landesamt sie) — Quelle: LSN, Blatt „9a".
   *
   *  Warum das neben `steuerkraft` steht und nicht darin: `steuerkraft.
   *  zuweisungen` kommt aus dem Open-Data-Datensatz 1106 der Stadt und
   *  enthält **nur zwei** der drei Komponenten (Gemeinde- plus Kreisaufgaben,
   *  auf den Euro nachgemessen). Die dritte gibt es nur beim Land. Zwei
   *  Quellen, zwei Felder — ein gemeinsames Feld verlöre die Auskunft, wer
   *  welche Zahl veröffentlicht. */
  finanzausgleich?: FinanzausgleichJahr[];
  /** Jüngste Einwohnerzahl — Bezugsgröße für Pro-Kopf-Einordnungen. */
  einwohner: { jahr: number; einwohner: number } | null;
  /** Ansatz, Plan und Ergebnis je Posten aus den Jahresabschlüssen. */
  ergebnisrechnung?: ErgebnisPosten[];
  /** Die Kassensicht aus denselben Jahresabschlüssen (Abschnitt 4.1). */
  finanzrechnung?: FinanzZeile[];
  /** Warum ein Posten vom Plan abwich (Abschnitt 6.3.1). */
  abweichungsgruende?: Abweichungsgrund[];
  /** Schlussberichte des Rechnungsprüfungsamts je Jahrgang. */
  pruefbericht_quellen?: Pruefbericht[];
  /** Jahre, für die die Produktebene vorliegt. */
  produkt_jahre?: number[];
  /** Jahre mit „geplant gegen tatsächlich" je Teilhaushalt. */
  plan_ist_jahre?: number[];
  /** Die lange Ausgabenreihe aus Datensatz 1102 — ein Betrag je Jahr seit 1972. */
  ausgabenreihe?: Ausgabenreihe;
  /** Nachbewilligungen nach § 117 NKomVG — was beschlossen wurde, nachdem der
   *  Haushalt beschlossen war. */
  nachbewilligungen?: Nachbewilligungen;
  /** Was die Stadt an Zuwendungen annimmt, aus den Ratsbeschlüssen. */
  spenden?: Spenden;
  /** Was je Steuerart geplant war und was daraus wurde (Jahrbuch 1103). */
  steuerplan?: Steuerplan;
  /** Die Realsteuer-Hebesätze je Änderungsjahr seit 1980 (Jahrbuch 1105). */
  hebesaetze?: Hebesaetze;
};

/** Welche Sorte Nachbewilligung eine Zeile ist.
 *
 *  `verpflichtungsermaechtigung` bindet künftige Jahre und fließt in diesem
 *  Jahr **nicht** — sie gehört in keine Jahressumme. `schwelle` sind die
 *  jährlichen Sammelberichte über die Fälle unter der Wertgrenze; ihr
 *  Titelbetrag (50.000 €) ist die Grenze, nicht die Summe, und sie tragen
 *  deshalb gar keinen Betrag. */
export type NachbewilligungsArt =
  | "bewilligung" | "verpflichtungsermaechtigung" | "schwelle";

/** Über- oder außerplanmäßig — und der Unterschied ist keine Wortklauberei:
 *  **überplanmäßig** heißt, der Posten stand im Haushalt und das Geld reichte
 *  nicht; **außerplanmäßig** heißt, den Posten gab es dort gar nicht.
 *
 *  Beides ist **gedeckt**. Jede dieser Vorlagen nennt in ihrem
 *  Beschlussvorschlag, woher das Geld kommt — „außerplanmäßig" ist eine
 *  Umwidmung, kein ungedeckter Griff in die Kasse. Wo die Seite das Wort
 *  benutzt, muss dieser Satz in Reichweite stehen. */
export type NachbewilligungsKategorie =
  | "ueberplanmaessig" | "ausserplanmaessig" | "beides";

/** Eine Nachbewilligung, wie das Ratsinformationssystem sie führt — je
 *  **Vorlage** eine, nicht je Beschlusszeile: Finanzausschuss und Rat
 *  entscheiden dieselbe Sache, 131 der 287 Zeilen sind Dubletten. */
export type Nachbewilligung = {
  vorlage_nr: string;
  /** Haushaltsjahr aus dem Jahrgang der Vorlagen-Nummer, nicht aus dem
   *  Sitzungsdatum — Januar-Vorlagen zählen zum Vorjahr. */
  jahr: number | null;
  titel: string;
  art: NachbewilligungsArt;
  kategorie: NachbewilligungsKategorie;
  /** In Euro. `null` bei `art === "schwelle"`. */
  betrag: number | null;
  /** Aus welcher Stufe der Betrag stammt: dem Titel oder dem
   *  Beschlussvorschlag der Vorlage. */
  betrag_quelle: "titel" | "beschlussvorschlag" | null;
  beschlossen: 0 | 1;
  /** Hat das **Plenum** selbst abgestimmt? Die wörtliche Auskunft — taugt als
   *  Zeilenhinweis („im Fachausschuss beschlossen"), aber **nie** als Basis
   *  eines Rats-Anteils. */
  im_rat: 0 | 1;
  /** Bucht der Rechenschaftsbericht das als „Beschluss des Rates"?
   *
   *  Das ist die Definition, die zählt: Der Bericht rechnet auch das dazu,
   *  was der Ausschuss für Finanzen und Beteiligungen **abschließend**
   *  entscheidet. 2024 sind das 8 von 21 Fällen — wer stattdessen `im_rat`
   *  summiert, zeigt 30,9 statt 43,1 Mio. € und damit 28 % zu wenig. */
  ratsentscheidung: 0 | 1;
  /** Ziel für den Link auf die vorhandene Beschluss-Seite. */
  beschluss_id: number | null;
  gremien: string[];
  volltextprobe: 0 | 1;
  herkunft_id: number | null;
};

/** Ein Entscheidungsweg aus Kapitel 3 des Rechenschaftsberichts. */
export type NachbewilligungsKanal = {
  jahr: number;
  kanal: string;
  /** Der Wortlaut der Stadt („Gemäß Haushaltsvermerk durch den Fachdienst
   *  200"), nicht unsere Umschreibung. */
  label: string;
  anzahl_konsumtiv: number;
  betrag_konsumtiv: number;
  anzahl_investiv: number;
  betrag_investiv: number;
  herkunft_id: number | null;
};

/** Ein Haushaltsjahr aus Kapitel 3 — die Gesamtsicht, die das RIS nicht hat. */
export type NachbewilligungsJahr = {
  jahr: number;
  summe_konsumtiv: number;
  summe_investiv: number;
  /** Was der Fließtext des Kapitels als Gesamtsumme nennt. Steht getrennt von
   *  der Summenzeile, **weil beide 2022 auseinanderfallen** (288.000 €). Wer
   *  nur eine der Zahlen behielte, hätte den Widerspruch weggeräumt. */
  text_gesamt: number | null;
  /** Verpflichtungsermächtigungen des Jahres — der Bericht zählt sie
   *  ausdrücklich getrennt, und wir addieren sie nirgends dazu. */
  verpflichtungen_betrag: number | null;
  probe_ok: 0 | 1;
  /** Im Klartext, was die Tabellenprobe gefunden hat. Steht auf der Seite,
   *  nicht nur im Log. */
  probe_text: string | null;
  herkunft_id: number | null;
  kanaele: NachbewilligungsKanal[];
};

export type Nachbewilligungen = {
  serie: Nachbewilligung[];
  jahre: NachbewilligungsJahr[];
  kanaele: Record<string, string>;
};

/** Zuwendungen an die Stadt (`council/spenden.py`).
 *
 *  Es gibt hier **kein** Feld für die Gebenden, und das ist Absicht: Die Namen
 *  stehen nur in der Anlage „Zuwendungsliste", die nicht im Bestand ist. Was
 *  der Typ nicht kennt, kann die Seite nicht versehentlich zeigen. */
export type Spenden = {
  jahre: SpendenJahr[];
  vorlagen: SpendenVorlage[];
  /** Beschlusszeilen ohne Zweitstelle — mit dem Satz, warum sie fehlen. */
  ohne_beleg: { vorlage_nr: string; sitzung?: string | null; grund: string }[];
  /** Wer über welche **einzelne** Zuwendung entscheidet. */
  schwellen: { gremium: string; ab: number | null; bis: number | null }[];
};

export type SpendenJahr = {
  jahr: number;
  betrag: number;
  vorlagen: number;
  rat: number;
  verwaltungsausschuss: number;
};

export type SpendenVorlage = {
  vorlage_nr: string;
  jahr: number;
  sitzung: string;
  betrag: number;
  gremium?: string | null;
  /** „identisch" oder „zerlegung" — wie die Zweitstelle den Betrag belegt. */
  zweitstelle: string;
  proben: string[];
  herkunft_id?: number | null;
};

/** Plan neben Ist je Steuerart — Tabelle 1103 des Statistischen Jahrbuchs.
 *
 *  `art` trägt **dieselbe** Schreibweise wie `HaushaltDaten.steuern[].art`;
 *  darüber findet ein Steckbrief seine Zeilen, und daran hängt die Prüfung der
 *  Jahresbeschriftung im Ingest. */
export type Steuerplan = {
  zeilen: SteuerplanZeile[];
  /** Was diese Zahlen umfassen — Angabe der Quelle, kein Frontend-Text. */
  abgrenzung: string;
};

export type SteuerplanZeile = {
  jahr: number;
  art: string;
  /** Ansatz der beschlossenen Haushaltssatzung, in Euro. */
  plan: number;
  /** Rechnungsergebnis desselben Jahres, in Euro. */
  ist: number;
  /** Die Quelle nennt dieses Ergebnis selbst „vorläufig" — es kann sich noch
   *  ändern, und das gehört an die Zahl. */
  vorlaeufig: 0 | 1;
};

/** Die Hebesatz-Treppe — Tabelle 1105.
 *
 *  **Nur Änderungsjahre.** Die Jahre dazwischen fehlen nicht, sie ändern
 *  nichts: Ein Hebesatz gilt, bis der Rat ihn ändert. Diese Reihe wird deshalb
 *  als `<Zeitreihe treppe>` gezeichnet und **nie** als gerade Linie zwischen
 *  zwei Stufen. */
export type Hebesaetze = {
  zeilen: HebesatzZeile[];
  abgrenzung: string;
  /** Jahre, in denen sich auch die **Bemessungsgrundlage** änderte, mit dem
   *  Grund. Ohne diese Angabe darf kein Sprung angezeigt werden: 2025 stieg
   *  der Grundsteuer-B-Satz um 21 %, während das Aufkommen um 4,6 % sank. */
  bemessung_neu: Record<string, string>;
};

export type HebesatzZeile = {
  jahr: number;
  /** „Grundsteuer A" · „Grundsteuer B" · „Gewerbesteuer". */
  art: string;
  /** Prozentpunkte. */
  hebesatz: number;
  /** Der Satz, der bis zu diesem Jahr galt — `null` in der ersten Zeile. */
  vorheriger: number | null;
};

/** Die beiden Rechnungswesen, unter denen die Stadt gezählt hat. Der Wechsel
 *  zum 1. Januar 2010 ist die Naht der langen Reihe. */
export type Regelwerk = "kameral" | "doppik";

/** Welche der beiden Veröffentlichungen den Betrag geliefert hat. Nur dort
 *  interessant, wo sie sich widersprechen — dann steht die unterlegene Zahl
 *  als `konflikt_betrag` daneben. */
export type Ausgabenquelle = "pdf" | "csv";

/** Wie eine Quelle auf der Seite heißt. „PDF" und „CSV" sind Dateiformate und
 *  keine Herausgeber; im Text steht, wer die Zahl veröffentlicht.
 *
 *  Mit Artikel und im Nominativ, weil beide Namen im selben Satz mitten drin
 *  stehen („… nennt das Statistische Jahrbuch X, der Open-Data-Datensatz Y").
 *  Ohne Artikel müsste der Satz ihn setzen — und „das Statistisches Jahrbuch"
 *  ist genau der Fehler, den eine Beschriftung aus einer Map gern produziert. */
export const AUSGABEN_QUELLE_LABEL: Record<Ausgabenquelle, string> = {
  pdf: "das Statistische Jahrbuch",
  csv: "der Open-Data-Datensatz",
};

/** Ein Jahrgang der langen Reihe. `betrag` in Euro.
 *
 *  `proben` sind die Rechenproben, die dieser Jahrgang bestanden hat — sie
 *  sind gestaffelt: Die dreißig ältesten Jahre hängen allein an der
 *  Pro-Kopf-Rechnung der Quelle, die jüngeren zusätzlich am Abgleich der
 *  beiden Veröffentlichungen und am Jahresabschluss. Die Erklärsätze dazu
 *  kommen über die `herkunft_id` mit (`lib/herkunft.ts`).
 *
 *  Eine Einwohnerzahl liefert dieser Datensatz bewusst nicht: Die Reihe darf
 *  nicht durch Einwohner geteilt werden, weil die Einwohnerreihe zwei
 *  Zensus-Brüche hat (2011 und 2022). Die Begründung steht an der Tabelle in
 *  `council/store.py`. */
export type AusgabenreiheJahr = {
  jahr: number;
  regelwerk: Regelwerk;
  betrag: number;
  quelle: Ausgabenquelle;
  proben: string[];
  /** Was die andere Veröffentlichung für dieses Jahr nennt — nur gefüllt, wo
   *  die beiden sich widersprechen. */
  konflikt_betrag: number | null;
  konflikt_quelle: Ausgabenquelle | null;
  revidiert: 0 | 1;
  herkunft_id: number | null;
};

export type Ausgabenreihe = {
  zeilen: AusgabenreiheJahr[];
  /** Das erste Jahr des neuen Rechnungswesens — die Naht liegt davor. */
  naht_ab: number;
  /** Je Regelwerk der Titel der Quelle und ihre Abgrenzung. Beide reisen mit
   *  den Daten, damit die Legende nicht in zwei Sprachen existiert. */
  regelwerke: Record<Regelwerk, { label: string; titel: string; abgrenzung: string }>;
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

/** Die Kassensicht eines Jahres, nach Rollen aufgeschlüsselt.
 *
 *  Gibt `null`, wenn der Jahrgang keine Finanzrechnung im Bestand hat — dann
 *  fehlt sie auf der Seite, statt aus den vorhandenen Zeilen zusammengerechnet
 *  zu werden. Fehlende Rollen bleiben `undefined`; die optionalen
 *  Bestandszeilen erlaubt das Dokument ausdrücklich wegzulassen. */
export function kassensicht(
  daten: HaushaltDaten, jahr: number,
): Partial<Record<FinanzRolle, FinanzZeile>> | null {
  const zeilen = (daten.finanzrechnung ?? []).filter((z) => z.jahr === jahr);
  if (!zeilen.length) return null;
  const aus: Partial<Record<FinanzRolle, FinanzZeile>> = {};
  for (const z of zeilen) if (z.rolle) aus[z.rolle] = z;
  // Ohne die drei Salden ist die Aussage nicht vollständig — dann lieber gar
  // keine Kassensicht als eine halbe (die Kaskade lässt das gar nicht zu,
  // aber der Lesepfad soll sich nicht darauf verlassen).
  return aus.saldo_verwaltung && aus.saldo_investition && aus.finanzmittel
    ? aus : null;
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

// --- Flussbild: Herkunft → ein Topf → Verwendung (Design H-18) -------------
//
// Kein klassisches Sankey. Ein durchgehendes Band von „Gewerbesteuer" nach
// „Soziales" behauptete eine Zweckbindung, die der kommunale Haushalt nicht
// kennt: Alle Einnahmen finanzieren gemeinsam alle Ausgaben. Deshalb laufen
// hier ALLE Bänder in EINEN Knoten und von dort neu heraus — dass alles durch
// einen Topf läuft, ist die Aussage des Bildes.

/** Kurznamen der Ertragsarten für die Grafik — redaktionell, nah am amtlichen
 *  Begriff und ohne Deutung. Die Langfassung steht in der Tabelle und im
 *  aria-Label; wo kein Kurzname gepflegt ist, gilt die Langfassung. */
export const ERTRAGSART_KURZ: Record<number, string> = {
  1: "Steuern",
  2: "Zuwendungen und Umlagen",
  3: "Auflösung von Sonderposten",
  4: "Transfererträge",
  5: "Gebühren und Beiträge",
  6: "privatrechtliche Entgelte",
  7: "Kostenerstattungen",
  8: "Zinsen",
  9: "Eigenleistungen",
  10: "Bestandsveränderungen",
  11: "sonstige Erträge",
};

export type FlussBand = {
  id: string;
  /** Kurzform für die Grafik. */
  label: string;
  /** Amtliche Bezeichnung — Tabelle, Titel, aria. */
  lang: string;
  /** Betrag in EURO (nicht Mio.): Sämtliche Summen und die Probe rechnen mit
   *  Rohwerten, sonst driftet der Vergleich um bis zu 0,1 je Posten. */
  wert: number;
  art: "posten" | "rest" | "ausgleich";
};

export type FlussSeite = {
  /** Absteigend nach Betrag; „rest" und „ausgleich" stehen immer hinten. */
  baender: FlussBand[];
  /** Die ausgewiesene Summenzeile (Posten 12 bzw. 20) in Euro. */
  gesamt: number;
  /** Summe der Einzelposten in Euro — ohne rest/ausgleich. */
  teile: number;
};

export type FlussDaten = {
  jahr: number;
  stand: "plan" | "ist";
  herkunft: FlussSeite;
  verwendung: FlussSeite;
  /** Gemeinsame Achse beider Seiten in Euro — die größere der beiden Summen. */
  skala: number;
  /** Erträge − Aufwendungen in Euro. */
  saldo: number;
  /** Summenprobe (Geometrie): Σ der gezeichneten Bänder je Seite. */
  summeLinks: number;
  summeRechts: number;
  /** Beide Seiten ergeben dieselbe Skala — die Bandbreiten sind vergleichbar. */
  stimmt: boolean;
  /** Beide Seiten sind bis auf ≤ 2 % durch Einzelposten gedeckt. Sonst wird
   *  das Bild NICHT gezeichnet: eine gestreckte Grafik wäre eine Behauptung. */
  aufgeschluesselt: boolean;
};

/** 0,05 Mio. € — feiner als die Anzeige (eine Nachkommastelle in Mio.). */
const FLUSS_TOLERANZ = 50_000;

/** Jahre, für die sich ein Flussbild bauen lässt: Der Jahresabschluss muss
 *  Ertragsarten UND Teilhaushalte hergeben. Ein Abschluss ohne
 *  Teilhaushalts-Ebene (2019) trägt nur die halbe Grafik — die zeigen wir
 *  nicht, sonst stünde rechts nichts neben einer vollen linken Seite. */
export function flussJahre(daten: HaushaltDaten): number[] {
  const posten = daten.ergebnisrechnung ?? [];
  return [...new Set(posten.map((p) => p.jahr))]
    .sort((a, b) => a - b)
    .filter((jahr) => {
      const gesamt = posten.filter((p) => p.jahr === jahr && p.thh_nr == null);
      return (
        gesamt.some((p) => p.nr >= 1 && p.nr <= 11) &&
        gesamt.some((p) => p.nr === 12) &&
        gesamt.some((p) => p.nr === 20) &&
        posten.some((p) => p.jahr === jahr && p.thh_nr != null && p.nr === 20)
      );
    });
}

/** Eine Seite bauen: Einzelposten, dann die beiden Ehrlichkeits-Bänder.
 *
 *  `rest` = was die Summenzeile mehr ausweist, als die Einzelposten hergeben
 *  (bei uns unlesbare Zeilen) — sichtbar als eigenes Band statt still verteilt.
 *  `ausgleich` = der Abstand zur gemeinsamen Skala, also genau der Saldo: Bei
 *  einem Minus steht links „aus dem Ersparten", bei einem Plus rechts
 *  „bleibt übrig". Erst dadurch sind beide Seiten wirklich gleich lang — und
 *  das Bild behauptet nicht, ein Defizit-Haushalt sei ausgeglichen. */
function flussSeite(
  teile: FlussBand[], gesamt: number, skala: number,
  restLabel: string, ausgleichLabel: string,
): FlussSeite {
  const summeTeile = teile.reduce((s, b) => s + b.wert, 0);
  const baender = [...teile].sort((a, b) => b.wert - a.wert);
  const rest = gesamt - summeTeile;
  if (rest > FLUSS_TOLERANZ) {
    baender.push({ id: "rest", label: restLabel, lang: restLabel, wert: rest, art: "rest" });
  }
  const gedeckt = summeTeile + Math.max(rest, 0);
  const ausgleich = skala - gedeckt;
  if (ausgleich > FLUSS_TOLERANZ) {
    baender.push({
      id: "ausgleich", label: ausgleichLabel, lang: ausgleichLabel,
      wert: ausgleich, art: "ausgleich",
    });
  }
  return { baender, gesamt, teile: summeTeile };
}

/** Das Flussbild eines Jahres in einem Stand (Plan oder Ist).
 *
 *  Links die Ertragsarten (Posten 01–11), rechts die Teilhaushalte (Posten 20
 *  je `thh_nr`) — beide aus derselben Tabelle desselben Jahres, damit nie zwei
 *  Stände nebeneinander stehen. `null`, wenn eine Seite fehlt. */
export function flussbild(
  daten: HaushaltDaten, jahr: number, stand: "plan" | "ist",
): FlussDaten | null {
  const zahl = (p: ErgebnisPosten | undefined) =>
    p ? (stand === "ist" ? p.ergebnis : p.ansatz) : null;
  const rows = (daten.ergebnisrechnung ?? []).filter((p) => p.jahr === jahr);
  const gesamt = rows.filter((p) => p.thh_nr == null);

  const ertraege = zahl(gesamt.find((p) => p.nr === 12));
  const aufwendungen = zahl(gesamt.find((p) => p.nr === 20));
  if (!ertraege || !aufwendungen || ertraege <= 0 || aufwendungen <= 0) return null;

  const arten: FlussBand[] = gesamt
    .filter((p) => p.nr >= 1 && p.nr <= 11 && (zahl(p) ?? 0) > 0)
    .map((p) => ({
      id: `art-${p.nr}`,
      label: ERTRAGSART_KURZ[p.nr] ?? p.bezeichnung,
      lang: p.bezeichnung,
      wert: zahl(p) as number,
      art: "posten" as const,
    }));
  const bereiche: FlussBand[] = rows
    .filter((p) => p.thh_nr != null && p.nr === 20 && (zahl(p) ?? 0) > 0)
    .map((p) => ({
      id: `thh-${p.thh_nr}`,
      label: p.thh_name ?? `Teilhaushalt ${p.thh_nr}`,
      lang: p.thh_name ?? `Teilhaushalt ${p.thh_nr}`,
      wert: zahl(p) as number,
      art: "posten" as const,
    }));
  if (!arten.length || !bereiche.length) return null;

  // Die Skala deckt auch den Fall ab, dass Einzelposten ihre eigene
  // Summenzeile übersteigen (fehlgelesene Zeile): Dann ragt nichts über den
  // Knoten hinaus, und `aufgeschluesselt` schaltet das Bild ohnehin ab.
  const skala = Math.max(
    ertraege, aufwendungen,
    arten.reduce((s, b) => s + b.wert, 0),
    bereiche.reduce((s, b) => s + b.wert, 0),
  );

  const herkunft = flussSeite(arten, ertraege, skala,
    "im Abschluss nicht aufgeschlüsselt", "aus dem Ersparten");
  const verwendung = flussSeite(bereiche, aufwendungen, skala,
    "im Abschluss nicht aufgeschlüsselt", "bleibt übrig");

  const summeLinks = herkunft.baender.reduce((s, b) => s + b.wert, 0);
  const summeRechts = verwendung.baender.reduce((s, b) => s + b.wert, 0);
  const luecke = (s: FlussSeite) => Math.abs(s.gesamt - s.teile);
  return {
    jahr, stand, herkunft, verwendung, skala,
    saldo: ertraege - aufwendungen,
    summeLinks, summeRechts,
    stimmt: Math.abs(summeLinks - summeRechts) <= FLUSS_TOLERANZ
      && Math.abs(summeLinks - skala) <= FLUSS_TOLERANZ,
    aufgeschluesselt: luecke(herkunft) <= 0.02 * herkunft.gesamt
      && luecke(verwendung) <= 0.02 * verwendung.gesamt,
  };
}

/** Kleine Posten bündeln, damit die Bänder beschriftbar bleiben: Wer unter
 *  `mindestAnteil` der Skala liegt, wandert in einen Sammelposten „weitere".
 *
 *  Die Schwelle ist eine Lesbarkeits-, keine Relevanzentscheidung — ein Band
 *  unter der Zeilenhöhe seiner eigenen Beschriftung ist nicht mehr zuzuordnen.
 *  Was im Sammelposten steckt, steht aufklappbar darunter und vollständig in
 *  der Tabelle. Die Ehrlichkeits-Bänder (rest/ausgleich) werden nie gebündelt:
 *  Genau sie erklären, warum das Bild aussieht, wie es aussieht. */
export function fasseKleineZusammen(
  baender: FlussBand[], skala: number, mindestAnteil: number,
): { gezeigt: FlussBand[]; gebuendelt: FlussBand[] } {
  const gross = baender.filter(
    (b) => b.art !== "posten" || b.wert >= mindestAnteil * skala);
  const gebuendelt = baender.filter(
    (b) => b.art === "posten" && b.wert < mindestAnteil * skala);
  if (gebuendelt.length < 2) return { gezeigt: baender, gebuendelt: [] };
  const sammel: FlussBand = {
    id: "weitere",
    label: `${gebuendelt.length} weitere`,
    lang: `${gebuendelt.length} weitere Posten`,
    wert: gebuendelt.reduce((s, b) => s + b.wert, 0),
    art: "posten",
  };
  // Sammelposten und Ehrlichkeits-Bänder ans Ende: Der Stapel liest sich von
  // oben nach unten „groß nach klein", die Sonderfälle stehen unten.
  const posten = gross.filter((b) => b.art === "posten");
  const sonder = gross.filter((b) => b.art !== "posten");
  return { gezeigt: [...posten, sammel, ...sonder], gebuendelt };
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

/** Betrag mit PASSENDER Einheit — Millionen nur, wo es welche sind.
 *
 *  Die Produktebene spannt vier Größenordnungen: 58,6 Mio. € für die
 *  Kindertagesbetreuung, 4.206 € Erträge beim Stadtarchiv. Alles starr in
 *  Mio. anzugeben macht aus dem halben Bestand „0,0 Mio. €" — eine Zahl, die
 *  nichts mehr sagt, obwohl wir sie genau kennen. Auf den Bereichs- und
 *  Übersichtsseiten bleibt `deMio` richtig: dort ist Mio. die Hausnummer. */
export function betrag(euro: number | null | undefined): { wert: string; einheit: string } {
  if (euro == null) return { wert: "—", einheit: "" };
  const abs = Math.abs(euro);
  if (abs >= 1_000_000) return { wert: deMio(euro / 1e6), einheit: "Mio. €" };
  if (abs >= 10_000) {
    return { wert: Math.round(euro / 1000).toLocaleString("de-DE"), einheit: "Tsd. €" };
  }
  return { wert: Math.round(euro).toLocaleString("de-DE"), einheit: "€" };
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

/** Die lange Ausgabenreihe, sortiert und nur mit den Jahren, die auch einen
 *  Betrag haben. Leer, solange die Tabelle leer ist — die Seite zeigt den
 *  Block dann gar nicht, statt eine Achse ohne Säulen zu zeichnen.
 *
 *  Die API liefert bereits sortiert; hier wird trotzdem sortiert, weil die
 *  Naht-Grafik eine aufsteigende Achse voraussetzt und ein Lesepfad, der sich
 *  auf die Reihenfolge einer fremden Antwort verlässt, still kippt. */
export function ausgabenreihe(daten: HaushaltDaten): AusgabenreiheJahr[] {
  const zeilen = daten.ausgabenreihe?.zeilen ?? [];
  return [...zeilen].sort((a, b) => a.jahr - b.jahr);
}

/** Die Jahrgänge, in denen sich die beiden Veröffentlichungen widersprechen.
 *
 *  Kein Nebenschauplatz, sondern Inhalt: Wo zwei amtliche Quellen für dasselbe
 *  Jahr zwei Beträge nennen, gehört das auf die Seite — mit beiden Zahlen. */
export function ausgabenKonflikte(daten: HaushaltDaten): AusgabenreiheJahr[] {
  return ausgabenreihe(daten).filter((z) => z.konflikt_betrag != null);
}

/** Ein Jahr der Rats-Serie: was der Rat nachbewilligt hat, und was daneben
 *  ausdrücklich **nicht** mitgezählt wurde.
 *
 *  `summe` enthält nur erteilte Bewilligungen mit Betrag. Draußen bleiben:
 *  Verpflichtungsermächtigungen (binden künftige Jahre), Sammelberichte
 *  (tragen eine Wertgrenze statt eines Betrags) und Vorlagen ohne Beschluss
 *  (beantragt ist nicht bewilligt). Alle drei stehen als eigene Felder
 *  daneben, damit die Seite sie benennen kann, statt sie zu verschweigen. */
export type NachbewilligungsSumme = {
  jahr: number;
  summe: number;
  faelle: number;
  verpflichtungen: number;
  verpflichtungenBetrag: number;
  sammelberichte: number;
};

export function nachbewilligungsJahre(
  daten: HaushaltDaten,
): NachbewilligungsSumme[] {
  const jahre = new Map<number, NachbewilligungsSumme>();
  const hol = (jahr: number) => {
    let e = jahre.get(jahr);
    if (!e) {
      e = { jahr, summe: 0, faelle: 0, verpflichtungen: 0,
            verpflichtungenBetrag: 0, sammelberichte: 0 };
      jahre.set(jahr, e);
    }
    return e;
  };
  for (const n of daten.nachbewilligungen?.serie ?? []) {
    if (n.jahr == null) continue;
    if (n.art === "schwelle") {
      hol(n.jahr).sammelberichte += 1;
    } else if (n.art === "verpflichtungsermaechtigung") {
      if (!n.beschlossen) continue;
      const e = hol(n.jahr);
      e.verpflichtungen += 1;
      e.verpflichtungenBetrag += n.betrag ?? 0;
    } else if (n.beschlossen && n.betrag != null) {
      const e = hol(n.jahr);
      e.summe += n.betrag;
      e.faelle += 1;
    }
  }
  return [...jahre.values()].sort((a, b) => a.jahr - b.jahr);
}

/** Die Bewilligungen eines Jahres, größte zuerst — die Liste, die auf ihre
 *  Beschluss-Seiten verlinkt. Ohne Sammelberichte und ohne
 *  Verpflichtungsermächtigungen: Die stehen auf der Seite getrennt. */
export function nachbewilligungenFuerJahr(
  daten: HaushaltDaten, jahr: number,
): Nachbewilligung[] {
  return (daten.nachbewilligungen?.serie ?? [])
    .filter((n) => n.jahr === jahr && n.art === "bewilligung"
      && n.beschlossen === 1 && n.betrag != null)
    .sort((a, b) => (b.betrag ?? 0) - (a.betrag ?? 0));
}

/** Wie viel Prozent der Nachbewilligungen eines Jahres der Rat selbst
 *  beschlossen hat — `null`, solange der Rechenschaftsbericht für das Jahr
 *  fehlt.
 *
 *  Gerechnet wird gegen die **Summenzeile** des Kapitels, nicht gegen die
 *  Gesamtzahl aus seinem Fließtext: Die Summenzeile ist die Zahl, für die das
 *  Dokument mit seiner eigenen Rechnung geradesteht. Wo beide auseinander-
 *  fallen (2022), sagt `probe_text` es an. */
export function ratsAnteil(j: NachbewilligungsJahr): number | null {
  const gesamt = j.summe_konsumtiv + j.summe_investiv;
  const rat = j.kanaele.find((k) => k.kanal === "rat");
  if (!gesamt || !rat) return null;
  return ((rat.betrag_konsumtiv + rat.betrag_investiv) / gesamt) * 100;
}

/** Gesamtsumme eines Kapitel-3-Jahrgangs (Summenzeile beider Spalten). */
export function nachbewilligungGesamt(j: NachbewilligungsJahr): number {
  return j.summe_konsumtiv + j.summe_investiv;
}

/** Ein Kanal quer über beide Spalten. */
export function kanalBetrag(k: NachbewilligungsKanal): number {
  return k.betrag_konsumtiv + k.betrag_investiv;
}

export function kanalAnzahl(k: NachbewilligungsKanal): number {
  return k.anzahl_konsumtiv + k.anzahl_investiv;
}

/** Die Spendenjahre, die **vollständig** sind — also alle bis auf das
 *  laufende.
 *
 *  Das laufende Jahr hat erst die Beschlüsse bis heute; es in eine Reihe zu
 *  zeichnen, hieße einen Rückgang zu zeigen, den es nicht gibt. Es steht
 *  deshalb daneben als Satz, nicht in der Kurve. */
export function spendenJahre(daten: HaushaltDaten): SpendenJahr[] {
  const jahre = daten.spenden?.jahre ?? [];
  const laufend = new Date().getFullYear();
  return jahre.filter((j) => j.jahr < laufend).sort((a, b) => a.jahr - b.jahr);
}

/** Das laufende Jahr, sofern es schon Beschlüsse trägt. */
export function spendenLaufend(daten: HaushaltDaten): SpendenJahr | null {
  const laufend = new Date().getFullYear();
  return (daten.spenden?.jahre ?? []).find((j) => j.jahr === laufend) ?? null;
}

/** Rat und Verwaltungsausschuss über alle belegten Vorlagen.
 *
 *  Die Aufteilung ist selbst die Auskunft: Beide Gremien behandeln ungefähr
 *  gleich viele Vorlagen, aber die Schwelle von 2.000 Euro sorgt dafür, dass
 *  fast das ganze Geld über den Rat läuft. */
export function spendenGremien(daten: HaushaltDaten) {
  const leer = { vorlagen: 0, betrag: 0 };
  const aus = { Rat: { ...leer }, Verwaltungsausschuss: { ...leer } };
  for (const v of daten.spenden?.vorlagen ?? []) {
    const k = v.gremium === "Rat" ? "Rat"
      : v.gremium === "Verwaltungsausschuss" ? "Verwaltungsausschuss" : null;
    if (!k) continue;
    aus[k].vorlagen += 1;
    aus[k].betrag += v.betrag;
  }
  return aus;
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

/** Kuratierte Langtexte der Teilhaushalte — redaktionell, nach dem Vorbericht
 *  des Haushaltsplans und den Produktzeilen des Bestands (Spiegel zu
 *  `council/haushalt.py`); bei neuen Jahrgängen prüfen.
 *
 *  Geschlüsselt auf den kanonischen Bereich, nicht auf den Namen: Sonst hätte
 *  der Text zu Teilhaushalt 9 nur in drei von sieben Jahrgängen gegriffen. */
const BEREICH_TEXTE: Record<BereichSchluessel, string> = {
  jugend:
    "Der größte Brocken sind die Kindertagesstätten — die Stadt betreibt eigene, " +
    "bezuschusst freie Träger und zahlt für Plätze in der Kindertagespflege. Dazu " +
    "kommt die Jugendhilfe: Hilfen zur Erziehung, Pflegefamilien, Heimunterbringung, " +
    "Jugendarbeit und der Allgemeine Soziale Dienst. Vieles davon ist gesetzliche " +
    "Pflicht — wie gut es ausgestattet ist, entscheidet der Rat.",
  // Reihenfolge nach den Produktzeilen 2023, nicht nach Gefühl: Die
  // Eingliederungshilfe ist über ihre drei Produkte zusammen der größte Block
  // des Teilhaushalts (rund 77 Mio. €), das größte Einzelprodukt ist die
  // Grundsicherung für Arbeitsuchende (54 Mio. €).
  soziales:
    "Fast alles davon sind gesetzliche Sozialleistungen: Grundsicherung, " +
    "Eingliederungshilfe für Menschen mit Behinderung, Hilfe zur Pflege, " +
    "Leistungen für Asylbewerber. Dazu kommt der öffentliche Gesundheitsdienst. " +
    "Ein großer Teil der Ausgaben wird durch Erstattungen von Bund und Land " +
    "gedeckt — deshalb ist der Bereich brutto der größte, unterm Strich aber " +
    "nicht der teuerste.",
  schule:
    "Schulgebäude, Ausstattung und Ganztagsangebote der Stadt als Schulträgerin — " +
    "die Lehrkräfte selbst bezahlt das Land.",
  // NICHT „alle Steuern und Zuweisungen": Die Steuern liegen zu 100 % hier
  // (2024: 377,9 Mio. €), die Zuwendungen nur zu rund zwei Dritteln
  // (115,4 von 179,1 Mio. €) — 46,4 Mio. buchen Soziales, 11,5 Mio. Jugend.
  // Quelle: council_ergebnisrechnung, Posten 1 und 2, Jahresabschluss 2024.
  finanzen:
    "Die zentrale Finanzwirtschaft: Hier werden alle Steuern und die allgemeinen " +
    "Zuweisungen des Landes für die ganze Stadt verbucht — zweckgebundene " +
    "Zuschüsse dagegen stehen bei den Fachbereichen, die sie erhalten. Die hohen " +
    "Einnahmen sind kein Gewinn der Kämmerei: Sie werden von hier auf alle " +
    "Aufgaben verteilt.",
  kultur:
    "Museen, Bibliotheken sowie Kultur- und Sportförderung — überwiegend " +
    "freiwillige Leistungen, über deren Umfang der Rat frei entscheidet.",
  verkehr: "Straßen, Radwege, Brücken und der Nahverkehr.",
  sicherheit:
    "Feuerwehr, Rettungsdienst und Ordnungsverwaltung — dazu die Bürgerdienste, " +
    "die man selbst am ehesten kennt: Einwohnermeldeamt, Standesamt, " +
    "Ausländerbehörde.",
  stadtplanung:
    "Bauleitplanung und Stadtentwicklung, Städtebau und Stadterneuerung, dazu " +
    "Vermessung und Geoinformation.",
  verwaltungsfuehrung:
    "Die Spitze des Hauses: Oberbürgermeister, Ratsbüro und die Stabsstellen — " +
    "dazu die örtliche Rechnungsprüfung, die die Verwaltung von innen " +
    "kontrolliert, und die Gleichstellungsstelle.",
  personal:
    "Personal, Organisation und IT der gesamten Verwaltung. Der Bereich hat kaum " +
    "eigene Einnahmen, aber hohe Aufwendungen für Menschen, die für die ganze " +
    "Stadt arbeiten — samt der Versorgung der Pensionärinnen und Pensionäre. Der " +
    "Zuschnitt heißt seit dem Haushalt 2026 „Personal/Organisation/" +
    "Digitalisierung/IT“; davor war es das „Personal- und Verwaltungsmanagement“.",
  wirtschaft:
    "Wirtschaftsförderung und Standortmarketing, dazu die Grundstücke und " +
    "Beteiligungen der Stadt — gemessen an den Aufwendungen einer der kleinsten " +
    "Teilhaushalte.",
  umwelt:
    "Grünflächen und Friedhöfe, Bauordnung, Natur- und Klimaschutz, zeitweise " +
    "auch die Verkehrsplanung. Kein anderer Teilhaushalt wurde seit 2020 so oft " +
    "neu zugeschnitten und umbenannt — Vergleiche über die Jahre sind hier mit " +
    "Vorsicht zu lesen.",
  stiftungen:
    "Treuhänderisch verwaltetes Stiftungsvermögen, das die Stadt für andere " +
    "führt. Zweckgebunden: Der Rat kann es nicht umwidmen, und es ist kein frei " +
    "verfügbares Geld der Stadt.",
};

/** Dieselben Texte unter jedem Namen, unter dem der Bereich in der Datenbank
 *  auftaucht. Bestehende Aufrufe (`BEREICH_INFO[zeile.bereich]`) bleiben damit
 *  gültig und treffen jetzt auch die Schreibweisen fremder Jahrgänge. */
export const BEREICH_INFO: Record<string, string> = Object.fromEntries(
  BEREICHE.flatMap((b) => b.aliase.map((a) => [a, BEREICH_TEXTE[b.schluessel]])),
);

/** Langtext zu einem Bereichsnamen — robuster als der Zugriff auf
 *  `BEREICH_INFO`, weil zusätzlich Schreibvarianten aufgelöst werden. */
export function bereichInfo(name: string): string | null {
  const k = bereichSchluessel(name);
  return k ? BEREICH_TEXTE[k] : null;
}
