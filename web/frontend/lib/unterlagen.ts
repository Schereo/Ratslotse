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
  const satzende = (wort: string) => /[.;:!?]["“”»)]?$/.test(wort);
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
