// Quellenverzeichnis des Haushalts-Bereichs — eine Quelle, ein Schlüssel.
//
// Warum als Konstante statt aus der API: Die Fundstelle („Übersicht
// Ergebnishaushalt", „Tabelle 1104") ist eine redaktionelle Angabe, die
// niemand aus den Daten ableiten kann. Sie hier zu pflegen macht sie
// überprüfbar; die DB liefert nur die URL des jeweiligen Jahrgangs.
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
  | "jahresabschluss" | "teilhaushalt";

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
      "Ist-Werte (abgerechnet), Gewerbesteuer nach Abzug der Umlage.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    stand: "1998–2025",
    lizenz: "dl-de/by-2.0",
    art: "csv",
    url: "https://opendata.oldenburg.de/sites/default/files/1104_Steuereinnahmen_0.csv",
  },
  steuerkraft: {
    titel: "Steuerkraftmesszahlen und Schlüsselzuweisungen seit 1992",
    fundstelle:
      "Datensatz 1106, je Ausgleichsjahr: Steuerkraftmesszahl und Schlüsselzuweisungen " +
      "(Anordnungssoll), jeweils absolut und je Einwohner.",
    herausgeber: "Stadt Oldenburg, Open-Data-Portal",
    stand: "1992–2025",
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
    fundstelle:
      "Ergebnisrechnung der Kernverwaltung — Ansatz und Ergebnis nebeneinander, Posten 1–24. " +
      "Wir übernehmen nur Zeilen, bei denen die im Dokument ausgewiesene Probe aufgeht " +
      "(Abweichung = Ergebnis − Ansatz). Als Anlagen zu Ratsvorlagen im Bürgerinformationssystem.",
    herausgeber: "Stadt Oldenburg, Controlling und Finanzen",
    stand: "Jahresabschlüsse 2019 und 2021–2024",
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
};
