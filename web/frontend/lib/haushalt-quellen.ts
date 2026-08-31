// Quellenverzeichnis des Haushalts-Bereichs — eine Quelle, ein Schlüssel.
//
// Warum als Konstante statt aus der API: Hier steht die Quelle einer ganzen
// SEITE in einem Absatz — was das Dokument ist, was wir daraus lesen und
// warum man es glauben kann. Das ist eine redaktionelle Zusammenfassung über
// alle Jahrgänge hinweg, keine Angabe, die aus einer einzelnen Zeile fällt.
//
// Je Datenzeile weiß es die Datenbank seit 08/2026 genauer: `council_herkunft`
// führt Dokument, Fundstelle darin, bestandene Rechenprobe samt Messwert und
// Stichtag, und `GET /api/council/haushalt` liefert das als `herkunft` mit
// (Format und Begründung: `council/herkunft.py`). Wer einen Beleg auf die
// einzelne Zahl genau machen will, nimmt die `herkunft_id` der Zeile — nicht
// diese Konstante.
//
// DER DATENSTAND KOMMT AUS DEM BESTAND, NICHT VON HAND
//
// Hier standen bis 08/2026 einundzwanzig Jahresspannen ausgeschrieben
// („Jahresabschlüsse 2017–2024"), dazu im Kopf die Bitte, sie beim Nachziehen
// eines Haushaltsjahres zu aktualisieren. Das ging erwartbar schief: Ein
// Ingest-Lauf zieht einen Jahrgang nach, die Seite behauptet weiter den alten
// Stand, und es fällt niemandem auf — die Angabe steht ja nicht neben den
// Daten, sondern in dieser Datei.
//
// Wo die Spanne aus dem Bestand fällt, steht sie deshalb nicht mehr hier:
// `standWort` trägt nur noch das Wort davor („Jahresabschlüsse"), die Zahlen
// kommen aus `GET /api/council/haushalt/dokumente` (`jahrgaenge`, gerechnet
// in `CouncilStore.haushalt_jahrgaenge`). Zusammengesetzt wird in
// `standText()`.
//
// `stand` bleibt für die vier Fälle, die sich NICHT ableiten lassen, und als
// Rückfall, solange die Antwort nicht da ist:
//   * `hebesaetze` — ein Beschlussdatum, keine Datenspanne;
//   * `ruecklage` — Bilanzreihe plus Bestätigung im späteren Vorbericht;
//   * `vergleich_2018` — eine einzelne Ratsvorlage, die nie einen zweiten
//     Jahrgang bekommt;
//   * `ratsbeschluss` — „seit Januar 2018", nach oben offen und deshalb
//     nicht veraltbar;
//   * die `lsn_*`-Quellen — deren Angabe nennt die AUSGABE der Landestabelle
//     („endgültig, Stand 26.03.2026"), nicht die Spanne ihrer Daten.

export type Quelle = {
  titel: string;
  /** Wo genau im Dokument die Zahlen stehen — der Punkt, an dem man nachschlägt. */
  citation: string;
  herausgeber: string;
  /** Datenstand, nicht Abrufdatum: Was die Zahl beschreibt, nicht wann wir sie
   *  holten. Rückfall — wo `standWort` gesetzt ist, gewinnt die gerechnete
   *  Spanne, sobald sie vorliegt. */
  stand: string;
  /** Das Wort vor der Jahresspanne („Jahresabschlüsse", „Haushaltsjahre").
   *  Gesetzt heißt: Die Zahlen dahinter kommen aus dem Bestand. Leerstring,
   *  wo die Spanne für sich steht. */
  standWort?: string;
  /** Was hinter der Spanne steht und nicht aus den Daten fällt — die Ausgabe
   *  einer Statistiktabelle etwa. */
  standZusatz?: string;
  lizenz?: string;
  url?: string;
  art: "pdf" | "csv" | "web";
};

/** Die Jahrgänge je Quelle, wie sie im Bestand stehen (aufsteigend). */
export type Jahrgaenge = Partial<Record<QuellenSchluessel, number[]>>;

/** Der Datenstand, den die Seite anschreibt.
 *
 *  Die gerechnete Spanne gewinnt, sobald sie da ist — sonst der von Hand
 *  gepflegte Satz. Der Rückfall ist nicht bloß Höflichkeit gegenüber dem
 *  Ladezustand: Vier Quellen haben gar keine ableitbare Spanne, und eine
 *  leere Tabelle (frische Datenbank, fehlgeschlagener Ingest) darf nicht in
 *  ein nacktes „Stand" münden. */
export function standText(q: Quelle, jahre: number[] | undefined): string {
  if (q.standWort === undefined || !jahre || jahre.length === 0) return q.stand;
  const von = jahre[0];
  const bis = jahre[jahre.length - 1];
  const spanne = von === bis ? `${von}` : `${von}–${bis}`;
  return [q.standWort, spanne, q.standZusatz].filter(Boolean).join(" ");
}

/** Die Schlüssel explizit statt per Inferenz: So sind die Werte einheitlich
 *  als `Quelle` getypt (inklusive optionaler Felder wie `lizenz`), und die
 *  Union bleibt trotzdem eng genug, um Tippfehler beim Aufruf zu fangen. */
export type QuellenSchluessel =
  | "plan" | "steuern" | "steuerkraft" | "hebesaetze" | "ruecklage"
  // Die Plan-Seite je Steuerart (Jahrbuch 1103). Ein eigener Schlüssel neben
  // `steuern`, weil es eine andere Tabelle mit einer anderen Grenze ist: Die
  // Ist-Reihe führt 28 Jahrgänge, diese hier drei.
  | "steuerplan"
  | "jahresabschluss" | "teilhaushalt" | "stellenplan" | "pruefbericht"
  // Der Gesamtergebnishaushalt (Anlage 005 des Haushaltsplans) — dieselbe
  // Postengliederung wie der Jahresabschluss, aber für Jahre, die noch keinen
  // haben. Ein eigener Schlüssel, weil es eine andere Sorte Zahl ist: Der
  // Abschluss zählt, was geflossen IST, dieser Plan, was fließen SOLL — und
  // zwar in der Fassung der Einbringung, nicht des Ratsbeschlusses.
  | "ergebnishaushalt"
  // Die Wirtschaftspläne der Eigenbetriebe. Eigener Schlüssel, weil es ein
  // anderer Haushalt ist: Er wird in derselben Ratssitzung beschlossen, gehört
  // aber nicht zum Kernhaushalt und ist mit ihm nicht addierbar.
  | "wirtschaftsplan"
  // Die Haushaltssatzung — der Rahmen um den Plan. Eigener Schlüssel, weil sie
  // etwas anderes ist als der Haushaltsplan: Der Plan sagt, wofür das Geld
  // ausgegeben werden SOLL, die Satzung, was die Stadt DÜRFTE.
  | "haushaltssatzung"
  // Die Gebührenbedarfsberechnung — eigener Schlüssel, weil sie ein anderes
  // Dokument ist als der Wirtschaftsplan desselben Betriebs: Der Plan sagt,
  // was der Betrieb vorhat, die Berechnung, was die Leute dafür zahlen.
  | "gebuehren"
  // Die Änderungslisten zum Haushalt — eigener Schlüssel, weil sie weder der
  // Plan noch die Satzung sind: Sie sind das Protokoll dessen, was sich
  // zwischen Entwurf und Beschluss noch bewegt hat, Position für Position.
  | "aenderungsliste"
  | "gesamtabschluss"
  | "einwohner" | "ergebnisrechnung_thh" | "ratsbeschluss"
  // Die Kassensicht aus denselben Jahresabschlüssen. Ein eigener Schlüssel,
  // weil es ein anderer Abschnitt mit einer anderen Abgrenzung ist: Die
  // Ergebnisrechnung bucht, die Finanzrechnung zahlt. Ein gemeinsamer Eintrag
  // lüde dazu ein, ihre Zahlen für dieselben zu halten.
  | "finanzrechnung"
  // Die Vermögensseite aus denselben Jahresabschlüssen (Abschnitt 2.1).
  // Wieder ein eigener Schlüssel, wieder aus demselben Grund: Ergebnis- und
  // Finanzrechnung zählen ein **Jahr**, die Bilanz einen **Stichtag**. Ihre
  // Zahlen sind miteinander nicht verrechenbar.
  | "bilanz"
  // A10: Städtevergleich — die einzigen Quellen des Bereichs, die nicht von
  // der Stadt Oldenburg stammen, sondern vom Land.
  | "lsn_finanzausgleich" | "lsn_realsteuern" | "vergleich_2018"
  // Die dritte Landesquelle, und die einzige, die NICHT vergleicht: Sie steht
  // auf dem Steuer-Steckbrief und beantwortet dort eine Oldenburger Frage —
  // wie viele Betriebe die Gewerbesteuer aufbringen.
  | "lsn_gewerbesteuer"
  // A11: Die Investitionen des Finanzhaushalts.
  | "investitionen"
  | "investitionsprogramm"
  // Und das Ist-Gegenstück aus dem Statistischen Jahrbuch. Bewusst ein
  // eigener Schlüssel und nicht ein zweiter Absatz unter `investitionen`:
  // Plan und Ist sind zwei Dokumente mit zwei Abgrenzungen, und ein
  // gemeinsamer Eintrag im Quellenverzeichnis lüde dazu ein, sie als eine
  // Quelle zu lesen.
  | "gebaut"
  // Die Schuldenzeitreihe — die einzige Quelle des Bereichs aus dem
  // Statistischen Jahrbuch der Stadt.
  | "schulden"
  // Die Kennzahlenübersicht des Rechenschaftsberichts. Eigener Schlüssel und
  // nicht ein Absatz unter `jahresabschluss`: Der Rechenschaftsbericht ist ein
  // ANDERES Dokument als der Abschluss, mit eigener Vorlagennummer — und seine
  // Besonderheit (jeder Bericht druckt fünf Jahre, die Berichte widersprechen
  // sich an sieben Stellen) gehört an die Quelle, nicht an eine Zahl.
  | "kennzahlen"
  // Die lange Ausgabenreihe seit 1972 — die einzige Quelle des Bereichs, die
  // in zwei Veröffentlichungen zugleich steht (Jahrbuch UND Open-Data-Portal)
  // und deshalb einen gemeinsamen Eintrag braucht: Wer nur eine der beiden
  // nennt, verschweigt die Hälfte der Reihe.
  | "ausgabenreihe"
  // Die Zuwendungen an die Stadt — die einzige Quelle des Bereichs, die kein
  // Dokument der Statistik oder der Finanzverwaltung ist, sondern eine Reihe
  // von Ratsbeschlüssen. Ihr eigener Eintrag, weil ihre Grenze eine andere ist
  // als bei allen übrigen: Der Beschluss macht die Summe öffentlich, die
  // Liste der Gebenden bleibt in einer Anlage, die wir nicht haben.
  | "spenden"
  // A12: Der Beteiligungsbericht — die einzige Quelle des Bereichs, die ein
  // eigener Cron von oldenburg.de herunterlädt.
  | "beteiligungsbericht";

export const QUELLEN: Record<QuellenSchluessel, Quelle> = {
  plan: {
    titel: "Beschlossener Haushaltsplan der Stadt Oldenburg",
    // Der Halbsatz „wir lesen maschinell aus und prüfen gegen die Summenzeile"
    // stand hier bis 16.08. Er benennt keine Grenze der Quelle, sondern nur
    // unser Verfahren — genau die Selbstvergewisserung, die DESIGNSPRACHE.md
    // als Anti-Pattern führt. Was eine Quelle NICHT hergibt, steht weiterhin
    // dabei (siehe steuern, teilhaushalt, pruefbericht).
    citation:
      "Übersicht „Ergebnishaushalt“ — ordentliche Erträge und Aufwendungen je Teilhaushalt.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Haushaltsjahre",
    stand: "Haushaltsjahre 2020–2026",
    art: "pdf",
    // 18.08.2026 nachgezogen: Die Unterseite „…/finanzen.html" antwortet mit
    // 404, die Übersicht darüber steht. Geprüft im Tote-Links-Lauf.
    url: "https://www.oldenburg.de/startseite/politik/verwaltung-finanzen.html",
  },
  steuern: {
    titel: "Steuereinnahmen der Stadt Oldenburg seit 1998",
    citation:
      "Datensatz 1104, eine Zeile je Haushaltsjahr, Spalten je Steuerart. " +
      "Ist-Werte (abgerechnet), Gewerbesteuer nach Abzug der Umlage. " +
      "Anders als die Dokumente aus dem Ratsinformationssystem trägt dieser " +
      "Datensatz keine Summe, gegen die wir ihn nachrechnen könnten — wir " +
      "übernehmen ihn, wie die Stadt ihn veröffentlicht.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    standWort: "",
    stand: "1998–2025",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/sites/default/files/1104_Steuereinnahmen_0.csv",
  },
  steuerkraft: {
    titel: "Steuerkraftmesszahlen und Schlüsselzuweisungen seit 1993",
    citation:
      "Datensatz 1106: Steuerkraftmesszahl und Schlüsselzuweisungen (Anordnungssoll) " +
      "je Ausgleichsjahr. Die einzige Stelle im Bereich, an der wir eine Quelle nicht " +
      "unverändert übernehmen: Der Datensatz beschriftet seine Jahrgänge um ein Jahr " +
      "zu früh, wir rücken sie zurecht. Die Beträge des Landesamts für Statistik " +
      "Niedersachsen stehen dort auf den Euro exact — nur ein Jahr später (geprüft für " +
      "die Ausgleichsjahre 2016 bis 2026), und die Haushaltspläne der Stadt weisen " +
      "dieselben Summen als Ist des jeweils späteren Jahres aus. Die Pro-Kopf-Spalten " +
      "des Datensatzes lassen wir deshalb liegen: Sie rechnen gegen die Einwohnerzahl " +
      "des zu frühen Jahres.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    standWort: "Ausgleichsjahre",
    stand: "Ausgleichsjahre 1993–2026",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/sites/default/files/1106_Steuerkraftmesszahlen-Schl%C3%BCsselzuweisung_0.csv",
  },
  // Bis 18.08.2026 stand hier „eine maschinenlesbare Zeitreihe der Vorjahre
  // gibt es noch nicht" und als Stand allein „2025". Beides ist überholt: Die
  // Reihe stand die ganze Zeit im Statistischen Jahrbuch — in Tabelle 1105,
  // auf demselben Blatt wie die Steuereinnahmen, die wir längst lesen.
  hebesaetze: {
    titel: "Realsteuer-Hebesätze der Stadt Oldenburg seit 1980",
    citation:
      "Tabelle 1105, je Änderungsjahr die Hebesätze für Grundsteuer A, Grundsteuer B " +
      "und Gewerbesteuer. Die Tabelle führt nach eigener Fußnote nur die Jahre, in denen " +
      "sich ein Satz geändert hat — neun in 45 Jahren. Zwischen zwei Änderungen gilt der " +
      "Satz unverändert weiter; die Jahre dazwischen fehlen also nicht, sie ändern nichts. " +
      "Was ein Hebesatz für die Zahlenden bedeutet, sagt er allein nicht: Er wirkt auf eine " +
      "Bemessungsgrundlage, die der Bund und das Land festlegen, und die kann sich " +
      "gleichzeitig ändern.",
    herausgeber: "Stadt Oldenburg, Fachdienst Geo und Daten",
    standWort: "Änderungsjahre",
    stand: "Änderungsjahre 1980–2025",
    art: "pdf",
    url: "https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/stadtverwaltung/statistik/statistisches-jahrbuch.html",
  },
  steuerplan: {
    titel: "Steuern und Finanzzuweisungen — Plan neben Ergebnis",
    citation:
      "Tabelle 1103, je Steuerart zwei Spalten pro Jahr: der Ansatz nach dem beschlossenen " +
      "Haushaltsplan und das Rechnungsergebnis desselben Jahres. Wo die Tabelle ihr " +
      "Ergebnis selbst „vorläufig“ nennt, steht das an der Zahl. " +
      "Die Grenze der Quelle: Jede Ausgabe führt nur **drei** Jahrgänge, und die Stadt " +
      "hält keine älteren Ausgaben online. Was wir zeigen können, wächst deshalb ab 2026 " +
      "mit jedem Jahr — es lässt sich aber nicht rückwirkend verlängern.",
    herausgeber: "Stadt Oldenburg, Fachdienst Geo und Daten",
    standWort: "Haushaltsjahre",
    stand: "Haushaltsjahre 2023–2025",
    art: "pdf",
    url: "https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/stadtverwaltung/statistik/statistisches-jahrbuch.html",
  },
  // Beide aus dem eigenen Bestand: Die Dokumente liegen als Anlagen zu
  // Ratsvorlagen im Bürgerinfo — kein externer Download (#500).
  jahresabschluss: {
    titel: "Jahresabschlüsse der Stadt Oldenburg",
    // Ein Satz, ein Gedanke: Die erste Fassung packte Fundstelle, zwei
    // Prüfregeln und die Bezugsgrößen-Frage in Schachtelsätze — lesbar für
    // den, der die Antwort schon kennt (16.08.).
    citation:
      "Die Ergebnisrechnung, einmal für die Kernverwaltung und einmal je Teilhaushalt: " +
      "Plan und Ergebnis nebeneinander, Posten 1–24. Dazu die Erläuterungen der " +
      "Verwaltung zu den erheblichen Abweichungen (Abschnitt 6.3.1). " +
      "Womit ein Jahrgang seinen Plan misst — Ansatz, Ansatz mit Nachtrag oder " +
      "Gesamtermächtigung —, steht auf der Seite dabei. " +
      "Die Dokumente hängen als Anlagen an Ratsvorlagen im Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Jahresabschlüsse",
    stand: "Jahresabschlüsse 2017–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  wirtschaftsplan: {
    titel: "Wirtschaftspläne der Eigenbetriebe und städtischen Gesellschaften",
    citation:
      "Die Ratsvorlage, mit der ein Wirtschaftsplan beschlossen wird — je nach " +
      "Betrieb der Beschlusstext selbst (er nennt Erträge, Aufwendungen und " +
      "Ergebnis) oder der Erfolgsplan der beigefügten Anlage. Bei den " +
      "Gesellschaften ist die einzige nachprüfbare Zahl das beschlossene " +
      "Jahresergebnis; Erträge und Aufwendungen bleiben dann leer, statt " +
      "geschätzt zu werden. " +
      "Diese Zahlen gehören NICHT zum Stadthaushalt und lassen sich nicht mit " +
      "ihm zusammenzählen: Der Eigenbetrieb Gebäudewirtschaft vermietet der " +
      "Stadt ihre eigenen Gebäude, seine Erträge sind zu großen Teilen Aufwand " +
      "des Kernhaushalts. Herausgerechnet wird das erst im Gesamtabschluss.",
    herausgeber: "Stadt Oldenburg, Betriebsleitungen der Eigenbetriebe",
    standWort: "Wirtschaftspläne",
    stand: "Wirtschaftspläne 2019–2026",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  gebuehren: {
    titel: "Gebührenbedarfsberechnungen des Abfallwirtschaftsbetriebs",
    citation:
      "Die Anlagen 1 bis 4 der jährlichen Ratsvorlage " +
      "„Gebührenbedarfsberechnungen“: je eine Rechnung für " +
      "Abfallbehandlungsanlagen, Abfallsammlung und Straßenreinigung. Jede " +
      "nennt die Kalkulationskosten, alles was davon Dritte tragen oder aus " +
      "Vorjahren ausgeglichen wird, und die Menge, durch die geteilt wird. " +
      "Die Gebühr steht doppelt darin: einmal errechnet (drei " +
      "Nachkommastellen) und einmal als gerundeter Vorschlag an den Rat.",
    herausgeber: "Abfallwirtschaftsbetrieb Stadt Oldenburg",
    standWort: "Gebührenbedarfsberechnungen",
    stand: "Gebührenbedarfsberechnungen 2023–2026",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  aenderungsliste: {
    titel: "Änderungslisten zum Haushaltsentwurf",
    citation:
      "Die Anlagen der Haushalts-Vorlage, in denen der Entwurf zwischen " +
      "Einbringung und Beschluss fortgeschrieben wird: die Änderungslisten " +
      "der Verwaltung (Verw. I–III) und die Datei „beschlossene Änderungen“ " +
      "des Finanzausschusses. Jede führt ihre Positionen je Planjahr mit " +
      "Ertrag, Aufwand und Erläuterung und am Ende eine „Zusammenstellung der " +
      "Veränderungen“ — gegen die jede hier gezeigte Positionsliste beim " +
      "Einlesen aufgehen musste. Die Änderungslisten der Fraktionen sind " +
      "in keinem dieser Papiere: Sie wurden als Tischvorlagen verteilt und " +
      "liegen nicht im Ratsinformationssystem; nur ihre Summen stehen in " +
      "den Beschluss-Dateien, mit dem Urheber daneben.",
    herausgeber: "Stadt Oldenburg, Finanzverwaltung",
    standWort: "Änderungslisten",
    stand: "Änderungslisten 2019–2026",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  haushaltssatzung: {
    titel: "Haushaltssatzungen der Stadt Oldenburg",
    citation:
      "Die Haushaltssatzung, die dem Haushaltsplan als Anlage beiliegt — drei " +
      "Seiten je Jahrgang: die Gesamtbeträge des Ergebnis- und des " +
      "Finanzhaushalts (§ 1), die Kreditermächtigung für Investitionen (§ 2), " +
      "die Verpflichtungsermächtigungen (§ 3), der Höchstbetrag für " +
      "Liquiditätskredite (§ 4) und die Hebesätze (§ 5). " +
      "IM RATSINFORMATIONSSYSTEM LIEGEN AUSSCHLIESSLICH VERWALTUNGSENTWÜRFE — " +
      "sie tragen auf dem Deckblatt „Verwaltungsentwurf“ und als Sitzungsdatum " +
      "„xx.xx.JJJJ“. Die beschlossene Fassung erscheint im Amtsblatt der Stadt, " +
      "nicht hier. Was der Rat aus dem Entwurf gemacht hat, steht in den " +
      "Änderungslisten und Beschlüssen zum Haushalt.",
    herausgeber: "Stadt Oldenburg, Fachdienst Verwaltung und Finanzen",
    standWort: "Haushaltssatzungen",
    stand: "Haushaltssatzungen 2019–2026 (Verwaltungsentwürfe)",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  ergebnishaushalt: {
    titel: "Gesamtergebnishaushalte der Stadt Oldenburg (Planjahre)",
    citation:
      "Anlage 005 des Haushaltsplans: die Erträge und Aufwendungen des kommenden " +
      "Jahres nach denselben Posten 1–24, die auch der Jahresabschluss führt — für " +
      "Jahre, die noch keinen Abschluss haben. " +
      "Von den fünf Spalten, die das Dokument „Ansatz“ nennt, ist genau eine der " +
      "Haushaltsansatz; die übrigen sind mittelfristige Finanzplanung nach § 8 NKomVG " +
      "und werden hier nicht gezeigt. " +
      "Es ist der Entwurf der Verwaltung: Die Anlage hängt an der Einbringungs-Vorlage, " +
      "nicht am Beschluss. " +
      "Die Dokumente hängen als Anlagen an Ratsvorlagen im Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Haushaltspläne",
    stand: "Haushaltspläne 2019–2026, Stand der Einbringung",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  teilhaushalt: {
    titel: "Teilhaushaltspläne der Stadt Oldenburg (Produktebene)",
    citation:
      "Teilergebnishaushalte je Teilhaushalt (THH 01–13): was einzelne Aufgaben kosten, " +
      "mit Produktnummer und zuständigem Amt. Die Abdeckung ist unvollständig — " +
      "nicht jeder Teilhaushalt liegt für jedes Jahr auslesbar vor.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Haushaltsjahre",
    stand: "Haushaltsjahre 2018–2025",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  stellenplan: {
    titel: "Stellenpläne der Stadt Oldenburg",
    citation:
      "Die Anlage zum Haushaltsplan, in der jede Stelle steht: Teil A für " +
      "Beamtinnen und Beamte, Teil B für Tarifbeschäftigte. Je Zeile eine " +
      "Amtsbezeichnung mit Besoldungs- oder Entgeltgruppe, die Zahl der " +
      "Stellen im Haushaltsjahr — und daneben, wie viele davon am Stichtag " +
      "des Vorjahres besetzt waren und wie viele nicht. " +
      "Es ist der Verwaltungsentwurf, nicht der Beschluss des Rates. " +
      "Die Dokumente hängen als Anlagen an Ratsvorlagen im " +
      "Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Amt für Personal- und Verwaltungsmanagement",
    standWort: "Haushaltsjahre",
    // Der Zusatz bleibt von Hand: Welcher Jahrgang seinen Teil B nicht
    // hergibt, steht nicht in der Tabelle, sondern hängt am Textextrakt des
    // PDFs (2026 liefert dort Glyphen statt Buchstaben, s.
    // `council/stellenplan.py`).
    standZusatz: "(2026 ohne Teil B)",
    stand: "Haushaltsjahre 2023–2026 (2026 ohne Teil B)",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  pruefbericht: {
    titel: "Schlussberichte des Rechnungsprüfungsamtes der Stadt Oldenburg",
    citation:
      "Die Randmarken des Berichts (B, WB, H, K) und der Absatz, der jeweils dahinter steht — " +
      "mit der Textziffer und der Seite, unter der er dort geführt wird. " +
      "Der Jahrgang 2024 fehlt, weil sein PDF keine Zeichenzuordnung mitbringt — der " +
      "Textextrakt besteht aus Glyphen-Nummern, und eine zweite Kopie gibt es nicht. " +
      "Die Berichte hängen als Anlagen an Ratsvorlagen im Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Rechnungsprüfungsamt",
    standWort: "Jahresabschlüsse",
    stand: "Jahresabschlüsse 2017–2023",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  gesamtabschluss: {
    titel: "Konsolidierte Gesamtabschlüsse der Stadt Oldenburg",
    citation:
      "Der Bericht, mit dem das Rechnungsprüfungsamt den Gesamtabschluss nach § 128 NKomVG " +
      "prüft — die einzige Rechnung, in der Kernverwaltung, Eigenbetriebe und Beteiligungen " +
      "zusammen stehen. Wir lesen zwei Tabellen daraus: die Gesamtergebnisrechnung " +
      "(Abschnitt 3.2) und die Aufstellung, wer wie viel beiträgt (Abschnitt 4.1.1). " +
      "Ein Jahrgang kommt nur herein, wenn drei Rechenproben des Dokuments aufgehen: " +
      "Erträge − Aufwendungen = ordentliches Ergebnis, dasselbe für die außerordentlichen " +
      "Posten, und beides zusammen = Gesamtjahresergebnis. " +
      "Die Trägeraufstellung zusätzlich nur, wenn ihre Zeilen die ausgewiesene Summe ergeben " +
      "und diese Summe zur Gesamtergebnisrechnung passt. " +
      "Der Jahrgang 2013 fehlt, weil sein PDF die Tabellenseiten ohne Textebene mitbringt; " +
      "beim Jahrgang 2018 fehlt die Aufwendungsseite der Trägeraufstellung, weil ihre " +
      "Konsolidierungszeile nicht zur eigenen Summe passt — der Bericht des Folgejahres " +
      "führt dort einen anderen Wert. " +
      "Die Berichte hängen als Anlagen an Ratsvorlagen im Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Rechnungsprüfungsamt",
    standWort: "Gesamtabschlüsse",
    stand: "Gesamtabschlüsse 2014–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  ruecklage: {
    titel: "Überschussrücklage aus den Jahresabschlüssen",
    citation:
      "Bilanzposition 1.2.1 „Rücklagen aus Überschüssen des ordentlichen " +
      "Ergebnisses“ plus das am Stichtag noch separat ausgewiesene " +
      "Jahresergebnis. Der genehmigte Vorbericht 2026 bestätigt diese Lesart " +
      "für 2024 als rund 195,1 Mio. € „unter Berücksichtigung des Ergebnisses“.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Jahresabschlüsse",
    stand: "Jahresabschlüsse 2017–2024; bestätigt im genehmigten Haushalt 2026",
    art: "pdf",
    url: "https://www.oldenburg.de/startseite/politik/verwaltung-finanzen/finanzen/haushalt-2026.html",
  },
  // Ab hier auf Vorrat angelegt (A1, 08/2026), damit die Folgearbeiten am
  // Haushalts-Bereich diese Datei nicht gleichzeitig anfassen müssen. Wer
  // später doch einen Schlüssel braucht: nur ANHÄNGEN, mit Kommentarmarke,
  // niemals bestehende Einträge umsortieren oder umformatieren.
  einwohner: {
    titel: "Einwohnerzahlen der Stadt Oldenburg je Haushaltsjahr",
    citation:
      "Datensatz 1102, Einwohner-Spalte — eine Zeile je Haushaltsjahr, Stichtag " +
      "jeweils der 31.12. des Vorjahres. Bezugsgröße aller Pro-Kopf-Angaben; das " +
      "jüngste Jahr mit Einwohnerzahl steht deshalb an der Zahl dabei. Die " +
      "Aufwendungs-Spalte derselben Datei ist eine eigene Quelle mit eigenem " +
      "Eintrag („Ausgaben der Stadt Oldenburg seit 1972“); die Einwohnerzahl " +
      "hier trägt keine Rechenprobe, gegen die sie sich prüfen ließe.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    standWort: "Haushaltsjahre",
    stand: "Haushaltsjahre 2010–2025",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/sites/default/files/1102-Ordentliche_Aufwendungen_des_Ergebnishaushaltes_seit_2010.csv",
  },
  ergebnisrechnung_thh: {
    titel: "Ergebnisrechnung je Teilhaushalt (Jahresabschlüsse)",
    citation:
      "Dieselben Jahresabschlüsse wie oben, aber die Ebene darunter: die " +
      "Ergebnisrechnung eines einzelnen Teilhaushalts, Posten 1–24 mit Plan und " +
      "Ergebnis nebeneinander. Hier steht, was ein Bereich tatsächlich eingenommen " +
      "und ausgegeben hat — Steuern, Zuwendungen, Entgelte, Personal, Transfers. " +
      "Anders als der Plan reicht diese Ebene nicht bis ins laufende Jahr.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Jahresabschlüsse",
    stand: "Jahresabschlüsse 2017–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  finanzrechnung: {
    titel: "Finanzrechnung der Kernverwaltung (Jahresabschlüsse)",
    citation:
      "Abschnitt 4.1 derselben Jahresabschlüsse: die Ein- und Auszahlungen des " +
      "Jahres, getrennt nach laufender Verwaltung, Investitionen und " +
      "Finanzierung, mit Ansatz und Ergebnis nebeneinander. Diese Tabelle " +
      "zählt Geld, das geflossen ist — nicht Erträge und Aufwendungen. Sie " +
      "sagt deshalb nichts über den Werteverzehr: Abschreibungen kommen darin " +
      "nicht vor, Kreditaufnahme und Tilgung dagegen schon. Die Zeilen zum " +
      "Kassenbestand dürfen laut Dokument fehlen und fehlen in einzelnen " +
      "Jahrgängen auch.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Jahresabschlüsse",
    stand: "Jahresabschlüsse 2017–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  bilanz: {
    titel: "Bilanz der Stadt Oldenburg (Jahresabschlüsse)",
    citation:
      "Abschnitt 2.1 derselben Jahresabschlüsse, im amtlichen Muster nach " +
      "NKomVG: was die Stadt zum 31. Dezember besitzt und wem es zusteht. " +
      "Anders als Ergebnis- und Finanzrechnung zählt diese Tabelle kein Jahr, " +
      "sondern einen Stichtag — ihre Beträge sind mit denen der übrigen " +
      "Seiten nicht verrechenbar. Zwei Zeilen heißen fast gleich: Position " +
      "3.1 „Pensionsrückstellungen und ähnliche Verpflichtungen“ schließt die " +
      "Beihilfe ein, Position 3.1.1 „Pensionsrückstellungen“ nicht; die " +
      "beiden ältesten Stichtage führen die Aufschlüsselung noch nicht. Die " +
      "Erläuterungen stammen aus Abschnitt 6.2 desselben Dokuments, die " +
      "Anlagenübersicht aus Abschnitt 8.1 („Anlagen zum Anhang“).",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Bilanzstichtage",
    stand: "Bilanzstichtage 2016–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  kennzahlen: {
    titel: "Kennzahlenübersicht der Rechenschaftsberichte",
    citation:
      "Die Anlage „Kennzahlenübersicht und Berechnungsmethoden“ am Ende jedes " +
      "Rechenschaftsberichts: dreizehn Zahlen, auf die die Stadt ihren " +
      "Jahresabschluss selbst eindampft — und darunter, im Wortlaut, wie sie " +
      "jede davon rechnet. Zwei Eigenheiten muss man kennen. Erstens druckt " +
      "jeder Bericht fünf Jahre, nicht eins; die sechs Berichte decken so " +
      "2015–2024 ab, und die mittleren Jahrgänge stehen mehrfach da. Zweitens " +
      "stimmen diese Mehrfachnennungen nicht immer überein: An sieben Stellen " +
      "hat ein späterer Bericht eine Zahl stillschweigend korrigiert. Wir " +
      "zeigen den jüngsten Stand und schreiben die Korrektur an. Die Berichte " +
      "2017 und 2018 führen dieselben Kennzahlen nur als Diagramm ohne " +
      "Tabelle — ihre Jahrgänge stehen im Bericht 2019.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    standWort: "Rechenschaftsberichte",
    stand: "Rechenschaftsberichte 2019–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  ratsbeschluss: {
    titel: "Sitzungen, Vorlagen und Beschlüsse des Rates (Bürgerinformationssystem)",
    citation:
      "Der amtliche Weg einer Vorlage: Sitzungstermin, Tagesordnungspunkt, " +
      "Beratungsfolge und Beschluss, wie das Ratsinformationssystem der Stadt sie " +
      "führt. Wir übernehmen nur öffentlich einsehbare Sitzungen und verlinken " +
      "jede Station auf ihren Eintrag dort. Was das System nicht kennt — etwa die " +
      "Tagesordnung künftiger Sitzungen —, steht auch bei uns nicht.",
    herausgeber: "Stadt Oldenburg, Ratsinformationssystem",
    stand: "Sitzungen seit Januar 2018",
    art: "web",
    url: "https://buergerinfo.oldenburg.de",
  },
  // A10: Der Städtevergleich (/haushalt/vergleich). Die einzigen Quellen des
  // Bereichs, die nicht die Stadt Oldenburg herausgibt — und genau das ist
  // ihr Wert: eine Stelle, eine Abgrenzung, alle Gemeinden.
  lsn_finanzausgleich: {
    titel: "Kommunaler Finanzausgleich in Niedersachsen — Vergleichstabellen",
    citation:
      "Blatt „ST_KR_MESS_VGL“: die Steuerkraftmesszahl jeder niedersächsischen " +
      "Gemeinde, zwei Ausgleichsjahre nebeneinander, dazu die Einwohnerzahl. " +
      "Berechnet mit Nivellierungshebesätzen (§ 11 NFAG, amtlich " +
      "„Steuerkraftzahlen“) — also mit fiktiven statt den tatsächlichen Sätzen, " +
      "damit die Zahl die Steuerbasis misst und nicht die Hebesatzpolitik. " +
      "Landeseinheitlich sind sie nicht: Gemeinden unter 100.000 Einwohner*innen " +
      "rechnen mit anderen Sätzen als die darüber. " +
      "Die Steuerkraft je Einwohner*in ist unsere eigene Division; das Landesamt " +
      "weist sie nicht aus. " +
      "Blatt „9a“: die Zuweisungen an die acht kreisfreien Städte, aufgeteilt in " +
      "Schlüsselzuweisungen für Gemeindeaufgaben, für Kreisaufgaben und " +
      "Zuweisungen für Aufgaben des übertragenen Wirkungskreises, abzüglich der " +
      "Finanzausgleichsumlage. Die dritte Komponente steht in keiner städtischen " +
      "Veröffentlichung; der Open-Data-Datensatz 1106 führt nur die ersten beiden.",
    herausgeber: "Landesamt für Statistik Niedersachsen",
    stand: "Ausgleichsjahr 2026 (endgültig, Stand 26.03.2026)",
    lizenz: "Vervielfältigung mit Quellennachweis gestattet",
    art: "csv",
    url: "https://www.statistik.niedersachsen.de/kommunaler-finanzausgleich/kommunaler-finanzausgleich-in-niedersachsen-tabellen-214575.html",
  },
  lsn_realsteuern: {
    titel: "Realsteuervergleich Niedersachsen",
    citation:
      "Blatt 2.1: Grundbeträge, Hebesätze und Ist-Aufkommen der Grundsteuern A und B " +
      "sowie der Gewerbesteuer je kreisfreier Stadt. Blatt 5.1: die " +
      "Steuereinnahmekraft je Einwohner*in über drei Jahre. " +
      "Grundlage ist die vierteljährliche Kassenstatistik — dieselbe Erhebung für " +
      "alle Gemeinden, keine Selbstauskunft der Städte. " +
      "Die Hebesätze der Grundsteuer sind ab 2025 nicht mit früheren vergleichbar — " +
      "die Grundsteuerreform hat die Messbeträge geändert, nicht die Belastung.",
    herausgeber: "Landesamt für Statistik Niedersachsen",
    stand: "Berichtsjahr 2025 (korrigierte Fassung vom 30.07.2026)",
    lizenz: "Vervielfältigung mit Quellennachweis gestattet",
    art: "csv",
    // 18.08.2026 nachgezogen: Das Landesamt hat den Pfad um eine Ebene
    // ergänzt („…/finanzen_steuern_personal/…"); die alte Adresse gibt 404.
    url: "https://www.statistik.niedersachsen.de/startseite/themen/finanzen_steuern_personal/steuern_in_niedersachsen/realsteuervergleich_in_niedersachsen/",
  },
  lsn_gewerbesteuer: {
    titel: "Gewerbesteuerstatistik Niedersachsen",
    citation:
      "Blatt 6.1: je kreisfreier Stadt die Zahl der Betriebe und " +
      "Betriebsstätten, wie viele davon einen positiven Steuermessbetrag " +
      "haben, und die Summe dieser Messbeträge — aufgeteilt in reine " +
      "Festsetzungen und Zerlegungen. Blatt 6.2: dieselben Zahlen je " +
      "Gemeinde, dazu der Hebesatz. " +
      "Grundlage sind die Steuermessbescheide der Finanzämter, also die " +
      "VERANLAGUNG eines Erhebungsjahres — nicht das Geld, das in diesem Jahr " +
      "in der Stadtkasse ankam. " +
      "Größenklassen des Gewerbeertrags, aus denen sich die Konzentration " +
      "rechnen ließe, veröffentlicht die Statistik nur für das Land und den " +
      "Bund, nicht je Gemeinde. " +
      "Was ein einzelnes Unternehmen zahlt, steht hier so wenig wie sonstwo: " +
      "Wo ein Zahler eine Gemeinde dominiert, sperrt das Landesamt sogar den " +
      "Summenbetrag.",
    herausgeber: "Landesamt für Statistik Niedersachsen",
    // Die Ausgabe, nicht die Datenspanne — und hier ist der Abstand die
    // wichtigste Angabe überhaupt: Der Bericht zum Erhebungsjahr 2021
    // erschien im März 2026.
    stand: "Erhebungsjahr 2021 (Statistischer Bericht L IV 13, erschienen im März 2026)",
    lizenz: "Vervielfältigung mit Quellennachweis gestattet",
    art: "csv",
    url: "https://www.statistik.niedersachsen.de/themen/gewerbesteuer-niedersachsen/gewerbesteuer-in-niedersachsen-statistische-berichte-179300.html",
  },
  vergleich_2018: {
    titel: "Personalentwicklung seit dem Jahr 2000 — Antrag der FDP-Fraktion und Antwort der Verwaltung",
    citation:
      "Ratsvorlage 18/0911 mit zwei Anlagen: dem Antrag der FDP-Fraktion vom " +
      "13.11.2018 und der Antwort der Verwaltung. Die Antwort enthält eine Tabelle " +
      "der Personalintensitätsquote über sieben Städte und neun Jahrgänge, die " +
      "Feststellung, dass diese Quoten keinen aussagefähigen Vergleich zulassen, " +
      "und die Aufstellung, was in welcher Stadt im Kernhaushalt steckt. " +
      "Zitiert wird sie auf dieser Seite wörtlich. " +
      "Das Dokument hängt als Anlage an der Vorlage im Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Amt für Personal- und Verwaltungsmanagement",
    stand: "26.11.2018",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=17170",
  },
  gebaut: {
    titel:
      "Statistisches Jahrbuch der Stadt Oldenburg, Tabellen 1107 und 1107-1 — " +
      "Investitionen der Stadt",
    citation:
      "Kapitel 11 „Verwaltung und Finanzen“: die Rechnungsergebnisse, also was " +
      "im Haushaltsjahr tatsächlich abgeflossen ist, je Jahr aufgeteilt nach " +
      "Auszahlungsart und mit der Summe daneben. " +
      "Zwei Tabellen in einer Datei, und der Schnitt zwischen ihnen ist die " +
      "wichtigste Angabe: 1107 führt die Jahre 2003 bis 2009 als „Ausgaben für " +
      "eigene Investitionen“ nach kameralem Rechnungswesen, 1107-1 die Jahre ab " +
      "2010 als „Auszahlungen für Investitionstätigkeiten“ nach doppischem — die " +
      "Fußnote nennt die Umstellung zum 1. Januar 2010 als Grund. " +
      "1107-1 begrenzt sich außerdem ausdrücklich auf die Kernverwaltung: Die " +
      "Eigenbetriebe und die städtischen Gesellschaften sind nicht enthalten. " +
      "Für 2019 fehlt der Jahrgang — dort ergeben die Auszahlungsarten in der " +
      "Tabelle selbst nicht die Summe daneben.",
    herausgeber: "Stadt Oldenburg, Fachdienst Geo und Daten (Zahlen: Fachdienst Finanzen)",
    standWort: "",
    standZusatz: "(Ausgabe vom 08.07.2026)",
    stand: "2003–2025 (Ausgabe vom 08.07.2026)",
    art: "pdf",
    url:
      "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/" +
      "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1107-1107-1-2025-AZ.pdf",
  },
  schulden: {
    titel: "Statistisches Jahrbuch der Stadt Oldenburg, Tabelle 1108 — Stand der Verschuldung",
    citation:
      "Kapitel 11 „Verwaltung und Finanzen“: eine Zeile je Jahr seit 1995, " +
      "aufgeteilt nach Kreditmarktmitteln, öffentlichen Sondermitteln, Schulden " +
      "bei Gebietskörperschaften und Schulden der Eigenbetriebe, dazu die Summe " +
      "und der Betrag je Einwohner*in. " +
      "Gezählt wird die Stadt als Rechtsträger — Kernhaushalt und Eigenbetriebe, " +
      "ohne die rechtlich selbstständigen Beteiligungen; die Kliniken fallen " +
      "deshalb ab 1999 aus der Reihe, als sie eine eigene Rechtsform bekamen. " +
      "Der Betrag je Einwohner*in ist die Angabe der Stadt, nicht unsere Division; " +
      "die Einwohnerzahl bezieht sich auf den 31. Dezember des Vorjahres.",
    herausgeber: "Stadt Oldenburg, Fachdienst Geo und Daten (Zahlen: Fachdienst Finanzen)",
    standWort: "",
    standZusatz: "(Ausgabe vom 08.07.2026)",
    stand: "1995–2025 (Ausgabe vom 08.07.2026)",
    art: "pdf",
    url:
      "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/" +
      "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1108-2025-AZ.pdf",
  },
  ausgabenreihe: {
    titel:
      "Ausgaben der Stadt Oldenburg seit 1972 — Datensatz 1102 " +
      "(Statistisches Jahrbuch und Open-Data-Portal)",
    citation:
      "Ein Betrag je Haushaltsjahr, daneben die Einwohnerzahl zum 31.12. des " +
      "Vorjahres und der Betrag je Einwohner*in. " +
      "Die Reihe zerfällt in zwei Teile, und der Schnitt ist die wichtigste " +
      "Angabe: Bis 2009 sind es die „Ausgaben des Verwaltungshaushalts“ — das " +
      "Anordnungssoll, also was zur Zahlung angeordnet wurde; ab 2010 die " +
      "„Ordentlichen Aufwendungen des Ergebnishaushalts“ aus der " +
      "Gesamtergebnisrechnung, also was das Jahr verbraucht hat. " +
      "Die Fußnote der Tabelle nennt den Grund: die Umstellung auf das Neue " +
      "Kommunale Rechnungswesen zum 1. Januar 2010. Über diesen Schnitt " +
      "hinweg lässt sich vergleichen, aber nicht rechnen. " +
      "Ab 2010 zählt die Reihe den Kernhaushalt und die nicht rechtsfähigen " +
      "Stiftungen zusammen; die Ergebnisrechnung auf den übrigen Seiten " +
      "dieses Bereichs zählt nur den Kernhaushalt und liegt deshalb um die " +
      "Aufwendungen der Stiftungen darunter. " +
      "Investitionen stehen in keinem der beiden Teile — sie laufen in einer " +
      "eigenen Rechnung. " +
      "Die Jahre bis 2001 führt nur das Open-Data-Portal; das PDF des " +
      "Jahrbuchs beginnt 2002. " +
      "Für 2021 nennen die beiden Veröffentlichungen verschiedene Beträge; " +
      "welchen wir zeigen und warum, steht bei der Grafik.",
    herausgeber:
      "Stadt Oldenburg, Fachdienst Geo und Daten und Open-Data-Portal " +
      "(Zahlen: Fachdienst Finanzen)",
    standWort: "Haushaltsjahre",
    standZusatz: "(Jahrbuch-Ausgabe vom 08.07.2026)",
    stand: "Haushaltsjahre 1972–2025 (Jahrbuch-Ausgabe vom 08.07.2026)",
    lizenz: "dl-de/by-2.0",
    art: "pdf",
    url:
      "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/" +
      "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1102-2025-AZ.pdf",
  },
  spenden: {
    titel:
      "Ratsvorlagen „Annahme von Zuwendungen“ — Beschlüsse des Rates und des " +
      "Verwaltungsausschusses",
    citation:
      "Acht- bis zwölfmal im Jahr beschließen Rat oder Verwaltungsausschuss, " +
      "welche angebotenen Zuwendungen die Stadt annimmt. Der Beschluss nennt " +
      "eine Summe („in Höhe von insgesamt … EUR laut anliegender Liste“); " +
      "dieselbe Summe steht in der Vorlage ein zweites Mal, im Abschnitt zu " +
      "den finanziellen Auswirkungen, dort oft zerlegt in Geldzuwendungen und " +
      "Sachspenden. " +
      "Wer gespendet hat und wofür, steht ausschließlich in der Anlage " +
      "„Zuwendungsliste“ — die ist nicht Teil dessen, was wir einlesen, und " +
      "wir zeigen deshalb die Summe und nicht die Gebenden. " +
      "Die Reihe zählt, was beschlossen wurde, nicht was gebucht ist: Sie ist " +
      "nicht mit einer Position der Ergebnisrechnung gleichzusetzen, die " +
      "Zuwendungen weder getrennt ausweist noch nach demselben Stichtag " +
      "abgrenzt.",
    herausgeber: "Stadt Oldenburg, Amt für Controlling und Finanzen (Ratsvorlagen)",
    standWort: "Sitzungsjahre",
    stand: "Sitzungsjahre 2018–2026",
    // „web": Die Quelle ist keine Datei, sondern eine Reihe von Vorlagen im
    // Bürgerinformationssystem — jede Zeile verlinkt ihre eigene über den
    // Beleg-Chip.
    art: "web",
    url: "https://buergerinfo.oldenburg.de/vo040.asp",
  },
  // A11: Die Investitionen des Finanzhaushalts (/haushalt/investitionen). Die
  // einzige CSV des Open-Data-Portals in diesem Verzeichnis, die eine
  // Rechenprobe mitbringt — bei den drei anderen steht ausdrücklich, dass sie
  // keine haben.
  investitionen: {
    titel: "Finanzhaushalt der Stadt Oldenburg — Investitionen je Teilhaushalt",
    citation:
      "Datensatz 1101, Tabellenblatt „Finanzhaushalt“: je Teilhaushalt eine Zeile " +
      "mit den Ein- und Auszahlungen aus Investitionstätigkeit, darunter die " +
      "Summenzeile „Finanzhaushalt Gesamtinvestitionen“. " +
      "Die Zeile „Gesamtbetrag des Finanzhaushaltes“ zeigen wir als Bezugsgröße " +
      "daneben — sie zählt die laufende Verwaltungstätigkeit mit und ist von " +
      "dieser Probe nicht gedeckt. " +
      "Für welches Jahr eine Datei gilt, steht nicht in ihr, sondern in ihrem " +
      "Dateinamen. " +
      "Es sind Planzahlen: Was am Jahresende wirklich gebaut wurde, steht nicht " +
      "darin, und einzelne Vorhaben nennt der Datensatz gar nicht.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    standWort: "Haushaltsjahre",
    stand: "Haushaltsjahre 2022–2025",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/dataset/haushaltsplan-stadt-oldenburg-2025",
  },
  // A12: Das Investitionsprogramm (/haushalt/investitionen, Block „Die
  // einzelnen Vorhaben"). Die Ebene unter A11 — und aus einer ganz anderen
  // Quelle: nicht dem Open-Data-Portal, sondern dem Haushaltsplan selbst.
  investitionsprogramm: {
    titel: "Investitionsprogramm zum Haushaltsplan (Anlage 004)",
    citation:
      "Je Teilhaushalt ein Abschnitt „Investitionen und " +
      "Investitionsförderungsmaßnahmen“ mit einer Zeile je Vorhaben, davor das " +
      "„Gesamtinvestitionsprogramm“ mit den Investitionssummen je Teilhaushalt. " +
      "Übernommen wird die Spalte „Gesamtinvestitionssumme“ — die Kosten eines " +
      "Vorhabens über alle Jahre. " +
      "Die Jahresraten daneben (Ansatz je Planjahr, Verpflichtungsermächtigungen) " +
      "übernehmen wir nicht: Im Textextrakt des PDFs fallen leere Zellen " +
      "ersatzlos weg, eine Zuordnung zu den Spalten wäre geraten. " +
      "Es sind Planzahlen aus dem Entwurf der Verwaltung, Stand der Einbringung; " +
      "was der Rat in den Beratungen ändert, steht nicht darin. " +
      "Sanierung und Neubau von Schulgebäuden liegen beim Eigenbetrieb " +
      "Gebäudewirtschaft und Hochbau und stehen deshalb nicht in diesem " +
      "Programm.",
    herausgeber: "Stadt Oldenburg, Ratsinformationssystem",
    standWort: "Haushaltsjahre",
    stand: "Haushaltsjahre 2019–2026",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de/getfile.php?id=297440&type=do",
  },
  beteiligungsbericht: {
    titel: "Beteiligungsbericht der Stadt Oldenburg (§ 151 NKomVG)",
    citation:
      "Je Gesellschaft ein Abschnitt mit acht Teilen: Gegenstand, " +
      "Beteiligungsverhältnisse, Aufsichtsorgane, eigene Beteiligungen, " +
      "Geschäftsverlauf, Bilanz und Kennzahlen, öffentlicher Zweck, " +
      "Auswirkungen auf den städtischen Haushalt. " +
      "Gelesen werden die Berichte ab dem Berichtsjahr 2022 — davor ist das " +
      "Dokument anders aufgebaut (die Bilanz steht zweispaltig, es gibt keine " +
      "Kennzahlen-Tabellen). Die Kennzahlen reichen trotzdem bis 2017 zurück, " +
      "weil jeder Bericht vier bis fünf Jahre nebeneinander führt. " +
      "Der Bericht erscheint rund zwei Jahre nach dem Geschäftsjahr; für " +
      "einzelne Gesellschaften stehen ältere Zahlen darin als für die übrigen. " +
      "Die beschreibenden Abschnitte sind Text der Verwaltung und tragen " +
      "keine Rechenprobe.",
    herausgeber: "Stadt Oldenburg, Amt für Controlling und Finanzen",
    stand: "Berichtsjahre 2022–2024, Kennzahlen ab 2017",
    art: "pdf",
    url: "https://www.oldenburg.de/startseite/politik/verwaltung-finanzen/finanzen/beteiligungsbericht.html",
  },
};
