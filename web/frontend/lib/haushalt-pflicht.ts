// Pflicht oder Kür? (Design H-14/H-15) — redaktionelle Einschätzung.
//
// Es gibt KEINE Datenquelle, die Teilhaushalte in Pflicht und Kür einteilt.
// Diese Zuordnung ist eine Einschätzung auf Ebene ganzer Teilhaushalte, und
// die Seite sagt das auch. Drei Stufen statt zwei, weil die Wirklichkeit
// dreistufig ist: Eine Kita muss die Stadt anbieten (Pflicht), wie gut sie
// ausgestattet ist, entscheidet der Rat (Spielraum), ein Stadttheater muss
// niemand betreiben (freiwillig).
//
// Die Summen darunter kommen aus dem Plan — nur die Einordnung ist von uns.

export type PflichtStufe = "pflicht" | "spielraum" | "freiwillig";

export const PFLICHT_LABEL: Record<PflichtStufe, string> = {
  pflicht: "Pflicht",
  spielraum: "Pflicht mit Spielraum",
  freiwillig: "überwiegend freiwillig",
};

export const PFLICHT_ERKLAERUNG: Record<PflichtStufe, string> = {
  pflicht:
    "Bundes- oder Landesgesetze schreiben diese Aufgaben vor. Der Rat kann sie nicht streichen — " +
    "beim Wie hat er meist nur geringen Spielraum.",
  spielraum:
    "Die Aufgabe selbst ist vorgeschrieben, ihr Umfang und ihre Qualität aber nicht. Hier " +
    "entscheidet der Rat mit — etwa über Öffnungszeiten, Personal oder Standards.",
  freiwillig:
    "Diese Aufgaben muss die Stadt nicht übernehmen. Sie tut es, weil der Rat es so will — " +
    "hier ist der Gestaltungsspielraum am größten.",
};

/** Zuordnung je Teilhaushalt, wie er im Haushaltsplan heißt. Bereiche ohne
 *  Eintrag erscheinen als „nicht eingeordnet" statt stillschweigend als Kür. */
export const PFLICHT_ZUORDNUNG: Record<string, { stufe: PflichtStufe; was: string }> = {
  "Soziales und Gesundheit": {
    stufe: "pflicht",
    was: "Sozialleistungen nach SGB, Hilfen zur Pflege, öffentlicher Gesundheitsdienst",
  },
  "Jugend und Familie": {
    stufe: "spielraum",
    was: "Kitas und Jugendhilfe sind Pflicht — Ausstattung, Betreuungsschlüssel und Angebote gestaltet der Rat",
  },
  "Schule und Bildung": {
    stufe: "spielraum",
    was: "Schulträgerschaft ist Pflicht — Sanierungstempo, Ausstattung und Ganztag entscheidet der Rat",
  },
  "Sicherheit und Ordnung": {
    stufe: "pflicht",
    was: "Feuerwehr, Rettungsdienst, Ordnungsverwaltung",
  },
  "Verkehr und Straßenbau": {
    stufe: "spielraum",
    was: "Straßen unterhalten ist Pflicht — Radwege, Nahverkehrsangebot und Tempo der Sanierung nicht",
  },
  "Kultur, Museen, Sport": {
    stufe: "freiwillig",
    was: "Theater, Museen, Bibliothek, Sportförderung",
  },
  "Wirtschaftsförderung, Liegenschaften": {
    stufe: "freiwillig",
    was: "Standortmarketing, Beteiligungen, Flächenentwicklung",
  },
  Stadtplanung: {
    stufe: "pflicht",
    was: "Bauleitplanung als gesetzliche Aufgabe der Stadt",
  },
  "Klima/Umwelt/Mobilität/Bau/Grün/Friedh.": {
    stufe: "spielraum",
    was: "Bauaufsicht und Friedhöfe sind Pflicht — Klimaschutz und Grünpflege gestaltet der Rat",
  },
  "Personal/Organisation/Digitalisierung/IT": {
    stufe: "pflicht",
    was: "Verwaltung, die die Stadt zum Arbeiten braucht",
  },
  "Finanzmanagement und Recht": {
    stufe: "pflicht",
    was: "Kämmerei, Steuern, Rechtsamt — hier laufen auch alle Einnahmen auf",
  },
  Verwaltungsführung: {
    stufe: "pflicht",
    was: "Oberbürgermeister, Ratsbüro, Verwaltungsspitze",
  },
  // NICHT als „freiwillig": Stiftungsvermögen ist zweckgebunden und wird nur
  // treuhänderisch verwaltet — der Rat kann es nicht umwidmen, auch wenn die
  // Stadt die Stiftung nicht betreiben müsste. Als Kür geführt hätte das
  // Labor suggeriert, man könne hier kürzen.
  "nicht rechtsfähige Stiftungen": {
    stufe: "pflicht",
    was: "Treuhänderisch verwaltetes Stiftungsvermögen — zweckgebunden, nicht frei verfügbar",
  },
};
