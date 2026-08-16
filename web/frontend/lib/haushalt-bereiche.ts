// Bereichs-Wörterbuch des Haushalts — ein Teilhaushalt, ein Schlüssel.
//
// Warum es diese Datei gibt: Die Stadt benennt ihre Teilhaushalte um, ohne den
// Zuschnitt zu ändern. Teilhaushalt 9 heißt in `council_haushalt` je nach
// Jahrgang „Umwelt, Bauordnung, Grün  u. Friedhöfe" (2020/21, mit doppeltem
// Leerzeichen), „Klima, Umwelt, Bauordnung, Grün" (2022),
// „Klima/Umwelt/Mobilität/Bau/Grün/Friedh." (2023, 2025, 2026) und
// „Umwelt, Bauordnung, Grün und Friedhöfe" (2024) — vier Schreibweisen in
// sieben Jahrgängen. Teilhaushalt 2 hat drei. Jede Map, die auf den exakten
// Namen geschlüsselt ist, verliert beim nächsten Jahrgang stillschweigend
// Zeilen: Der Bereich fällt aus der Zuordnung, die Summe schrumpft, und
// niemand sieht einen Fehler.
//
// Deshalb: Namen aus der Datenbank laufen durch `bereichKanon()`. Der
// Rückgabewert trägt den kanonischen Schlüssel, die THH-Nummer, einen kurzen
// Namen fürs Balkensegment und eine Zeile Klartext.
//
// Drei Regeln:
//  1. `bereichKanon()` gibt IMMER etwas zurück. Ein unbekannter Name fällt auf
//     sich selbst zurück (`bekannt: false`) — ein neuer Jahrgang taucht dann
//     unter seinem Rohnamen auf, statt zu verschwinden.
//  2. Slug, Link und Sortierung hängen weiter am DB-Namen (`bereichSlug()` in
//     `lib/haushalt.ts`). Der Anzeigename ist eine Anzeige, kein Schlüssel.
//  3. Wer einen Jahrgang nachzieht und einen neuen Namen sieht, trägt ihn hier
//     in `aliase` ein — nicht in seiner eigenen Komponente.
//
// Die Alias-Listen sind gegen den Bestand geprüft (`council_haushalt` 2020–2026,
// `council_ergebnisrechnung` 2017–2024, `council_produkte` 2018–2023); die
// Normalisierung fängt zusätzlich Groß-/Kleinschreibung, doppelte Leerzeichen,
// „u." gegen „und" und den Jahres-Präfix ab, den die Ergebnisrechnung für 2017
// und 2019 mitschleppt („_2019 Stadtplanung").

/** Kanonischer Schlüssel eines Teilhaushalts — stabil über alle Jahrgänge. */
export type BereichSchluessel =
  | "verwaltungsfuehrung"
  | "personal"
  | "wirtschaft"
  | "finanzen"
  | "sicherheit"
  | "kultur"
  | "stadtplanung"
  | "verkehr"
  | "umwelt"
  | "soziales"
  | "jugend"
  | "schule"
  | "stiftungen";

export type Bereich = {
  schluessel: BereichSchluessel;
  /** Nummer des Teilhaushalts im Haushaltsplan (Reihenfolge der Übersicht). */
  thh: number;
  /** Anzeigename: die jüngste amtliche Schreibweise, nicht unsere Erfindung. */
  name: string;
  /** Kurzform fürs Balkensegment und enge Spalten (höchstens 20 Zeichen). */
  kurz: string;
  /** Eine Zeile Klartext: was in diesem Teilhaushalt steckt. */
  klartext: string;
  /** Jede Schreibweise, die im Bestand vorkommt — jüngste zuerst. */
  aliase: string[];
};

/** Alle 13 Teilhaushalte in der Reihenfolge des Haushaltsplans.
 *
 *  Die THH-Nummern 1–12 stehen so in `council_ergebnisrechnung`. Für die
 *  nicht rechtsfähigen Stiftungen führt die Ergebnisrechnung keine Nummer —
 *  13 ist ihre Position in der Übersicht des Ergebnishaushalts (letzte Zeile
 *  vor der Summe, in jedem Jahrgang 2020–2026). */
export const BEREICHE: readonly Bereich[] = [
  {
    schluessel: "verwaltungsfuehrung",
    thh: 1,
    name: "Verwaltungsführung",
    kurz: "Verwaltungsspitze",
    klartext:
      "Oberbürgermeister, Ratsbüro und Verwaltungsspitze — dazu die örtliche " +
      "Rechnungsprüfung und die Gleichstellungsstelle.",
    aliase: ["Verwaltungsführung"],
  },
  {
    schluessel: "personal",
    thh: 2,
    name: "Personal/Organisation/Digitalisierung/IT",
    kurz: "Personal & IT",
    klartext:
      "Personal, Organisation und IT der gesamten Verwaltung — hier stehen auch " +
      "die Versorgungsaufwendungen für die Pensionen.",
    aliase: [
      "Personal/Organisation/Digitalisierung/IT",
      "Personal- und Verwaltungsmanagement",
      "Personal- u. Verwaltungsmanagement",
    ],
  },
  {
    schluessel: "wirtschaft",
    thh: 3,
    name: "Wirtschaftsförderung, Liegenschaften",
    kurz: "Wirtschaft & Flächen",
    klartext:
      "Wirtschaftsförderung und Standortmarketing, dazu die Grundstücke und " +
      "Beteiligungen der Stadt.",
    aliase: ["Wirtschaftsförderung, Liegenschaften"],
  },
  {
    schluessel: "finanzen",
    thh: 4,
    name: "Finanzmanagement und Recht",
    kurz: "Finanzen",
    klartext:
      "Kämmerei, Stadtkasse und Rechtsamt — hier laufen alle Steuern und die " +
      "allgemeinen Zuweisungen des Landes für die ganze Stadt auf.",
    aliase: ["Finanzmanagement und Recht"],
  },
  {
    schluessel: "sicherheit",
    thh: 5,
    name: "Sicherheit und Ordnung",
    kurz: "Sicherheit",
    klartext:
      "Feuerwehr, Rettungsdienst und Ordnungsverwaltung, dazu die Bürgerdienste " +
      "vom Einwohnermeldeamt bis zum Standesamt.",
    aliase: ["Sicherheit und Ordnung"],
  },
  {
    schluessel: "kultur",
    thh: 6,
    name: "Kultur, Museen, Sport",
    kurz: "Kultur & Sport",
    klartext:
      "Museen, Bibliothek, Musikschule und Stadtarchiv sowie die Kultur- und " +
      "Sportförderung.",
    aliase: ["Kultur, Museen, Sport"],
  },
  {
    schluessel: "stadtplanung",
    thh: 7,
    name: "Stadtplanung",
    kurz: "Stadtplanung",
    klartext:
      "Bauleitplanung, Stadtentwicklung und Stadterneuerung, dazu Vermessung " +
      "und Geoinformation.",
    aliase: ["Stadtplanung"],
  },
  {
    schluessel: "verkehr",
    thh: 8,
    name: "Verkehr und Straßenbau",
    kurz: "Verkehr & Straßen",
    klartext: "Straßen, Radwege, Brücken und der Nahverkehr.",
    aliase: ["Verkehr und Straßenbau"],
  },
  {
    schluessel: "umwelt",
    thh: 9,
    name: "Klima/Umwelt/Mobilität/Bau/Grün/Friedh.",
    kurz: "Klima & Umwelt",
    klartext:
      "Grünflächen und Friedhöfe, Bauordnung, Natur- und Klimaschutz — der " +
      "Zuschnitt dieses Teilhaushalts wurde seit 2020 mehrfach geändert.",
    aliase: [
      "Klima/Umwelt/Mobilität/Bau/Grün/Friedh.",
      "Umwelt, Bauordnung, Grün und Friedhöfe",
      "Klima, Umwelt, Bauordnung, Grün",
      "Umwelt, Bauordnung, Grün  u. Friedhöfe",
    ],
  },
  {
    schluessel: "soziales",
    thh: 10,
    name: "Soziales und Gesundheit",
    kurz: "Soziales",
    klartext:
      "Gesetzliche Sozialleistungen von der Grundsicherung über die " +
      "Eingliederungshilfe bis zur Hilfe zur Pflege, dazu der öffentliche " +
      "Gesundheitsdienst.",
    aliase: ["Soziales und Gesundheit"],
  },
  {
    schluessel: "jugend",
    thh: 11,
    name: "Jugend und Familie",
    kurz: "Jugend & Familie",
    klartext:
      "Kindertagesbetreuung, erzieherische Hilfen und die übrige Jugendhilfe.",
    aliase: ["Jugend und Familie"],
  },
  {
    schluessel: "schule",
    thh: 12,
    name: "Schule und Bildung",
    kurz: "Schulen",
    klartext:
      "Schulgebäude, Ausstattung und Ganztagsangebote der Stadt als " +
      "Schulträgerin — die Lehrkräfte bezahlt das Land.",
    aliase: ["Schule und Bildung"],
  },
  {
    schluessel: "stiftungen",
    thh: 13,
    name: "nicht rechtsfähige Stiftungen",
    kurz: "Stiftungen",
    klartext:
      "Treuhänderisch verwaltetes Stiftungsvermögen — zweckgebunden, kein frei " +
      "verfügbares Geld der Stadt.",
    aliase: ["nicht rechtsfähige Stiftungen"],
  },
];

export const BEREICH_NACH_SCHLUESSEL: Record<BereichSchluessel, Bereich> =
  Object.fromEntries(BEREICHE.map((b) => [b.schluessel, b])) as Record<
    BereichSchluessel,
    Bereich
  >;

/** Vergleichsform eines Bereichsnamens.
 *
 *  Fängt genau die Abweichungen ab, die im Bestand vorkommen und keine
 *  inhaltliche Änderung sind: Groß-/Kleinschreibung, doppelte Leerzeichen
 *  („Grün  u. Friedhöfe"), „u." gegen „und", verschiedene Bindestriche und
 *  der Jahres-Präfix der Ergebnisrechnung („_2019 Stadtplanung"). Alles
 *  andere ist ein echter neuer Name und gehört in `aliase`. */
export function normalisiereBereich(name: string): string {
  return name
    .replace(/^_\d{4}\s+/, "")
    .replace(/[‐-―]/g, "-")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim()
    .replace(/(^|\s)u\.(\s|$)/g, "$1und$2");
}

const NACH_ALIAS: Map<string, Bereich> = new Map(
  BEREICHE.flatMap((b) =>
    b.aliase.map((a) => [normalisiereBereich(a), b] as [string, Bereich]),
  ),
);

/** Ergebnis der Auflösung — immer gefüllt, auch für unbekannte Namen. */
export type BereichKanon = {
  /** `null`, wenn der Name im Wörterbuch fehlt (neuer Jahrgang). */
  schluessel: BereichSchluessel | null;
  thh: number | null;
  /** Anzeigename; bei unbekanntem Namen der Rohname aus der Datenbank. */
  name: string;
  kurz: string;
  klartext: string | null;
  /** `false` heißt: Rückfall auf den Rohnamen — der Name gehört ins Wörterbuch. */
  bekannt: boolean;
};

/** Kurzform für einen unbekannten Namen: erstes Segment, hart gekappt.
 *  Lieber ein abgeschnittener Rohname als ein erfundener Kurzname. */
function notKurz(name: string): string {
  const kopf = name.split(/[,/]/)[0].trim() || name.trim();
  return kopf.length > 20 ? `${kopf.slice(0, 19)}…` : kopf;
}

/** Bereichsnamen aus der Datenbank auflösen. Unbekannte Namen fallen auf sich
 *  selbst zurück — sie verschwinden nie stillschweigend. */
export function bereichKanon(name: string): BereichKanon {
  const b = NACH_ALIAS.get(normalisiereBereich(name));
  if (!b) {
    const roh = name.trim();
    return {
      schluessel: null,
      thh: null,
      name: roh,
      kurz: notKurz(roh),
      klartext: null,
      bekannt: false,
    };
  }
  return {
    schluessel: b.schluessel,
    thh: b.thh,
    name: b.name,
    kurz: b.kurz,
    klartext: b.klartext,
    bekannt: true,
  };
}

/** Kurzname fürs Balkensegment („Finanzen", „Personal & IT"). */
export function bereichKurz(name: string): string {
  return bereichKanon(name).kurz;
}

/** Eine Zeile Klartext, oder `null` bei unbekanntem Bereich. */
export function bereichKlartext(name: string): string | null {
  return bereichKanon(name).klartext;
}

/** Kanonischer Schlüssel, oder `null` — der Schlüssel für eigene Maps
 *  (Pflicht/Kür, Farben, Icons). Nie den Namen als Schlüssel nehmen. */
export function bereichSchluessel(name: string): BereichSchluessel | null {
  return bereichKanon(name).schluessel;
}

/** Die Summenzeile trägt keinen Bereichsnamen — `is_summe` der Zeile ist die
 *  belastbare Prüfung, dies hier der Notnagel für Namenslisten ohne Zeile. */
export function istSummenzeile(name: string): boolean {
  return normalisiereBereich(name) === "summe";
}
