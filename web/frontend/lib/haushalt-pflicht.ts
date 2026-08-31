// Pflicht oder Kür? — redaktionelle Einordnung, seit #500 mit Boden.
//
// Bis 08/2026 stand hier: „Es gibt KEINE Datenquelle, die Teilhaushalte in
// Pflicht und Kür einteilt." Der erste Halbsatz stimmt weiter — eine amtliche
// Einteilung GANZER Teilhaushalte gibt es nicht, und wird es nicht geben, weil
// in jedem Teilhaushalt beides steckt. Der Rest stimmt nicht mehr. Die
// Produktebene trägt zu jeder einzelnen Aufgabe zwei Angaben der Stadt selbst:
//
//   `legal_basis`   — die Gesetze, Satzungen und Ratsbeschlüsse, auf
//                           denen die Aufgabe beruht, im Wortlaut des
//                           Teilhaushaltsplans. 377 von 377 Zeilen (2018–2023).
//   `controllability`   — wie viel Spielraum die STADT bei der Aufgabe
//                           sieht (niedrig/mittel/hoch), 371 von 377. Dazu
//                           `controllability_raw` mit dem Originalwortlaut,
//                           damit Mischformen nicht verschwinden.
//
// Damit bleibt unsere Einordnung redaktionell — sie wird aber prüfbar. Diese
// Datei liefert beides: die Einordnung UND den Abgleich mit der Selbstauskunft.
// Wo beide auseinandergehen, weist die Seite das aus, statt es zu glätten. Das
// ist die interessanteste Auskunft, die sie hat: Bei „Jugend und Familie"
// sagen wir „Pflicht mit Spielraum", die Stadt sieht für 95 % des Geldes
// „kaum Spielraum".
//
// ZWEI JAHRE, NICHT EINS. Der Plan reicht bis ins Kopfjahr der Seite, die
// Produktebene endet 2023. Jede Aussage aus ihr trägt deshalb ihren eigenen
// Jahresstempel — `SpielraumBefund.year`. Vermischen wäre die stillste Art,
// hier falsch zu liegen.

import {
  BEREICHE, bereichKanon, type BereichSchluessel,
} from "@/lib/haushalt-bereiche";
import type { Produkt, Spielraum } from "@/lib/haushalt";

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

export type PflichtEintrag = { stufe: PflichtStufe; was: string };

/** Die Einordnung, auf den KANONISCHEN Bereichsschlüssel geschlüsselt.
 *
 *  Vorher stand hier der exakte Bereichsname des Haushaltsplans. Das war eine
 *  stille Falle: Teilhaushalt 9 heißt je nach Jahrgang „Umwelt, Bauordnung,
 *  Grün  u. Friedhöfe", „Klima, Umwelt, Bauordnung, Grün" oder
 *  „Klima/Umwelt/Mobilität/Bau/Grün/Friedh." — beim nächsten Jahrgangswechsel
 *  wäre der Bereich aus der Zuordnung gefallen, als „nicht eingeordnet"
 *  erschienen und aus jeder Summe verschwunden, ohne dass irgendwo ein Fehler
 *  sichtbar geworden wäre. Der Schlüssel aus `lib/haushalt-bereiche.ts`
 *  überlebt Umbenennungen. */
export const PFLICHT_NACH_SCHLUESSEL: Record<BereichSchluessel, PflichtEintrag> = {
  soziales: {
    stufe: "pflicht",
    was: "Sozialleistungen nach SGB, Hilfen zur Pflege, öffentlicher Gesundheitsdienst",
  },
  jugend: {
    stufe: "spielraum",
    was: "Kitas und Jugendhilfe sind Pflicht — Ausstattung, Betreuungsschlüssel und Angebote gestaltet der Rat",
  },
  schule: {
    stufe: "spielraum",
    was: "Schulträgerschaft ist Pflicht — Sanierungstempo, Ausstattung und Ganztag entscheidet der Rat",
  },
  sicherheit: {
    stufe: "pflicht",
    was: "Feuerwehr, Rettungsdienst, Ordnungsverwaltung",
  },
  verkehr: {
    stufe: "spielraum",
    was: "Straßen unterhalten ist Pflicht — Radwege, Nahverkehrsangebot und Tempo der Sanierung nicht",
  },
  kultur: {
    stufe: "freiwillig",
    was: "Theater, Museen, Bibliothek, Sportförderung",
  },
  wirtschaft: {
    stufe: "freiwillig",
    was: "Standortmarketing, Beteiligungen, Flächenentwicklung",
  },
  stadtplanung: {
    stufe: "pflicht",
    was: "Bauleitplanung als gesetzliche Aufgabe der Stadt",
  },
  umwelt: {
    stufe: "spielraum",
    was: "Bauaufsicht und Friedhöfe sind Pflicht — Klimaschutz und Grünpflege gestaltet der Rat",
  },
  personal: {
    stufe: "pflicht",
    was: "Verwaltung, die die Stadt zum Arbeiten braucht",
  },
  finanzen: {
    stufe: "pflicht",
    was: "Kämmerei, Steuern, Rechtsamt — hier laufen auch alle Einnahmen auf",
  },
  verwaltungsfuehrung: {
    stufe: "pflicht",
    was: "Oberbürgermeister, Ratsbüro, Verwaltungsspitze",
  },
  // NICHT als „freiwillig": Stiftungsvermögen ist zweckgebunden und wird nur
  // treuhänderisch verwaltet — der Rat kann es nicht umwidmen, auch wenn die
  // Stadt die Stiftung nicht betreiben müsste. Als Kür geführt hätte das
  // Labor suggeriert, man könne hier kürzen.
  stiftungen: {
    stufe: "pflicht",
    was: "Treuhänderisch verwaltetes Stiftungsvermögen — zweckgebunden, nicht frei verfügbar",
  },
};

/** Einordnung zu einem Bereichsnamen, wie ihn die Datenbank führt.
 *  Der bevorzugte Zugriff: er läuft über `bereichKanon()` und übersteht damit
 *  auch Schreibweisen, die nur in Groß-/Kleinschreibung abweichen. */
export function pflichtFuer(name: string): PflichtEintrag | undefined {
  const s = bereichKanon(name).key;
  return s ? PFLICHT_NACH_SCHLUESSEL[s] : undefined;
}

/** Namensindizierte Sicht auf dieselbe Zuordnung — für Aufrufer, die nur den
 *  DB-Namen in der Hand haben (`components/haushalt/labor.tsx`).
 *
 *  Abgeleitet aus den Alias-Listen des Wörterbuchs, deckt also jede
 *  Schreibweise jedes Jahrgangs ab. Wer neu schreibt, nimmt `pflichtFuer()`. */
export const PFLICHT_ZUORDNUNG: Record<string, PflichtEintrag> = Object.fromEntries(
  BEREICHE.flatMap((b) =>
    b.aliase.map((a) => [a, PFLICHT_NACH_SCHLUESSEL[b.key]] as const),
  ),
);

// --- Der Abgleich mit der Selbstauskunft der Stadt --------------------------

/** Welche Selbstauskunft zu welcher redaktionellen Stufe passt.
 *
 *  Die Zuordnung ist die naheliegende und wird deshalb offengelegt: „Pflicht"
 *  müsste sich als „kaum Spielraum" wiederfinden, „überwiegend freiwillig"
 *  als „viel Spielraum". Sie ist eine Erwartung, kein Beweis — die Stadt
 *  beantwortet mit `controllability` eine leicht andere Frage (wie stark
 *  lassen sich die KOSTEN beeinflussen, nicht: muss es die Aufgabe geben). */
export const STUFE_ERWARTET: Record<PflichtStufe, Spielraum> = {
  pflicht: "niedrig",
  spielraum: "mittel",
  freiwillig: "hoch",
};

export const SPIELRAUM_STUFEN: Spielraum[] = ["niedrig", "mittel", "hoch"];

/** Was die Stadt zu einem Teilhaushalt selbst angibt, über seine Produkte
 *  hinweg zusammengefasst.
 *
 *  Gewichtet wird nach AUFWAND, nicht nach Anzahl: „Soziales und Gesundheit"
 *  hat 20 Produkte, aber allein die Grundsicherung nach SGB II trägt ein
 *  Viertel des Geldes. Eine Kopfzählung ließe drei kleine Beratungsangebote
 *  („viel Spielraum") schwerer wiegen als 54 Mio. € Rechtsanspruch. */
export type SpielraumBefund = {
  /** Jahr der Produktebene — nicht das Planjahr der Seite. */
  year: number;
  key: BereichSchluessel;
  produkte: number;
  /** Summe der Aufwendungen aller Produkte dieses Teilhaushalts, in Euro. */
  expense: number;
  /** Anteil am Aufwand je Stufe, 0–1. `ohne` = Produkte ohne Angabe. */
  anteil: Record<Spielraum | "ohne", number>;
  /** Die Stufe mit dem größten Aufwandsanteil, oder `null` bei Gleichstand
   *  bzw. wenn die Mehrheit ohne Angabe ist. */
  dominant: Spielraum | null;
  /** Die teuerste Aufgabe — ihr Wortlaut belegt, worauf der Bereich beruht. */
  groesste: Produkt | null;
};

function leerZaehler(): Record<Spielraum | "ohne", number> {
  return { niedrig: 0, mittel: 0, hoch: 0, ohne: 0 };
}

/** Produktzeilen eines Jahres zu Befunden je Teilhaushalt verdichten.
 *
 *  Der Teilhaushalt wird über `bereichKanon(sub_budget_name)` bestimmt, nicht über
 *  `sub_budget_no`: Die Nummer ist im Plan eine Positionsangabe und wurde zwischen
 *  Jahrgängen schon neu vergeben, der Name läuft durchs Wörterbuch. Zeilen
 *  ohne auflösbaren Namen fallen heraus — sie einem Bereich zuzuschlagen wäre
 *  geraten. */
export function spielraumBefunde(
  produkte: Produkt[], year: number,
): Map<BereichSchluessel, SpielraumBefund> {
  const aus = new Map<BereichSchluessel, SpielraumBefund>();
  for (const p of produkte) {
    if (p.year !== year) continue;
    const s = p.sub_budget_name ? bereichKanon(p.sub_budget_name).key : null;
    if (!s) continue;
    let b = aus.get(s);
    if (!b) {
      b = {
        year, key: s, produkte: 0, expense: 0,
        anteil: leerZaehler(), dominant: null, groesste: null,
      };
      aus.set(s, b);
    }
    const a = p.expenses ?? 0;
    b.produkte += 1;
    b.expense += a;
    b.anteil[p.controllability ?? "ohne"] += a;
    if (!b.groesste || a > (b.groesste.expenses ?? 0)) b.groesste = p;
  }
  for (const b of aus.values()) {
    const roh = { ...b.anteil };
    const summe = b.expense;
    for (const k of ["niedrig", "mittel", "hoch", "ohne"] as const) {
      b.anteil[k] = summe > 0 ? roh[k] / summe : 0;
    }
    // Strikt größer als jede andere Stufe UND als der Anteil ohne Angabe.
    // Bei Gleichstand bleibt `dominant` leer: „irgendeine" zu nehmen wäre eine
    // erfundene Aussage, und wo die Mehrheit des Geldes gar keine Angabe
    // trägt, hat die Stadt zu diesem Bereich schlicht nichts gesagt.
    let beste: Spielraum | null = null;
    let bester = roh.ohne;
    for (const s of SPIELRAUM_STUFEN) {
      if (roh[s] > bester) { bester = roh[s]; beste = s; }
      else if (roh[s] === bester) beste = null;
    }
    b.dominant = bester > 0 ? beste : null;
  }
  return aus;
}

export type Abgleich = "deckt" | "weicht" | "offen";

/** Deckt sich unsere Einordnung mit dem, was die Stadt selbst angibt?
 *  `offen`, solange es keine Produktebene für den Bereich gibt — das ist
 *  keine Übereinstimmung und darf auch nicht als eine gezählt werden. */
export function abgleich(
  stufe: PflichtStufe, befund: SpielraumBefund | undefined,
): Abgleich {
  if (!befund || befund.dominant === null) return "offen";
  return befund.dominant === STUFE_ERWARTET[stufe] ? "deckt" : "weicht";
}
