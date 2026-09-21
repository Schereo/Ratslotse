/**
 * Auf welchen Seiten Lotti von selbst anklopfen darf.
 *
 * **Warum diese Liste hier steht, obwohl die Wahrheit im Backend liegt.** Der
 * Anstupser entscheidet, BEVOR irgendein Endpunkt gerufen wird — er wartet
 * ja gerade darauf, dass jemand liest, ohne zu fragen. Ein Abruf nur für die
 * Frage „darf ich hier?" wäre ein Netzaufruf je Seitenaufruf für eine
 * Antwort, die sich nie ändert.
 *
 * Also eine Kopie — aber eine, die nicht auseinanderlaufen kann:
 * `tests/test_anstupser_seiten.py` hält sie Zeile für Zeile gegen
 * `kern/knowledge.py` (`PageKnowledge.nudge`). Wer dort eine Seite freigibt
 * und hier vergisst, bekommt einen roten Test mit dem fertigen Befehl.
 *
 * **Die Auswahl selbst** ist eine inhaltliche: Angeklopft wird nur, wo man
 * LIEST — Haushalt, Beschlüsse, Sitzungen, Themen, Orte, Karte. Nicht auf
 * „Heute" (dort überfliegt man), nicht auf `/fragen` (dort fragt man schon),
 * nicht in Listen, die man abarbeitet (Merkliste, Abos), und nicht im Quiz.
 */
export const ANSTUPSER_SEITEN: readonly string[] = [
  "/council/decision",
  "/council/ideen",
  "/council/ort",
  "/council/person",
  "/council/sitzung",
  "/council/thema",
  "/council?tab=analysis",
  "/council?tab=decisions",
  "/council?tab=sessions",
  "/council?tab=themen",
  "/haushalt",
  "/haushalt/bereich",
  "/haushalt/einnahmen",
  "/haushalt/investitionen",
  "/haushalt/konzern",
  "/haushalt/mitreden",
  "/haushalt/personal",
  "/haushalt/pflicht",
  "/haushalt/plan-ist",
  "/haushalt/produkte",
  "/haushalt/pruefung",
  "/haushalt/schulden",
  "/haushalt/steuer",
  "/haushalt/vergleich",
  "/karte",
] as const;

/** Darf auf dieser (normalisierten) Route angeklopft werden? */
export function anstupserErlaubt(route: string): boolean {
  return ANSTUPSER_SEITEN.includes(route);
}
