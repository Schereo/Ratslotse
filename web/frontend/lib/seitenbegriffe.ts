/* Fachwörter am Wort auf Leseseiten (Punkt-Seite). Welche Wörter erklärt
   werden und wo die erste Fundstelle liegt, entscheidet der Server
   (`council/seitenbegriffe.py`) — hier wird nur noch an der gemeldeten Stelle
   geschnitten. */

import type { ApiAntwort } from "@/lib/vertrag";

export type SeitenBegriff = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["terms"]>[number];
export type Stueck = string | { text: string; begriff: SeitenBegriff };

/** Einen Text an den Fundstellen zerlegen, die zu GENAU diesem Text gehören:
 *  `snippet` ist ein wörtliches Stück davon, `offset` die Stelle des Worts
 *  darin. Texte ohne Fundstelle kommen unverändert zurück. */
export function zerlege(text: string, begriffe: readonly SeitenBegriff[]): Stueck[] {
  const stellen: { von: number; bis: number; begriff: SeitenBegriff }[] = [];
  for (const b of begriffe) {
    const i = b.snippet ? text.indexOf(b.snippet) : -1;
    if (i < 0) continue;
    let von = i + b.offset;
    // Der Server zählt Zeichen, der Browser UTF-16-Einheiten — vor einem
    // Emoji läge die Stelle daneben. Dann im Stück nach der Form suchen.
    if (text.slice(von, von + b.form.length) !== b.form) von = text.indexOf(b.form, i);
    if (von < 0 || von >= i + b.snippet.length) continue;
    const bis = von + b.form.length;
    if (stellen.some((s) => von < s.bis && bis > s.von)) continue;
    stellen.push({ von, bis, begriff: b });
  }
  if (stellen.length === 0) return [text];
  stellen.sort((a, b) => a.von - b.von);
  const aus: Stueck[] = [];
  let pos = 0;
  for (const s of stellen) {
    if (s.von > pos) aus.push(text.slice(pos, s.von));
    aus.push({ text: text.slice(s.von, s.bis), begriff: s.begriff });
    pos = s.bis;
  }
  if (pos < text.length) aus.push(text.slice(pos));
  return aus;
}
