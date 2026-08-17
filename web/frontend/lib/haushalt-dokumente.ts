// Welches Dokument hinter einem Beleg steht — die Jahrgangs-Ebene der Quellen.
//
// `lib/haushalt-quellen.ts` beschreibt eine Quelle als Ganzes: was das
// Dokument ist, was wir daraus lesen, warum man es glauben kann. Diese
// Beschreibung ist redaktionell und kennt bewusst keine Jahrgänge — sie gilt
// für acht Jahresabschlüsse gleichermaßen.
//
// Genau daran scheiterte aber der Link darunter: „Dokument öffnen" führte auf
// `https://buergerinfo.oldenburg.de`, die Startseite des
// Ratsinformationssystems. Wer dort landet, sucht das Dokument selbst — ein
// Beleg, der sein Versprechen nicht einlöst, auf einer Seite, die auf
// Nachprüfbarkeit gebaut ist.
//
// Hier steht deshalb die andere Hälfte: je Quelle und Jahrgang das konkrete
// PDF, aus `GET /api/council/haushalt/dokumente` (Zuordnung und Begründung in
// `CouncilStore._DOKUMENT_QUELLEN`). Die statische Adresse bleibt die
// Rückfallebene — aber wo sie greift, heißt der Link auch nicht mehr
// „Dokument öffnen".

import type { QuellenSchluessel } from "@/lib/haushalt-quellen";

/** Der Ratsvorgang hinter einem Dokument: Welches Gremium wann worüber
 *  entschieden hat.
 *
 *  `outcome` wird ungefiltert durchgereicht — auch `vertagt` oder
 *  `abgelehnt`. Eine Zahl, deren Vorgang noch läuft, ist keine Zahl ohne
 *  Beleg; sie ist eine, bei der noch nichts entschieden ist, und das gehört
 *  dahin statt weggelassen. */
export type Ratsvorgang = {
  id: number;
  ksinr: number;
  kvonr: number | null;
  top: string | null;
  titel: string | null;
  outcome: string | null;
  vote: string | null;
  vorlage_nr: string | null;
  gremium: string | null;
  datum: string | null;
};

/** Ein konkretes Dokument hinter einer Quelle. `fundstelle` kommt aus
 *  `council_herkunft` und ist der eigentliche Gewinn: „Abschnitt 3.2" macht
 *  aus 300 Seiten eine Stelle, an der man nachschlägt.
 *
 *  `beschluss` ist die zweite Hälfte davon: nicht nur, in welchem Papier die
 *  Zahl steht, sondern welcher Ratsvorgang sie verabschiedet hat. `null` bei
 *  den Schichten von oldenburg.de und vom Landesamt — die hängen an keiner
 *  Vorlage. */
export type HaushaltDokument = {
  jahr: number | null;
  url: string;
  label: string | null;
  fundstelle: string | null;
  seite: number | null;
  beschluss: Ratsvorgang | null;
};

/** Nach Quellenschlüssel. Ein Schlüssel fehlt, wo wir kein Dokument haben. */
export type HaushaltDokumente = Partial<Record<QuellenSchluessel, HaushaltDokument[]>>;

export type DokumenteAntwort = { dokumente: HaushaltDokumente };

/** Das Dokument, auf das ein Beleg zeigt — samt allem, was danebengeschrieben
 *  gehört.
 *
 *  `abweichend` ist der Ehrlichkeits-Teil: Zeigt der Link nicht auf den
 *  Jahrgang, den die Seite gerade anzeigt (weil sie gar keinen hat oder weil
 *  für ihn kein Dokument vorliegt), muss das Jahr an den Link — sonst hält man
 *  ein PDF von 2024 für den Beleg einer Zahl von 2019.
 *
 *  `weitere` zählt die übrigen Dokumente desselben Jahrgangs. Bei der
 *  Produktebene sind das bis zu acht: Ein Jahrgang verteilt sich auf rund neun
 *  Teilhaushalts-Anlagen. Eine davon zu verlinken und die anderen zu
 *  verschweigen wäre wieder die halbe Wahrheit. */
export type Belegziel = {
  dokument: HaushaltDokument;
  /** Jahrgang des verlinkten Dokuments (`null`, wo die Quelle keinen führt). */
  jahrgang: number | null;
  abweichend: boolean;
  weitere: number;
};

/** Was der Rat mit dieser Vorlage gemacht hat, als Satzanfang.
 *
 *  Bewusst ein Verb je Ergebnis statt eines Etiketts: „beschlossen" und
 *  „vertagt" sind verschiedene Auskünfte, und ein neutrales „Status:
 *  vertagt" verlangt vom Leser die Übersetzung. Unbekannte oder fehlende
 *  Ergebnisse sagen „behandelt" — das stimmt immer und behauptet nichts. */
export function vorgangVerb(outcome: string | null): string {
  switch (outcome) {
    case "angenommen": return "beschlossen";
    case "abgelehnt": return "abgelehnt";
    case "vertagt": return "vertagt";
    case "zur_kenntnis": return "zur Kenntnis genommen";
    default: return "behandelt";
  }
}

function neuester(liste: HaushaltDokument[]): HaushaltDokument | null {
  if (!liste.length) return null;
  return liste.reduce((best, d) =>
    (d.jahr ?? -Infinity) > (best.jahr ?? -Infinity) ? d : best);
}

/** Das Dokument einer Quelle für das gerade gezeigte Jahr.
 *
 *  Reihenfolge der Auskünfte, von der besten zur ehrlichsten:
 *  1. Es gibt ein Dokument für genau dieses Jahr → das.
 *  2. Die Seite führt kein Jahr, oder für ihres liegt keines vor → das
 *     jüngste, mit `abweichend`, damit die Anzeige den Jahrgang anschreibt.
 *  3. Gar keines → `null`, und die Anzeige fällt auf die statische Adresse
 *     zurück (mit anderem Linktext, s. `zielText`). */
export function belegziel(
  dokumente: HaushaltDokumente | undefined,
  q: QuellenSchluessel,
  jahr: number | null | undefined,
): Belegziel | null {
  const liste = dokumente?.[q] ?? [];
  if (!liste.length) return null;
  const passend = jahr == null ? [] : liste.filter((d) => d.jahr === jahr);
  const dokument = passend.length ? passend[0] : neuester(liste);
  if (!dokument) return null;
  const gleicherJahrgang = liste.filter((d) => d.jahr === dokument.jahr);
  return {
    dokument,
    jahrgang: dokument.jahr,
    abweichend: jahr == null || dokument.jahr !== jahr,
    weitere: Math.max(0, gleicherJahrgang.length - 1),
  };
}

/** Alle Dokumente eines Jahrgangs — die Langfassung fürs Quellenverzeichnis,
 *  wo Platz für alle neun Teilhaushalte ist. */
export function belegzieleAlle(
  dokumente: HaushaltDokumente | undefined,
  q: QuellenSchluessel,
  jahr: number | null | undefined,
): HaushaltDokument[] {
  const ziel = belegziel(dokumente, q, jahr);
  if (!ziel) return [];
  return (dokumente?.[q] ?? []).filter((d) => d.jahr === ziel.jahrgang);
}

/** Wohin ein Link führt — abgelesen an der Adresse, nicht behauptet.
 *
 *  Der Grund für diese Funktion ist die Anforderung „kein toter Link": Wo wir
 *  kein Dokument haben, bleibt die statische Adresse stehen — aber dann darf
 *  darunter nicht „Dokument öffnen" stehen. Weil die Entscheidung an der URL
 *  hängt und nicht an einem Schalter, stimmt sie für die statische Adresse
 *  genauso wie für das nachgeschlagene PDF. */
export type Zielart = "dokument" | "datensatz" | "vorlage" | "ris" | "webseite";

export function zielart(url: string): Zielart {
  const u = url.toLowerCase();
  // Die Anlagen-URL des Ratsinformationssystems ist immer eine Datei.
  if (u.includes("/getfile.php")) return "dokument";
  if (u.includes(".csv")) return "datensatz";
  if (u.includes(".pdf")) return "dokument";
  // Die Seite einer Ratsvorlage listet ihre Anlagen — ein Dokument ist sie nicht.
  if (u.includes("vo0050.php") || u.includes("to0040.php") || u.includes("si0057.php")) {
    return "vorlage";
  }
  if (u.includes("buergerinfo.oldenburg.de")) return "ris";
  return "webseite";
}

const ZIELTEXT: Record<Zielart, string> = {
  dokument: "Dokument öffnen",
  datensatz: "Datensatz öffnen",
  vorlage: "Vorlage im Ratsinformationssystem öffnen",
  ris: "Im Ratsinformationssystem suchen",
  webseite: "Quelle öffnen",
};

/** Der Linktext, der zu dieser Adresse die Wahrheit sagt. */
export function zielText(url: string): string {
  return ZIELTEXT[zielart(url)];
}
