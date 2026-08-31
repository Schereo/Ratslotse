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
import type { Herkunft } from "@/lib/herkunft";

export type HaushaltZeile = {
  area: string;
  revenues: number | null;
  expenses: number | null;
  result: number | null;
  is_total: 0 | 1;
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
 *  Haushaltsansatz, `result` = was es tatsächlich wurde. In den meisten
 *  Jahrgängen sind `plan` und `ansatz` derselbe Wert. */
export type ErgebnisPosten = {
  year: number; nr: number; label: string;
  /** null = Kernverwaltung gesamt, sonst der Teilhaushalt (1–13). */
  sub_budget_no: number | null; sub_budget_name: string | null;
  prior_year: number | null; ansatz: number | null;
  plan: number | null; plan_art: PlanArt | null;
  result: number | null; deviation: number | null;
  is_total: 0 | 1;
  source_label: string | null; source_url: string | null;
};

/** Eine Zeile des **Gesamtergebnishaushalts** — dieselbe Postengliederung wie
 *  die Ergebnisrechnung, aber für Jahre, die noch keinen Abschluss haben.
 *
 *  Zwei Felder tragen die ganze Vorsicht dieser Tabelle:
 *
 *  * `art` trennt den **Haushaltsansatz** von der mittelfristigen
 *    Finanzplanung nach § 8 NKomVG. Das Dokument schreibt über fünf Spalten
 *    „Ansatz"; aufgestellt ist nur eines der Jahre, die übrigen sind eine
 *    Vorausschau, die jeder neue Haushalt neu schreibt (von 23 Posten bleiben
 *    zwischen zwei Plänen 0 bis 2 gleich). **Ohne diese Angabe darf keine Zahl
 *    aus dieser Liste angezeigt werden.**
 *  * `plan_budget_year` sagt, aus welchem Haushalt die Zeile stammt — dasselbe
 *    Jahr kommt in mehreren Plänen vor. */
export type ErgebnishaushaltZeile = {
  /** Der Haushalt, aus dem die Zahl stammt. */
  plan_budget_year: number;
  /** Das Jahr, für das sie gilt. */
  year: number;
  art: "ansatz" | "finanzplanung";
  nr: number;
  label: string;
  amount: number;
  is_total: 0 | 1;
  herkunft_id: number | null;
};

/** Überschussrücklage nach einem abgeschlossenen Jahr. Die Bilanz weist den
 * schon umgebuchten Bestand und das jüngste Jahresergebnis getrennt aus;
 * `state_after_result` ist deren Addition und entspricht der Formulierung
 * des Vorberichts „unter Berücksichtigung des Ergebnisses“. */
export type RuecklageJahr = {
  year: number;
  ruecklage: number;
  jahresergebnis: number;
  state_after_result: number;
  herkunft_id: number | null;
};

/** Die Zeilen der Finanzrechnung, auf die es ankommt. **An der Rolle hängen,
 *  nicht an der Nummer:** Die Tabelle hat 2017–2020 eine Zeile mehr als ab
 *  2021 (eine Einzahlungsart fiel weg), wodurch sich jede Nummer ab 08 um eins
 *  verschiebt — der Finanzmittelsaldo ist 2019 die Zeile 33 und 2024 die 32. */
export type FinanzRolle =
  | "total_in_operating" | "total_out_operating" | "balance_operating"
  | "total_in_capital" | "total_out_capital" | "balance_capital"
  | "finanzmittel" | "balance_financing" | "finanzmittelveraenderung"
  | "balance_non_budgetary" | "anfangsbestand" | "endbestand";

/** Eine Zeile der Finanzrechnung der Kernverwaltung (Abschnitt 4.1 desselben
 *  Jahresabschlusses): nicht was gebucht, sondern was **gezahlt** wurde.
 *
 *  `authorization` ist die Spalte „Ermächtigungen aus Haushaltsvorjahren" —
 *  Geld aus früheren Jahren, das in diesem Jahr noch ausgegeben werden durfte.
 *  Sie ist `null`, wo der Jahrgang die Spalte nicht führt.
 *
 *  Die Bestandszeilen (`anfangsbestand`, `endbestand`,
 *  `balance_non_budgetary`) tragen **keinen** `plan`: Ein Kassenbestand
 *  wird nicht veranschlagt, und das Dokument lässt die Spalte dort leer. */
export type FinanzZeile = {
  year: number;
  /** Zeilennummer des Dokuments — nur für die Fundstelle, nie zum Suchen. */
  nr: number;
  rolle: FinanzRolle | null;
  label: string;
  prior_year: number | null; ansatz: number | null;
  plan: number | null; plan_art: PlanArt | null;
  result: number | null; deviation: number | null;
  authorization: number | null;
  is_total: 0 | 1;
};

/** Warum ein Posten vom Plan abwich — Abschnitt 6.3.1 des Jahresabschlusses,
 *  in den Worten der Verwaltung. Übernommen wird nur, was die Rechenprobe
 *  besteht: Betrag UND Prozentsatz der Überschrift müssen zur Tabellenzeile
 *  passen. */
export type Abweichungsgrund = {
  year: number; nr: number; label: string;
  delta_meur: number | null; prozent: number | null;
  text: string;
  source_label: string | null; source_url: string | null;
};

/** Fundstelle des Schlussberichts des Rechnungsprüfungsamts. `readable === 0`
 *  heißt: Das PDF liegt vor, sein Textextrakt ist aber unbrauchbar (2024). */
export type Pruefbericht = {
  year: number; label: string | null; url: string | null;
  n_pages: number | null; readable: 0 | 1;
};

/** Produktebene aus den Teilhaushalts-Plänen (#500) — was einzelne Aufgaben
 *  kosten. `result` ist negativ = Zuschussbedarf.
 *
 *  Dazu der Steckbrief, den die Pläne zu jedem Produkt führen: was die Aufgabe
 *  umfasst, worauf sie beruht, wie viel Spielraum die Stadt bei ihr hat. Alle
 *  Steckbrief-Felder sind optional — nicht jedes Produkt trägt jedes Feld, und
 *  eine Lücke wird gezeigt, nicht gefüllt. */
export type Spielraum = "niedrig" | "mittel" | "hoch";

export type Produkt = {
  year: number; product_no: string; product_name: string;
  sub_budget_no: number | null; sub_budget_name: string | null; office: string | null;
  revenues: number | null; expenses: number | null; result: number | null;
  short_description?: string | null;
  /** Die Rechtsgrundlagen, im Wortlaut des Plans. */
  legal_basis?: string | null;
  /** Normalisiert. Der Plan schreibt mal „niedrig", mal „gering". */
  controllability?: Spielraum | null;
  /** Der Wortlaut des Plans — steht neben der normalisierten Stufe, damit
   *  Mischformen („niedrig/mittel bei Prävention") nicht verschwinden. */
  controllability_raw?: string | null;
  scope?: string | null;
  target_group?: string | null;
  source_label: string | null; source_url: string | null;
  /** Jahrgänge, in denen dieses Produkt im Bestand steht — gegen
   *  `alle_jahre` gehalten wird daraus das Abdeckungs-Badge (H4-04). */
  jahre?: number[];
};

export type ProdukteAntwort = {
  year: number; produkte: Produkt[]; treffer?: number;
  abdeckung_prozent: number | null; plan_expenses: number | null;
  /** Alle Jahrgänge mit Produktebene — die Bezugsreihe der `jahre` je
   *  Produkt. */
  alle_jahre?: number[];
  /** Filterwerte mit Anzahl + wie viele Produkte welches Feld tragen. */
  facetten?: {
    aemter: { office: string; count: number }[];
    spielraum: Partial<Record<Spielraum, number>>;
    mit_feld: Record<string, number>;
  };
  /** Das per `?nr=` angeforderte Produkt — auch wenn ein Filter es aus der
   *  Liste nähme. */
  product?: Produkt | null;
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
  year: number;
  zuweisungen_gemeindeaufgaben?: number | null;
  zuweisungen_kreisaufgaben?: number | null;
  zuweisungen_uebertragener_wirkungskreis?: number | null;
  finanzausgleichsumlage?: number | null;
  nettobetrag?: number | null;
};

/** Ein Punkt einer Kennzahl-Reihe: der Wert aus dem jüngsten Bericht, der
 *  dieses Jahr druckt.
 *
 *  `stellen` sind die **gedruckten** Nachkommastellen — 2019 stand „48%", ab
 *  2021 „53,15%". Wer eine Reihe über diesen Wechsel zeichnet, muss ihn
 *  anschreiben können, statt aus der glatteren Zahl eine genauere zu machen.
 *
 *  `fassung` nummeriert den gedruckten Rechenweg. Wechselt sie zwischen zwei
 *  Jahren, darf über die Stelle **keine Linie laufen**: Die Stadt hat dann
 *  etwas anderes gemessen, nicht etwas anderes herausbekommen. */
export type KennzahlPunkt = {
  indicator: string;
  year: number;
  wert: number;
  stellen: number;
  fassung: number | null;
  /** Aus welchem Rechenschaftsbericht dieser Stand stammt. */
  report_year: number;
  herkunft_id?: number | null;
};

/** Ein gedruckter Rechenweg, im Wortlaut, mit der Spanne der Berichte, in
 *  denen er so stand. */
export type KennzahlFormel = {
  indicator: string;
  fassung: number;
  /** Wie die Überschrift im Bericht lautet — nicht unser Label. */
  heading: string;
  formel: string;
  von_bericht: number;
  bis_bericht: number;
  herkunft_id?: number | null;
};

/** Ein Unterschied zwischen zwei Berichten an derselben Stelle.
 *
 *  `art` ist gemessen, nicht angenommen:
 *  - `revision` — gleicher Rechenweg, anderer Wert: die Stadt hat korrigiert.
 *  - `definition` — anderer Rechenweg, anderer Wert: nicht dasselbe gemessen.
 *  - `umbenennung` — anderer Rechenweg, **gleicher** Wert: nur umformuliert. */
export type KennzahlFund = {
  art: "revision" | "definition" | "umbenennung";
  indicator: string;
  year: number;
  alt: number;
  alt_bericht: number;
  neu: number;
  neu_bericht: number;
  difference: number;
};

export type Kennzahlen = {
  /** Schlüssel → Klartext. Steht einmal statt an jeder der 365 Zeilen. */
  label: Record<string, string>;
  /** Schlüssel → „prozent" | „eur" | „anzahl". */
  einheit: Record<string, string>;
  reihe: KennzahlPunkt[];
  formeln: KennzahlFormel[];
  funde: KennzahlFund[];
};

export type HaushaltDaten = {
  jahre: Record<string, HaushaltZeile[]>;
  steuern: { year: number; art: string; amount: number | null }[];
  steuerkraft: {
    year: number; messzahl: number | null; tax_capacity_per_capita: number | null;
    allocations: number | null; allocations_per_capita: number | null;
  }[];
  /** Die drei Komponenten der Landeszuweisung je Ausgleichsjahr, in **Tausend
   *  Euro** (so führt das Landesamt sie) — Quelle: LSN, Blatt „9a".
   *
   *  Warum das neben `steuerkraft` steht und nicht darin: `steuerkraft.
   *  allocations` kommt aus dem Open-Data-Datensatz 1106 der Stadt und
   *  enthält **nur zwei** der drei Komponenten (Gemeinde- plus Kreisaufgaben,
   *  auf den Euro nachgemessen). Die dritte gibt es nur beim Land. Zwei
   *  Quellen, zwei Felder — ein gemeinsames Feld verlöre die Auskunft, wer
   *  welche Zahl veröffentlicht. */
  finanzausgleich?: FinanzausgleichJahr[];
  /** Jüngste Einwohnerzahl — Bezugsgröße für Pro-Kopf-Einordnungen. */
  einwohner: { year: number; einwohner: number } | null;
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
  /** Die Postengliederung für Jahre **ohne** Jahresabschluss, aus dem
   *  Gesamtergebnishaushalt der Haushaltspläne (Anlage 005). */
  ergebnishaushalt?: ErgebnishaushaltZeile[];
  /** Verfügbare Überschussrücklage aus den Jahresabschlüssen. */
  ruecklage?: RuecklageJahr[];
  /** Die Wirtschaftspläne der Eigenbetriebe — der Haushalt neben dem Haushalt. */
  wirtschaftsplaene?: WirtschaftsplanZeile[];
  /** Die Herkunft je `herkunft_id` — nur die Einträge, auf die eine gelieferte
   *  Zeile zeigt.
   *
   *  ANFORDERN MUSS MAN SIE (`FELDER` um `"herkunft"` ergänzen). Die meisten
   *  Seiten dieses Bereichs brauchen sie nicht: Ihr Beleg hängt am
   *  Quellen-Schlüssel, und `/haushalt/dokumente` liefert je Jahrgang das
   *  zugehörige Papier.
   *
   *  Wo ein Jahrgang aber aus MEHREREN Papieren besteht, reicht das nicht —
   *  ein Jahrgang Wirtschaftsplan sind bis zu sieben Pläne von sieben
   *  Betrieben. Dann ist die `herkunft_id` der Zeile die einzige Angabe, die
   *  „diese Zahl steht in DIESEM Papier" beantwortet
   *  (`components/haushalt/quelle.tsx: Dokumentbeleg`). */
  herkunft?: Record<string, Herkunft>;
  /** Die Haushaltssatzung je Jahrgang — der Rahmen um den Plan. */
  haushaltssatzung?: HaushaltssatzungZeile[];
  /** Woraus die Abfall- und Straßenreinigungsgebühren entstehen. */
  gebuehren?: GebuehrenZeile[];
  /** Die konkreten Tarifvorschläge derselben Unterlagen. */
  gebuehrensaetze?: GebuehrensatzZeile[];
  /** Jahre mit einem beschlossenen **Haushaltsansatz** — das jüngste ist das
   *  Jahr, für das gerade ein Haushalt gilt.
   *
   *  Bewusst OHNE die Finanzplanungsjahre desselben Dokuments: Der Plan
   *  schreibt über fünf Spalten „Ansatz", aufgestellt ist aber nur eines der
   *  Jahre; die übrigen sind Vorausschau nach § 8 NKomVG, die jeder neue
   *  Haushalt neu schreibt (`store.ansatz_jahre` filtert das). Wer diese Liste
   *  als Jahr-Umschalter benutzt, bekommt deshalb keine Jahre angeboten, für
   *  die nie ein Haushalt beschlossen wurde. */
  ansatz_jahre?: number[];
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
  /** Wie viele Betriebe die Gewerbesteuer aufbringen (Landesamt für Statistik). */
  gewerbesteuerstatistik?: Gewerbesteuerstatistik;
  /** Die dreizehn Kennzahlen des Rechenschaftsberichts — mit den Rechenwegen,
   *  die die Stadt danebendruckt, und den Korrekturen zwischen den Berichten. */
  kennzahlen?: Kennzahlen;
};

/** Die Adresse der Haushalts-Übersicht, zugeschnitten auf das, was eine Seite
 *  wirklich rendert.
 *
 *  WARUM DAS SEIN MUSS. Der Endpunkt trägt neunzehn Blöcke; keine Seite
 *  braucht mehr als sechs. `/haushalt/labor` braucht **einen** und lud dafür
 *  bis 08/2026 knapp 2 MB — auf dem Handy über Mobilfunk, denn die iOS-App
 *  holt dieselbe Antwort.
 *
 *  WARUM ZUSAMMEN MIT `HaushaltAuswahl`. Die Feldliste steht genau einmal im
 *  Code und speist beides: die Adresse **und** den Typ. Wer ein Feld benutzt,
 *  das er nicht angefordert hat, bekommt keinen leeren Block, sondern einen
 *  Fehler beim Bauen — und ein still leerer Block wäre in diesem Bereich der
 *  schlimmere Fehler, weil eine leere Stelle hier „diese Daten gibt es nicht"
 *  bedeutet und nicht „falsch abgefragt".
 *
 *      const FELDER = ["jahre", "produkt_jahre"] as const;
 *      const { data } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(
 *        haushaltUrl(FELDER));
 *
 *  `herkunft` ist bewusst **nicht** dabei: Die Belege dieser Seiten hängen am
 *  Quellen-Schlüssel (`lib/haushalt-quellen.ts` + `/haushalt/dokumente`), nicht
 *  an der `herkunft_id` der Zeile. Wer sie doch braucht, fordert sie an. */
export function haushaltUrl(
  felder: readonly (keyof HaushaltDaten)[],
  /** Welche Posten der **Teilhaushalts-Ebene** die Seite aus der
   *  Ergebnisrechnung braucht. Die Kernverwaltung kommt immer vollständig.
   *
   *  Der Block ist mit Abstand der größte (751 KB, davon 664 KB
   *  Teilhaushalts-Zeilen), und fast niemand braucht ihn ganz:
   *
   *  * `"keine"` — nur die Kernverwaltung (`/haushalt/labor` rechnet nur mit ihr),
   *  * `"20"` — dazu die Aufwendungen je Teilhaushalt; das Flussbild der
   *    Übersicht zeichnet rechts genau diesen einen Posten,
   *  * weglassen — alles (`/haushalt/plan-ist` und `/haushalt/bereich`
   *    brauchen die volle Ebene).
   *
   *  Bewusst eine Aussage über die DATEN, nicht über die Ansicht: Wer morgen
   *  einen zweiten Posten zeichnet, ändert hier eine Zahl statt am Endpunkt. */
  thhPosten?: "keine" | string,
): string {
  const teile = [`felder=${felder.join(",")}`];
  if (thhPosten !== undefined) teile.push(`thh_posten=${thhPosten}`);
  return `/council/haushalt?${teile.join("&")}`;
}

/** Der Ausschnitt von `HaushaltDaten`, den `haushaltUrl(FELDER)` liefert. */
export type HaushaltAuswahl<K extends keyof HaushaltDaten> = Pick<HaushaltDaten, K>;

/** Die Herkunft zu einer `herkunft_id` — oder `null`.
 *
 *  Absichtlich strukturell getypt (`{ herkunft?: … }` statt eines konkreten
 *  Seitentyps): Dieselbe Suche steht in neun Seitenmodulen dieses Bereichs,
 *  jedes Mal wortgleich, weil jedes seinen eigenen Antworttyp hat. Diese
 *  Fassung passt auf alle — auch auf `HaushaltAuswahl<…>`, sobald `"herkunft"`
 *  in `FELDER` steht.
 *
 *  Gibt `null` zurück, wenn die Karte gar nicht angefordert wurde. Das ist
 *  bewusst kein Fehler: Die Anzeige lässt den Dokumentbeleg dann weg und
 *  behält ihren Quellen-Chip — sichtbar falsch wäre schlimmer als knapp. */
export function herkunftVon(
  daten: { herkunft?: Record<string, Herkunft> } | null | undefined,
  id: number | null | undefined,
): Herkunft | null {
  if (!daten?.herkunft || id == null) return null;
  return daten.herkunft[String(id)] ?? null;
}

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
  template_number: string;
  /** Haushaltsjahr aus dem Jahrgang der Vorlagen-Nummer, nicht aus dem
   *  Sitzungsdatum — Januar-Vorlagen zählen zum Vorjahr. */
  year: number | null;
  titel: string;
  art: NachbewilligungsArt;
  category: NachbewilligungsKategorie;
  /** In Euro. `null` bei `art === "schwelle"`. */
  amount: number | null;
  /** Aus welcher Stufe der Betrag stammt: dem Titel oder dem
   *  Beschlussvorschlag der Vorlage. */
  amount_source: "titel" | "beschlussvorschlag" | null;
  beschlossen: 0 | 1;
  /** Hat das **Plenum** selbst abgestimmt? Die wörtliche Auskunft — taugt als
   *  Zeilenhinweis („im Fachausschuss beschlossen"), aber **nie** als Basis
   *  eines Rats-Anteils. */
  in_plenary: 0 | 1;
  /** Bucht der Rechenschaftsbericht das als „Beschluss des Rates"?
   *
   *  Das ist die Definition, die zählt: Der Bericht rechnet auch das dazu,
   *  was der Ausschuss für Finanzen und Beteiligungen **abschließend**
   *  entscheidet. 2024 sind das 8 von 21 Fällen — wer stattdessen `in_plenary`
   *  summiert, zeigt 30,9 statt 43,1 Mio. € und damit 28 % zu wenig. */
  ratsentscheidung: 0 | 1;
  /** Ziel für den Link auf die vorhandene Beschluss-Seite. */
  decision_id: number | null;
  gremien: string[];
  fulltext_probe: 0 | 1;
  herkunft_id: number | null;
};

/** Ein Entscheidungsweg aus Kapitel 3 des Rechenschaftsberichts. */
export type NachbewilligungsKanal = {
  year: number;
  kanal: string;
  /** Der Wortlaut der Stadt („Gemäß Haushaltsvermerk durch den Fachdienst
   *  200"), nicht unsere Umschreibung. */
  label: string;
  count_operating: number;
  amount_operating: number;
  count_capital: number;
  amount_capital: number;
  herkunft_id: number | null;
};

/** Ein Haushaltsjahr aus Kapitel 3 — die Gesamtsicht, die das RIS nicht hat. */
export type NachbewilligungsJahr = {
  year: number;
  total_operating: number;
  total_capital: number;
  /** Was der Fließtext des Kapitels als Gesamtsumme nennt. Steht getrennt von
   *  der Summenzeile, **weil beide 2022 auseinanderfallen** (288.000 €). Wer
   *  nur eine der Zahlen behielte, hätte den Widerspruch weggeräumt. */
  total_per_text: number | null;
  /** Verpflichtungsermächtigungen des Jahres — der Bericht zählt sie
   *  ausdrücklich getrennt, und wir addieren sie nirgends dazu. */
  commitments_amount: number | null;
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
  ohne_beleg: { template_number: string; sitzung?: string | null; grund: string }[];
  /** Wer über welche **einzelne** Zuwendung entscheidet. */
  schwellen: { gremium: string; ab: number | null; bis: number | null }[];
};

export type SpendenJahr = {
  year: number;
  amount: number;
  vorlagen: number;
  rat: number;
  verwaltungsausschuss: number;
};

export type SpendenVorlage = {
  template_number: string;
  year: number;
  sitzung: string;
  amount: number;
  gremium?: string | null;
  /** „identisch" oder „zerlegung" — wie die Zweitstelle den Betrag belegt. */
  zweitstelle: string;
  probes: string[];
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
  year: number;
  art: string;
  /** Ansatz der beschlossenen Haushaltssatzung, in Euro. */
  plan: number;
  /** Rechnungsergebnis desselben Jahres, in Euro. */
  ist: number;
  /** Die Quelle nennt dieses Ergebnis selbst „vorläufig" — es kann sich noch
   *  ändern, und das gehört an die Zahl. */
  provisional: 0 | 1;
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

/** Die Gewerbesteuerstatistik des Landesamts (Bericht L IV 13) — der Nenner
 *  zur Gewerbesteuer.
 *
 *  **Das ist die Veranlagung, nicht das Aufkommen.** Der Steuermessbetrag
 *  entsteht aus dem Gewerbeertrag eines Erhebungsjahres; was in diesem Jahr in
 *  der Kasse ankam, steht in `steuern` und ist etwas anderes — in den drei
 *  prüfbaren Jahren lagen beide zwischen 13 % darunter und 27 % darüber. Keine
 *  Anzeige darf die zwei Reihen zu einer machen; `abgrenzung` sagt es im
 *  Klartext und kommt deshalb mit den Zahlen aus der API. */
export type Gewerbesteuerstatistik = {
  zeilen: GewerbesteuerstatistikZeile[];
  /** Der eine Satz, ohne den die Zahlen irreführen — steht immer. */
  abgrenzung_kurz: string;
  /** Der Rest: was gezählt wird, warum Messbetrag nicht Aufkommen ist, wie
   *  groß der Verzug ist. Darf eingeklappt sein, weggelassen nicht. */
  abgrenzung: string;
};

export type GewerbesteuerstatistikZeile = {
  /** Das **Erhebungsjahr** der Veranlagung. Der Bericht dazu erscheint rund
   *  fünf Jahre später — das jüngste Jahr hier ist nicht das jüngste der
   *  Aufkommenskurve. */
  year: number;
  stadt: string;
  /** Betriebe und Betriebsstätten, für die hier Gewerbesteuer erhoben wird. */
  faelle: number;
  /** Davon die, die einen positiven Steuermessbetrag haben — also zahlen. */
  cases_positive: number;
  /** Summe der Steuermessbeträge in Euro. `null` heißt **gesperrt**
   *  (Geheimhaltung), nicht „null Euro". */
  tax_base_eur: number | null;
  /** Betriebe, die nur hier eine Betriebsstätte haben. */
  festsetzungen: number | null;
  assessments_positive: number | null;
  assessment_tax_base_eur: number | null;
  /** Betriebsstätten, deren Messbetrag nach Arbeitslöhnen auf mehrere
   *  Gemeinden zerlegt wurde (§ 28 GewStG). */
  apportionments: number | null;
  apportionments_positive: number | null;
  apportioned_assessment_eur: number | null;
  /** Der Hebesatz, den das Landesamt nachrichtlich beilegt (Prozentpunkte). */
  hebesatz: number | null;
  /** Ob für diese Stadt ein Betrag der Geheimhaltung unterliegt. */
  gesperrt: number;
};

export type HebesatzZeile = {
  year: number;
  /** „Grundsteuer A" · „Grundsteuer B" · „Gewerbesteuer". */
  art: string;
  /** Prozentpunkte. */
  hebesatz: number;
  /** Der Satz, der bis zu diesem Jahr galt — `null` in der ersten Zeile. */
  prior_rate: number | null;
};

/** Die beiden Rechnungswesen, unter denen die Stadt gezählt hat. Der Wechsel
 *  zum 1. Januar 2010 ist die Naht der langen Reihe. */
export type Regelwerk = "kameral" | "doppik";

/** Welche der beiden Veröffentlichungen den Betrag geliefert hat. Nur dort
 *  interessant, wo sie sich widersprechen — dann steht die unterlegene Zahl
 *  als `conflict_amount` daneben. */
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

/** Ein Jahrgang der langen Reihe. `amount` in Euro.
 *
 *  `probes` sind die Rechenproben, die dieser Jahrgang bestanden hat — sie
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
  year: number;
  regelwerk: Regelwerk;
  amount: number;
  quelle: Ausgabenquelle;
  probes: string[];
  /** Was die andere Veröffentlichung für dieses Jahr nennt — nur gefüllt, wo
   *  die beiden sich widersprechen. */
  conflict_amount: number | null;
  conflict_source: Ausgabenquelle | null;
  revised: 0 | 1;
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
  daten: HaushaltAuswahl<"ergebnisrechnung">,
): { year: number; plan: number; ist: number; delta: number; planArt: PlanArt }[] {
  const posten = daten.ergebnisrechnung ?? [];
  const jahre = [...new Set(posten.map((p) => p.year))].sort((a, b) => a - b);
  return jahre
    .map((year) => {
      const teile = [21, 24].map((nr) =>
        posten.find((p) => p.year === year && p.nr === nr && p.sub_budget_no == null));
      if (teile.some((t) => !t || t.plan == null || t.result == null)) return null;
      const plan = teile.reduce((s, t) => s + (t!.plan as number), 0) / 1e6;
      const ist = teile.reduce((s, t) => s + (t!.result as number), 0) / 1e6;
      return {
        year,
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
  daten: HaushaltAuswahl<"finanzrechnung">, year: number,
): Partial<Record<FinanzRolle, FinanzZeile>> | null {
  const zeilen = (daten.finanzrechnung ?? []).filter((z) => z.year === year);
  if (!zeilen.length) return null;
  const aus: Partial<Record<FinanzRolle, FinanzZeile>> = {};
  for (const z of zeilen) if (z.rolle) aus[z.rolle] = z;
  // Ohne die drei Salden ist die Aussage nicht vollständig — dann lieber gar
  // keine Kassensicht als eine halbe (die Kaskade lässt das gar nicht zu,
  // aber der Lesepfad soll sich nicht darauf verlassen).
  return aus.balance_operating && aus.balance_capital && aus.finanzmittel
    ? aus : null;
}

/** Die Erläuterung zu einem Posten eines Jahres — oder nichts. */
export function grundZuPosten(
  daten: HaushaltAuswahl<"abweichungsgruende">, year: number, nr: number,
): Abweichungsgrund | null {
  return (daten.abweichungsgruende ?? []).find((g) => g.year === year && g.nr === nr) ?? null;
}

/** Der Schlussbericht des Rechnungsprüfungsamts zu einem Jahrgang. */
export function pruefberichtZuJahr(
  daten: HaushaltAuswahl<"pruefbericht_quellen">, year: number,
): Pruefbericht | null {
  return (daten.pruefbericht_quellen ?? []).find((p) => p.year === year) ?? null;
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
  daten: HaushaltAuswahl<"abweichungsgruende">, year: number, thhNr: number,
): Abweichungsgrund[] {
  // „Teilhaushalt 10", „THH 10", „THH10" — mit und ohne führende Null.
  const n = String(thhNr);
  const muster = new RegExp(
    `(?:Teilhaushalt|THH)\\s?0?${n}(?!\\d)`, "i");
  return (daten.abweichungsgruende ?? [])
    .filter((g) => g.year === year && muster.test(g.text))
    .sort((a, b) => Math.abs(b.delta_meur ?? 0) - Math.abs(a.delta_meur ?? 0));
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
  year: number;
  stand: "plan" | "ist";
  herkunft: FlussSeite;
  verwendung: FlussSeite;
  /** Gemeinsame Achse beider Seiten in Euro — die größere der beiden Summen. */
  skala: number;
  /** Erträge − Aufwendungen in Euro. */
  balance: number;
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
export function flussJahre(daten: HaushaltAuswahl<"ergebnisrechnung">): number[] {
  const posten = daten.ergebnisrechnung ?? [];
  return [...new Set(posten.map((p) => p.year))]
    .sort((a, b) => a - b)
    .filter((year) => {
      const gesamt = posten.filter((p) => p.year === year && p.sub_budget_no == null);
      return (
        gesamt.some((p) => p.nr >= 1 && p.nr <= 11) &&
        gesamt.some((p) => p.nr === 12) &&
        gesamt.some((p) => p.nr === 20) &&
        posten.some((p) => p.year === year && p.sub_budget_no != null && p.nr === 20)
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
 *  je `sub_budget_no`) — beide aus derselben Tabelle desselben Jahres, damit nie zwei
 *  Stände nebeneinander stehen. `null`, wenn eine Seite fehlt. */
export function flussbild(
  daten: HaushaltAuswahl<"ergebnisrechnung">, year: number, stand: "plan" | "ist",
): FlussDaten | null {
  const zahl = (p: ErgebnisPosten | undefined) =>
    p ? (stand === "ist" ? p.result : p.ansatz) : null;
  const rows = (daten.ergebnisrechnung ?? []).filter((p) => p.year === year);
  const gesamt = rows.filter((p) => p.sub_budget_no == null);

  const revenues = zahl(gesamt.find((p) => p.nr === 12));
  const expenses = zahl(gesamt.find((p) => p.nr === 20));
  if (!revenues || !expenses || revenues <= 0 || expenses <= 0) return null;

  const arten: FlussBand[] = gesamt
    .filter((p) => p.nr >= 1 && p.nr <= 11 && (zahl(p) ?? 0) > 0)
    .map((p) => ({
      id: `art-${p.nr}`,
      label: ERTRAGSART_KURZ[p.nr] ?? p.label,
      lang: p.label,
      wert: zahl(p) as number,
      art: "posten" as const,
    }));
  const bereiche: FlussBand[] = rows
    .filter((p) => p.sub_budget_no != null && p.nr === 20 && (zahl(p) ?? 0) > 0)
    .map((p) => ({
      id: `sub_budget-${p.sub_budget_no}`,
      label: p.sub_budget_name ?? `Teilhaushalt ${p.sub_budget_no}`,
      lang: p.sub_budget_name ?? `Teilhaushalt ${p.sub_budget_no}`,
      wert: zahl(p) as number,
      art: "posten" as const,
    }));
  if (!arten.length || !bereiche.length) return null;

  // Die Skala deckt auch den Fall ab, dass Einzelposten ihre eigene
  // Summenzeile übersteigen (fehlgelesene Zeile): Dann ragt nichts über den
  // Knoten hinaus, und `aufgeschluesselt` schaltet das Bild ohnehin ab.
  const skala = Math.max(
    revenues, expenses,
    arten.reduce((s, b) => s + b.wert, 0),
    bereiche.reduce((s, b) => s + b.wert, 0),
  );

  const herkunft = flussSeite(arten, revenues, skala,
    "im Abschluss nicht aufgeschlüsselt", "aus dem Ersparten");
  const verwendung = flussSeite(bereiche, expenses, skala,
    "im Abschluss nicht aufgeschlüsselt", "bleibt übrig");

  const summeLinks = herkunft.baender.reduce((s, b) => s + b.wert, 0);
  const summeRechts = verwendung.baender.reduce((s, b) => s + b.wert, 0);
  const luecke = (s: FlussSeite) => Math.abs(s.gesamt - s.teile);
  return {
    year, stand, herkunft, verwendung, skala,
    balance: revenues - expenses,
    summeLinks, summeRechts,
    stimmt: Math.abs(summeLinks - summeRechts) <= FLUSS_TOLERANZ
      && Math.abs(summeLinks - skala) <= FLUSS_TOLERANZ,
    aufgeschluesselt: luecke(herkunft) <= 0.02 * herkunft.gesamt
      && luecke(verwendung) <= 0.02 * verwendung.gesamt,
  };
}

/** Ein Wirtschaftsplan eines Eigenbetriebs oder einer städtischen
 *  Gesellschaft, wie der Rat ihn beschließt.
 *
 *  **`revenues` und `expenses` sind oft `null`, und das ist die Auskunft.**
 *  Nur zwei der sechs Betriebe nennen sie in prüfbarer Form — der Eigenbetrieb
 *  Gebäudewirtschaft im Beschlusstext, der Abfallwirtschaftsbetrieb im
 *  Erfolgsplan seiner Anlage. Bei den übrigen ist die einzige doppelt belegte
 *  Zahl das Jahresergebnis. Eine 0 an diesen Stellen wäre eine Behauptung. */
/** Ein Bereich einer Gebührenbedarfsberechnung.
 *
 *  ACHTUNG BEI DER ANZEIGE: `gebuehr` und `reference_quantity` sind bei der
 *  **Abfallsammlung** `null`, und das ist die Auskunft und keine Lücke: Sie
 *  erhebt eine Grundgebühr UND eine Gebühr je Liter Behältervolumen, es gibt
 *  dort also keine einzelne Division. Eine 0 wäre eine Behauptung. */
export type GebuehrenZeile = {
  year: number;
  /** `abfallbehandlung` · `abfallsammlung` · `strassenreinigung`. */
  area: string;
  area_name: string;
  /** Was der Bereich im Jahr insgesamt kostet. */
  kostenkalkulation: number;
  /** Alles, was davon abgeht — negativ. */
  deductions: number;
  /** Was die Gebührenzahler tragen. */
  costs_to_cover: number;
  reference_quantity: number | null;
  reference_unit: string | null;
  /** Die errechnete Gebühr, drei Nachkommastellen. */
  gebuehr: number | null;
  /** Der gerundete Vorschlag an den Rat — das, was erhoben wird. */
  fee_proposed: number | null;
  template_number: string | null;
  probes: string;
  herkunft_id: number | null;
};

/** Ein ausdrücklich benannter Tarif aus Anlage 4 der
 * Gebührenbedarfsberechnung. Anders als `GebuehrenZeile.gebuehr` ist das
 * keine aus einer Gesamtkalkulation abgeleitete Durchschnittsgröße, sondern
 * der konkrete Verwaltungsvorschlag für Grundgebühr, Litergebühr, Karte oder
 * Anlieferung. */
export type GebuehrensatzZeile = {
  year: number;
  schluessel: string;
  area: string;
  label: string;
  amount: number;
  einheit: string;
  prior_year: number | null;
  change_pct: number | null;
  template_number: string | null;
  probes: string;
  herkunft_id: number | null;
};

/** Ein Jahrgang der Haushaltssatzung (§§ 1–5).
 *
 *  ACHTUNG BEI DER ANZEIGE: `fassung` ist in jeder Zeile des Bestands
 *  `"entwurf"`. Im Ratsinformationssystem liegen ausschließlich
 *  Verwaltungsentwürfe; die beschlossene Satzung erscheint im Amtsblatt. Eine
 *  Anzeige, die das wegließe, machte aus einem Vorschlag der Verwaltung einen
 *  Ratsbeschluss. */
export type HaushaltssatzungZeile = {
  year: number;
  /** 0 = die Satzung selbst. Nachträge werden (noch) nicht gelesen. */
  supplement: number;
  /** `entwurf` | `unbekannt` — nie `beschlossen`, s. o. */
  fassung: string;

  ordinary_revenues: number;
  ordinary_expenses: number;
  extraordinary_revenues: number;
  extraordinary_expenses: number;

  in_operating: number;
  out_operating: number;
  in_capital: number;
  aus_invest: number;
  in_financing: number;
  out_financing: number;
  /** Die „Nachrichtlich"-Zeilen der Satzung — nachgerechnet, nicht übernommen. */
  in_total: number;
  out_total: number;

  /** § 2. `0` heißt „nicht veranschlagt" und ist eine Aussage; `null` hieße
   *  „die Satzung sagt dazu nichts". */
  investment_loans: number | null;
  /** § 3. */
  commitment_authorizations: number | null;
  /** § 4 — der Dispo der Stadt. */
  liquidity_loans: number | null;

  /** § 5. Ab dem Jahrgang 2025 nennt die Satzung nur noch die Gewerbesteuer
   *  und verweist für die Grundsteuer auf eine eigene Satzung — dann sind
   *  diese beiden Felder leer, und das ist die Auskunft. */
  hebesatz_grundsteuer_a: number | null;
  hebesatz_grundsteuer_b: number | null;
  hebesatz_gewerbesteuer: number | null;

  /** Das im Text genannte Sitzungsdatum, `null` bei „xx.xx.JJJJ". */
  session_date: string | null;
  template_number: string | null;
  probes: string;
  herkunft_id: number | null;
};

export type WirtschaftsplanZeile = {
  /** Kürzel: `egh`, `awb`, `bbo`, `bbgo`, `stadion`, `stadion_planung`. */
  betrieb: string;
  betrieb_name: string;
  year: number;
  template_number: string;
  revenues: number | null;
  expenses: number | null;
  steuern: number | null;
  /** Als einziges immer da. */
  result: number;
  vermoegensplan: number | null;
  /** Die Investitionen IM Vermögensplan — ein Posten, nicht die Summe.
   *
   *  Nicht mit `vermoegensplan` verwechseln: Der ist die Gesamtsumme
   *  (Einzahlungen = Auszahlungen), diese Zahl ein Posten darin. Der
   *  Bäderbetrieb nennt im Beschlusstext nur den Posten, der Eigenbetrieb
   *  Gebäudewirtschaft nur die Summe — beide dürfen nicht dieselbe Zeile
   *  bekommen. */
  investitionen: number | null;
  verpflichtungen: number | null;
  /** Stand des Verwaltungsentwurfs, wo das Dokument ihn nennt. */
  entwurf_vom: string | null;
  /** Komma-getrennt, welche Rechenproben für diese Zeile gelaufen sind. */
  probes: string;
  herkunft_id: number | null;
};

export type EinnahmeartenPlan = {
  year: number;
  /** Aus welchem Haushalt die Zahlen stammen — bei uns immer derselbe
   *  Jahrgang wie `year`, aber die Angabe gehört an die Anzeige. */
  planJahrgang: number;
  /** Ertragsarten (Posten 01–11), absteigend nach Betrag, in EURO. */
  arten: { nr: number; label: string; lang: string; amount: number }[];
  /** Die ausgewiesene Summenzeile (Posten 12) in Euro. */
  gesamt: number;
  /** Summe der Einzelposten — muss `gesamt` treffen, sonst wird nichts
   *  gezeichnet (siehe unten). */
  teile: number;
  /** Was die Anzeigetafel derselben Seite für dieses Jahr ausweist
   *  (`council_haushalt`), und der Abstand dazu. `null`, wenn die Seite den
   *  Jahrgang gar nicht führt.
   *
   *  Die beiden Zahlen sind NICHT dieselbe Größe: Hier steht der Entwurf aus
   *  Anlage 005 der Einbringungs-Vorlage, dort der beschlossene Plan. Für 2026
   *  liegen sie 24,3 Mio. € auseinander. Wer beide auf einer Seite zeigt, muss
   *  den Abstand benennen — sonst steht dort ein Widerspruch, den sich der
   *  Leser selbst erklären soll. */
  tafel: { revenues: number; abstand: number } | null;
};

/** Woher das Geld eines **Planjahres** kommen soll — die eine Seite, die es
 *  für Jahre ohne Jahresabschluss gibt.
 *
 *  Das Flussbild braucht beide Seiten aus **einer** Quelle; für Planjahre gibt
 *  es die nicht (`council_ergebnishaushalt` führt keine Teilhaushalte, und
 *  `council_haushalt` steht in einem anderen Stand). Statt deshalb gar nichts
 *  zu zeigen, steht die Herkunftsseite allein da — ausdrücklich als halbes
 *  Bild und ohne Gegenstück.
 *
 *  **Nur `art === "ansatz"`.** Die Finanzplanungsjahre desselben Dokuments
 *  sind eine Vorausschau nach § 8 NKomVG; sie hier mitzunehmen hieße, für 2029
 *  einen Haushalt zu zeigen, den nie jemand aufgestellt hat.
 *
 *  `null`, wenn das Jahr fehlt oder die Einzelposten ihre eigene Summenzeile
 *  nicht treffen — dieselbe Regel wie beim Flussbild: Was sich nicht aufaddiert,
 *  wird nicht gezeichnet. */
export function einnahmearten(
  daten: HaushaltAuswahl<"ergebnishaushalt" | "jahre">, year: number,
): EinnahmeartenPlan | null {
  const zeilen = (daten.ergebnishaushalt ?? [])
    .filter((z) => z.year === year && z.art === "ansatz");
  if (!zeilen.length) return null;

  const arten = zeilen
    .filter((z) => z.nr >= 1 && z.nr <= 11 && z.amount > 0)
    .map((z) => ({
      nr: z.nr,
      label: ERTRAGSART_KURZ[z.nr] ?? z.label,
      lang: z.label,
      amount: z.amount,
    }))
    .sort((a, b) => b.amount - a.amount);
  const gesamt = zeilen.find((z) => z.nr === 12)?.amount ?? 0;
  if (!arten.length || gesamt <= 0) return null;

  const teile = arten.reduce((s, a) => s + a.amount, 0);
  // Dieselbe Toleranz wie das Flussbild (0,05 Mio. €): Was die ausgewiesene
  // Summe nicht trifft, ist keine Aufschlüsselung, sondern eine Auswahl.
  if (Math.abs(gesamt - teile) > FLUSS_TOLERANZ) return null;

  const tafelErtraege = summe(daten.jahre?.[String(year)] ?? [])?.revenues ?? null;
  return {
    year,
    planJahrgang: zeilen[0].plan_budget_year,
    arten,
    gesamt,
    teile,
    tafel: tafelErtraege == null
      ? null : { revenues: tafelErtraege, abstand: tafelErtraege - gesamt },
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
    p.result != null && p.result < 0 && (!thhName || p.sub_budget_name === thhName));
  if (!passend.length) return null;
  return passend.reduce((best, p) =>
    Math.abs(-(p.result as number) / 1e6 - mioBetrag)
      < Math.abs(-(best.result as number) / 1e6 - mioBetrag) ? p : best);
}

/** Jüngster geprüfter Stand der verfügbaren Überschussrücklage. */
export function juengsteRuecklage(
  daten: HaushaltAuswahl<"ruecklage">,
): RuecklageJahr | null {
  return [...(daten.ruecklage ?? [])]
    .filter((z) => Number.isFinite(z.state_after_result))
    .sort((a, b) => a.year - b.year)
    .at(-1) ?? null;
}

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
export function amount(euro: number | null | undefined): { wert: string; einheit: string } {
  if (euro == null) return { wert: "—", einheit: "" };
  const abs = Math.abs(euro);
  if (abs >= 1_000_000) return { wert: deMio(euro / 1e6), einheit: "Mio. €" };
  if (abs >= 10_000) {
    return { wert: Math.round(euro / 1000).toLocaleString("de-DE"), einheit: "Tsd. €" };
  }
  return { wert: Math.round(euro).toLocaleString("de-DE"), einheit: "€" };
}

export function jahreSortiert(daten: HaushaltAuswahl<"jahre">): number[] {
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
  return zeilen.find((z) => z.is_total === 1);
}

/** Die lange Ausgabenreihe, sortiert und nur mit den Jahren, die auch einen
 *  Betrag haben. Leer, solange die Tabelle leer ist — die Seite zeigt den
 *  Block dann gar nicht, statt eine Achse ohne Säulen zu zeichnen.
 *
 *  Die API liefert bereits sortiert; hier wird trotzdem sortiert, weil die
 *  Naht-Grafik eine aufsteigende Achse voraussetzt und ein Lesepfad, der sich
 *  auf die Reihenfolge einer fremden Antwort verlässt, still kippt. */
export function ausgabenreihe(daten: HaushaltAuswahl<"ausgabenreihe">): AusgabenreiheJahr[] {
  const zeilen = daten.ausgabenreihe?.zeilen ?? [];
  return [...zeilen].sort((a, b) => a.year - b.year);
}

/** Die Jahrgänge, in denen sich die beiden Veröffentlichungen widersprechen.
 *
 *  Kein Nebenschauplatz, sondern Inhalt: Wo zwei amtliche Quellen für dasselbe
 *  Jahr zwei Beträge nennen, gehört das auf die Seite — mit beiden Zahlen. */
export function ausgabenKonflikte(daten: HaushaltAuswahl<"ausgabenreihe">): AusgabenreiheJahr[] {
  return ausgabenreihe(daten).filter((z) => z.conflict_amount != null);
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
  year: number;
  summe: number;
  faelle: number;
  verpflichtungen: number;
  verpflichtungenBetrag: number;
  sammelberichte: number;
};

export function nachbewilligungsJahre(
  daten: HaushaltAuswahl<"nachbewilligungen">,
): NachbewilligungsSumme[] {
  const jahre = new Map<number, NachbewilligungsSumme>();
  const hol = (year: number) => {
    let e = jahre.get(year);
    if (!e) {
      e = { year, summe: 0, faelle: 0, verpflichtungen: 0,
            verpflichtungenBetrag: 0, sammelberichte: 0 };
      jahre.set(year, e);
    }
    return e;
  };
  for (const n of daten.nachbewilligungen?.serie ?? []) {
    if (n.year == null) continue;
    if (n.art === "schwelle") {
      hol(n.year).sammelberichte += 1;
    } else if (n.art === "verpflichtungsermaechtigung") {
      if (!n.beschlossen) continue;
      const e = hol(n.year);
      e.verpflichtungen += 1;
      e.verpflichtungenBetrag += n.amount ?? 0;
    } else if (n.beschlossen && n.amount != null) {
      const e = hol(n.year);
      e.summe += n.amount;
      e.faelle += 1;
    }
  }
  return [...jahre.values()].sort((a, b) => a.year - b.year);
}

/** Die Bewilligungen eines Jahres, größte zuerst — die Liste, die auf ihre
 *  Beschluss-Seiten verlinkt. Ohne Sammelberichte und ohne
 *  Verpflichtungsermächtigungen: Die stehen auf der Seite getrennt. */
export function nachbewilligungenFuerJahr(
  daten: HaushaltAuswahl<"nachbewilligungen">, year: number,
): Nachbewilligung[] {
  return (daten.nachbewilligungen?.serie ?? [])
    .filter((n) => n.year === year && n.art === "bewilligung"
      && n.beschlossen === 1 && n.amount != null)
    .sort((a, b) => (b.amount ?? 0) - (a.amount ?? 0));
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
  const gesamt = j.total_operating + j.total_capital;
  const rat = j.kanaele.find((k) => k.kanal === "rat");
  if (!gesamt || !rat) return null;
  return ((rat.amount_operating + rat.amount_capital) / gesamt) * 100;
}

/** Gesamtsumme eines Kapitel-3-Jahrgangs (Summenzeile beider Spalten). */
export function nachbewilligungGesamt(j: NachbewilligungsJahr): number {
  return j.total_operating + j.total_capital;
}

/** Ein Kanal quer über beide Spalten. */
export function kanalBetrag(k: NachbewilligungsKanal): number {
  return k.amount_operating + k.amount_capital;
}

export function kanalAnzahl(k: NachbewilligungsKanal): number {
  return k.count_operating + k.count_capital;
}

/** Die Spendenjahre, die **vollständig** sind — also alle bis auf das
 *  laufende.
 *
 *  Das laufende Jahr hat erst die Beschlüsse bis heute; es in eine Reihe zu
 *  zeichnen, hieße einen Rückgang zu zeigen, den es nicht gibt. Es steht
 *  deshalb daneben als Satz, nicht in der Kurve. */
export function spendenJahre(daten: HaushaltAuswahl<"spenden">): SpendenJahr[] {
  const jahre = daten.spenden?.jahre ?? [];
  const laufend = new Date().getFullYear();
  return jahre.filter((j) => j.year < laufend).sort((a, b) => a.year - b.year);
}

/** Das laufende Jahr, sofern es schon Beschlüsse trägt. */
export function spendenLaufend(daten: HaushaltAuswahl<"spenden">): SpendenJahr | null {
  const laufend = new Date().getFullYear();
  return (daten.spenden?.jahre ?? []).find((j) => j.year === laufend) ?? null;
}

/** Rat und Verwaltungsausschuss über alle belegten Vorlagen.
 *
 *  Die Aufteilung ist selbst die Auskunft: Beide Gremien behandeln ungefähr
 *  gleich viele Vorlagen, aber die Schwelle von 2.000 Euro sorgt dafür, dass
 *  fast das ganze Geld über den Rat läuft. */
export function spendenGremien(daten: HaushaltAuswahl<"spenden">) {
  const leer = { vorlagen: 0, amount: 0 };
  const aus = { Rat: { ...leer }, Verwaltungsausschuss: { ...leer } };
  for (const v of daten.spenden?.vorlagen ?? []) {
    const k = v.gremium === "Rat" ? "Rat"
      : v.gremium === "Verwaltungsausschuss" ? "Verwaltungsausschuss" : null;
    if (!k) continue;
    aus[k].vorlagen += 1;
    aus[k].amount += v.amount;
  }
  return aus;
}

export function bereiche(zeilen: HaushaltZeile[]): HaushaltZeile[] {
  return zeilen.filter((z) => z.is_total !== 1);
}

/** Kostendeckungsgrad in Prozent (eigene Erträge / Aufwendungen), 0–100. */
export function deckung(z: HaushaltZeile): number | null {
  if (!z.expenses || z.expenses <= 0 || z.revenues == null) return null;
  return Math.round((z.revenues / z.expenses) * 100);
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
  daten: HaushaltAuswahl<"jahre">, name: string,
): { year: number; zeile: HaushaltZeile }[] {
  return jahreSortiert(daten)
    .map((year) => {
      const z = daten.jahre[String(year)]?.find((r) => r.area === name);
      return z ? { year, zeile: z } : null;
    })
    .filter((x): x is { year: number; zeile: HaushaltZeile } => x !== null);
}

/** Quelle einer Jahres-Scheibe menschenlesbar (PDF vs. Open-Data-CSV). */
export function quellenLabel(zeilen: HaushaltZeile[], year: number): { text: string; url: string | null } {
  const url = zeilen[0]?.source_url ?? null;
  const csv = url?.includes("opendata.oldenburg.de");
  return {
    text: csv
      ? `Haushaltsplan ${year}, Stadt Oldenburg — Open-Data-Portal (CSV, Lizenz dl-de/by-2.0)`
      : `Beschlossener Haushaltsplan ${year}, Stadt Oldenburg (PDF)`,
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
 *  auftaucht. Bestehende Aufrufe (`BEREICH_INFO[zeile.area]`) bleiben damit
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
