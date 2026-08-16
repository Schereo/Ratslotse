// Das Investitionsprogramm — Typen und Rechenwege für den Block „Die einzelnen
// Vorhaben" auf /haushalt/investitionen.
//
// Die Ebene unter `haushalt-investitionen.ts`: dort „Schule und Bildung:
// 8,3 Mio. €", hier „BBS Haarentor: Ausstattung".
//
// DREI FALLEN, die jeden Rechenweg hier betreffen:
//
// 1. DIESE ZAHLEN SIND NICHT DIE AUS `haushalt-investitionen.ts`, auch wenn
//    beide „Investitionen" heißen und dieselbe Teilhaushaltsnummer tragen. Das
//    Investitionsprogramm führt die GESAMTKOSTEN eines Vorhabens über alle
//    Jahre, der Finanzhaushalt die ZAHLUNGEN EINES JAHRES. Dazu gehören die zu
//    aktivierenden Eigenleistungen nur ins Programm — das Dokument sagt diese
//    Abweichung in einer Fußnote selbst an. Die beiden Summen nebeneinander zu
//    stellen und die Differenz zu zeigen wäre eine erfundene Aussage; die
//    Verbindung zwischen den Blöcken ist deshalb eine NAVIGATION („welche
//    Vorhaben stecken in diesem Bereich?"), keine Rechnung.
//
// 2. DIE SUMME KOMMT AUS DEM DOKUMENT, NICHT VON UNS. `teilhaushalte` ist die
//    Gesamtsumme, die der Abschnitt selbst ausweist — und das Ziel der
//    Rechenprobe beim Einlesen. Wer die Maßnahmen hier noch einmal addiert,
//    zeigt eine zweite Zahl, die dasselbe meint.
//
// 3. NEGATIVE BETRÄGE SIND NORMAL und keine Fehler: Tilgungen, Zuschüsse von
//    Land und Bund, Grundstücksverkäufe stehen mit Minus im Programm. Der
//    Teilhaushalt „Finanzmanagement und Recht" ist 2026 in der Summe
//    −121,4 Mio. €. Sie dürfen nicht als „Ausgabe" beschriftet und nicht
//    weggelassen werden — ohne sie ginge keine Probe auf.

import type { Herkunft } from "@/lib/haushalt-konzern";

export type { Herkunft };

/** Eine Zeile aus `council_investitionsmassnahmen`. */
export type ProgrammZeile = {
  jahr: number;
  ebene: "massnahme" | "teilhaushalt" | "gesamt";
  thh_nr: number;
  /** IPSP-Element („I10.090126"); leer auf den beiden Summenebenen. */
  code: string;
  bezeichnung: string;
  /** Gesamtinvestitionssumme — die Kosten über alle Jahre, nicht die
   *  Jahresrate. Die Jahresaufteilung liegt nicht vor. */
  gesamtsumme: number;
  herkunft_id: number | null;
};

export type ProgrammDaten = {
  jahre: number[];
  massnahmen: ProgrammZeile[];
  teilhaushalte: ProgrammZeile[];
  gesamt: ProgrammZeile[];
  herkunft: Record<string, Herkunft>;
};

export function herkunftVon(
  daten: ProgrammDaten | null,
  id: number | null | undefined,
): Herkunft | null {
  if (!daten || id == null) return null;
  return daten.herkunft[String(id)] ?? null;
}

/** Die Teilhaushalte eines Jahrgangs, nach Gesamtsumme absteigend.
 *
 *  Absteigend nach dem Betrag und nicht nach der Nummer: Die Frage ist „wo
 *  steckt das Geld?". Negative Teilhaushalte landen damit hinten — richtig so,
 *  sie sind der Sonderfall (Tilgungen, Ausleihungen). */
export function teilhaushalte(
  daten: ProgrammDaten | null,
  jahr: number,
): ProgrammZeile[] {
  if (!daten) return [];
  return daten.teilhaushalte
    .filter((z) => z.jahr === jahr)
    .sort((a, b) => b.gesamtsumme - a.gesamtsumme);
}

export function gesamtJahr(
  daten: ProgrammDaten | null,
  jahr: number,
): ProgrammZeile | null {
  return daten?.gesamt.find((z) => z.jahr === jahr) ?? null;
}

/** Die Vorhaben eines Teilhaushalts, nach Gesamtsumme absteigend.
 *
 *  Die Reihenfolge des Dokuments wäre die des IPSP-Elements — für eine
 *  Verwaltung sinnvoll, für eine Leserin nicht: Sie will wissen, was das größte
 *  Vorhaben ist, nicht welches die kleinste Kontonummer hat. */
export function vorhaben(
  daten: ProgrammDaten | null,
  jahr: number,
  thhNr: number,
): ProgrammZeile[] {
  if (!daten) return [];
  return daten.massnahmen
    .filter((z) => z.jahr === jahr && z.thh_nr === thhNr)
    .sort((a, b) => b.gesamtsumme - a.gesamtsumme);
}

/** Die Gesamtsumme, die das Dokument für einen Teilhaushalt ausweist. */
export function teilhaushaltSumme(
  daten: ProgrammDaten | null,
  jahr: number,
  thhNr: number,
): ProgrammZeile | null {
  return daten?.teilhaushalte.find(
    (z) => z.jahr === jahr && z.thh_nr === thhNr) ?? null;
}

/** Vorhaben eines Jahrgangs, deren Bezeichnung zur Suche passt.
 *
 *  Über alle Teilhaushalte hinweg — genau das ist der Zweck: „Kunstrasen" oder
 *  „Feuerwehr" steht nicht in einem Bereich allein. Ohne Suchwort kommt nichts
 *  zurück, damit die Liste nicht ungefragt 565 Zeilen lang wird. */
export function suche(
  daten: ProgrammDaten | null,
  jahr: number,
  wort: string,
): ProgrammZeile[] {
  const w = wort.trim().toLowerCase();
  if (!daten || w.length < 2) return [];
  return daten.massnahmen
    .filter((z) => z.jahr === jahr && z.bezeichnung.toLowerCase().includes(w))
    .sort((a, b) => b.gesamtsumme - a.gesamtsumme);
}

/** Wie viele Vorhaben ein Teilhaushalt führt — 0, wenn der Jahrgang fehlt. */
export function anzahl(
  daten: ProgrammDaten | null,
  jahr: number,
  thhNr: number,
): number {
  if (!daten) return 0;
  return daten.massnahmen.filter(
    (z) => z.jahr === jahr && z.thh_nr === thhNr).length;
}

/** Der Jahrgang, den der Block zeigen soll.
 *
 *  Bevorzugt den, den die Seite oben schon gewählt hat — zwei Blöcke mit
 *  verschiedenen Jahren nebeneinander liest niemand richtig. Nur wenn das
 *  Programm diesen Jahrgang nicht hat (die beiden Quellen reichen verschieden
 *  weit: Portal 2022–2025, Haushaltsplan 2019–2026), fällt es auf den
 *  jüngsten eigenen zurück. */
export function passenderJahrgang(
  jahre: number[],
  gewuenscht: number | null,
): number | null {
  if (!jahre.length) return null;
  if (gewuenscht != null && jahre.includes(gewuenscht)) return gewuenscht;
  return [...jahre].sort((a, b) => a - b)[jahre.length - 1];
}
