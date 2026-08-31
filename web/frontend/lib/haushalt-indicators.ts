// Was die Seite /haushalt/kennzahlen aus den Rohdaten macht — getrennt vom
// Bild, damit beides einzeln lesbar bleibt (dieselbe Aufteilung wie
// `lib/haushalt-schulden.ts`).
//
// DIE EINE ENTSCHEIDUNG, DIE HIER FÄLLT: wann eine Reihe **bricht**.
//
// Drei der dreizehn Kennzahlen haben zwischen 2019 und 2024 ihren gedruckten
// Rechenweg geändert. Naheliegend wäre, jede dieser Reihen an der Stelle zu
// zerschneiden — aber das wäre bei zweien falsch: Aus „Gesamtschulden" wurde
// „Schulden" und aus „Gesamtvermögen (inklusive liquide Mittel)" wurde
// „Aktiva (ohne aktive Rechnungsabgrenzung)", und in beiden Fällen blieben
// die Werte über den Wechsel hinweg auf den Cent gleich. Umformuliert, nicht
// umgerechnet.
//
// Bei der Personalintensität ist es umgekehrt: Dort fielen die
// Versorgungsempfänger aus dem Zähler, und für 2020 sinkt die Quote dadurch
// von 26,03 % auf 25,09 %. Über diese Stelle darf keine Linie laufen.
//
// Unterschieden wird das **nicht hier**, sondern im Backend an den Daten
// selbst (`council/indicators.py`, `ueberlappungsprobe`): Wo zwei Berichte
// dasselbe Jahr drucken, wird verglichen — auch über einen Rechenwegwechsel
// hinweg. Kommt dasselbe heraus, heißt der Fund `umbenennung`, sonst
// `definition`. Diese Datei liest nur das Ergebnis. Eine zweite Fassung
// derselben Regel im Browser wäre eine, die driftet.

import type {
  KennzahlFormel, KennzahlFund, KennzahlPunkt, Kennzahlen,
} from "@/lib/haushalt";
import type { JahrPunkt } from "@/components/grafik/daten";
import { deZahl } from "@/components/grafik/format";

/** Die dreizehn in drei Gruppen, in der Reihenfolge der Tabelle.
 *
 *  Die Gruppen sind unsere Ordnung, nicht die der Stadt — der Bericht druckt
 *  eine einzige Liste. Sie stehen hier, weil dreizehn Kacheln nebeneinander
 *  niemand liest, und sie sind nach der Frage geschnitten, die sie
 *  beantworten, nicht nach der Bilanzseite. */
export const GRUPPEN: { titel: string; question: string; keys: string[] }[] = [
  {
    titel: "Was der Stadt gehört",
    question: "Wie viel des Vermögens ist wirklich ihres — und wie viel davon "
      + "steckt in Gebäuden, Straßen und Leitungen?",
    keys: ["eigenkapitalquote_1", "eigenkapitalquote_2", "anlagenintensitaet",
           "infrastrukturquote"],
  },
  {
    titel: "Was auf jede*n entfällt",
    question: "Dieselben Beträge, geteilt durch die Zahl der Einwohnenden — "
      + "die Reihe, die vom Wachstum der Stadt abhängt.",
    keys: ["population", "vermoegen_je_einwohner", "verschuldung_je_einwohner",
           "verschuldung_mit_rueckstellungen_je_einwohner",
           "neuverschuldung_je_einwohner", "netto_neuinvestitionen_je_einwohner"],
  },
  {
    titel: "Wofür das Geld draufgeht",
    question: "Welcher Teil der Ausgaben ins Personal fließt, welcher Teil der "
      + "Einnahmen aus Steuern kommt — und ob mehr gebaut als abgeschrieben wird.",
    keys: ["steuerquote", "personalintensitaet", "reinvestitionsquote"],
  },
];

/** Ein Wert so schreiben, wie der Bericht ihn druckt.
 *
 *  Die Nachkommastellen kommen aus den Daten (`stellen`), nicht aus dieser
 *  Datei: 2019 stand „48%", ab 2021 „53,15%". Wer hier zwei Stellen erzwingt,
 *  macht aus einer gerundeten Angabe eine genaue. */
export function schreibe(unit: string, wert: number, stellen = 2): string {
  if (unit === "percent") return `${deZahl(wert, stellen)} %`;
  if (unit === "anzahl") return deZahl(wert, 0);
  return `${deZahl(wert, stellen)} €`;
}

/** Das Format für die Ableseleiste einer Kennzahl — feste Stellen, weil eine
 *  Achse sonst zwischen den Jahren die Genauigkeit wechselte. */
export function formatVon(unit: string): (wert: number) => string {
  return (wert) => schreibe(unit, wert, unit === "anzahl" ? 0 : 2);
}

/** Das Format für die Vorjahresdifferenz.
 *
 *  Bei einer Prozent-Reihe ist die Differenz in **Prozentpunkten** zu lesen:
 *  Von 54,62 % auf 50,11 % sind 4,51 Prozentpunkte — der relative Rückgang
 *  wäre 8,3 %. Beides „−4,51 %" zu schreiben, wären zwei Zahlen unter einer
 *  Schreibweise. Bei Euro und Personen ändert sich nichts. */
export function differenzFormatVon(unit: string): (wert: number) => string {
  if (unit !== "percent") return formatVon(unit);
  return (wert) => `${deZahl(wert, 2)} %-Punkte`;
}

/** Die Einheit für die Kopfzeile der Grafik. */
export function einheitWort(unit: string): string {
  return unit === "percent" ? "%" : unit === "anzahl" ? "Personen" : "€";
}

/** Alle Punkte einer Kennzahl, nach Jahr. */
export function punkteVon(daten: Kennzahlen, key: string): KennzahlPunkt[] {
  return daten.series.filter((p) => p.indicator === key)
    .sort((a, b) => a.year - b.year);
}

/** Die Reihe einer Kennzahl — mit dem Bruch, wo die Stadt etwas anderes misst.
 *
 *  Die Reihe bleibt **eine**: Alle Jahre stehen auf derselben Achse, und die
 *  drei ältesten verschwinden nicht, bloß weil sie anders gerechnet wurden.
 *  Getrennt wird die Linie, nicht die Reihe — dafür trägt der erste Punkt der
 *  neuen Fassung `bruchDavor` (GB-00).
 *
 *  Der Satz dazu kommt als Anmerkung an genau dieses Jahr zurück: Er steht
 *  dann in der Ableseleiste, sobald das Jahr gewählt ist — Text im Layout,
 *  kein Tooltip. */
export function reiheVon(daten: Kennzahlen, key: string): {
  series: JahrPunkt[];
  anmerkung: { year: number; kurz: string; text: string } | null;
} {
  const punkte = punkteVon(daten, key);
  const wechsel = daten.funde.find(
    (f) => f.indicator === key && f.art === "definition");
  if (!wechsel || !punkte.length) {
    return { series: punkte.map((p) => ({ year: p.year, wert: p.wert })), anmerkung: null };
  }

  const unit = daten.unit[key] ?? "eur";
  const juengste = Math.max(...punkte.map((p) => p.version ?? 0));
  const erstesNeues = punkte.find((p) => (p.version ?? 0) === juengste)?.year ?? null;
  const text = `Ab dem Rechenschaftsbericht ${wechsel.neu_bericht} rechnet die `
    + `Stadt anders. Für ${wechsel.year} ergibt der alte Weg `
    + `${schreibe(unit, wechsel.alt)}, der neue ${schreibe(unit, wechsel.neu)} `
    + `— deshalb läuft die Linie hier nicht durch.`;
  return {
    series: punkte.map((p) => ({
      year: p.year,
      wert: p.wert,
      ...(p.year === erstesNeues && punkte[0].year !== erstesNeues
        ? { bruchDavor: text } : {}),
    })),
    anmerkung: erstesNeues != null && punkte[0].year !== erstesNeues
      ? { year: erstesNeues, kurz: "anderer Rechenweg", text }
      : null,
  };
}

/** Der Rechenweg, den die Stadt zuletzt gedruckt hat. */
export function formelVon(daten: Kennzahlen, key: string): KennzahlFormel | null {
  const alle = daten.formeln.filter((f) => f.indicator === key);
  return alle.length
    ? alle.reduce((a, b) => (b.bis_bericht > a.bis_bericht ? b : a))
    : null;
}

/** Die Korrekturen an einer Kennzahl, jüngste zuerst.
 *
 *  Nur `revision` — ein Definitionswechsel steht am Bruch der Reihe, eine
 *  bloße Umbenennung ist keine Nachricht. */
export function korrekturenVon(daten: Kennzahlen, key?: string): KennzahlFund[] {
  return daten.funde
    .filter((f) => f.art === "revision" && (!key || f.indicator === key))
    .sort((a, b) => b.neu_bericht - a.neu_bericht || b.year - a.year);
}

/** Das jüngste Jahr, für das überhaupt eine Kennzahl vorliegt. */
export function juengstesJahr(daten: Kennzahlen): number | null {
  const years = daten.series.map((p) => p.year);
  return years.length ? Math.max(...years) : null;
}
