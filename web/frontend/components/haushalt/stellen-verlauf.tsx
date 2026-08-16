"use client";

// Der Stellenplan über die Jahre — geplante Stellen und die Besetzung daneben.
//
// DIE EINE ENTSCHEIDUNG, UM DIE ES HIER GEHT: **zwei Spalten, nicht ein
// Balken.** Der naheliegende Entwurf wäre ein Balken je Jahr, der bei den
// geplanten Stellen endet und in dem der unbesetzte Teil heller steht. Er wäre
// falsch, und zwar auf die stille Art: Die Besetzungszahlen des Plans beziehen
// sich auf den Stichtag im **Vorjahr**, nicht auf das Haushaltsjahr. Für 2026
// heißt das 815 geplante Stellen — und 143,71 unbesetzt von 796 Stellen am
// 30.6.2025. Beides in einen Balken zu legen behauptet eine Lücke von 162,69
// Stellen, die in keinem Dokument steht.
//
// Deshalb steht der Plan als Zahl links und die Besetzung als Balken rechts,
// mit dem Stichtag an der Zeile. Zwei Angaben, zwei Orte, eine Zeile — die
// Entwicklung liest man in beiden Spalten von oben nach unten.
//
// KEINE BEWERTUNGSFARBEN (wie im ganzen Bereich, s. components/haushalt/
// hantel.tsx). Bei unbesetzten Stellen ist das besonders wichtig: Sie sind
// weder ein Erfolg (gespartes Geld) noch ein Versagen (fehlende Leute),
// sondern erklärungsbedürftig. Rot hieße „schlimm", Grün hieße „gespart" —
// beides wäre eine Behauptung, die wir nicht belegen können. Die beiden
// Segmente sind deshalb zwei Stufen derselben blauen Rampe.
//
// Die Balken aller Zeilen teilen sich EINE Skala (die größte
// Vorjahresspalte). Sonst wäre ein Jahr mit 700 Stellen so breit wie eines
// mit 1.700, und der Vergleich zwischen den Teilen ginge verloren.

import { deStellen, luecke } from "@/lib/haushalt-stellenplan";
import type { StellenZeile } from "@/lib/haushalt-stellenplan";

export type VerlaufZeile = {
  jahrgang: number;
  zeile: StellenZeile | null;
  /** Warum diese Zeile leer ist — nur gesetzt, wo ein Teil fehlt. */
  fehlt?: string;
};

/** Der besetzte Anteil trägt seine Zahl im Segment. Er ist in allen bisher
 *  gelesenen Jahrgängen mindestens 78 % des Balkens und damit immer breit
 *  genug; die Schranke ist trotzdem da, weil ein künftiger Jahrgang das
 *  ändern kann.
 *
 *  Die **unbesetzten** Stellen stehen dagegen grundsätzlich rechts NEBEN dem
 *  Balken, nicht darin — obwohl sie die wichtigere Zahl sind, und genau
 *  deshalb. Im Segment hing ihre Sichtbarkeit an zwei Faktoren zugleich: am
 *  unbesetzten Anteil UND daran, wie breit der Balken auf der gemeinsamen
 *  Skala überhaupt ist. Bei den Beamtenstellen 2024 fiel sie damit weg
 *  (15,6 % eines Balkens, der selbst nur 42 % der Zeile misst) — in einer
 *  Spalte, in der die Nachbarzeilen ihre Zahl zeigten. Eine Zahl, die je nach
 *  Jahrgang da ist oder nicht, liest sich wie eine fehlende Angabe. */
const BESCHRIFTBAR = 0.3;

export function StellenVerlauf({ zeilen, skala }: {
  zeilen: VerlaufZeile[];
  /** Gemeinsame Obergrenze aller Balken — in Stellen. */
  skala: number;
}) {
  return (
    <ol className="flex flex-col gap-2">
      {zeilen.map(({ jahrgang, zeile, fehlt }) => {
        // `luecke()` ist die einzige Stelle, an der der unbesetzte Anteil
        // gerechnet wird — und sie teilt durch die Vorjahresspalte, nie durch
        // den Plan (s. lib/haushalt-stellenplan.ts).
        const l = luecke(zeile);
        const breite = l && skala ? l.stellen / skala : 0;
        const lueckeAnteil = l ? l.anteil : 0;
        const besetztAnteil = 1 - lueckeAnteil;
        return (
          <li key={jahrgang} className="flex flex-col gap-1 @lg/verlauf:flex-row @lg/verlauf:items-center @lg/verlauf:gap-3">
            {/* Spalte 1: das Planjahr und seine Stellen. */}
            <div className="flex flex-none items-baseline gap-2 @lg/verlauf:w-[11.5rem]">
              <span className="font-mono text-[11px] font-medium tabular-nums text-muted-foreground">
                {jahrgang}
              </span>
              {zeile ? (
                <span className="font-display text-[15px] font-bold tabular-nums tracking-tight">
                  {deStellen(zeile.stellen_plan)}
                  <span className="ml-1 font-sans text-[11px] font-medium text-muted-foreground">
                    Stellen geplant
                  </span>
                </span>
              ) : (
                <span className="text-[12px] text-muted-foreground">{fehlt}</span>
              )}
            </div>

            {/* Spalte 2: die Besetzung am Stichtag — eine andere Zahl, und
                deshalb sichtbar getrennt. */}
            {zeile ? (
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <div className="h-6 flex-1 overflow-hidden rounded-md"
                    style={{ background: "transparent" }}>
                    <div className="flex h-full overflow-hidden rounded-md"
                      style={{ width: `${Math.max(breite, 0.02) * 100}%` }}>
                      <div className="flex items-center justify-start pl-2"
                        style={{ width: `${besetztAnteil * 100}%`,
                                 background: "var(--hh-ein-2)" }}>
                        {besetztAnteil > BESCHRIFTBAR && (
                          <span className="font-mono text-[10px] font-semibold tabular-nums"
                            style={{ color: "var(--hh-seg-text)" }}>
                            {deStellen(zeile.besetzt)}
                          </span>
                        )}
                      </div>
                      <div style={{ width: `${lueckeAnteil * 100}%`,
                                    background: "var(--hh-ein-5)" }} />
                    </div>
                  </div>
                  {/* Die eigentliche Aussage der Zeile, und deshalb an einer
                      Stelle, an der sie nie von der Balkenbreite abhängt. */}
                  <span className="flex flex-none items-baseline gap-1.5">
                    <span className="font-display text-[13.5px] font-bold tabular-nums">
                      {deStellen(zeile.nicht_besetzt)}
                    </span>
                    <span className="w-[3.4rem] font-mono text-[10.5px] tabular-nums text-muted-foreground">
                      {(lueckeAnteil * 100)
                        .toLocaleString("de-DE", { maximumFractionDigits: 1 })}
                      &nbsp;%
                    </span>
                  </span>
                </div>
              </div>
            ) : (
              <div className="min-w-0 flex-1">
                <div className="h-6 rounded-md border border-dashed border-border" />
              </div>
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
 *  dass der Balken das Jahr VOR dem Plan zeigt, ist die Bedienungsanleitung
 *  für die Grafik. Stünde er nur dort, wo alle Jahrgänge denselben Stichtag
 *  tragen, fehlte er ausgerechnet im Block mit vier verschiedenen. */
export function StellenLegende() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[3px]"
          style={{ background: "var(--hh-ein-2)" }} aria-hidden />
        besetzt
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[3px]"
          style={{ background: "var(--hh-ein-5)" }} aria-hidden />
        nicht besetzt · rechts als Zahl und Anteil
      </span>
      <span>Stand jeweils am 30. Juni des Jahres vor dem Plan.</span>
    </div>
  );
}
