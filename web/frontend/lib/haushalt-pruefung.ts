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
 *  auszeichnet. `marke` ist B/WB/H/K, `marke_name` und `marke_erlaeuterung`
 *  sind die Legende **dieses** Jahrgangs — nicht unsere Formulierung. */
export type Feststellung = {
  jahr: number;
  lfd: number;
  marke: string;
  marke_name: string;
  marke_erlaeuterung: string | null;
  textziffer: string;
  abschnitt: string;
  /** Schlüssel, unter dem dieselbe Sache über Jahrgänge zusammenfindet. */
  kette: string | null;
  seite: number | null;
  text: string;
  /** Der Absatz, der im Bericht direkt darauf folgt — dort steht oft die
   *  Antwort der Verwaltung. Getrennt geführt, damit nicht als Beanstandung
   *  gilt, was der Bericht gar nicht so gemeint hat. */
  folgeabsatz: string | null;
  quelle_label: string | null;
  quelle_url: string | null;
};

export type PruefberichtDaten = {
  jahre: number[];
  legende: Record<string, { name: string; erlaeuterung: string | null }>;
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

export function markeRang(marke: string): number {
  const i = (MARKEN_REIHE as readonly string[]).indexOf(marke);
  return i < 0 ? MARKEN_REIHE.length : i;
}

/** Eine über Jahre laufende Sache: derselbe Abschnitt, mehrere Jahrgänge. */
export type Kette = {
  schluessel: string;
  /** Titel aus dem jüngsten Jahrgang — Abschnitte werden umbenannt. */
  titel: string;
  jahre: number[];
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
    if (!f.kette) continue;
    const liste = nach.get(f.kette);
    if (liste) liste.push(f);
    else nach.set(f.kette, [f]);
  }
  const ketten: Kette[] = [];
  for (const [schluessel, eintraege] of nach) {
    if (!eintraege.some((f) => f.marke === "WB")) continue;
    const sortiert = [...eintraege].sort((a, b) => a.jahr - b.jahr || a.lfd - b.lfd);
    const jahre = [...new Set(sortiert.map((f) => f.jahr))];
    const beanstandet = [...new Set(
      sortiert.filter((f) => f.marke === "B" || f.marke === "WB").map((f) => f.jahr))];
    ketten.push({
      schluessel,
      titel: sortiert[sortiert.length - 1].abschnitt,
      jahre, eintraege: sortiert, beanstandet,
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
  feststellungen: Feststellung[], jahr: number,
): { textziffer: string; abschnitt: string; eintraege: Feststellung[] }[] {
  const gruppen: { textziffer: string; abschnitt: string; eintraege: Feststellung[] }[] = [];
  for (const f of feststellungen.filter((x) => x.jahr === jahr).sort((a, b) => a.lfd - b.lfd)) {
    const letzte = gruppen[gruppen.length - 1];
    if (letzte && letzte.textziffer === f.textziffer) letzte.eintraege.push(f);
    else gruppen.push({ textziffer: f.textziffer, abschnitt: f.abschnitt, eintraege: [f] });
  }
  return gruppen;
}

/** Wie oft welche Marke vorkommt — für „die meisten sind Hinweise". */
export function markenZaehlen(feststellungen: Feststellung[]): Record<string, number> {
  const zahl: Record<string, number> = {};
  for (const f of feststellungen) zahl[f.marke] = (zahl[f.marke] ?? 0) + 1;
  return zahl;
}

/** Deeplink auf die Fundstelle im Originaldokument.
 *
 *  Das Bürgerinfo liefert das PDF ohne Seitenanker aus; der `#page=`-Zusatz
 *  wird aber von jedem eingebauten PDF-Betrachter ausgewertet. Wo er ins
 *  Leere läuft, landet man auf Seite 1 desselben Dokuments — die Seitenzahl
 *  steht zusätzlich im Klartext daneben. */
export function belegLink(f: Feststellung): string | null {
  if (!f.quelle_url) return null;
  return f.seite ? `${f.quelle_url}#page=${f.seite}` : f.quelle_url;
}
