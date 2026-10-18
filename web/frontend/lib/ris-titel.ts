/** Das Ergebnis, das das Ratsinformationssystem an den TOP-Titel hängt.
 *
 *  Gemessen am 09.10.2026: Knapp die Hälfte der 21.649 Titel endet auf
 *  „Beschluss: ungeändert beschlossen" (oft als „- Beschluss Beschluss: …",
 *  manchmal samt „Abstimmung: Ja: 11, Nein: 0 …"). Neben der Ergebnis-Marke
 *  steht das Ergebnis damit doppelt — und auf dem Telefon kostete es bis zu
 *  vier Zeilen je Punkt.
 *
 *  Nur zur ANZEIGE und nur dort, wo das Ergebnis daneben steht; gespeichert
 *  und durchsucht wird der volle Titel. „Beschlussantrag", „Beschlussvorlage"
 *  bleiben — die sagen, was für ein Papier es ist. */
export function ohneRisErgebnis(titel: string): string {
  const ohne = titel
    .replace(/\s+Beschluss:\s.*$/s, "")
    .replace(/\s*-\s*Beschluss\s*-?\s*$/, "")
    .trimEnd();
  // Bliebe nichts Sinnvolles übrig, lieber den vollen Titel.
  return ohne.length >= 3 ? ohne : titel;
}
