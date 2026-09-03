/**
 * Beleg-Marker und Datumsformat einer „Frag den Rat"-Antwort — reine Logik,
 * bewusst OHNE "use client": Die Teilen-Seite (`app/g`) ist eine Server-
 * Komponente und kann aus einem Client-Modul zwar Komponenten rendern, aber
 * keine Funktionen aufrufen (dort kommen nur Client-Referenzen an).
 */

// Zitat-Klammern im Antworttext. Spiegelt council/qa.py (_CITE_RE /
// citation_ids) — beide Seiten MÜSSEN dieselbe Regel anwenden, sonst laufen
// Fußnoten-Nummerierung und die vom Server gemeldeten `cited` auseinander.
export const CITE_SOURCE = String.raw`\[\d[^\]\n]{0,160}\]`;
export const CITE_RE = new RegExp(CITE_SOURCE, "g");
export const CITE_EXACT_RE = new RegExp(`^${CITE_SOURCE}$`);

// Anlagen-Belege des Recherche-Berichts: „[A1]" verweist auf die Anlage mit
// nr = 1 (council/qa.py `_anlagen_block`). Bewusst ein eigener Marker — die
// Beschluss-Klammer MUSS mit einer Ziffer beginnen, sonst würde normaler
// Klammertext zur Fußnote. Gerendert wird daraus a, b, c … (Buchstaben statt
// Zahlen, damit man Gutachten und Beschluss im Text auseinanderhält).
export const ANL_SOURCE = String.raw`\[A\d{1,2}\]`;
export const ANL_RE = new RegExp(ANL_SOURCE, "g");
export const ANL_EXACT_RE = new RegExp(`^${ANL_SOURCE}$`);
export const BELEG_SPLIT_RE = new RegExp(`(${CITE_SOURCE}|${ANL_SOURCE})`, "g");

export function citationIds(bracket: string): number[] {
  const inner = bracket.slice(1, -1);
  if (/^[\d,\s]+$/.test(inner)) return (inner.match(/\d+/g) ?? []).map(Number);
  const m = /^\s*(\d+)/.exec(inner);
  return m ? [Number(m[1])] : [];
}

/** Anlagen-Nummer aus „[A3]". */
export function anlagenNr(bracket: string): number {
  return Number(bracket.slice(2, -1));
}

/** a, b, c … — mehr als 26 Anlagen liefert die Recherche nie (top_k = 6). */
export const anlagenBuchstabe = (i: number) => String.fromCharCode(97 + (i % 26));

/** Anlagen-Fußnoten eines Antworttexts: nr → Buchstabe, in Reihenfolge des
 *  Auftauchens. Nur Marker, zu denen es wirklich eine Anlage gibt — ein
 *  halluziniertes „[A9]" bekommt keinen Buchstaben und wird beim Rendern
 *  ersatzlos geschluckt (wie die ungültigen [id] serverseitig). */
export function anlagenBuchstaben(
  text: string, attachments: { nr?: number | null }[] | undefined | null,
): Map<number, string> {
  const vorhanden = new Set((attachments ?? []).map((a, i) => a.nr ?? i + 1));
  const map = new Map<number, string>();
  for (const g of text.matchAll(ANL_RE)) {
    const nr = anlagenNr(g[0]);
    if (vorhanden.has(nr) && !map.has(nr)) map.set(nr, anlagenBuchstabe(map.size));
  }
  return map;
}

/** ISO-Daten im Antworttext eindeutschen: Der Kontext liefert die Daten zwar
 *  deutsch (council/qa.py `_datum_de`), aber das Modell rechnet gelegentlich
 *  selbst und schreibt dann „am 2026-06-01" — und alte gespeicherte Antworten
 *  tragen die ISO-Form ohnehin. Nur plausible Kalenderdaten werden angefasst. */
export function datenEindeutschen(text: string): string {
  return text.replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, (ganz, j, m, t) =>
    Number(m) >= 1 && Number(m) <= 12 && Number(t) >= 1 && Number(t) <= 31
      ? `${t}.${m}.${j}` : ganz);
}

export const fmtDatumKurz = (d?: string | null) =>
  d ? new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "";
