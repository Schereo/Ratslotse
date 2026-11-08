/** Auswahl aus den Wortbeiträgen zu einer Antwort.
 *
 *  Zu einer Frage kommen schnell 30, 40 Beiträge zusammen. Alle aufgeklappt
 *  verdrängten sie die Pressemitteilungen darunter bis ans Ende einer langen
 *  Liste, und oft standen fünfmal dieselbe Fraktion hintereinander (Tim
 *  08.11.2026). Gezeigt werden deshalb zuerst wenige — und zwar aus
 *  möglichst vielen verschiedenen Stimmen.
 */

type Beitrag = { speaker: string | null; party: string | null };

/** Wessen Stimme ein Beitrag ist: die Fraktion, sonst die Person (die
 *  Verwaltung trägt keine Partei), sonst „ohne". */
export function stimme(b: Beitrag): string {
  return (b.party?.trim() || b.speaker?.trim() || "ohne").toLowerCase();
}

/** Bis zu `anzahl` Beiträge, möglichst jede Stimme einmal.
 *
 *  Erst je Stimme der früheste Beitrag (die Liste kommt in der Reihenfolge,
 *  in der die Antwort sie nutzt), dann wird mit den übrigen in derselben
 *  Reihenfolge aufgefüllt. Ausgegeben wird in der ursprünglichen Reihenfolge
 *  — die Auswahl springt nicht durcheinander.
 */
export function vielfaeltigeAuswahl<T extends Beitrag>(beitraege: T[], anzahl: number): T[] {
  if (beitraege.length <= anzahl) return beitraege;
  const gewaehlt = new Set<number>();
  const gesehen = new Set<string>();
  beitraege.forEach((b, i) => {
    if (gewaehlt.size >= anzahl) return;
    const s = stimme(b);
    if (!gesehen.has(s)) { gesehen.add(s); gewaehlt.add(i); }
  });
  for (let i = 0; i < beitraege.length && gewaehlt.size < anzahl; i++) gewaehlt.add(i);
  return beitraege.filter((_, i) => gewaehlt.has(i));
}
