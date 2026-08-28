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
// selbst (`council/kennzahlen.py`, `ueberlappungsprobe`): Wo zwei Berichte
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
export const GRUPPEN: { titel: string; frage: string; keys: string[] }[] = [
  {
    titel: "Was der Stadt gehört",
    frage: "Wie viel des Vermögens ist wirklich ihres — und wie viel davon "
      + "steckt in Gebäuden, Straßen und Leitungen?",
    keys: ["eigenkapitalquote_1", "eigenkapitalquote_2", "anlagenintensitaet",
           "infrastrukturquote"],
  },
  {
    titel: "Was auf jede*n entfällt",
    frage: "Dieselben Beträge, geteilt durch die Zahl der Einwohnenden — "
      + "die Reihe, die vom Wachstum der Stadt abhängt.",
    keys: ["einwohner", "vermoegen_je_einwohner", "verschuldung_je_einwohner",
           "verschuldung_mit_rueckstellungen_je_einwohner",
           "neuverschuldung_je_einwohner", "netto_neuinvestitionen_je_einwohner"],
  },
  {
    titel: "Wofür das Geld draufgeht",
    frage: "Welcher Teil der Ausgaben ins Personal fließt, welcher Teil der "
      + "Einnahmen aus Steuern kommt — und ob mehr gebaut als abgeschrieben wird.",
    keys: ["steuerquote", "personalintensitaet", "reinvestitionsquote"],
  },
];

/** Ein Wert so schreiben, wie der Bericht ihn druckt.
 *
 *  Die Nachkommastellen kommen aus den Daten (`stellen`), nicht aus dieser
 *  Datei: 2019 stand „48%", ab 2021 „53,15%". Wer hier zwei Stellen erzwingt,
 *  macht aus einer gerundeten Angabe eine genaue. */
export function schreibe(einheit: string, wert: number, stellen = 2): string {
  if (einheit === "prozent") return `${deZahl(wert, stellen)} %`;
  if (einheit === "anzahl") return deZahl(wert, 0);
  return `${deZahl(wert, stellen)} €`;
}

/** Das Format für die Ableseleiste einer Kennzahl — feste Stellen, weil eine
 *  Achse sonst zwischen den Jahren die Genauigkeit wechselte. */
export function formatVon(einheit: string): (wert: number) => string {
  return (wert) => schreibe(einheit, wert, einheit === "anzahl" ? 0 : 2);
}

/** Das Format für die Vorjahresdifferenz.
 *
 *  Bei einer Prozent-Reihe ist die Differenz in **Prozentpunkten** zu lesen:
 *  Von 54,62 % auf 50,11 % sind 4,51 Prozentpunkte — der relative Rückgang
 *  wäre 8,3 %. Beides „−4,51 %" zu schreiben, wären zwei Zahlen unter einer
 *  Schreibweise. Bei Euro und Personen ändert sich nichts. */
export function differenzFormatVon(einheit: string): (wert: number) => string {
  if (einheit !== "prozent") return formatVon(einheit);
  return (wert) => `${deZahl(wert, 2)} %-Punkte`;
}

/** Die Einheit für die Kopfzeile der Grafik. */
export function einheitWort(einheit: string): string {
  return einheit === "prozent" ? "%" : einheit === "anzahl" ? "Personen" : "€";
}

/** Alle Punkte einer Kennzahl, nach Jahr. */
export function punkteVon(daten: Kennzahlen, key: string): KennzahlPunkt[] {
  return daten.reihe.filter((p) => p.kennzahl === key)
    .sort((a, b) => a.jahr - b.jahr);
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
  reihe: JahrPunkt[];
  anmerkung: { jahr: number; kurz: string; text: string } | null;
} {
  const punkte = punkteVon(daten, key);
  const wechsel = daten.funde.find(
    (f) => f.kennzahl === key && f.art === "definition");
  if (!wechsel || !punkte.length) {
    return { reihe: punkte.map((p) => ({ jahr: p.jahr, wert: p.wert })), anmerkung: null };
  }

  const einheit = daten.einheit[key] ?? "eur";
  const juengste = Math.max(...punkte.map((p) => p.fassung ?? 0));
  const erstesNeues = punkte.find((p) => (p.fassung ?? 0) === juengste)?.jahr ?? null;
  const text = `Ab dem Rechenschaftsbericht ${wechsel.neu_bericht} rechnet die `
    + `Stadt anders. Für ${wechsel.jahr} ergibt der alte Weg `
    + `${schreibe(einheit, wechsel.alt)}, der neue ${schreibe(einheit, wechsel.neu)} `
    + `— deshalb läuft die Linie hier nicht durch.`;
  return {
    reihe: punkte.map((p) => ({
      jahr: p.jahr,
      wert: p.wert,
      ...(p.jahr === erstesNeues && punkte[0].jahr !== erstesNeues
        ? { bruchDavor: text } : {}),
    })),
    anmerkung: erstesNeues != null && punkte[0].jahr !== erstesNeues
      ? { jahr: erstesNeues, kurz: "anderer Rechenweg", text }
      : null,
  };
}

/** Der Rechenweg, den die Stadt zuletzt gedruckt hat. */
export function formelVon(daten: Kennzahlen, key: string): KennzahlFormel | null {
  const alle = daten.formeln.filter((f) => f.kennzahl === key);
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
    .filter((f) => f.art === "revision" && (!key || f.kennzahl === key))
    .sort((a, b) => b.neu_bericht - a.neu_bericht || b.jahr - a.jahr);
}

/** Das jüngste Jahr, für das überhaupt eine Kennzahl vorliegt. */
export function juengstesJahr(daten: Kennzahlen): number | null {
  const jahre = daten.reihe.map((p) => p.jahr);
  return jahre.length ? Math.max(...jahre) : null;
}
