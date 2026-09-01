"use client";

// Der Stellenplan über die Jahre — je Jahrgang ein BALKENPAAR (H3-01):
// oben die Stellen, die der Plan fürs Haushaltsjahr vorhält (gefüllt),
// darunter die Besetzung am Stichtag des Vorjahres (helle Stufe derselben
// Rampe). Zwei Balken, zwei Zeitpunkte, eine Zeile.
//
// WARUM EIN PAAR UND KEIN EINZELNER BALKEN MIT ZWEI SEGMENTEN: Die
// Besetzungszahlen des Plans beziehen sich auf den Stichtag im **Vorjahr**,
// nicht auf das Haushaltsjahr. Für 2026 heißt das 815 geplante Stellen — und
// 652,31 besetzte von 796 Stellen am 30.6.2025. Beides in EINEN Balken zu
// legen behauptet eine Lücke von 162,69 Stellen, die in keinem Dokument
// steht. Das Paar zeigt beide Angaben getrennt und lässt die Schere über die
// Jahrgänge trotzdem sehen — verglichen wird mit dem Auge, verrechnet wird
// nicht (deshalb gibt es hier auch keine Differenz-Zahl).
//
// KEINE BEWERTUNGSFARBEN (wie im ganzen Bereich, s. components/haushalt/
// hantel.tsx): Beide Balken sind Stufen derselben blauen Rampe. Unbesetzte
// Stellen sind weder Erfolg noch Versagen, sondern erklärungsbedürftig —
// die Deutung steht auf der Seite, nicht in einer Farbe.
//
// Die Balken aller Zeilen teilen sich EINE Skala (übergeben als `skala`).
// Sonst wäre ein Jahr mit 700 Stellen so breit wie eines mit 1.700, und der
// Vergleich zwischen den Teilen ginge verloren.
//
// Ein Jahrgang, dessen Teil im PDF nicht lesbar ist (Teil B 2026), bleibt
// als Zeile stehen — mit <LueckenFeld> statt Balken. Die Lücke rendert die
// Komponente, nie die Seite (GB-00); sie bleibt auch mobil sichtbar (H4-05).

import { LueckenFeld } from "@/components/grafik/luecken-field";
import { deStellen } from "@/lib/haushalt-stellenplan";
import type { StellenZeile } from "@/lib/haushalt-stellenplan";
import { cn } from "@/lib/utils";

export type VerlaufZeile = {
  budget_year: number;
  row: StellenZeile | null;
  /** Warum diese Zeile leer ist — nur gesetzt, wo ein Teil fehlt. */
  fehlt?: string;
};

export function StellenPaare({ zeilen, skala, aktJahr }: {
  zeilen: VerlaufZeile[];
  /** Gemeinsame Obergrenze aller Balken — in Stellen. */
  skala: number;
  /** Der hervorgehobene (jüngste) Jahrgang. */
  aktJahr?: number | null;
}) {
  return (
    <ol className="flex flex-col gap-3">
      {zeilen.map(({ budget_year, row, fehlt }) => {
        const akt = budget_year === aktJahr;
        return (
          <li key={budget_year} className="grid grid-cols-[3rem_minmax(0,1fr)_auto] items-center gap-x-3">
            <span className={cn(
              "font-mono text-[12px] font-medium tabular-nums",
              akt ? "text-primary" : "text-muted-foreground",
            )}>
              {budget_year}
            </span>

            {row ? (
              <>
                <div className="flex min-w-0 flex-col gap-[3px]" aria-hidden="true">
                  <div className="h-2.5 rounded-[3px]"
                    style={{
                      width: `${Math.min(row.positions_planned / skala, 1) * 100}%`,
                      background: "var(--hh-ein-0)",
                    }} />
                  <div className="h-2.5 rounded-[3px]"
                    style={{
                      width: `${Math.min(row.filled / skala, 1) * 100}%`,
                      background: "var(--hh-ein-4)",
                    }} />
                </div>
                {/* Die beiden Zahlen der Zeile — Plan und Besetzung, nie ihre
                    Differenz. Vorgelesen wird der ganze Satz. */}
                <span
                  aria-label={`${budget_year}: ${deStellen(row.positions_planned)} Stellen `
                    + `vorgehalten, ${deStellen(row.filled)} besetzt am Stichtag `
                    + `des Vorjahres`}
                  className={cn(
                    "text-right font-mono text-[12.5px] tabular-nums",
                    akt ? "font-semibold text-foreground" : "text-muted-foreground",
                  )}>
                  {deStellen(row.positions_planned)} · {deStellen(row.filled)}
                </span>
              </>
            ) : (
              <>
                <LueckenFeld label={String(budget_year)}
                  reason={fehlt ?? "liegt nicht vor"} className="min-w-0" />
                <span className="text-right font-mono text-[12.5px] tabular-nums text-muted-foreground">
                  — · —
                </span>
              </>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Die Legende — einmal je Block, nicht je Zeile.
 *
 *  Sie sagt in jedem Block denselben Satz, und das ist Absicht: Der Hinweis,
 *  dass der untere Balken das Jahr VOR dem Plan zeigt, ist die
 *  Bedienungsanleitung für die Grafik. */
export function StellenPaareLegende() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[3px]"
          style={{ background: "var(--hh-ein-0)" }} aria-hidden />
        vorgehalten im Planjahr
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[3px]"
          style={{ background: "var(--hh-ein-4)" }} aria-hidden />
        besetzt — Stand jeweils am 30. Juni des Jahres vor dem Plan
      </span>
    </div>
  );
}
