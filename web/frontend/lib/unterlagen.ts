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
