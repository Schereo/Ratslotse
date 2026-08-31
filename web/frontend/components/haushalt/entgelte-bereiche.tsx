"use client";

// „Wofür die Leute zahlen" — die Aufschlüsselung eines Ertragspostens nach
// Teilhaushalt (Steuer-Steckbrief, Einnahmearten ohne Steuerreihe).
//
// Eine Gesamtsumme beantwortet die Frage nicht, mit der Leute auf diese Seite
// kommen. „26 Mio. € Gebühren" ist eine Zahl; „5,9 Mio. € davon aus Jugend und
// Familie" ist die Auskunft, dass hier die Kita-Beiträge stecken. Die
// Aufschlüsselung steht deshalb nicht als Zusatz unter der Kurve, sondern als
// eigener Block direkt hinter dem Betrag.
//
// DREI ENTSCHEIDUNGEN:
//
//  1. **Balken, keine Torte.** Die Frage ist „welcher Bereich ist groß?", also
//     ein Größenvergleich auf einer Achse — dafür ist die Länge da. Ein
//     Kreissegment vergleicht Winkel, und das kann niemand.
//  2. **Keine Bewertungsfarben** (Regel des ganzen Bereichs). Ein Bereich mit
//     hohen Gebühreneinnahmen ist weder gut noch schlecht: Er kann viele
//     Leistungen erbringen oder teure. Alle Balken tragen dieselbe Farbe wie
//     der Betrag darüber — sie gehören zu derselben Zahl.
//  3. **Keine Null, wo eine Zahl steht.** Der kleinste Bereich nimmt 16 Tsd. €
//     ein — in Millionen gerundet steht dort „0,0 Mio. € · 0 %", und das liest
//     sich als „nichts", obwohl wir den Betrag genau kennen. Deshalb `amount()`
//     mit passender Einheit und „unter 1 %" statt einer gerundeten Null.
//  4. **Die Namen kommen aus den Daten, nicht von hier.** `sub_budget_name` ist die
//     Bezeichnung des Dokuments („Klima/Umwelt/Mobilität/Bau/Grün/Friedh."),
//     Abkürzungen inklusive. Eine schönere Fassung im Frontend wäre eine
//     zweite Wahrheit neben der Quelle und driftete beim nächsten Jahrgang.

import { amount } from "@/lib/haushalt";
import type { ErgebnisPosten } from "@/lib/haushalt";

/** Eine Zeile der Aufschlüsselung. */
type Bereich = { name: string; amount: number };

export function EntgelteBereiche({ zeilen, year, beleg }: {
  /** Die Teilhaushalts-Zeilen **eines** Postens und **eines** Jahres. */
  zeilen: ErgebnisPosten[];
  year: number;
  /** Beleg-Chip-Slot (GB-00) — die Seite wählt die Quelle. */
  beleg?: React.ReactNode;
}) {
  // `result` ist nullbar: Ein Teilhaushalt, der diesen Posten nicht führt,
  // hat dort keine Null, sondern keine Zeile. Beides als 0 zu zeichnen machte
  // aus „kommt hier nicht vor" ein „hat nichts eingenommen".
  const bereiche: Bereich[] = zeilen
    .filter((z) => z.sub_budget_name && z.result != null && z.result > 0)
    .map((z) => ({ name: z.sub_budget_name as string, amount: z.result as number }))
    .sort((a, b) => b.amount - a.amount);

  if (bereiche.length < 2) return null;

  const groesster = bereiche[0].amount;
  const summe = bereiche.reduce((s, b) => s + b.amount, 0);

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Wofür die Leute zahlen
        </p>
        {/* Ehrliche Menge statt „viele" (Designsprache § 6). */}
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {bereiche.length} Bereiche · {year}
        </span>
      </div>

      <ul className="mt-3 flex flex-col gap-2">
        {bereiche.map((b) => {
          const anteil = Math.round((b.amount / summe) * 100);
          const { wert, unit } = amount(b.amount);
          return (
            <li key={b.name}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 flex-1 truncate text-[12.5px] leading-snug text-foreground/90">
                  {b.name}
                </span>
                <span className="flex-none font-display text-[13px] font-bold tabular-nums">
                  {wert}
                  <span className="ml-1 text-[11px] font-semibold text-muted-foreground">
                    {unit}
                  </span>
                </span>
              </div>
              {/* Die Länge hängt am größten Bereich, nicht an der Summe: Sonst
                  wären alle Balken kurz und der Vergleich, um den es geht,
                  bliebe im linken Fünftel stecken. */}
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-[color:var(--hh-ein-0)]"
                    style={{ width: `${Math.max((b.amount / groesster) * 100, 2)}%` }}
                  />
                </div>
                <span className="flex-none font-mono text-[10px] tabular-nums text-muted-foreground">
                  {anteil < 1 ? "unter 1" : anteil}&nbsp;%
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
        Anteile am hier aufgeschlüsselten Betrag, gerundet.
        {beleg}
      </p>
    </div>
  );
}
