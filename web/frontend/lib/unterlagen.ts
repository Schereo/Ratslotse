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
 *  kürzen: vorn die letzten, hinten die ersten Wörter, dazwischen beide Enden. */
export function kurzerDiff(diff: string[][], rand = 8): string[][] {
  return diff.map(([op, text], i) => {
    if (op !== "=") return [op, text];
    const w = text.split(" ");
    if (w.length <= rand * 2) return [op, text];
    if (i === 0) return [op, "… " + w.slice(-rand).join(" ")];
    if (i === diff.length - 1) return [op, w.slice(0, rand).join(" ") + " …"];
    return [op, `${w.slice(0, rand).join(" ")} … ${w.slice(-rand).join(" ")}`];
  });
}
