"use client";

// Hantel-Diagramm „geplant und tatsächlich" (Design H-16, Empfehlung).
//
// Zwei Punkte auf einer gemeinsamen Achse, dazwischen eine Linie: Die Linie
// IST die Abweichung — Länge und Richtung liest man, ohne die Zahl zu suchen.
//
// WARUM DIE ACHSE DIE ABWEICHUNG ZEIGT UND NICHT DEN BETRAG.
// Die erste Fassung setzte beide Punkte auf eine Skala von 0 bis zum größten
// Wert. Bei echten Haushaltszahlen fallen sie damit aufeinander: Ein Bereich
// mit 6,2 geplant und 6,3 tatsächlich hat auf einer Skala bis 251 Mio. eine
// Differenz von 0,04 % der Breite — unsichtbar. Genau die Differenz ist aber
// die Aussage. Deshalb liegt der Nullpunkt jetzt bei „wie geplant", und die
// Strecke misst, wie weit es davon abwich. Die Beträge selbst stehen als Zahl
// daneben; sie brauchen keine Pixel, um lesbar zu sein.
//
// KEINE BEWERTUNGSFARBEN. Mehrausgaben sind nicht automatisch schlecht
// (Tarifabschluss, mehr Kita-Plätze), Minderausgaben nicht automatisch gut
// (nicht gebaut, Stellen unbesetzt). Deshalb steht Signal-Orange hier nur für
// „hier ist die Differenz", nicht für „das ist schlimm" — und Grün kommt gar
// nicht vor.

import { deMio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

export type HantelZeile = {
  label: string;
  plan: number | null;
  ist: number | null;
};

export function Hantel({ zeilen, klein = false, einheit = "Mio." }: {
  zeilen: HantelZeile[];
  klein?: boolean;
  einheit?: string;
}) {
  const gueltig = zeilen.filter((z) => z.plan != null && z.ist != null);
  if (!gueltig.length) return null;

  const diff = (z: HantelZeile) => Math.round(((z.ist as number) - (z.plan as number)) * 10) / 10;
  // Gemeinsame Skala über alle Zeilen — sonst wären die Längen nicht
  // vergleichbar. Die Null ist immer dabei, auch wenn alle Abweichungen in
  // dieselbe Richtung gehen: Sonst verschöbe sich der Bezugspunkt.
  const werte = gueltig.map(diff);
  const min = Math.min(0, ...werte);
  const max = Math.max(0, ...werte);
  const spanne = max - min || 1;
  const pos = (v: number) => ((v - min) / spanne) * 100;
  const nullPos = pos(0);

  const gitter = klein ? "grid-cols-[minmax(38px,auto)_1fr_auto]" : "grid-cols-[minmax(96px,150px)_1fr_auto]";

  return (
    <div className={cn("flex flex-col", klein ? "gap-1.5" : "gap-2.5")}>
      {gueltig.map((z) => {
        const d = diff(z);
        const plan = z.plan as number;
        const anteil = plan !== 0 ? (d / Math.abs(plan)) * 100 : null;
        return (
          <div key={z.label} className={cn("grid items-center gap-x-3", gitter)}>
            <span className={cn("truncate", klein ? "text-[11.5px] tabular-nums text-muted-foreground" : "text-[12.5px]")}>
              {z.label}
            </span>
            <div className="relative h-5">
              {/* Achse und die Marke „wie geplant" */}
              <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border/60" />
              <div className="absolute inset-y-0 w-px bg-border" style={{ left: `${nullPos}%` }} />
              {/* Die Abweichung als Strecke, ab der Null */}
              <div
                className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-signal/70"
                style={{
                  left: `${Math.min(nullPos, pos(d))}%`,
                  width: `${Math.max(Math.abs(pos(d) - nullPos), 0.5)}%`,
                }}
              />
              {/* Geplant: offener Punkt auf der Null. Tatsächlich: gefüllter Punkt am Ende. */}
              <span
                className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-card"
                style={{ left: `${nullPos}%`, borderColor: "var(--hh-ein-0)" }}
                title={`geplant ${deMio(plan)}`}
              />
              <span
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ left: `${pos(d)}%`, background: "var(--hh-aus-0)" }}
                title={`tatsächlich ${deMio(z.ist as number)}`}
              />
            </div>
            <span className="whitespace-nowrap text-right text-[12px] tabular-nums">
              <span className="text-muted-foreground">{deMio(plan)}</span>
              <span className="mx-1 text-muted-foreground">→</span>
              <span className="font-semibold">{deMio(z.ist as number)}</span>
              <span className={cn("ml-1.5", d !== 0 && "text-signal")}>
                {d > 0 ? "+" : ""}{deMio(d)}
              </span>
              {!klein && anteil != null && (
                <span className="ml-1 text-[11px] text-muted-foreground">
                  ({anteil > 0 ? "+" : "−"}{Math.abs(anteil).toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%)
                </span>
              )}
            </span>
          </div>
        );
      })}

      {/* Skalenenden — ohne sie wüsste niemand, wofür die Länge steht. */}
      <div className={cn("grid gap-x-3", gitter)}>
        <span />
        <div className="relative h-4 text-[10px] tabular-nums text-muted-foreground">
          {min < 0 && <span className="absolute left-0 top-0">{deMio(min)}</span>}
          <span className="absolute top-0 -translate-x-1/2 whitespace-nowrap" style={{ left: `${nullPos}%` }}>
            wie geplant
          </span>
          {max > 0 && <span className="absolute right-0 top-0">+{deMio(max)}</span>}
        </div>
        <span />
      </div>

      {!klein && (
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/60 pt-2.5 text-[11.5px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full border-2 bg-card" style={{ borderColor: "var(--hh-ein-0)" }} />
            geplant
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full" style={{ background: "var(--hh-aus-0)" }} />
            tatsächlich
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-[3px] w-4 rounded-full bg-signal/70" />
            Abweichung in {einheit} Euro
          </span>
          <span className="basis-full text-[11px] leading-relaxed">
            Die Strecke misst den Abstand zum Plan, nicht die Höhe des Betrags — sonst wären
            Abweichungen von unter einem Prozent nicht zu sehen. Die Farbe bewertet nicht: Mehr
            ausgegeben kann ein Tarifabschluss sein oder mehr Kita-Plätze; weniger ausgegeben heißt
            oft, dass etwas nicht gebaut oder eine Stelle nicht besetzt wurde.
          </span>
        </div>
      )}
    </div>
  );
}
