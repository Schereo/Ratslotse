// Die Gesetze, auf denen die Einnahmen der Stadt beruhen — mit dem Weg zum
// amtlichen Text.
//
// WARUM DAS EIN EIGENES REGISTER IST UND NICHT IN `haushalt-quellen.ts` STEHT
//
// Der Beleg-Apparat des Haushalts-Bereichs beantwortet eine Frage: „Woher
// kommt diese ZAHL?" Jede Ziffer im Verzeichnis zeigt auf ein Papier, aus dem
// wir gelesen haben. Ein Gesetz ist nichts davon — aus ihm haben wir keine
// Zahl gelesen, es sagt, warum es die Zahl überhaupt gibt. Beides in eine
// Nummernfolge zu werfen hieße, das Verzeichnis um eine zweite Bedeutung zu
// erweitern, die niemand ansagt (die Regel dazu: Belege zählen Papiere, nicht
// Kategorien).
//
// Deshalb: dasselbe Fähnchen, dieselbe Bedienung, ein anderes Zeichen. Der
// Gesetz-Chip trägt eine Waage statt einer Ziffer und steht außerhalb der
// Nummerierung; wer ihn antippt, bekommt zuerst einen Satz in normaler Sprache
// und darunter den Link zum Volltext.
//
// ZWEI HERAUSGEBER, UND DER UNTERSCHIED IST KEINE FORMSACHE
//
// Bundesrecht steht auf gesetze-im-internet.de (Bundesamt für Justiz),
// Landesrecht im niedersächsischen Vorschrifteninformationssystem VORIS. Die
// Trennung steht als `ebene` an jedem Eintrag und wird im Fähnchen angezeigt,
// weil sie die Anschlussfrage beantwortet: Wer könnte das ändern? Beim
// Hebesatz ist die Antwort „der Rat", beim Steuergeheimnis „der Bundestag" —
// und dazwischen liegt der ganze Unterschied zwischen einer politischen und
// einer rechtlichen Grenze.
//
// DIE GRUNDSTEUER IST DER FALL, IN DEM DAS WICHTIG WURDE
//
// Niedersachsen hat bei der Grundsteuerreform die Öffnungsklausel genutzt und
// ein eigenes Gesetz beschlossen (NGrStG, Flächen-Lage-Modell). Wer hier auf
// die Bundesnormen verlinkte — § 15 und § 25 des Grundsteuergesetzes —, zeigte
// auf Vorschriften, nach denen in Oldenburg **nicht** gerechnet wird. Genau
// deshalb wird hier je Steuerart nachgesehen und nicht das nächstliegende
// Bundesgesetz genommen.
//
// PFLEGE: Jede URL ist beim Eintragen abgerufen worden (24 von 24 mit HTTP
// 200, 26.08.2026). Die VORIS-Adressen tragen eine UUID statt eines sprechenden
// Pfades — sie lassen sich nicht raten; wer einen Paragrafen ergänzt, sucht ihn
// dort und kopiert die Adresse.

export type Gesetzesebene = "Bund" | "Land";

export type Gesetz = {
  /** Die Fundstelle, wie sie im Text steht: „§ 30 AO". Ohne Paragrafenzeichen,
   *  wo ein ganzes Gesetz gemeint ist. */
  kurz: string;
  /** Die amtliche Überschrift der Vorschrift — oder der Gesetzestitel. */
  titel: string;
  /** Das Gesetz ausgeschrieben, für alle, denen „GewStG" nichts sagt. */
  gesetz: string;
  ebene: Gesetzesebene;
  /** Was drinsteht — ein bis zwei Sätze, ohne Juristendeutsch. Keine
   *  Zusammenfassung des ganzen Gesetzes, sondern der Teil, wegen dem die
   *  Vorschrift an dieser Stelle der Seite steht. */
  zusammenfassung: string;
  /** Der amtliche Volltext. Bund: gesetze-im-internet.de (Bundesamt für
   *  Justiz). Land: VORIS. */
  url: string;
};

export type GesetzSchluessel =
  // Gewerbesteuer
  | "gewstg" | "gewstg-11" | "gewstg-16" | "gewstg-29" | "ao-30"
  // Grundsteuer — Landesrecht, siehe Kopf
  | "ngrstg" | "ngrstg-6" | "ngrstg-7"
  // Anteile an den Gemeinschaftsteuern
  | "estg" | "gemfinrefg-1" | "ustg" | "gemfinrefg-5a"
  // Örtliche Steuern, Gebühren, Finanzausgleich
  | "nkag" | "nfag";

export const GESETZE: Record<GesetzSchluessel, Gesetz> = {
  gewstg: {
    kurz: "Gewerbesteuergesetz",
    titel: "Gewerbesteuergesetz",
    gesetz: "Gewerbesteuergesetz (GewStG)",
    ebene: "Bund",
    zusammenfassung:
      "Regelt bundesweit einheitlich, wer Gewerbesteuer zahlt und wie der " +
      "Gewinn dafür umgerechnet wird — mit Hinzurechnungen (etwa für Mieten " +
      "und Zinsen) und Kürzungen. Freiberufler*innen und Land- und " +
      "Forstwirtschaft fallen nicht darunter.",
    url: "https://www.gesetze-im-internet.de/gewstg/",
  },
  "gewstg-11": {
    kurz: "§ 11 GewStG",
    titel: "Steuermesszahl und Steuermessbetrag",
    gesetz: "Gewerbesteuergesetz",
    ebene: "Bund",
    zusammenfassung:
      "Aus dem Gewerbeertrag wird der Steuermessbetrag: 3,5 % — bundesweit " +
      "gleich, keine Stellschraube der Stadt. Für Einzelunternehmen und " +
      "Personengesellschaften bleiben vorher 24.500 € frei.",
    url: "https://www.gesetze-im-internet.de/gewstg/__11.html",
  },
  "gewstg-16": {
    kurz: "§ 16 GewStG",
    titel: "Hebesatz",
    gesetz: "Gewerbesteuergesetz",
    ebene: "Bund",
    zusammenfassung:
      "Die Gemeinde beschließt den Hebesatz, mit dem der Steuermessbetrag " +
      "multipliziert wird — das ist die eine Zahl, über die der Rat hier " +
      "wirklich entscheidet. Das Gesetz schreibt nur vor, dass er für alle " +
      "Betriebe der Gemeinde gleich sein muss, und setzt eine Untergrenze " +
      "von 200 %.",
    url: "https://www.gesetze-im-internet.de/gewstg/__16.html",
  },
  "gewstg-29": {
    kurz: "§ 29 GewStG",
    titel: "Zerlegungsmaßstab",
    gesetz: "Gewerbesteuergesetz",
    ebene: "Bund",
    zusammenfassung:
      "Hat ein Unternehmen Betriebsstätten in mehreren Gemeinden, wird sein " +
      "Steuermessbetrag unter ihnen aufgeteilt — Maßstab sind die " +
      "Arbeitslöhne, die es an jedem Standort zahlt. Deshalb hängt der " +
      "Oldenburger Anteil an den Beschäftigten hier, nicht am Firmensitz.",
    url: "https://www.gesetze-im-internet.de/gewstg/__29.html",
  },
  "ao-30": {
    kurz: "§ 30 AO",
    titel: "Steuergeheimnis",
    gesetz: "Abgabenordnung",
    ebene: "Bund",
    zusammenfassung:
      "Amtsträger dürfen nicht offenbaren, was sie über die steuerlichen " +
      "Verhältnisse einer Person oder Firma erfahren haben. Das gilt auch " +
      "für die Kämmerei und auch gegenüber dem Rat — deshalb gibt es " +
      "nirgends in Deutschland eine Liste der größten Gewerbesteuerzahler.",
    url: "https://www.gesetze-im-internet.de/ao_1977/__30.html",
  },

  ngrstg: {
    kurz: "NGrStG",
    titel: "Niedersächsisches Grundsteuergesetz",
    gesetz: "Niedersächsisches Grundsteuergesetz (NGrStG)",
    ebene: "Land",
    zusammenfassung:
      "Niedersachsen rechnet die Grundsteuer seit der Reform nach einem " +
      "eigenen Gesetz: Grundlage sind Flächen und ein Lage-Faktor, nicht der " +
      "Wert des Grundstücks (Flächen-Lage-Modell). Die Bundesregeln zur " +
      "Bewertung gelten hier deshalb nicht.",
    url: "https://voris.wolterskluwer-online.de/browse/document/bf97ea29-8415-3e27-aae7-0141525c5137",
  },
  "ngrstg-6": {
    kurz: "§ 6 NGrStG",
    titel: "Grundsteuermesszahlen",
    gesetz: "Niedersächsisches Grundsteuergesetz",
    ebene: "Land",
    zusammenfassung:
      "Aus den Äquivalenzbeträgen eines Grundstücks wird der Messbetrag — " +
      "mit Abschlägen unter anderem für Wohnnutzung und für denkmalgeschützte " +
      "Gebäude. Die Zahlen stehen im Landesgesetz, die Stadt kann sie nicht " +
      "ändern.",
    url: "https://voris.wolterskluwer-online.de/browse/document/4249c6dd-95ae-3dd0-a3f2-673eec5bac6f",
  },
  "ngrstg-7": {
    kurz: "§ 7 NGrStG",
    titel: "Hebesatz",
    gesetz: "Niedersächsisches Grundsteuergesetz",
    ebene: "Land",
    zusammenfassung:
      "Den Hebesatz auf den Messbetrag beschließt die Gemeinde. Seit 2025 " +
      "darf sie für Wohn- und Nichtwohngrundstücke verschiedene Sätze " +
      "festlegen — Oldenburg tut das nicht.",
    url: "https://voris.wolterskluwer-online.de/browse/document/9611c2e8-7e65-3987-9093-20b90a9cf734",
  },

  estg: {
    kurz: "Einkommensteuergesetz",
    titel: "Einkommensteuergesetz",
    gesetz: "Einkommensteuergesetz (EStG)",
    ebene: "Bund",
    zusammenfassung:
      "Bestimmt, wer wie viel Einkommensteuer zahlt — Tarif, Freibeträge, " +
      "abziehbare Kosten. Die Stadt bekommt davon einen Anteil, hat auf die " +
      "Höhe der Steuer aber keinen Einfluss.",
    url: "https://www.gesetze-im-internet.de/estg/",
  },
  "gemfinrefg-1": {
    kurz: "§ 1 GemFinRefG",
    titel: "Gemeindeanteil an der Einkommensteuer",
    gesetz: "Gemeindefinanzreformgesetz",
    ebene: "Bund",
    zusammenfassung:
      "15 % des Aufkommens der Lohn- und veranlagten Einkommensteuer gehen " +
      "an die Gemeinden. Verteilt wird nach den Einkommensteuerbeträgen der " +
      "Einwohner*innen — bis zu einer Kappungsgrenze, damit einzelne " +
      "Spitzenverdiener eine Gemeinde nicht nach oben ziehen.",
    url: "https://www.gesetze-im-internet.de/gemfinrefg/__1.html",
  },
  ustg: {
    kurz: "Umsatzsteuergesetz",
    titel: "Umsatzsteuergesetz",
    gesetz: "Umsatzsteuergesetz (UStG)",
    ebene: "Bund",
    zusammenfassung:
      "Regelt die Mehrwertsteuer: welche Umsätze steuerpflichtig sind und " +
      "mit welchem Satz. Die Gemeinden bekommen einen Anteil am Aufkommen, " +
      "erheben die Steuer aber nicht selbst.",
    url: "https://www.gesetze-im-internet.de/ustg_1980/",
  },
  "gemfinrefg-5a": {
    kurz: "§ 5a GemFinRefG",
    titel: "Verteilung des Gemeindeanteils an der Umsatzsteuer",
    gesetz: "Gemeindefinanzreformgesetz",
    ebene: "Bund",
    zusammenfassung:
      "Legt den Schlüssel fest, nach dem der Umsatzsteueranteil auf die " +
      "Gemeinden verteilt wird — überwiegend nach Wirtschaftskraft " +
      "(Gewerbesteueraufkommen, sozialversicherungspflichtig Beschäftigte), " +
      "nicht nach dem, was vor Ort eingekauft wird.",
    url: "https://www.gesetze-im-internet.de/gemfinrefg/__5a.html",
  },

  nkag: {
    kurz: "NKAG",
    titel: "Niedersächsisches Kommunalabgabengesetz",
    gesetz: "Niedersächsisches Kommunalabgabengesetz (NKAG)",
    ebene: "Land",
    zusammenfassung:
      "Der Rahmen für alles, was Städte selbst erheben: örtliche Steuern " +
      "wie die Hunde- und die Vergnügungssteuer, dazu Gebühren und Beiträge. " +
      "Gebühren dürfen die Kosten der Leistung höchstens decken — Gewinn ist " +
      "nicht vorgesehen.",
    url: "https://voris.wolterskluwer-online.de/browse/document/1b730821-648d-3a12-aca7-f466336b3ceb",
  },
  nfag: {
    kurz: "NFAG",
    titel: "Niedersächsisches Finanzausgleichsgesetz",
    gesetz: "Niedersächsisches Finanzausgleichsgesetz (NFAG)",
    ebene: "Land",
    zusammenfassung:
      "Regelt, wie viel Geld das Land an Kommunen verteilt und nach welcher " +
      "Formel. Die Schlüsselzuweisung einer Stadt ergibt sich aus ihrem " +
      "Bedarf abzüglich ihrer Steuerkraft — wer mehr eigene Steuern " +
      "einnimmt, bekommt weniger.",
    url: "https://voris.wolterskluwer-online.de/browse/document/9c483e50-0258-3289-bc6d-4a01ca0bfabb",
  },
};

/** Wer den Volltext herausgibt — steht im Fähnchen unter dem Link, damit
 *  sichtbar ist, dass er von einer amtlichen Stelle kommt und nicht von uns. */
export function herausgeber(g: Gesetz): string {
  return g.ebene === "Bund"
    ? "Bundesamt für Justiz, gesetze-im-internet.de"
    : "Niedersächsisches Vorschrifteninformationssystem (VORIS)";
}
