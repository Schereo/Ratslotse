"use client";

import type { CSSProperties } from "react";

/** Gestaffelter Listen-Einstieg — die Zeilen laufen versetzt ein statt als Block.
 *
 *  Bewusst als Klasse + Stil-Helfer statt als Wrapper-Komponente: Die Zeilen
 *  liegen in `<ul>`/`<tbody>`/Rastern, wo ein zusätzliches `<div>` das Layout
 *  bräche (ein `div` zwischen `ul` und `li` ist ungültig, in einem Grid wäre es
 *  eine eigene Rasterzelle). So bekommt die Zeile selbst die Bewegung:
 *
 *      <li className={cn(STAFFEL, "…")} style={staffelStil(i)}>
 *
 *  Die Bewegung selbst (Keyframe, Versatz, Stilllegung bei reduzierter
 *  Bewegung) steht in `app/globals.css` unter `.staffel-auf`. */
export const STAFFEL = "staffel-auf";

/** Ab hier laufen alle Zeilen gemeinsam ein.
 *
 *  Ohne Deckel wächst der Versatz linear mit der Listenlänge: Die 40. Zeile
 *  einer Trefferliste käme 1,8 s nach der ersten — das liest sich nicht als
 *  Lebendigkeit, sondern als lahmende Seite. Sechs Stufen (0–225 ms) reichen,
 *  damit das Auge eine Richtung sieht; alles darunter ist ohnehin nur noch
 *  Kulisse, weil es beim Erscheinen unter dem Falz liegt. */
const DECKEL = 5;

export function staffelStil(i: number): CSSProperties {
  return { "--staffel-i": Math.min(i, DECKEL) } as CSSProperties;
}
