// Städtevergleich — Typen, Rechenwege und die Einordnungen für /haushalt/vergleich.
//
// Die Seite beantwortet eine Frage, die sich fast jeder stellt („steht
// Oldenburg besser da als Osnabrück?"), und muss dabei zwei Dinge zugleich
// tun: das zeigen, was sich vergleichen lässt, und erklären, warum das meiste
// sich nicht vergleichen lässt. Alles hier dient einem der beiden.
//
// DIE TRENNLINIE, die den ganzen Bereich betrifft: Eine Kennzahl ist
// vergleichbar, wenn sie nicht davon abhängt, wie weit eine Stadt ausgelagert
// hat. Steuerkraft, Hebesätze und Steuereinnahmekraft erfüllen das — Steuern
// erhebt nie ein Eigenbetrieb, und die Steuerkraftmesszahl rechnet das Land
// für alle Gemeinden mit denselben fiktiven Hebesätzen. Ausgaben, Personal
// und Schulden je Einwohner erfüllen es nicht: Sie messen zuerst die
// Organisationsform. Begründung und Belege stehen in `council/staedtevergleich.py`.

import type { Herkunft } from "@/lib/herkunft";

export type { Herkunft };

export type VergleichStadt = {
  schluessel: string;
  name: string;
  ist_oldenburg: boolean;
  /** Unter 100.000 Einwohnern rechnet das NFAG die Steuerkraftmesszahl mit
   *  anderen Nivellierungshebesätzen — die Fußnote gehört an den Wert. */
  unter_100k: boolean;
};

export type VergleichWert = {
  reihe: "steuerkraft" | "realsteuern";
  jahr: number;
  schluessel: string;
  stadt: string;
  kennzahl: string;
  wert: number;
  einheit: string;
  herkunft_id: number | null;
};

/** Die Ratsvorlage, mit der die Stadt den Vergleich selbst entwertet hat. */
export type VergleichBeleg = {
  vorlage_nr: string;
  kvonr: number;
  vorlage_url: string;
  /** Der Eintrag in unserem eigenen Bestand — der Ausschuss hat den Bericht
   *  zur Kenntnis genommen. `null`, wenn der Bestand ihn (noch) nicht kennt. */
  beschluss_id: number | null;
  titel: string | null;
  anlagen: { document_id: number; label: string | null; url: string | null; is_antrag: number }[];
};

export type VergleichDaten = {
  staedte: VergleichStadt[];
  werte: VergleichWert[];
  jahre: { steuerkraft?: number[]; realsteuern?: number[] };
  beleg: VergleichBeleg;
  herkunft: Record<string, Herkunft>;
};

export function herkunftVon(daten: VergleichDaten,
                            id: number | null | undefined): Herkunft | null {
  return id == null ? null : daten.herkunft[String(id)] ?? null;
}

/** Eine Kennzahl eines Jahres, je Stadt — `null`, wo sie fehlt.
 *
 *  Fehlen ist der Normalfall und kein Fehler: Eine Stadt, deren Rechenprobe
 *  nicht aufging, steht gar nicht im Bestand (`council/staedtevergleich.py`).
 *  Die Oberfläche zeigt dann eine Lücke, keine geschätzte Zahl. */
export function kennzahl(
  daten: VergleichDaten, reihe: "steuerkraft" | "realsteuern",
  name: string, jahr: number,
): Map<string, VergleichWert> {
  const aus = new Map<string, VergleichWert>();
  for (const w of daten.werte) {
    if (w.reihe === reihe && w.kennzahl === name && w.jahr === jahr) {
      aus.set(w.schluessel, w);
    }
  }
  return aus;
}

/** Das jüngste Jahr einer Reihe, für das überhaupt etwas vorliegt. */
export function juengstesJahr(daten: VergleichDaten,
                              reihe: "steuerkraft" | "realsteuern"): number | null {
  const jahre = daten.jahre[reihe] ?? [];
  return jahre.length ? jahre[jahre.length - 1] : null;
}

export type Balken = {
  schluessel: string;
  name: string;
  wert: number;
  ist_oldenburg: boolean;
  unter_100k: boolean;
};

/** Steuerkraft je Einwohnerin — UNSERE Division, nicht das Amt.
 *
 *  Das LSN weist die Steuerkraftmesszahl absolut aus und die Einwohnerzahl
 *  daneben; den Pro-Kopf-Wert bildet niemand. Deshalb wird hier geteilt und
 *  auf der Seite dazugeschrieben, dass geteilt wurde — dieselbe Regel wie bei
 *  `LottiVergleich`. Gespeichert wird der Wert bewusst nicht, sonst ließe
 *  sich später nicht mehr unterscheiden, was amtlich ist und was gerechnet. */
export function steuerkraftJeEinwohner(daten: VergleichDaten, jahr: number): Balken[] {
  const messzahl = kennzahl(daten, "steuerkraft", "steuerkraftmesszahl", jahr);
  const einwohner = kennzahl(daten, "steuerkraft", "einwohner", jahr);
  const aus: Balken[] = [];
  for (const s of daten.staedte) {
    const m = messzahl.get(s.schluessel);
    const e = einwohner.get(s.schluessel);
    if (!m || !e || !e.wert) continue;
    aus.push({
      schluessel: s.schluessel, name: s.name,
      wert: (m.wert * 1000) / e.wert,
      ist_oldenburg: s.ist_oldenburg, unter_100k: s.unter_100k,
    });
  }
  return aus.sort((a, b) => b.wert - a.wert);
}

/** Eine gespeicherte Pro-Kopf- oder Prozent-Kennzahl als Balkenliste. */
export function balken(daten: VergleichDaten, reihe: "steuerkraft" | "realsteuern",
                       name: string, jahr: number): Balken[] {
  const werte = kennzahl(daten, reihe, name, jahr);
  const aus: Balken[] = [];
  for (const s of daten.staedte) {
    const w = werte.get(s.schluessel);
    if (!w) continue;
    aus.push({
      schluessel: s.schluessel, name: s.name, wert: w.wert,
      ist_oldenburg: s.ist_oldenburg, unter_100k: s.unter_100k,
    });
  }
  return aus.sort((a, b) => b.wert - a.wert);
}

/** Oldenburgs Platz in einer Balkenliste, 1-basiert. */
export function platzVonOldenburg(zeilen: Balken[]): number | null {
  const i = zeilen.findIndex((z) => z.ist_oldenburg);
  return i < 0 ? null : i + 1;
}

/** Eine Zeitreihe je Stadt — für die Steuereinnahmekraft über drei Jahre. */
export function reihe(daten: VergleichDaten, name: string,
                      schluessel: string): { jahr: number; wert: number }[] {
  return daten.werte
    .filter((w) => w.kennzahl === name && w.schluessel === schluessel)
    .map((w) => ({ jahr: w.jahr, wert: w.wert }))
    .sort((a, b) => a.jahr - b.jahr);
}

/** Wie sich ein Wert über die Reihe verändert hat — in Prozent, gerundet.
 *  `null`, wenn Anfang oder Ende fehlen; eine halbe Reihe ergibt keine
 *  Veränderung, sondern eine Lücke. */
export function veraenderung(punkte: { jahr: number; wert: number }[]): number | null {
  if (punkte.length < 2) return null;
  const erst = punkte[0].wert;
  const letzt = punkte[punkte.length - 1].wert;
  if (!erst) return null;
  return Math.round(((letzt - erst) / erst) * 100);
}

/** Die drei Städte, die als Vergleich wirklich taugen — und wofür je eine steht.
 *
 *  Redaktionell, nicht aus den Daten: Welche Stadt ein sinnvoller Maßstab ist,
 *  entscheidet ihr Aufgabenzuschnitt und ihre Struktur, nicht ihre Zahlenhöhe.
 *  Alle acht kreisfreien Städte stehen trotzdem in den Listen — eine Aussage
 *  wie „der höchste Wert von allen" ist nur mit allen prüfbar. */
export const ROLLEN: Record<string, { rolle: string; text: string }> = {
  "404000": {
    rolle: "Der Zwilling",
    text: "94 Prozent unserer Einwohnerzahl, dieselbe Rechtsstellung, dieselbe "
      + "Aufteilung in Eigenbetriebe: Gebäudewirtschaft und Abfall laufen auch dort "
      + "getrennt vom Haushalt, das Krankenhaus gehört auch dort der Stadt. Wo die "
      + "Hebesätze fast gleich stehen, misst ein Unterschied die Steuerbasis "
      + "und nicht die Politik.",
  },
  "101000": {
    rolle: "Das Gegenmodell",
    text: "Anderthalbmal so groß — und bei der Auslagerung das genaue Gegenteil: "
      + "Gebäudewirtschaft, Abfall und Entwässerung stehen dort im Haushalt selbst. "
      + "Deshalb weist Braunschweig weit höhere Ausgaben aus, ohne mehr zu leisten. "
      + "Bei der Grundsteuer B verlangt die Stadt 750 Prozent.",
  },
  "401000": {
    rolle: "Der Maßstab nach unten",
    text: "Direkt nebenan, derselbe Aufgabenzuschnitt — und die mit Abstand "
      + "schwächste Steuerkraft der acht. Delmenhorst beantwortet die Frage, wie gut "
      + "Oldenburg eigentlich dasteht, ehrlicher als jeder Durchschnitt.",
  },
};

/** Wolfsburg ist kein Vergleich, sondern eine Warnung — und deshalb genau an
 *  einer Stelle interessant: Es zeigt, was eine hohe Gewerbesteuer kosten
 *  kann, wenn sie an einem einzigen Unternehmen hängt. */
export const WOLFSBURG = "103000";

/** Der Satz, um den es auf dieser Seite geht — wörtlich aus der Antwort der
 *  Stadtverwaltung auf den FDP-Antrag von 2018 (`document_id` 196525).
 *
 *  Er steht hier als Konstante, damit er an genau einer Stelle im Code lebt:
 *  Ein Zitat, das man beim Umbauen versehentlich umformuliert, wäre schlimmer
 *  als keins. */
//
//  Die inneren Anführungszeichen sind EINFACH (‚besser'), weil sie in einem
//  doppelt zitierten Satz stehen — so steht es auch im Original.
export const ZITAT_VERWALTUNG =
  "Die heterogenen Strukturen der verschiedenen Städte lassen einen "
  + "aussagefähigen Vergleich in dem Sinne nicht zu, dass eine niedrigere Quote "
  + "‚besser‘ als eine höhere Quote ist.";

/** Was die Verwaltung 2018 je Stadt aufgelistet hat: was im Kernhaushalt
 *  steckt und was nicht. Die Liste ist der Beweis des Arguments — ohne sie
 *  bliebe „heterogene Strukturen" eine Behauptung. */
export const AUSGLIEDERUNGEN_2018: { stadt: string; was: string }[] = [
  { stadt: "Oldenburg", was: "ohne Gebäudewirtschaft" },
  { stadt: "Osnabrück", was: "ohne Gebäudewirtschaft, Grünflächen und Straßenunterhaltung" },
  { stadt: "Braunschweig", was: "Sonderrechnung für den Pensionsfonds" },
  { stadt: "Hannover", was: "mit Gebäudewirtschaft, Volkshochschule, Herrenhäuser Gärten" },
  { stadt: "Wolfsburg", was: "ohne Bibliotheken, mit Gebäudewirtschaft" },
  { stadt: "Göttingen", was: "verschiedenste Ausgliederungen in Betriebe" },
  { stadt: "Wilhelmshaven", was: "ohne Liegenschaften, Gebäudewirtschaft, Straßenunterhaltung, Verkehrslenkung und Stadtgrün" },
];

/** Die Anlage mit der Antwort der Verwaltung — sie trägt das Zitat und die
 *  Liste. Erkannt am Label, weil die `document_id` eine Eigenschaft unseres
 *  Bestands ist und kein Schlüssel, den die Seite kennen sollte. */
export function antwortAnlage(beleg: VergleichBeleg) {
  return beleg.anlagen.find((a) => /beantwortung/i.test(a.label ?? "")) ?? null;
}

export function antragAnlage(beleg: VergleichBeleg) {
  return beleg.anlagen.find((a) => /antrag/i.test(a.label ?? "")
    && !/beantwortung/i.test(a.label ?? "")) ?? null;
}

/** Euro je Einwohner, deutsch formatiert und ohne Nachkommastellen —
 *  Pro-Kopf-Beträge dieser Größenordnung tragen keine Cent-Genauigkeit. */
export function euroJeEw(v: number | null | undefined): string {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("de-DE");
}
