// Kurznamen für die (langen) Oldenburger Gremiennamen — eine Funktion, überall
// (Design 19a). Amtliche Namen wie „Ausschuss für Wirtschaftsförderung,
// Digitalisierung und internationale Zusammenarbeit" sprengen jede Karte, jedes
// Chip, jedes Dropdown. `shortCommittee` bildet sie auf eine knappe, sinntragende
// Kurzform ab — der volle Name bleibt im title/aria-label und (auf Karten) als
// Unterzeile erhalten. Nie stumpf nach n Zeichen abschneiden.

// Die Oldenburger Gremienliste ist endlich (~15 aktuell + ein paar historische
// Umbenennungen). Gepflegte Tabelle zuerst, Heuristik nur als Fallback.
const SHORT: Record<string, string> = {
  "Rat": "Rat",
  "Rat der Stadt Oldenburg": "Rat",
  "Rat der Stadt Oldenburg (Oldb)": "Rat",
  "Verwaltungsausschuss": "Verwaltungsausschuss",
  "Ausschuss für Allgemeine Angelegenheiten": "Allgemeine Angelegenheiten",
  "Ausschuss für Finanzen und Beteiligungen": "Finanzen & Beteiligungen",
  "Ausschuss für Integration und Migration": "Integration & Migration",
  "Ausschuss für Stadtgrün, Umwelt und Klima": "Stadtgrün & Klima",
  "Ausschuss für Stadtplanung und Bauen": "Stadtplanung & Bauen",
  "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit": "Wirtschaft & Digitales",
  "Betriebsausschuss Abfallwirtschaftsbetrieb": "Abfallwirtschaft",
  "Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau": "Betrieb Gebäudewirtschaft",
  "Jugendhilfeausschuss": "Jugendhilfe",
  "Kulturausschuss": "Kultur",
  "Schulausschuss": "Schule",
  "Sozialausschuss": "Soziales",
  "Sportausschuss": "Sport",
  "Verkehrsausschuss": "Verkehr",
  // historische Umbenennungen (Bestand seit 2018)
  "Ausschuss für Umwelt, Grünflächen und Klimaschutz": "Umwelt & Klima",
  "Ausschuss für Umwelt und Klimaschutz": "Umwelt & Klima",
  "Betriebsausschuss Gebäudewirtschaft und Hochbau": "Betrieb Gebäudewirtschaft",
  "Ausschuss für Wirtschaftsförderung und Digitalisierung": "Wirtschaft & Digitales",
};

/** Amtlicher Gremienname → knappe Kurzform. Unbekannte Namen laufen in eine
 *  Heuristik (Präfix „Ausschuss für …" streichen, „und" → „&", „…ausschuss" →
 *  Kern), nie ein hartes Zeichen-Abschneiden. */
export function shortCommittee(name: string | null | undefined): string {
  if (!name) return "";
  const key = name.trim();
  if (SHORT[key]) return SHORT[key];

  let s = key
    .replace(/^Ausschuss für (den |die |das )?/i, "")
    .replace(/^Betriebsausschuss (Eigenbetrieb )?/i, "");
  // Ein einzelnes „Xausschuss" (Verkehrsausschuss, Kulturausschuss) → Kern.
  if (/^\S+ausschuss$/i.test(s)) s = s.replace(/s?ausschuss$/i, "");
  s = s.replace(/\s+und\s+/gi, " & ");
  s = s.trim();
  return s.length >= 2 ? s : key;
}

/** True, wenn der Kurzname vom vollen Namen abweicht — dann lohnt die Unterzeile. */
export function hasShortCommittee(name: string | null | undefined): boolean {
  return !!name && shortCommittee(name) !== name.trim();
}

// Ein Satz „was hier behandelt wird" je Gremium (Design 26a, Schritt 1). Ohne
// das ist die Abo-Auswahl eine Liste von Amtsbezeichnungen — „Ausschuss für
// Allgemeine Angelegenheiten" sagt niemandem, was drin verhandelt wird.
// Bewusst dieselbe Datei wie shortCommittee: eine Quelle je Gremium.
const EXPLAINS: Record<string, string> = {
  "Rat": "Entscheidet die großen Linien: Haushalt, Satzungen und Grundsatzbeschlüsse.",
  "Verwaltungsausschuss": "Bereitet die Ratsbeschlüsse vor und entscheidet Eilfälle — tagt nichtöffentlich.",
  "Allgemeine Angelegenheiten": "Verwaltung, Personal, Ordnung und alles, was in keinen Fachausschuss fällt.",
  "Finanzen & Beteiligungen": "Haushalt, Zuwendungen und die städtischen Beteiligungen.",
  "Integration & Migration": "Zuwanderung, Teilhabe und interkulturelle Arbeit in der Stadt.",
  "Stadtgrün & Klima": "Grünflächen, Klimaschutz, Energie und Naturschutz in der Stadt.",
  "Umwelt & Klima": "Grünflächen, Klimaschutz, Energie und Naturschutz in der Stadt.",
  "Stadtplanung & Bauen": "Bebauungspläne, Bauprojekte und wie sich Viertel entwickeln.",
  "Wirtschaft & Digitales": "Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit.",
  "Abfallwirtschaft": "Müllabfuhr, Recycling und der städtische Abfallbetrieb.",
  "Betrieb Gebäudewirtschaft": "Bau und Unterhalt der städtischen Gebäude — Schulen, Kitas, Verwaltung.",
  "Jugendhilfe": "Kitas, Jugendarbeit und Hilfen für Familien.",
  "Kultur": "Museen, Theater, Bibliotheken und die Förderung der freien Szene.",
  "Schule": "Schulen, Ganztagsbetreuung und neue Bildungsstandorte.",
  "Soziales": "Wohnen, Pflege, Teilhabe und soziale Angebote der Stadt.",
  "Sport": "Sportstätten, Vereinsförderung und Bäder.",
  "Verkehr": "Radwege, Straßen, Bus & Bahn, Parken und Verkehrsberuhigung.",
};

/** Ein Satz, was in diesem Gremium behandelt wird — leer, wenn unbekannt (dann
 *  zeigt die Oberfläche einfach nur den Namen, statt etwas zu erfinden). */
export function committeeExplains(name: string | null | undefined): string {
  if (!name) return "";
  return EXPLAINS[shortCommittee(name)] ?? "";
}
