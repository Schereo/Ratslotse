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
// PDF, aus `GET /api/council/budget/documents` (Zuordnung und Begründung in
// `CouncilStore._DOKUMENT_QUELLEN`). Die statische Adresse bleibt die
// Rückfallebene — aber wo sie greift, heißt der Link auch nicht mehr
// „Dokument öffnen".

import type { Jahrgaenge, QuellenSchluessel } from "@/lib/haushalt-quellen";

// Der Ratsvorgang ist kein Typ dieser Seite: Er hängt an `council_herkunft`
// und kommt an zwei Endpunkten heraus (hier und bei `get_herkunft`). Deshalb
// steht er neutral in `lib/herkunft.ts` — siehe die Begründung dort.
import type { Ratsvorgang } from "@/lib/herkunft";

export type { Ratsvorgang };

/** Ein konkretes Dokument hinter einer Quelle. `citation` kommt aus
 *  `council_herkunft` und ist der eigentliche Gewinn: „Abschnitt 3.2" macht
 *  aus 300 Seiten eine Stelle, an der man nachschlägt.
 *
 *  `beschluss` ist die zweite Hälfte davon: nicht nur, in welchem Papier die
 *  Zahl steht, sondern welcher Ratsvorgang sie verabschiedet hat. `null` bei
 *  den Schichten von oldenburg.de und vom Landesamt — die hängen an keiner
 *  Vorlage. */
export type HaushaltDokument = {
  year: number | null;
  url: string;
  label: string | null;
  citation: string | null;
  page: number | null;
  official_text: Ratsvorgang | null;
};

/** Nach Quellenschlüssel. Ein Schlüssel fehlt, wo wir kein Dokument haben. */
export type HaushaltDokumente = Partial<Record<QuellenSchluessel, HaushaltDokument[]>>;

export type DokumenteAntwort = {
  documents: HaushaltDokumente;
  /** Je Quelle die Jahrgänge, die wirklich im Bestand stehen — die Grundlage
   *  des Datenstands im Quellenverzeichnis (s. `standText`). Kommt aus
   *  derselben Antwort, weil es an derselben Stelle gebraucht wird. */
  editions: Jahrgaenge;
};

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
  budget_year: number | null;
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
    case "accepted": return "beschlossen";
    case "rejected": return "abgelehnt";
    case "postponed": return "vertagt";
    case "noted": return "zur Kenntnis genommen";
    default: return "behandelt";
  }
}

function neuester(liste: HaushaltDokument[]): HaushaltDokument | null {
  if (!liste.length) return null;
  return liste.reduce((best, d) =>
    (d.year ?? -Infinity) > (best.year ?? -Infinity) ? d : best);
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
  year: number | null | undefined,
): Belegziel | null {
  const liste = dokumente?.[q] ?? [];
  if (!liste.length) return null;
  const passend = year == null ? [] : liste.filter((d) => d.year === year);
  const dokument = passend.length ? passend[0] : neuester(liste);
  if (!dokument) return null;
  // Gezählt werden DATEIEN, nicht Fundstellen: Der Satz „Alle 3 Dokumente im
  // Verzeichnis" führte sonst zu einem Verzeichnis mit einem Eintrag, weil
  // dieselbe Anlage dreimal gezählt worden war (s. `jeAdresseEinmal`).
  const gleicherJahrgang = jeAdresseEinmal(
    liste.filter((d) => d.year === dokument.year));
  return {
    dokument,
    budget_year: dokument.year,
    abweichend: year == null || dokument.year !== year,
    weitere: Math.max(0, gleicherJahrgang.length - 1),
  };
}

/** Alle Dokumente eines Jahrgangs — die Langfassung fürs Quellenverzeichnis,
 *  wo Platz für alle neun Teilhaushalte ist.
 *
 *  JE ADRESSE EINMAL. Die Antwort führt eine Zeile je *Fundstelle*, nicht je
 *  Datei, und mehrere Fundstellen liegen oft in demselben PDF: Die
 *  Gebührenbedarfsberechnung 2026 kam dreimal (Abfallbehandlung,
 *  Abfallsammlung, Straßenreinigung — eine Anlage), der Stellenplan zweimal
 *  (Teil A und Teil B). Im Verzeichnis stünden dann drei Links, die alle
 *  dasselbe öffnen.
 *
 *  Für den Beleg-Chip bleibt die Unterscheidung erhalten: `belegziel` wählt
 *  weiter die Zeile mit IHRER Fundstelle, und die steht dann auch dran. Hier
 *  geht es um die Frage „welche Papiere sind das?", und darauf ist dieselbe
 *  Datei eine Antwort und nicht drei. */
export function belegzieleAlle(
  dokumente: HaushaltDokumente | undefined,
  q: QuellenSchluessel,
  year: number | null | undefined,
): HaushaltDokument[] {
  const ziel = belegziel(dokumente, q, year);
  if (!ziel) return [];
  return jeAdresseEinmal(
    (dokumente?.[q] ?? []).filter((d) => d.year === ziel.budget_year));
}

/** Aus einer Liste von Fundstellen die Liste der Dateien — Reihenfolge bleibt. */
function jeAdresseEinmal(liste: HaushaltDokument[]): HaushaltDokument[] {
  const gesehen = new Set<string>();
  const aus: HaushaltDokument[] = [];
  for (const d of liste) {
    if (gesehen.has(d.url)) continue;
    gesehen.add(d.url);
    aus.push(d);
  }
  return aus;
}

/** Ein nummerierter Eintrag im Quellenverzeichnis.
 *
 *  Entweder EIN Papier (`dokument` gesetzt) oder eine Quellenart als Ganzes
 *  (`dokument === null`, `dokumente` trägt dann ihre Papiere). */
export type NummerEintrag = {
  nr: number;
  q: QuellenSchluessel;
  dokument: HaushaltDokument | null;
  dokumente: HaushaltDokument[];
};

/** Die Nummern einer Seite: was trägt welche Ziffer.
 *
 *  WARUM DIE NUMMERN NICHT MEHR DIE QUELLENARTEN ZÄHLEN (Tim, 21.08.2026):
 *
 *      „Es steht eine 1, dann stehen da mehrere Quellen drunter. […] Ich will
 *      als Leser das Gefühl haben, die haben viele Quellen herangezogen, und
 *      hier sieht es auf den ersten Blick nur aus, als wäre es eine."
 *
 *  Auf `/haushalt/betriebe` stand „1 Quelle" über fünf Wirtschaftsplänen aus
 *  fünf Betrieben. Die Zahl war nicht falsch gerechnet — sie zählte
 *  Quellen*arten*, und das ging auf, solange eine Art ein Papier bedeutete.
 *  Hier bedeutet sie fünf, und dann zählt sie die Beleglage klein.
 *
 *  ABER NICHT ÜBERALL EINZELN. Die Produktebene eines Jahrgangs verteilt sich
 *  auf zehn Teilhaushalts-Anlagen, und ein Satz wie „das ist die Angabe der
 *  Stadt, keine Bewertung von uns" stützt sich auf alle zehn zusammen. Zehn
 *  Nummern zu vergeben und den Chip auf eine davon zu setzen wäre **weniger**
 *  genau, nicht mehr. Deshalb entscheidet die Seite über `jeDokument`, und die
 *  Regel dahinter ist inhaltlich: Eine eigene Nummer bekommt ein Papier dort,
 *  wo eine einzelne Aussage auf genau ihm ruht. */
export function nummerierung(
  key: readonly QuellenSchluessel[],
  jeDokument: JeDokument,
  dokumente: HaushaltDokumente | undefined,
  year: number | null | undefined,
): NummerEintrag[] {
  const aus: NummerEintrag[] = [];
  for (const q of key) {
    const benutzte = jeDokument[q];
    if (benutzte && benutzte.length > 1) {
      // DIE SEITE SAGT, WELCHE PAPIERE SIE BENUTZT — nicht der Jahrgang.
      //
      // Ein erster Versuch nahm die Dokumente des gezeigten Jahres. Auf
      // `/haushalt/betriebe` stimmt das für vier von sieben Betrieben: Den
      // Stadthafen gibt es seit 2020 nicht mehr, die Stadion-Planung endete
      // 2024. Ihre Karten fanden ihr Papier in der Jahrgangsliste nicht und
      // trugen deshalb alle die Ziffer 1 — die des AWB-Plans 2026.
      const alle = dokumente?.[q] ?? [];
      for (const url of benutzte) {
        const d = alle.find((x) => x.url === url);
        if (d) aus.push({ nr: aus.length + 1, q, dokument: d, dokumente: [] });
      }
      // Die Papiere der Gruppe stehen erst fest, wenn alle gefunden sind.
      const gruppe = aus.filter((e) => e.q === q).map((e) => e.dokument!);
      for (const e of aus) if (e.q === q) e.dokumente = gruppe;
      if (gruppe.length) continue;
      // Kein einziges wiedergefunden: lieber die Art als gar keine Nummer.
    }
    aus.push({
      nr: aus.length + 1, q, dokument: null,
      dokumente: belegzieleAlle(dokumente, q, year),
    });
  }
  return aus;
}

/** Je Quellenart die Adressen der Papiere, auf denen einzelne Aussagen der
 *  Seite ruhen — in der Reihenfolge, in der sie nummeriert werden sollen. */
export type JeDokument = Partial<Record<QuellenSchluessel, string[]>>;

/** Die Nummer, die an einer Zahl stehen soll.
 *
 *  `url` ist das Papier, auf dem genau diese Zahl ruht (aus der `herkunft_id`
 *  ihrer Zeile). Fehlt es oder ist die Art nicht einzeln nummeriert, gilt die
 *  Nummer der Art. Gibt `null`, wenn die Seite die Quelle nicht anmeldet —
 *  dann rendert der Chip nichts, und `Beleg` sagt das in der Entwicklung. */
export function nummerFuer(
  eintraege: NummerEintrag[],
  q: QuellenSchluessel,
  url?: string | null,
): NummerEintrag | null {
  const derArt = eintraege.filter((e) => e.q === q);
  if (!derArt.length) return null;
  if (url) {
    const exact = derArt.find((e) => e.dokument?.url === url);
    if (exact) return exact;
  }
  return derArt[0];
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
