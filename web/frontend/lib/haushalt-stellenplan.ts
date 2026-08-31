// Der Stellenplan — Typen und Rechenwege für /haushalt/personal.
//
// EINE FALLE VORWEG, und sie betrifft jede Zahl auf der Seite: **Die
// Besetzung gehört zur Vorjahresspalte, nicht zum Haushaltsjahr.** Der Plan
// 2026 sieht 815 Stellen vor und sagt daneben, wie es am 30.6.2025 aussah:
// 796 Stellen, davon 143,71 nicht besetzt. Geplant wird vorwärts, gezählt
// werden kann nur rückwärts.
//
// Wer „815 − 652,31" rechnet, bekommt 162,69 und damit eine Zahl, die in
// keinem Dokument steht — sie mischt zwei Stichtage. Deshalb gibt es hier
// keine Funktion, die den Plan und die Besetzung verrechnet; `luecke()` nimmt
// ausschließlich die Vorjahresspalte, und die Anzeige schreibt den Stichtag
// dazu.
//
// Und ein Jahrgang kann halb dastehen: Im Stellenplan 2026 liefert der
// Textextrakt für Teil B Glyphen statt Buchstaben. `fehlend` sagt, welcher
// Teil fehlt — ohne diese Liste sähe 2026 aus wie ein Jahr ohne
// Tarifbeschäftigte.

import type { Herkunft } from "@/lib/haushalt-konzern";

export type StellenTeil = "A" | "B";

/** Eine Zeile des Plans. `art` ist die Stufe der Summenzeilen:
 *  `posten` = eine Amtsbezeichnung, `gruppe` = eine Laufbahn- bzw.
 *  Beschäftigtengruppe, `gesamt` = die Gesamtzeile des Teils.
 *
 *  Die Summen stehen als eigene Zeilen da, weil sie im Dokument stehen: Auf
 *  der Seite soll die Zahl der Stadt stehen, nicht unsere Addition. */
export type StellenZeile = {
  budget_year: number;
  part: StellenTeil;
  art: "posten" | "gruppe" | "gesamt";
  gruppe: string | null;
  seq_no: number | null;
  label: string;
  pay_grade: string | null;
  /** Stellen im Haushaltsjahr — die Planspalte. */
  positions_planned: number;
  /** Stellen im Vorjahr. Auf DIESE Zahl beziehen sich alle Besetzungswerte. */
  positions_prior_year: number;
  filled: number;
  /** Nur Teil A: Eine Beamtenstelle darf mit Tarifbeschäftigten besetzt werden. */
  filled_by_officials: number | null;
  filled_by_employees: number | null;
  vacant: number;
  /** Tag, auf den sich die Besetzung bezieht (ISO). */
  as_of_date: string | null;
  /** 0 = In dieser Zeile ergeben besetzt + unbesetzt nicht die Stellen des
   *  Vorjahres. So steht es im Plan; zwei Zeilen im Bestand sind das. */
  consistent: number;
  herkunft_id: number | null;
};

export type StellenplanDaten = {
  jahrgaenge: number[];
  teile: Record<StellenTeil, string>;
  summen: StellenZeile[];
  gruppen: StellenZeile[];
  /** Nur für den angefragten Jahrgang — je Jahrgang rund 190 Zeilen. */
  zeilen: StellenZeile[];
  fehlend: { budget_year: number; part: StellenTeil; name: string }[];
  herkunft: Record<string, Herkunft>;
};

/** Wie die Teile auf der Seite heißen. Der Plan schreibt „Arbeitnehmerinnen
 *  und Arbeitnehmer"; im Fließtext ist „Tarifbeschäftigte" das Wort, das
 *  heute jemand benutzt — und es schließt niemanden aus. Der amtliche Titel
 *  steht in der Fundstelle des Belegs. */
export const TEIL_LABEL: Record<StellenTeil, string> = {
  A: "Beamtinnen und Beamte",
  B: "Tarifbeschäftigte",
};

export const TEILE: StellenTeil[] = ["A", "B"];

/** Die Gesamtzeile eines Jahrgangs und Teils — oder `null`, wo sie fehlt. */
export function gesamt(daten: StellenplanDaten, budget_year: number,
                       part: StellenTeil): StellenZeile | null {
  return daten.summen.find((z) => z.budget_year === budget_year && z.part === part) ?? null;
}

/** Fehlt dieser Teil im Jahrgang? Dann gibt es ihn nicht als Null, sondern
 *  als Lücke mit Begründung. */
export function fehlt(daten: StellenplanDaten, budget_year: number,
                      part: StellenTeil): boolean {
  return daten.fehlend.some((f) => f.budget_year === budget_year && f.part === part);
}

/** Die Besetzungslücke eines Teils — ausschließlich aus der Vorjahresspalte.
 *
 *  `anteil` ist unsere einzige Division auf dieser Seite und steht auf der
 *  Seite als solche gekennzeichnet. Sie teilt durch `positions_prior_year`, nicht
 *  durch `positions_planned`: Beides sind Stellen, aber zu verschiedenen
 *  Zeitpunkten (s. Kopf dieser Datei). */
export function luecke(z: StellenZeile | null): {
  stellen: number; filled: number; vacant: number;
  anteil: number; as_of_date: string | null;
} | null {
  if (!z || !z.positions_prior_year) return null;
  return {
    stellen: z.positions_prior_year,
    filled: z.filled,
    vacant: z.vacant,
    anteil: z.vacant / z.positions_prior_year,
    as_of_date: z.as_of_date,
  };
}

/** Jahrgänge, für die dieser Teil vorliegt — aufsteigend. */
export function jahrgaengeMitTeil(daten: StellenplanDaten,
                                  part: StellenTeil): number[] {
  return daten.summen.filter((z) => z.part === part)
    .map((z) => z.budget_year).sort((a, b) => a - b);
}

/** Die Einzelposten mit den größten Besetzungslücken.
 *
 *  Bewusst nach absoluten Stellen sortiert und nicht nach Anteil: Eine Zeile
 *  mit einer von einer Stelle unbesetzt hat 100 %, bewegt aber nichts. Zeilen,
 *  in denen der Plan sich selbst widerspricht (`consistent === 0`), bleiben
 *  draußen — ihre Lücke ist keine Aussage über den Dienst, sondern über einen
 *  Übertrag. */
export function groessteLuecken(zeilen: StellenZeile[], part: StellenTeil,
                                count = 8): StellenZeile[] {
  return zeilen
    .filter((z) => z.art === "posten" && z.part === part && z.consistent === 1)
    .filter((z) => z.vacant > 0)
    .sort((a, b) => b.vacant - a.vacant)
    .slice(0, count);
}

/** Stellen mit deutschem Komma und ohne unnötige Nachkommastellen.
 *
 *  Der Plan rechnet auf zwei Stellen genau, weil eine halbe Stelle eine halbe
 *  Stelle ist. „815,00 Stellen" liest sich aber wie eine Messung; ganze
 *  Zahlen stehen deshalb ganz da, gebrochene mit zwei Nachkommastellen. */
export function deStellen(n: number): string {
  const ganz = Math.abs(n - Math.round(n)) < 0.005;
  return n.toLocaleString("de-DE", {
    minimumFractionDigits: ganz ? 0 : 2,
    maximumFractionDigits: ganz ? 0 : 2,
  });
}

/** Ein ISO-Datum als „30. Juni 2025". */
export function deDatum(iso: string | null): string {
  if (!iso) return "";
  const [j, m, t] = iso.split("-").map(Number);
  const monate = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
                  "August", "September", "Oktober", "November", "Dezember"];
  return `${t}. ${monate[m - 1]} ${j}`;
}

/** Die Herkunft einer Zeile — nachgeschlagen über ihre `herkunft_id`.
 *  Teil A und Teil B eines Jahrgangs tragen verschiedene IDs: verschiedene
 *  Tabellen im selben PDF, verschiedene Proben. */
export function herkunftVon(daten: StellenplanDaten,
                            id: number | null | undefined): Herkunft | null {
  if (id == null) return null;
  return daten.herkunft[String(id)] ?? null;
}
