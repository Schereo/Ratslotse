"use client";

// Hantel-Diagramm „geplant und tatsächlich" (Design H-16, Empfehlung).
//
// Zwei Punkte auf einer gemeinsamen Achse, dazwischen eine Linie: Die Linie
// IST die Abweichung — Länge und Richtung liest man, ohne die Zahl zu suchen.
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

export function Hantel({ zeilen, maxWert, klein = false, einheit = "Mio." }: {
  zeilen: HantelZeile[];
  /** Gemeinsame Skala aller Zeilen — sonst wären die Längen nicht vergleichbar. */
  maxWert?: number;
  klein?: boolean;
  einheit?: string;
}) {
  const gueltig = zeilen.filter((z) => z.plan != null && z.ist != null);
  if (!gueltig.length) return null;
  const max = maxWert ?? Math.max(...gueltig.flatMap((z) => [z.plan ?? 0, z.ist ?? 0]));
  const pos = (v: number) => (max > 0 ? (v / max) * 100 : 0);

  return (
    <div className={cn("flex flex-col", klein ? "gap-2" : "gap-3")}>
      {gueltig.map((z) => {
        const plan = z.plan as number, ist = z.ist as number;
        const diff = Math.round((ist - plan) * 10) / 10;
        const von = Math.min(pos(plan), pos(ist));
        const bis = Math.max(pos(plan), pos(ist));
        return (
          <div key={z.label} className={cn("grid items-center gap-x-3",
            klein ? "grid-cols-[1fr_auto]" : "grid-cols-[minmax(96px,150px)_1fr_auto]")}>
            {!klein && <span className="truncate text-[12.5px]">{z.label}</span>}
            <div className="relative h-5">
              {/* Achse */}
              <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border/70" />
              {/* Die Abweichung als Strecke */}
              <div className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-signal/70"
                style={{ left: `${von}%`, width: `${Math.max(bis - von, 0.4)}%` }} />
              {/* Geplant: offener Punkt. Tatsächlich: gefüllter Punkt. */}
              <span className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-card"
                style={{ left: `${pos(plan)}%`, borderColor: "var(--hh-ein-0)" }}
                title={`geplant ${deMio(plan)}`} />
              <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ left: `${pos(ist)}%`, background: "var(--hh-aus-0)" }}
                title={`tatsächlich ${deMio(ist)}`} />
            </div>
            <span className="whitespace-nowrap text-right text-[12px] tabular-nums">
              <span className="text-muted-foreground">{deMio(plan)}</span>
              <span className="mx-1 text-muted-foreground">→</span>
              <span className="font-semibold">{deMio(ist)}</span>
              <span className={cn("ml-1.5", diff !== 0 && "text-signal")}>
                {diff > 0 ? "+" : ""}{deMio(diff)}
              </span>
            </span>
          </div>
        );
      })}
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
            Die Farbe bewertet nicht: Mehr ausgegeben kann ein Tarifabschluss sein oder mehr
            Kita-Plätze; weniger ausgegeben heißt oft, dass etwas nicht gebaut oder eine Stelle
            nicht besetzt wurde.
          </span>
        </div>
      )}
    </div>
  );
}
