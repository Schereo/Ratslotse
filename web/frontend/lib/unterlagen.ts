/* Die Gegenlese-Liste eines Punkts (docs/plan-vorlagen-aufbereiten.md, § 6.1):
   Art als Wort, Label ohne Datumspräfix, Lesestoff vorn und Belegmaterial
   eingeklappt. Reihenfolge und Nummern kommen vom Backend. */

export const ART_WORT: Record<string, string> = {
  template: "Vorlage",
  amendment: "Änderungsantrag",
  motion: "Antrag",
  report_request: "Berichtsantrag",
  synopsis: "Synopse",
  statute: "Satzung/Regelwerk",
  statement: "Stellungnahme",
  objection_table: "Abwägung",
  audit_report: "Prüfbericht",
  plan: "Plan",
  report: "Bericht/Anlage",
  presentation: "Präsentation",
  other: "Anlage",
  protocol: "Protokoll",
};

/** Was man liest, um die Aufbereitung gegenzulesen — der Rest ist Belegmaterial. */
const LESESTOFF = new Set(["template", "amendment", "motion", "report_request", "synopsis", "statute", "statement"]);

/** „2026-10-31 Reduzierung …", „2026 11 01. - Antrag …", „20241025 DIE GRÜNEN …" → ohne Datum. */
export function ohneDatum(label: string): string {
  const ohne = label
    .replace(/^\s*\d{4}[-. ]?\d{2}[-. ]?\d{2}\.?\s*(?:[-–]\s*)?/, "")
    .replace(/^\s*\d{6}\s+/, "")
    .trim();
  return ohne || label;
}

export interface ListenDoc { kind: string; doc_type?: string; label: string }

export function teileListe<T extends ListenDoc>(docs: T[]): { lesestoff: T[]; beleg: T[]; protokolle: T[] } {
  const lesestoff: T[] = [], beleg: T[] = [], protokolle: T[] = [];
  for (const d of docs) {
    if (d.kind === "protocol") protokolle.push(d);
    else if (LESESTOFF.has(d.doc_type ?? (d.kind === "template" ? "template" : "other"))) lesestoff.push(d);
    else beleg.push(d);
  }
  return { lesestoff, beleg, protokolle };
}

/** Unveränderte Stücke eines Wortdiffs auf den Kontext um die Änderung
 *  kürzen — an der Satzgrenze, wenn sie in Reichweite liegt: hinten bis zum
 *  ersten Satzende, vorn ab dem letzten. Erst ohne Satzgrenze in ``weit``
 *  Wörtern bleiben ``rand`` Wörter stehen. Mit fester Wortzahl fiel bei der
 *  GO-Änderung von Volt (Rat 02.11.2026) gerade „verkürzt werden" weg: „In
 *  dringenden Fällen kann sie auf sechs Stunden …" (Tim, 13.11.2026). */
export function kurzerDiff(diff: string[][], rand = 8, weit = 24): string[][] {
  // „am 10. September“: Eine Zahl mit Punkt ist ein Datum oder eine
  // Ordnungszahl, kein Satzende — der Rest endete sonst bei „… am 10. …“.
  const satzende = (wort: string) => /[.;:!?]["“”»)]?$/.test(wort) && !/^\d+\.$/.test(wort);
  const hinten = (w: string[]): number => {
    const i = w.findIndex(satzende);
    return i >= 0 && i < weit ? i + 1 : rand;
  };
  const vorn = (w: string[]): number => {
    for (let i = w.length - 2; i >= 0 && w.length - 1 - i <= weit; i--) if (satzende(w[i])) return i + 1;
    return w.length - rand;
  };
  return diff.map(([op, text], i) => {
    if (op !== "=") return [op, text];
    const w = text.split(" ");
    const erstes = i === 0, letztes = i === diff.length - 1;
    if (erstes && letztes) return [op, text];
    if (erstes) {
      const ab = vorn(w);
      return ab <= 0 ? [op, text] : [op, "… " + w.slice(ab).join(" ")];
    }
    if (letztes) {
      const bis = hinten(w);
      return bis >= w.length ? [op, text] : [op, w.slice(0, bis).join(" ") + " …"];
    }
    const bis = hinten(w), ab = vorn(w);
    return bis >= ab ? [op, text] : [op, `${w.slice(0, bis).join(" ")} … ${w.slice(ab).join(" ")}`];
  });
}

/** Die Aussagen eines Dossier-Abschnitts nach ihrer Art gruppiert, in der
 *  Reihenfolge des Servers. Die Art trägt die zweite Gliederungsstufe:
 *  „Nicht Teil des Beschlusses“, „Deckung“, „Termine“, „Noch offen“ stehen
 *  EINMAL als Zwischenzeile, statt vor jedem Satz wiederholt zu werden
 *  (Tim, 14.11.2026: „sehr viel nicht übersichtlich formatierter Text“).
 *
 *  `label` ist `null`, wo die Abschnitts-Überschrift schon alles sagt: bei der
 *  ersten, gewöhnlichen Gruppe — und bei „Termine“, wenn der Abschnitt nichts
 *  anderes trägt. */
const GRUPPEN_WORT: Record<string, string> = {
  not_included: "Nicht Teil des Beschlusses",
  coverage: "Deckung",
  dates: "Termine",
  open: "Noch offen",
};

export interface AussagenGruppe<T> { kind: string; label: string | null; aussagen: T[] }

export function aussagenGruppen<T extends { kind: string }>(aussagen: readonly T[]): AussagenGruppe<T>[] {
  const gruppen: AussagenGruppe<T>[] = [];
  for (const a of aussagen) {
    const letzte = gruppen[gruppen.length - 1];
    if (letzte && letzte.kind === a.kind) letzte.aussagen.push(a);
    else gruppen.push({ kind: a.kind, label: GRUPPEN_WORT[a.kind] ?? null, aussagen: [a] });
  }
  if (gruppen.length === 1 && gruppen[0].kind === "dates") gruppen[0].label = null;
  return gruppen;
}

/** „3 Angaben“ — die Zahl an der zugeklappten Zeile eines Abschnitts. */
export function angabenWort(n: number): string {
  return n === 1 ? "1 Angabe" : `${n} Angaben`;
}
