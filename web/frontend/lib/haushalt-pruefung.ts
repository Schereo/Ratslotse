// Datenschicht für „Was das Rechnungsprüfungsamt beanstandet".
//
// Quelle ist GET /api/council/haushalt/pruefberichte: eine Zeile je Randmarke
// aus den Schlussberichten 2017–2023, mit Textziffer, Seite und Deeplink.
//
// Hier stehen nur Gruppierungen — kein Bewerten, kein Zusammenfassen. Der Text
// einer Feststellung ist der Wortlaut des Rechnungsprüfungsamts und wird
// nirgends umformuliert; wo etwas eingeordnet werden muss, sagt das die Seite
// selbst und nicht diese Datei.

/** Eine Prüfungsfeststellung, wie der Bericht sie mit einer Randmarke
 *  auszeichnet. `mark` ist B/WB/H/K, `mark_name` und `mark_explanation`
 *  sind die Legende **dieses** Jahrgangs — nicht unsere Formulierung. */
export type Feststellung = {
  year: number;
  seq: number;
  mark: string;
  mark_name: string;
  mark_explanation: string | null;
  text_number: string;
  section: string;
  /** Schlüssel, unter dem dieselbe Sache über Jahrgänge zusammenfindet. */
  chain: string | null;
  page: number | null;
  text: string;
  /** Der Absatz, der im Bericht direkt darauf folgt — dort steht oft die
   *  Antwort der Verwaltung. Getrennt geführt, damit nicht als Beanstandung
   *  gilt, was der Bericht gar nicht so gemeint hat. */
  follow_paragraph: string | null;
  source_label: string | null;
  source_url: string | null;
};

export type PruefberichtDaten = {
  years: number[];
  legende: Record<string, { name: string; explanation: string | null }>;
  feststellungen: Feststellung[];
  /** Jahre mit ausgelesenem Jahresabschluss, aber ohne Schlussbericht. */
  ohne_bericht: number[];
};

/** Reihenfolge der Marken auf der Seite: schwerste zuerst.
 *
 *  Bewusst NICHT die Reihenfolge der Legende (dort B, WB, H, K) — eine
 *  wiederholte Beanstandung ist die schwerere Aussage als eine erstmalige,
 *  und sie ist der Grund, warum es diese Seite gibt. Die Legende selbst wird
 *  im Wortlaut des Berichts wiedergegeben, nur eben in dieser Ordnung. */
export const MARKEN_REIHE = ["WB", "B", "K", "H"] as const;

export function markeRang(mark: string): number {
  const i = (MARKEN_REIHE as readonly string[]).indexOf(mark);
  return i < 0 ? MARKEN_REIHE.length : i;
}

/** Eine über Jahre laufende Sache: derselbe Abschnitt, mehrere Jahrgänge. */
export type Kette = {
  key: string;
  /** Titel aus dem jüngsten Jahrgang — Abschnitte werden umbenannt. */
  titel: string;
  years: number[];
  eintraege: Feststellung[];
  /** Jahre, in denen der Abschnitt eine Beanstandung trug (B oder WB). */
  beanstandet: number[];
};

/** Die Ketten, in denen mindestens einmal eine **wiederholte** Beanstandung
 *  steht — nach Länge sortiert, längste zuerst.
 *
 *  Warum WB und nicht einfach „mehrfach vorgekommen": Die Marke WB ist die
 *  Aussage des Rechnungsprüfungsamts selbst, dass ein Mangel aus Vorjahren
 *  noch offen ist. Sie zu verwenden heißt, den Bericht zu zitieren statt zu
 *  interpretieren. Ein Abschnitt, der in mehreren Jahren nur Hinweise trägt,
 *  ist etwas anderes und taucht hier nicht auf.
 *
 *  Der Kettenschlüssel kommt aus dem Backend (Abschnittstitel ohne
 *  Klammerzusätze). Die Textziffer taugt dafür nicht — sie verschiebt sich
 *  zwischen den Jahrgängen. */
export function wiederholungsketten(feststellungen: Feststellung[]): Kette[] {
  const nach = new Map<string, Feststellung[]>();
  for (const f of feststellungen) {
    if (!f.chain) continue;
    const liste = nach.get(f.chain);
    if (liste) liste.push(f);
    else nach.set(f.chain, [f]);
  }
  const ketten: Kette[] = [];
  for (const [key, eintraege] of nach) {
    if (!eintraege.some((f) => f.mark === "WB")) continue;
    const sortiert = [...eintraege].sort((a, b) => a.year - b.year || a.seq - b.seq);
    const years = [...new Set(sortiert.map((f) => f.year))];
    const beanstandet = [...new Set(
      sortiert.filter((f) => f.mark === "B" || f.mark === "WB").map((f) => f.year))];
    ketten.push({
      key,
      titel: sortiert[sortiert.length - 1].section,
      years, eintraege: sortiert, beanstandet,
    });
  }
  return ketten.sort((a, b) =>
    b.beanstandet.length - a.beanstandet.length
    || (b.beanstandet.at(-1) ?? 0) - (a.beanstandet.at(-1) ?? 0)
    || a.titel.localeCompare(b.titel, "de"));
}

/** Feststellungen eines Jahrgangs, nach Textziffer gebündelt — so steht auf
 *  der Seite dieselbe Gliederung wie im Bericht. */
export function nachAbschnitt(
  feststellungen: Feststellung[], year: number,
): { text_number: string; section: string; eintraege: Feststellung[] }[] {
  const gruppen: { text_number: string; section: string; eintraege: Feststellung[] }[] = [];
  for (const f of feststellungen.filter((x) => x.year === year).sort((a, b) => a.seq - b.seq)) {
    const letzte = gruppen[gruppen.length - 1];
    if (letzte && letzte.text_number === f.text_number) letzte.eintraege.push(f);
    else gruppen.push({ text_number: f.text_number, section: f.section, eintraege: [f] });
  }
  return gruppen;
}

/** Wie oft welche Marke vorkommt — für „die meisten sind Hinweise". */
export function markenZaehlen(feststellungen: Feststellung[]): Record<string, number> {
  const zahl: Record<string, number> = {};
  for (const f of feststellungen) zahl[f.mark] = (zahl[f.mark] ?? 0) + 1;
  return zahl;
}

/** Deeplink auf die Fundstelle im Originaldokument.
 *
 *  Das Bürgerinfo liefert das PDF ohne Seitenanker aus; der `#page=`-Zusatz
 *  wird aber von jedem eingebauten PDF-Betrachter ausgewertet. Wo er ins
 *  Leere läuft, landet man auf Seite 1 desselben Dokuments — die Seitenzahl
 *  steht zusätzlich im Klartext daneben. */
export function belegLink(f: Feststellung): string | null {
  if (!f.source_url) return null;
  return f.page ? `${f.source_url}#page=${f.page}` : f.source_url;
}
