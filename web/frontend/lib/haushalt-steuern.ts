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
//  2. „Gebühren und Beiträge" ist keine Steuer — in den Open-Data-Steuerreihen
//     steht sie deshalb nicht, und `datenArt` bleibt dort `null`. Bis zum
//     24.08.2026 hieß das auf der Seite „keiner der offenen Datensätze führt
//     diese Einnahme", und der Steckbrief blieb leer. Die Zahl lag da: Der
//     Jahresabschluss führt sie als Posten 5 der Ergebnisrechnung
//     („öffentlich-rechtliche Entgelte"), mit Ansatz und Ergebnis je Jahr und
//     aufgeschlüsselt nach Teilhaushalt. Dafür ist `ergebnisPosten` da — der
//     zweite Weg an die Zahl, für Einnahmearten, die keine Steuer sind.

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
  /** Die Postennummer der **Ergebnisrechnung**, wo `datenArt` nichts hergibt.
   *
   *  Der Jahresabschluss gliedert seine Erträge in 24 Posten; Nummer 5 sind
   *  die öffentlich-rechtlichen Entgelte, also die Gebühren. Diese Quelle kann
   *  mehr als die Steuerreihe: Sie führt Ansatz **und** Ergebnis je Jahr und
   *  schlüsselt beides nach Teilhaushalt auf.
   *
   *  Ihre Grenze steht im Titel des Dokuments und gehört an jede Anzeige: Es
   *  ist der Abschluss **der Kernverwaltung**. Was ein Eigenbetrieb einnimmt —
   *  allen voran die Abfallgebühren des AWB — steht hier nicht (`grenze`). */
  ergebnisPosten?: number;
  /** Was diese Zahl NICHT umfasst, in einem Satz. Pflicht, wo `ergebnisPosten`
   *  steht: Eine Summe ohne ihre Abgrenzung liest sich als Gesamtsumme. */
  grenze?: string;
  /** Der Pro-Kopf-Satz, wo „aus der ${titel}" kein Deutsch ergibt
   *  („aus der Gebühren und Beiträge"). */
  proKopfWas?: string;
  titel: string;
  /** Ein Satz, der die Steuer erklärt, ohne ein Fachwort zu benutzen. */
  kurz: string;
  spielraum: Spielraum;
  /** Kurzform für die Landkarte („Der Rat setzt den Hebesatz: 439 %"). */
  stellschraube: string;
  stufen: SteuerStufe[];
  /** Rechenbeispiel, wo es eines gibt — konkret statt abstrakt. */
  beispiel?: { rechnung: string; hinweis: string };
  /* Hier stand bis 19.08.2026 `hebesatz?: number` — der aktuelle Satz als
     Zahl im Quelltext (439 bzw. 539). Sie war nicht bloß Deko: Der Steckbrief
     rechnete den Überschlag „was brächte ein Punkt mehr?" damit und druckte
     sie als Rechenweg aus. Seit `council_hebesaetze` die Reihe seit 1980
     führt, kommt der Satz aus den Daten, und zwar der, der im Jahr des
     Aufkommens galt. Ob der Rat für eine Steuer überhaupt einen Hebesatz
     beschließt, sagt jetzt `hebesatzArten` — dasselbe Feld, das auch auf die
     Daten zeigt, statt einer zweiten Wahrheit daneben.

     WAS BLEIBT: In den Erklärtexten unten stehen die Sätze weiter als Zahl
     ausgeschrieben — „Der Hebesatz: 439 %", das Rechenbeispiel, die beiden
     Grundsteuer-Sätze und Lottis Erklärung zum Sprung 445 → 539. Das ist
     Absicht: Ein Beispiel, das mit `${satz}` rechnet, wäre kein Beispiel mehr,
     sondern eine zweite Rechnung neben dem Überschlag. Sie stehen aber im
     Bild neben der Treppe, die die echte Reihe zeichnet — ein Widerspruch
     fiele beim Lesen auf, anders als bei der stillen Division vorher.
     WER EINEN HEBESATZ NACHZIEHT, fasst genau diese Stellen an: `stufen[].titel`
     und `.text`, `beispiel.rechnung` sowie `lotti.text`. Sonst nichts. */
  /** Welche Reihen aus `council_hebesaetze` zu diesem Steckbrief gehören —
   *  die erste ist die Haupt-Treppe, eine zweite läuft dünn daneben.
   *
   *  Zwei Einträge gibt es nur bei der Grundsteuer, und dort gehören sie
   *  zusammen: Der Rat beschließt A und B in derselben Satzung, sie stehen in
   *  derselben Tabellenzeile, und beide sind Prozentpunkte — also dieselbe
   *  Achse. Die Reihenfolge ist nicht beliebig: B trifft Wohn- und
   *  Geschäftsgrundstücke und damit fast alle, A die Land- und
   *  Forstwirtschaft. B steht deshalb vorn. */
  hebesatzArten?: string[];
  /** Gesetzt heißt: Der Überschlag „was brächte ein Punkt mehr?" lässt sich
   *  hier NICHT rechnen, und das ist der Grund.
   *
   *  Bei der Grundsteuer war er bis 16.08.2026 trotzdem zu sehen: Der Betrag
   *  aus dem Open-Data-Satz umfasst A und B zusammen, der Hebesatz daneben
   *  gilt nur für B — die Division mischte also zwei Steuern. Das Labor
   *  verweigert genau diese Zahl seit jeher mit derselben Begründung
   *  (components/haushalt/labor.tsx); zwei Seiten dürfen nicht verschieden
   *  antworten, wenn die Datenlage dieselbe ist. */
  punktUnmoeglich?: string;
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
    hebesatzArten: ["Gewerbesteuer"],
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
    // Die Kicker-Zeile über einer Lotti-Karte ist überall im Haushalts-Bereich
    // ihre Aussage („Warum Kürzen allein nicht reicht"), nicht ihr Absender.
    // Drei Steckbriefe trugen bis 16.08. das generische „Lotti erklärt's
    // einfach" — eine Überschrift, die nichts überschreibt.
    lotti: {
      titel: "Wer an welcher Schraube dreht",
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
      "sie meist auch Mieter*innen mit. Sie fällt jedes Jahr an, unabhängig davon, " +
      "ob jemand Gewinn macht.",
    spielraum: "frei",
    stellschraube: "Der Rat setzt zwei Hebesätze",
    hebesatzArten: ["Grundsteuer B", "Grundsteuer A"],
    punktUnmoeglich:
      "Was ein Hebesatzpunkt bringt, lässt sich hier nicht überschlagen: Der offene "
      + "Datensatz führt Grundsteuer A und B in einer Spalte zusammen, die Hebesätze "
      + "gelten aber getrennt. Wir schätzen die Aufteilung nicht — sobald wir sie "
      + "belegen können, steht die Zahl hier.",
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
      titel: "Warum der Rat hier nichts beschließen kann",
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
      titel: "Ein kleiner Teil von jedem Einkauf",
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
    datenArt: null, // In keiner der Open-Data-Steuerreihen enthalten …
    // … dafür im Jahresabschluss, als Posten 5 der Ergebnisrechnung.
    ergebnisPosten: 5,
    // Der Jahresabschluss heißt selbst „der Kernverwaltung und ihrer nicht
    // rechtsfähigen Stiftungen" — Eigenbetriebe zählt er nicht mit. Nachgesehen
    // statt geschlossen: Die Abfallgebühren waren 2024 zusammen 19,4 Mio. €,
    // die größte Teilhaushalts-Zeile dieses Postens in acht Jahrgängen liegt
    // bei 7,5 Mio. € — sie können dort nirgends stecken.
    grenze:
      "Die Müllgebühr steckt hier nicht drin. Sie läuft über den " +
      "Abfallwirtschaftsbetrieb, und der ist ein Eigenbetrieb — der " +
      "Jahresabschluss der Kernverwaltung zählt ihn nicht mit.",
    proKopfWas: "an Gebühren und Beiträgen",
    titel: "Gebühren und Beiträge",
    kurz:
      "Wer eine Leistung der Stadt nutzt, zahlt dafür — vom Kita-Beitrag bis zur " +
      "Friedhofsgebühr. Die Sätze beschließt der Rat; höher als die Kosten dürfen " +
      "sie nicht sein.",
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
