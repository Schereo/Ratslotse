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
// Beim Nachziehen eines neuen Haushaltsjahres bitte `stand` aktualisieren.

export type Quelle = {
  titel: string;
  /** Wo genau im Dokument die Zahlen stehen — der Punkt, an dem man nachschlägt. */
  fundstelle: string;
  herausgeber: string;
  /** Datenstand, nicht Abrufdatum: Was die Zahl beschreibt, nicht wann wir sie holten. */
  stand: string;
  lizenz?: string;
  url?: string;
  art: "pdf" | "csv" | "web";
};

/** Die Schlüssel explizit statt per Inferenz: So sind die Werte einheitlich
 *  als `Quelle` getypt (inklusive optionaler Felder wie `lizenz`), und die
 *  Union bleibt trotzdem eng genug, um Tippfehler beim Aufruf zu fangen. */
export type QuellenSchluessel =
  | "plan" | "steuern" | "steuerkraft" | "hebesaetze" | "ruecklage"
  | "jahresabschluss" | "teilhaushalt" | "pruefbericht" | "gesamtabschluss"
  | "einwohner" | "ergebnisrechnung_thh" | "ratsbeschluss"
  // A10: Städtevergleich — die einzigen Quellen des Bereichs, die nicht von
  // der Stadt Oldenburg stammen, sondern vom Land.
  | "lsn_finanzausgleich" | "lsn_realsteuern" | "vergleich_2018"
  // A11: Die Investitionen des Finanzhaushalts.
  | "investitionen";

export const QUELLEN: Record<QuellenSchluessel, Quelle> = {
  plan: {
    titel: "Beschlossener Haushaltsplan der Stadt Oldenburg",
    fundstelle:
      "Übersicht „Ergebnishaushalt“ — ordentliche Erträge und Aufwendungen je Teilhaushalt. " +
      "Wir lesen die Tabellenseite maschinell aus und prüfen sie gegen die Summenzeile.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    stand: "Haushaltsjahre 2020–2026",
    art: "pdf",
    url: "https://www.oldenburg.de/startseite/politik/verwaltung-finanzen/finanzen.html",
  },
  steuern: {
    titel: "Steuereinnahmen der Stadt Oldenburg seit 1998",
    fundstelle:
      "Datensatz 1104, eine Zeile je Haushaltsjahr, Spalten je Steuerart. " +
      "Ist-Werte (abgerechnet), Gewerbesteuer nach Abzug der Umlage. " +
      "Anders als die Dokumente aus dem Ratsinformationssystem trägt dieser " +
      "Datensatz keine Summe, gegen die wir ihn nachrechnen könnten — wir " +
      "übernehmen ihn, wie die Stadt ihn veröffentlicht.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    stand: "1998–2025",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/sites/default/files/1104_Steuereinnahmen_0.csv",
  },
  steuerkraft: {
    titel: "Steuerkraftmesszahlen und Schlüsselzuweisungen seit 1993",
    fundstelle:
      "Datensatz 1106: Steuerkraftmesszahl und Schlüsselzuweisungen (Anordnungssoll) " +
      "je Ausgleichsjahr. Die einzige Stelle im Bereich, an der wir eine Quelle nicht " +
      "unverändert übernehmen: Der Datensatz beschriftet seine Jahrgänge um ein Jahr " +
      "zu früh, wir rücken sie zurecht. Die Beträge des Landesamts für Statistik " +
      "Niedersachsen stehen dort auf den Euro genau — nur ein Jahr später (geprüft für " +
      "die Ausgleichsjahre 2016 bis 2026), und die Haushaltspläne der Stadt weisen " +
      "dieselben Summen als Ist des jeweils späteren Jahres aus. Die Pro-Kopf-Spalten " +
      "des Datensatzes lassen wir deshalb liegen: Sie rechnen gegen die Einwohnerzahl " +
      "des zu frühen Jahres.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    stand: "Ausgleichsjahre 1993–2026",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/sites/default/files/1106_Steuerkraftmesszahlen-Schl%C3%BCsselzuweisung_0.csv",
  },
  hebesaetze: {
    titel: "Hebesätze der Stadt Oldenburg",
    fundstelle:
      "Gewerbesteuer 439 %, Grundsteuer B 539 %, Grundsteuer A 500 % — beschlossen mit der " +
      "Haushaltssatzung. Von uns aus der städtischen Bekanntmachung übernommen; eine " +
      "maschinenlesbare Zeitreihe der Vorjahre gibt es noch nicht.",
    herausgeber: "Stadt Oldenburg",
    stand: "2025",
    art: "web",
    url: "https://www.oldenburg.de/startseite/rathaus/informiert-bleiben/aktuelles/neue-hebesaetze.html",
  },
  // Beide aus dem eigenen Bestand: Die Dokumente liegen als Anlagen zu
  // Ratsvorlagen im Bürgerinfo — kein externer Download (#500).
  jahresabschluss: {
    titel: "Jahresabschlüsse der Stadt Oldenburg",
    // Ein Satz, ein Gedanke: Die erste Fassung packte Fundstelle, zwei
    // Prüfregeln und die Bezugsgrößen-Frage in Schachtelsätze — lesbar für
    // den, der die Antwort schon kennt (16.08.).
    fundstelle:
      "Die Ergebnisrechnung, einmal für die Kernverwaltung und einmal je Teilhaushalt: " +
      "Plan und Ergebnis nebeneinander, Posten 1–24. Dazu die Erläuterungen der " +
      "Verwaltung zu den erheblichen Abweichungen (Abschnitt 6.3.1). " +
      "Wir übernehmen eine Zeile nur, wenn die Probe des Dokuments aufgeht: " +
      "Abweichung = Ergebnis − Plan. Die Teilhaushalts-Ebene zusätzlich nur, wenn ihre " +
      "Summe die Gesamtrechnung ergibt. " +
      "Womit ein Jahrgang seinen Plan misst — Ansatz, Ansatz mit Nachtrag oder " +
      "Gesamtermächtigung —, steht auf der Seite dabei. " +
      "Die Dokumente hängen als Anlagen an Ratsvorlagen im Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    stand: "Jahresabschlüsse 2017–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  teilhaushalt: {
    titel: "Teilhaushaltspläne der Stadt Oldenburg (Produktebene)",
    fundstelle:
      "Teilergebnishaushalte je Teilhaushalt (THH 01–13): was einzelne Aufgaben kosten, " +
      "mit Produktnummer und zuständigem Amt. Übernommen werden nur Produktzeilen, bei denen " +
      "Erträge − Aufwendungen = ordentliches Ergebnis aufgeht. Die Abdeckung ist unvollständig — " +
      "nicht jeder Teilhaushalt liegt für jedes Jahr auslesbar vor.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    stand: "Haushaltsjahre 2018–2023",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  pruefbericht: {
    titel: "Schlussberichte des Rechnungsprüfungsamtes der Stadt Oldenburg",
    fundstelle:
      "Die Randmarken des Berichts (B, WB, H, K) und der Absatz, der jeweils dahinter steht — " +
      "mit der Textziffer und der Seite, unter der er dort geführt wird. " +
      "Übernommen wird nur, was der Bericht selbst erklärt: Die Marke muss in seiner Legende " +
      "stehen, die Textziffer in seinem Inhaltsverzeichnis. " +
      "Der Jahrgang 2024 fehlt, weil sein PDF keine Zeichenzuordnung mitbringt — der " +
      "Textextrakt besteht aus Glyphen-Nummern, und eine zweite Kopie gibt es nicht. " +
      "Wir lesen dann lieber nichts als etwas Geratenes. " +
      "Die Berichte hängen als Anlagen an Ratsvorlagen im Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Rechnungsprüfungsamt",
    stand: "Jahresabschlüsse 2017–2023",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  gesamtabschluss: {
    titel: "Konsolidierte Gesamtabschlüsse der Stadt Oldenburg",
    fundstelle:
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
    stand: "Gesamtabschlüsse 2014–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  ruecklage: {
    titel: "Rücklage und Genehmigung des Haushalts 2026",
    fundstelle:
      "Rund 195 Mio. € Rücklage, aus der das geplante Defizit gedeckt wird; " +
      "Genehmigung durch das Nds. Ministerium für Inneres und Sport.",
    herausgeber: "Stadt Oldenburg",
    stand: "April 2026",
    art: "web",
    url: "https://www.oldenburg.de/startseite/politik/verwaltung-finanzen/finanzen/haushalt-2026.html",
  },
  // Ab hier auf Vorrat angelegt (A1, 08/2026), damit die Folgearbeiten am
  // Haushalts-Bereich diese Datei nicht gleichzeitig anfassen müssen. Wer
  // später doch einen Schlüssel braucht: nur ANHÄNGEN, mit Kommentarmarke,
  // niemals bestehende Einträge umsortieren oder umformatieren.
  einwohner: {
    titel: "Einwohnerzahlen der Stadt Oldenburg je Haushaltsjahr",
    fundstelle:
      "Datensatz 1102, Einwohner-Spalte — eine Zeile je Haushaltsjahr, Stichtag " +
      "jeweils der 31.12. des Vorjahres. Bezugsgröße aller Pro-Kopf-Angaben; das " +
      "jüngste Jahr mit Einwohnerzahl steht deshalb an der Zahl dabei. Die " +
      "Aufwendungs-Spalten desselben Datensatzes bleiben bewusst ungenutzt: Sie " +
      "weichen vom beschlossenen Plan ab, ohne als Ist oder Nachtrag " +
      "gekennzeichnet zu sein. Auch dieser Datensatz trägt keine Summe, gegen die " +
      "wir ihn nachrechnen könnten.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    stand: "Haushaltsjahre 2010–2025",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/sites/default/files/1102-Ordentliche_Aufwendungen_des_Ergebnishaushaltes_seit_2010.csv",
  },
  ergebnisrechnung_thh: {
    titel: "Ergebnisrechnung je Teilhaushalt (Jahresabschlüsse)",
    fundstelle:
      "Dieselben Jahresabschlüsse wie oben, aber die Ebene darunter: die " +
      "Ergebnisrechnung eines einzelnen Teilhaushalts, Posten 1–24 mit Plan und " +
      "Ergebnis nebeneinander. Hier steht, was ein Bereich tatsächlich eingenommen " +
      "und ausgegeben hat — Steuern, Zuwendungen, Entgelte, Personal, Transfers. " +
      "Übernommen nur, wenn die Probe des Dokuments aufgeht und die Summe der " +
      "Teilhaushalte die Gesamtrechnung ergibt. Anders als der Plan reicht diese " +
      "Ebene nicht bis ins laufende Jahr.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    stand: "Jahresabschlüsse 2017–2024",
    art: "pdf",
    url: "https://buergerinfo.oldenburg.de",
  },
  ratsbeschluss: {
    titel: "Sitzungen, Vorlagen und Beschlüsse des Rates (Bürgerinformationssystem)",
    fundstelle:
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
    fundstelle:
      "Blatt „ST_KR_MESS_VGL“: die Steuerkraftmesszahl jeder niedersächsischen " +
      "Gemeinde, zwei Ausgleichsjahre nebeneinander, dazu die Einwohnerzahl. " +
      "Berechnet nach § 11 NFAG mit Nivellierungshebesätzen — also für alle " +
      "Gemeinden mit denselben fiktiven Hebesätzen, damit die Zahl die Steuerbasis " +
      "misst und nicht die Hebesatzpolitik. " +
      "Wir übernehmen einen Jahrgang nur, wenn er sich mit dem vorherigen deckt: " +
      "Das ältere der beiden Jahre muss die Hauptspalte der Vorjahresausgabe " +
      "wiederholen, und zwar für jede der 403 Gemeinden. " +
      "Die Steuerkraft je Einwohner*in ist unsere eigene Division; das Landesamt " +
      "weist sie nicht aus.",
    herausgeber: "Landesamt für Statistik Niedersachsen",
    stand: "Ausgleichsjahr 2026 (endgültig, Stand 26.03.2026)",
    lizenz: "Vervielfältigung mit Quellennachweis gestattet",
    art: "csv",
    url: "https://www.statistik.niedersachsen.de/kommunaler-finanzausgleich/kommunaler-finanzausgleich-in-niedersachsen-tabellen-214575.html",
  },
  lsn_realsteuern: {
    titel: "Realsteuervergleich Niedersachsen",
    fundstelle:
      "Blatt 2.1: Grundbeträge, Hebesätze und Ist-Aufkommen der Grundsteuern A und B " +
      "sowie der Gewerbesteuer je kreisfreier Stadt. Blatt 5.1: die " +
      "Steuereinnahmekraft je Einwohner*in über drei Jahre. " +
      "Grundlage ist die vierteljährliche Kassenstatistik — dieselbe Erhebung für " +
      "alle Gemeinden, keine Selbstauskunft der Städte. " +
      "Übernommen wird eine Stadt nur, wenn die Rechnung des Dokuments aufgeht: " +
      "Grundbetrag mal Hebesatz ergibt das ausgewiesene Aufkommen, und der " +
      "Dreijahresdurchschnitt ist das Mittel der drei Jahre daneben. " +
      "Die Hebesätze der Grundsteuer sind ab 2025 nicht mit früheren vergleichbar — " +
      "die Grundsteuerreform hat die Messbeträge geändert, nicht die Belastung.",
    herausgeber: "Landesamt für Statistik Niedersachsen",
    stand: "Berichtsjahr 2025 (korrigierte Fassung vom 30.07.2026)",
    lizenz: "Vervielfältigung mit Quellennachweis gestattet",
    art: "csv",
    url: "https://www.statistik.niedersachsen.de/startseite/themen/steuern_in_niedersachsen/realsteuervergleich_in_niedersachsen/realsteuervergleich-in-niedersachsen-197957.html",
  },
  vergleich_2018: {
    titel: "Personalentwicklung seit dem Jahr 2000 — Antrag der FDP-Fraktion und Antwort der Verwaltung",
    fundstelle:
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
  // A11: Die Investitionen des Finanzhaushalts (/haushalt/investitionen). Die
  // einzige CSV des Open-Data-Portals in diesem Verzeichnis, die eine
  // Rechenprobe mitbringt — bei den drei anderen steht ausdrücklich, dass sie
  // keine haben.
  investitionen: {
    titel: "Finanzhaushalt der Stadt Oldenburg — Investitionen je Teilhaushalt",
    fundstelle:
      "Datensatz 1101, Tabellenblatt „Finanzhaushalt“: je Teilhaushalt eine Zeile " +
      "mit den Ein- und Auszahlungen aus Investitionstätigkeit, darunter die " +
      "Summenzeile „Finanzhaushalt Gesamtinvestitionen“. " +
      "Übernommen wird ein Jahrgang nur, wenn die Rechnung der Datei aufgeht: Die " +
      "Teilhaushalte müssen die Summenzeile ergeben, in beiden Spalten. " +
      "Die Zeile „Gesamtbetrag des Finanzhaushaltes“ zeigen wir als Bezugsgröße " +
      "daneben — sie zählt die laufende Verwaltungstätigkeit mit und ist von " +
      "dieser Probe nicht gedeckt. " +
      "Für welches Jahr eine Datei gilt, steht nicht in ihr, sondern in ihrem " +
      "Dateinamen. " +
      "Es sind Planzahlen: Was am Jahresende wirklich gebaut wurde, steht nicht " +
      "darin, und einzelne Vorhaben nennt der Datensatz gar nicht.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    stand: "Haushaltsjahre 2022–2025",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/dataset/haushaltsplan-stadt-oldenburg-2025",
  },
};
