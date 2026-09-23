/**
 * `*kursiv*` in Antworttexten erkennen.
 *
 * `AntwortText` (components/qa-bausteine.tsx) kannte bis 09/2026 nur
 * `**fett**`. Gemini 2.5 Flash setzte praktisch nie Kursivschrift; GPT-6 Luna
 * (Lotti und Frag den Rat seit #1501) tut es regelmäßig — „im
 * *Ergebnishaushalt*“ stand dann mit Sternchen im Fenster (Tim, 23.09.2026).
 *
 * Die Regel ist bewusst eng, weil ein Sternchen auch etwas anderes sein kann:
 * Das öffnende `*` steht am Anfang oder nach einem Nicht-Wortzeichen, das
 * schließende vor einem Nicht-Wortzeichen oder am Ende, und direkt innen
 * steht kein Leerzeichen. So bleiben „Mitarbeiter*innen“, „3 * 4“ und eine
 * Aufzählung „* Punkt“ Text. Ein offenes `*` beim Streamen bleibt ebenfalls
 * Text, bis sein Gegenstück kommt.
 */
export type KursivTeil = { text: string; kursiv: boolean };

const KURSIV = /(^|[^\p{L}\p{N}*])\*(?=\S)([^*\n]*?\S)\*(?=$|[^\p{L}\p{N}*])/gu;

export function teileKursiv(text: string): KursivTeil[] {
  const teile: KursivTeil[] = [];
  let pos = 0;
  for (const m of text.matchAll(KURSIV)) {
    const start = (m.index ?? 0) + m[1].length;
    if (start > pos) teile.push({ text: text.slice(pos, start), kursiv: false });
    teile.push({ text: m[2], kursiv: true });
    pos = start + m[2].length + 2;
  }
  if (pos < text.length) teile.push({ text: text.slice(pos), kursiv: false });
  return teile.length ? teile : [{ text, kursiv: false }];
}
