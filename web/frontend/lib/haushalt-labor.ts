// Rechenwege des Haushalts-Labors (Labor 2.0, Entwürfe vom 24.08.2026).
//
// Alles hier sind reine Funktionen über den Daten des Haushalts-Endpunkts —
// getrennt von den Komponenten, damit jede Regel an einer Stelle steht und
// die drei Werkbänke (labor-einnahmen/-ausgaben/-invest.tsx) nicht je eine
// eigene Wahrheit rechnen.
//
// DIE REGELN DES LABORS gelten für jede Funktion in dieser Datei:
//  1. Kein Wert ohne echte Reihe — fehlt die Grundlage, kommt `null` zurück,
//     und die Komponente lässt den Baustein weg, statt zu raten.
//  2. Annahmen sind Spannen mit benannter Herkunft, nie nackte Zahlen.
//  3. Vergleichsgrößen (Städte, Historie) ordnen ein — gerechnet wird nur
//     mit dem Planjahr.

import { type ErgebnishaushaltZeile, type HebesatzZeile } from "@/lib/haushalt";
import type { VergleichDaten } from "@/lib/haushalt-vergleich";

/** Der geltende Hebesatz einer Art — und seit wann er gilt.
 *
 *  Tabelle 1105 führt nur Änderungsjahre; die jüngste Zeile ist der geltende
 *  Satz, ihr Jahr sein Beginn. Fehlt die Reihe, gibt es keinen Ersatzwert —
 *  dann verschwindet der Regler lieber, als mit einer geratenen Ausgangslage
 *  zu rechnen (dieselbe Regel wie seit dem 21.08., jetzt je Steuerart). */
export function hebesatzHeute(
  zeilen: HebesatzZeile[] | undefined, art: string,
): { satz: number; seit: number } | null {
  const series = (zeilen ?? [])
    .filter((z) => z.art === art && z.rate != null)
    .sort((a, b) => a.year - b.year);
  const letzte = series.at(-1);
  return letzte ? { satz: letzte.rate as number, seit: letzte.year } : null;
}

/** Der jüngste Ist-Betrag einer Steuerart aus dem Open-Data-Satz. */
export function letzterSteuerbetrag(
  steuern: { year: number; art: string; amount: number | null }[],
  art: string,
): { year: number; amount: number } | null {
  const z = steuern
    .filter((s) => s.art === art && s.amount)
    .sort((a, b) => a.year - b.year)
    .at(-1);
  return z ? { year: z.year, amount: z.amount as number } : null;
}

/** Der Anteil der Grundsteuer A am gemeinsamen Aufkommen „Grundsteuer A+B“ —
 *  belegt über den Realsteuervergleich des Landes, nicht geschätzt.
 *
 *  Der Open-Data-Satz führt A und B in einer Spalte; der Grundsteuer-Regler
 *  teilt deshalb durch den B-Hebesatz und muss sagen, wie groß der Fehler
 *  dabei ist. Das LSN weist je Stadt das Ist-Aufkommen beider Steuern je
 *  Einwohner*in aus — daraus kommt der Anteil (Oldenburg, jüngstes Jahr).
 *  In kreisfreien Städten liegt A im Promillebereich; genau das macht die
 *  Näherung tragfähig, und genau deshalb steht die Zahl am Regler. */
export function grundsteuerAnteilA(vergleich: VergleichDaten | null): number | null {
  if (!vergleich) return null;
  const oldenburg = vergleich.staedte.find((s) => s.ist_oldenburg)?.schluessel;
  if (!oldenburg) return null;
  const werte = vergleich.werte.filter(
    (w) => w.series === "realsteuern" && w.schluessel === oldenburg
      && (w.indicator === "ist_je_ew_grundsteuer_a" || w.indicator === "ist_je_ew_grundsteuer_b"));
  const year = Math.max(...werte.map((w) => w.year), -Infinity);
  const a = werte.find((w) => w.year === year && w.indicator === "ist_je_ew_grundsteuer_a")?.wert;
  const b = werte.find((w) => w.year === year && w.indicator === "ist_je_ew_grundsteuer_b")?.wert;
  if (a == null || b == null || a + b <= 0) return null;
  return a / (a + b);
}

export type StadtHebesatz = {
  stadt: string;
  wert: number;
  istOldenburg: boolean;
  year: number;
};

/** Die Hebesätze der kreisfreien Städte, jüngstes vorliegendes Jahr,
 *  absteigend sortiert — die Leiter, die am Regler mitläuft. */
export function staedteHebesaetze(
  vergleich: VergleichDaten | null,
  indicator: "hebesatz_gewerbesteuer" | "hebesatz_grundsteuer_b",
): StadtHebesatz[] {
  if (!vergleich) return [];
  const jahre = vergleich.jahre.realsteuern ?? [];
  const year = jahre.at(-1);
  if (year == null) return [];
  const oldenburg = vergleich.staedte.find((s) => s.ist_oldenburg)?.schluessel;
  return vergleich.werte
    .filter((w) => w.series === "realsteuern" && w.year === year && w.indicator === indicator)
    .map((w) => ({
      stadt: w.city, wert: w.wert, year: w.year,
      istOldenburg: w.schluessel === oldenburg,
    }))
    .sort((a, b) => b.wert - a.wert);
}

/** Was vom nächsten Einnahme-Euro nach dem Finanzausgleich übrig bliebe —
 *  als SPANNE aus den echten Ausgleichsjahren, nie als fester Faktor.
 *
 *  Die Regel „der Dämpfer wird nicht verrechnet“ bleibt: Das Ergebnis oben
 *  ändert sich nicht. Neu ist, dass die Unsicherheit GEZEIGT wird, statt in
 *  einer Fußnote zu stehen. Je zwei aufeinanderfolgende Jahre mit Messzahl
 *  und Zuweisung ergeben ein beobachtetes Verhältnis −ΔZuweisung/ΔMesszahl;
 *  die Spanne ist das Kleinste und Größte davon, beschnitten auf [0, 1] —
 *  ein Jahr, in dem die Zuweisung trotz höherer Steuerkraft stieg (auch der
 *  Landestopf schwankt), heißt ehrlich „es blieb alles übrig“, nicht „es
 *  blieb mehr als alles übrig“. */
export function daempferSpanne(
  steuerkraft: { year: number; tax_index: number | null; allocations: number | null }[],
): { verbleibVon: number; verbleibBis: number; paare: number } | null {
  const series = steuerkraft
    .filter((k) => k.tax_index != null && k.allocations != null)
    .sort((a, b) => a.year - b.year);
  const quoten: number[] = [];
  for (let i = 1; i < series.length; i++) {
    const dMess = (series[i].tax_index as number) - (series[i - 1].tax_index as number);
    const dZuw = (series[i].allocations as number) - (series[i - 1].allocations as number);
    // Nur Jahre, in denen die Steuerkraft nennenswert gestiegen ist — ein
    // Verhältnis über einer Mini-Änderung wäre Rauschen, keine Beobachtung.
    if (dMess > 1_000_000) quoten.push(Math.min(1, Math.max(0, -dZuw / dMess)));
  }
  if (quoten.length < 2) return null;
  return {
    verbleibVon: 1 - Math.max(...quoten),
    verbleibBis: 1 - Math.min(...quoten),
    paare: quoten.length,
  };
}

/** Die Jahresergebnisse des jüngsten Plan-Jahrgangs — Ansatz plus
 *  Finanzplanungsjahre, in Mio. € (negativ = Minus).
 *
 *  Quelle ist der Gesamtergebnishaushalt (Anlage 005): Posten 21
 *  (ordentliches Ergebnis) plus, wo vorhanden, Posten 24 (außerordentliches)
 *  — dieselbe Addition wie beim Plan-Ist-Vergleich. ZWEI EHRLICHKEITEN
 *  gehören an jede Anzeige davon: Es ist der ENTWURF der Verwaltung, nicht
 *  der Beschluss (die Anlage hängt an der Einbringungs-Vorlage), und die
 *  Finanzplanungsjahre sind Vorausschau nach § 8 NKomVG, kein aufgestellter
 *  Haushalt. Deshalb trägt der Pfad seinen eigenen Beleg und rechnet nicht
 *  mit dem beschlossenen Minus der Ergebnis-Karte zusammen. */
export function planjahrErgebnisse(
  zeilen: ErgebnishaushaltZeile[] | undefined,
): { planJahrgang: number; series: { year: number; ergebnisMio: number }[] } | null {
  if (!zeilen?.length) return null;
  const budget_year = Math.max(...zeilen.map((z) => z.plan_budget_year));
  const eigene = zeilen.filter((z) => z.plan_budget_year === budget_year);
  const jahre = [...new Set(eigene.map((z) => z.year))].sort((a, b) => a - b);
  const series = jahre.flatMap((year) => {
    const ordentlich = eigene.find((z) => z.year === year && z.nr === 21)?.amount;
    if (ordentlich == null) return [];
    const ausser = eigene.find((z) => z.year === year && z.nr === 24)?.amount ?? 0;
    return [{ year, ergebnisMio: (ordentlich + ausser) / 1e6 }];
  });
  return series.length >= 2 ? { planJahrgang: budget_year, series } : null;
}

export type PfadPunkt = { year: number; stand: number };

export type RuecklagenPfad = {
  /** Geprüfter Bestand vor dem ersten Planjahr, in Mio. €. */
  start: number;
  /** Der Stand am ENDE jedes Planjahres, in Mio. € — Startpunkt ist die
   *  Rücklage vor dem ersten Jahr. Nie unter 0 gezeichnet. */
  punkte: PfadPunkt[];
  /** Das Jahr, in dem der Stand rechnerisch unter 0 fiele — `null`, wenn die
   *  Rücklage über alle Planjahre trägt. */
  kippjahr: number | null;
  /** Letztes Jahr, für das eine Planzahl vorliegt — dahinter wird nichts
   *  fortgeschrieben („für später liegen keine Planzahlen vor“). */
  letztesPlanjahr: number;
};

/** Der Rücklagen-Pfad: Startbestand minus die geplanten Jahres-Minus,
 *  wahlweise um die Wirkung des Szenarios je Jahr entlastet.
 *
 *  Die Wirkung wird KONSTANT fortgeschrieben — wer heute den Hebesatz hebt,
 *  hebt ihn für alle Planjahre. Das ist eine Fortschreibung, keine Prognose,
 *  und steht so an der Grafik. */
export function ruecklagenPfad(
  ergebnisse: { year: number; ergebnisMio: number }[],
  wirkungMio: number,
  startMio: number,
): RuecklagenPfad {
  let stand = startMio;
  let kippjahr: number | null = null;
  const punkte: PfadPunkt[] = [];
  for (const e of ergebnisse) {
    const minus = Math.max(0, -e.ergebnisMio - wirkungMio);
    stand -= minus;
    if (stand < 0 && kippjahr == null) kippjahr = e.year;
    punkte.push({ year: e.year, stand: Math.max(0, stand) });
  }
  return { start: startMio, punkte, kippjahr, letztesPlanjahr: ergebnisse.at(-1)?.year ?? 0 };
}

/** Die Zinssätze, die die Stadt zuletzt WIRKLICH gezahlt hat — Zinsaufwand
 *  (Posten 17 der Jahresabschlüsse) geteilt durch den Schuldenstand desselben
 *  Jahres. Eine Spanne aus Beobachtungen, keine Marktannahme; mehr behauptet
 *  der Kredit-Baustein nicht. */
export function gezahlteZinsspanne(
  zinslast: { year: number; expense: number }[] | undefined,
  schulden: { year: number; insgesamt: number }[] | undefined,
): { von: number; bis: number; jahre: [number, number] } | null {
  if (!zinslast?.length || !schulden?.length) return null;
  const saetze = zinslast.flatMap((z) => {
    const s = schulden.find((r) => r.year === z.year);
    return s && s.insgesamt > 0 ? [{ year: z.year, satz: z.expense / s.insgesamt }] : [];
  });
  if (saetze.length < 2) return null;
  const sortiert = [...saetze].sort((a, b) => a.satz - b.satz);
  const jahre = saetze.map((s) => s.year);
  return {
    von: sortiert[0].satz,
    bis: sortiert[sortiert.length - 1].satz,
    jahre: [Math.min(...jahre), Math.max(...jahre)],
  };
}
