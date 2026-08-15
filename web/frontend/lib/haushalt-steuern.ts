// Steuer-Steckbriefe (Design H-10/H-11/H-12) — die redaktionelle Schicht.
//
// Die Beträge kommen aus der Datenbank (Ist-Werte des Open-Data-Portals);
// hier steht nur, was keine Datenquelle hergibt: wer welche Stellschraube
// bedient, worauf sie beruht und wie man das jemandem erklärt, der noch nie
// eine Haushaltssatzung gesehen hat.
//
// GEGENCHECK gegen die Daten (16.08.2026), zwei Korrekturen am Entwurf:
//  1. Das Open-Data-CSV führt **Grundsteuer A und B in einer Spalte**. Der
//     Entwurf sah zwei Karten mit eigenen Beträgen vor — die gibt es nicht.
//     Also eine Karte „Grundsteuer A+B" mit beiden Hebesätzen.
//  2. „Gebühren und Beiträge" ist keine Steuer und steht in keinem der
//     Datensätze. Die Karte bleibt ohne Betrag, ehrlich gekennzeichnet.

export type Spielraum = "frei" | "begrenzt" | "keiner";

export type SteuerStufe = {
  /** Wer entscheidet: „Bundestag", „Land", „Rat Oldenburg". */
  wer: string;
  titel: string;
  text: string;
  /** true = hier entscheidet der Rat (Signal-Rahmen im Design). */
  rat?: boolean;
};

export type SteuerArt = {
  slug: string;
  /** Genau die Schreibweise aus `council_steuern.art`; null = kein Datensatz. */
  datenArt: string | null;
  titel: string;
  /** Ein Satz, der die Steuer erklärt, ohne ein Fachwort zu benutzen. */
  kurz: string;
  spielraum: Spielraum;
  /** Kurzform für die Landkarte („Der Rat setzt den Hebesatz: 439 %"). */
  stellschraube: string;
  stufen: SteuerStufe[];
  /** Rechenbeispiel, wo es eines gibt — konkret statt abstrakt. */
  beispiel?: { rechnung: string; hinweis: string };
  /** Hebesatz in Prozentpunkten, falls der Rat einen beschließt. */
  hebesatz?: number;
  /** Lotti-Erklärung an der schwersten Stelle der Seite. */
  lotti: { titel: string; text: string };
};

export const STEUERARTEN: SteuerArt[] = [
  {
    slug: "gewerbesteuer",
    datenArt: "Gewerbesteuer (-umlage)",
    titel: "Gewerbesteuer",
    kurz:
      "Jedes Unternehmen in Oldenburg zahlt sie auf seinen Gewinn — vom Handwerksbetrieb " +
      "bis zum Konzern. Freiberufler und Landwirte sind ausgenommen. Sie ist die größte " +
      "eigene Einnahme der Stadt.",
    spielraum: "frei",
    stellschraube: "Der Rat setzt den Hebesatz",
    hebesatz: 439,
    stufen: [
      {
        wer: "Bundestag",
        titel: "Was als Gewinn zählt",
        text: "Das Gewerbesteuergesetz legt fest, wer zahlt und was abgezogen werden darf. Daran kann die Stadt nichts ändern.",
      },
      {
        wer: "Bundestag",
        titel: "Die Messzahl: 3,5 %",
        text: "Das Finanzamt rechnet den Gewinn mit 3,5 % in einen Messbetrag um — bundesweit gleich.",
      },
      {
        wer: "Rat Oldenburg",
        titel: "Der Hebesatz: 439 %",
        text: "Der Messbetrag wird mit dem Hebesatz multipliziert. Diese eine Zahl beschließt der Rat — jedes Jahr neu mit dem Haushalt.",
        rat: true,
      },
    ],
    beispiel: {
      rechnung: "100.000 € Gewinn × 3,5 % = 3.500 € × 439 % = 15.365 € Steuer",
      hinweis:
        "Vereinfacht: Der Freibetrag für Einzelunternehmen und Personengesellschaften ist " +
        "nicht eingerechnet, ebenso wenig die Umlage an Bund und Land.",
    },
    lotti: {
      titel: "Lotti erklärt's einfach",
      text:
        "Stell dir die Steuer wie ein Rezept vor: Der Bund bestimmt die Zutaten und die " +
        "Grundmenge, die Stadt dreht am Ende nur an einem Regler — dem Hebesatz. Dreht der " +
        "Rat ihn hoch, zahlen Unternehmen mehr; dreht er ihn runter, weniger.",
    },
  },
  {
    slug: "grundsteuer",
    datenArt: "Grundsteuer A+B",
    titel: "Grundsteuer",
    kurz:
      "Wer ein Grundstück oder ein Haus besitzt, zahlt sie — über die Nebenkosten tragen " +
      "sie meist auch Mieterinnen und Mieter mit. Sie fällt jedes Jahr an, unabhängig davon, " +
      "ob jemand Gewinn macht.",
    spielraum: "frei",
    stellschraube: "Der Rat setzt zwei Hebesätze",
    hebesatz: 539,
    stufen: [
      {
        wer: "Bundestag & Land",
        titel: "Was das Grundstück wert ist",
        text: "Nach der Grundsteuerreform berechnen die Finanzämter für jedes Grundstück einen neuen Wert. Die Stadt rechnet daran nicht mit.",
      },
      {
        wer: "Bundestag",
        titel: "Die Steuermesszahl",
        text: "Aus dem Wert wird nach bundesweit gleichen Regeln ein Messbetrag — je nach Art des Grundstücks unterschiedlich.",
      },
      {
        wer: "Rat Oldenburg",
        titel: "Die Hebesätze: 539 % und 500 %",
        text:
          "539 % für Wohn- und Geschäftsgrundstücke (Grundsteuer B), 500 % für Land- und " +
          "Forstwirtschaft (Grundsteuer A). Beide beschließt der Rat.",
        rat: true,
      },
    ],
    lotti: {
      titel: "Warum ist der Satz plötzlich so hoch?",
      text:
        "Bis 2024 lag der Hebesatz für Grundsteuer B bei 445 %, seit der Reform bei 539 %. " +
        "Das heißt nicht automatisch, dass alle mehr zahlen: Weil die Finanzämter gleichzeitig " +
        "alle Grundstückswerte neu berechnet haben, wurde der Hebesatz angepasst. Für einzelne " +
        "Grundstücke kann die Steuer trotzdem steigen oder sinken.",
    },
  },
  {
    slug: "einkommensteueranteil",
    datenArt: "Einkommensteueranteil",
    titel: "Anteil an der Einkommensteuer",
    kurz:
      "Von der Lohn- und Einkommensteuer, die Menschen in Oldenburg zahlen, bekommt die " +
      "Stadt einen festen Anteil ab. Sie stellt dafür keine eigenen Bescheide aus.",
    spielraum: "keiner",
    stellschraube: "Fester Anteil — nichts zu beschließen",
    stufen: [
      {
        wer: "Bundestag",
        titel: "Die Steuer selbst",
        text: "Wie viel Einkommensteuer jemand zahlt, steht im Einkommensteuergesetz.",
      },
      {
        wer: "Bundestag",
        titel: "Der Gemeindeanteil",
        text: "Das Gemeindefinanzreformgesetz legt fest, welcher Anteil an die Kommunen geht und nach welchem Schlüssel er verteilt wird.",
      },
      {
        wer: "Rat Oldenburg",
        titel: "Nichts.",
        text: "Der Rat hat hier keine Stellschraube. Steigt die Summe, liegt es an den Einkommen in der Stadt — nicht an einem Beschluss.",
      },
    ],
    lotti: {
      titel: "Lotti erklärt's einfach",
      text:
        "Dieses Geld kommt wie ein Abo aufs Konto: Die Höhe hängt davon ab, wie viel die " +
        "Menschen in Oldenburg verdienen. Der Rat kann daran nichts drehen — er kann nur " +
        "einplanen, was voraussichtlich kommt.",
    },
  },
  {
    slug: "umsatzsteueranteil",
    datenArt: "Gemeindeanteil an der Umsatzsteuer",
    titel: "Anteil an der Umsatzsteuer",
    kurz:
      "Ein kleiner Teil der bundesweiten Umsatzsteuer wird an die Städte verteilt — nach " +
      "einem Schlüssel, in den unter anderem die örtliche Wirtschaft einfließt.",
    spielraum: "keiner",
    stellschraube: "Bundesweit verteilt, nach Schlüssel",
    stufen: [
      { wer: "Bundestag", titel: "Die Steuer selbst", text: "Höhe und Regeln der Umsatzsteuer sind Bundesrecht." },
      { wer: "Bundestag", titel: "Der Verteilschlüssel", text: "Er bestimmt, welcher Anteil bei welcher Kommune landet." },
      { wer: "Rat Oldenburg", titel: "Nichts.", text: "Keine kommunale Stellschraube." },
    ],
    lotti: {
      titel: "Lotti erklärt's einfach",
      text:
        "Von jedem Einkauf fließt Umsatzsteuer an den Staat. Ein sehr kleiner Teil davon " +
        "wandert weiter an die Städte — Oldenburg bekommt seinen Anteil automatisch.",
    },
  },
  {
    slug: "kleine-steuern",
    datenArt: "Vergnügungssteuer",
    titel: "Kleine örtliche Steuern",
    kurz:
      "Vergnügungssteuer auf Spielautomaten, Hundesteuer, früher auch die Getränkesteuer. " +
      "Der Rat beschließt sie selbst — sie fallen im Gesamthaushalt aber kaum ins Gewicht.",
    spielraum: "frei",
    stellschraube: "Der Rat beschließt eigene Satzungen",
    stufen: [
      {
        wer: "Land",
        titel: "Der Rahmen",
        text: "Das Kommunalabgabengesetz erlaubt Städten, bestimmte örtliche Steuern zu erheben.",
      },
      {
        wer: "Rat Oldenburg",
        titel: "Ob und wie viel",
        text: "Der Rat beschließt die Satzung und die Sätze — bei der Hundesteuer etwa den Betrag je Hund.",
        rat: true,
      },
    ],
    lotti: {
      titel: "Klein, aber sichtbar",
      text:
        "Diese Steuern bringen wenig Geld, sind aber die einzigen, bei denen der Rat wirklich " +
        "alles selbst festlegt. Deshalb tauchen sie in Debatten öfter auf, als ihr Anteil " +
        "vermuten lässt.",
    },
  },
  {
    slug: "schluesselzuweisungen",
    datenArt: null, // eigene Tabelle: council_steuerkraft
    titel: "Schlüsselzuweisungen vom Land",
    kurz:
      "Niedersachsen gibt Geld an seine Kommunen weiter — nach einer Formel, nicht auf " +
      "Antrag. Wer selbst mehr Steuern einnimmt, bekommt rechnerisch weniger.",
    spielraum: "keiner",
    stellschraube: "Formel des Landes — kein Ratsbeschluss",
    stufen: [
      {
        wer: "Land",
        titel: "Die Formel und der Topf",
        text: "Der Landtag beschließt das Finanzausgleichsgesetz und wie viel Geld insgesamt verteilt wird.",
      },
      {
        wer: "Land",
        titel: "Die Berechnung je Stadt",
        text: "Steuerkraft gegen Bedarf — daraus ergibt sich die Summe für Oldenburg.",
      },
      {
        wer: "Rat Oldenburg",
        titel: "Nichts.",
        text: "Der Rat kann die Höhe nicht beschließen — nur indirekt beeinflussen, weil eigene Steuereinnahmen in die Formel eingehen.",
      },
    ],
    lotti: {
      titel: "Warum das Land überhaupt zahlt",
      text:
        "Städte haben sehr unterschiedliche Einnahmen, müssen aber ähnliche Aufgaben " +
        "erfüllen. Der Finanzausgleich gleicht das aus: Wer weniger eigene Steuerkraft hat, " +
        "bekommt mehr aus dem Landestopf.",
    },
  },
  {
    slug: "gebuehren",
    datenArt: null, // In keinem der Open-Data-Sätze enthalten.
    titel: "Gebühren und Beiträge",
    kurz:
      "Kita-Beiträge, Müllgebühren, Friedhofsgebühren: Wer eine Leistung nutzt, zahlt " +
      "dafür. Die Sätze beschließt der Rat — höher als die Kosten dürfen sie nicht sein.",
    spielraum: "begrenzt",
    stellschraube: "Der Rat beschließt die Sätze, gedeckelt durch die Kosten",
    stufen: [
      {
        wer: "Land",
        titel: "Die Grenze",
        text: "Das Kommunalabgabengesetz erlaubt höchstens kostendeckende Gebühren — Gewinn ist nicht vorgesehen.",
      },
      {
        wer: "Rat Oldenburg",
        titel: "Die Sätze",
        text: "Innerhalb dieser Grenze beschließt der Rat die einzelnen Gebührensatzungen.",
        rat: true,
      },
    ],
    lotti: {
      titel: "Warum Gebühren nicht beliebig steigen",
      text:
        "Eine Gebühr ist kein Preis, sondern eine Umlage der echten Kosten. Deshalb kann die " +
        "Stadt sie nicht erhöhen, um ein Loch im Haushalt zu stopfen — sie darf nur so viel " +
        "verlangen, wie die Leistung sie kostet.",
    },
  },
];

export function steuerartNachSlug(slug: string): SteuerArt | undefined {
  return STEUERARTEN.find((s) => s.slug === slug);
}

export const SPIELRAUM_LABEL: Record<Spielraum, string> = {
  frei: "frei gestaltbar",
  begrenzt: "begrenzt",
  keiner: "kein Einfluss",
};
