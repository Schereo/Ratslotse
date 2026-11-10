// Das Zeitband eines Plans: wann er gilt und wann im Rat berichtet wurde.
//
// Gerechnet wird im Backend (council/plan_pages.py): Lagen kommen als Anteile
// einer Achse von 0 bis 1 an, hier wird nur gezeichnet — mit Prozent-Lagen in
// einem `relative`-Kasten statt in einem SVG, damit Punkte und Striche bei
// jeder Breite ihre Größe behalten.
//
// DAS BAND IST KEIN FORTSCHRITTSBALKEN (Plan § 3.4). Es zeigt Laufzeit, nicht
// Erledigtes: durchgehend ein Ton, die Gegenwart ist ein Strich quer durch
// alle Bänder. Was es sagt, sagt es über die Form:
//
//   gefüllt, Primär-Tint       beschlossen
//   gefüllt, neutral           zur Kenntnis genommen (≠ beschlossen, Regel 7)
//   gestrichelt                in Arbeit — „noch nicht fertig“ (DESIGNSPRACHE § 4)
//   läuft blass aus            ohne Enddatum; kommt blass herein: begann vor der Achse
//   Punkt / Ring               Bericht mit Vorlage / mündlich, ohne Text
//   Strich                     Beschluss über den Plan
//   Raute                      vorgesehene Überprüfung oder Fortschreibung
//   dünne Spur davor           die Laufzeit des Vorgängers

import type { CSSProperties } from "react";
import { percent, type PlanBand, type PlanLane } from "@/lib/plans";
import { cn } from "@/lib/utils";

type BandLook = PlanLane["style"];
type MarkKind = PlanLane["marks"][number]["kind"];

const FILL: Record<BandLook, string> = {
  adopted: "border border-primary/45 bg-primary/20",
  noted: "border border-muted-foreground/45 bg-muted-foreground/15",
  preparing: "border-[1.5px] border-dashed border-primary/60 bg-primary/[0.05]",
};

/** So breit ist der Übergang, wo ein Band über den Rand der Achse hinausgeht. */
const EDGE = "28px";

function edgeMask(band: PlanBand): string | undefined {
  if (band.open_start && band.beyond) {
    return `linear-gradient(to right, transparent, black ${EDGE}, black calc(100% - ${EDGE}), transparent)`;
  }
  if (band.open_start) return `linear-gradient(to right, transparent, black ${EDGE})`;
  if (band.beyond) return `linear-gradient(to left, transparent, black ${EDGE})`;
  return undefined;
}

function withMask(image: string | undefined): CSSProperties {
  return image ? { maskImage: image, WebkitMaskImage: image } : {};
}

/** Die Strecke selbst. `fade`: wie weit ein Band ohne Enddatum hinter seinem
 *  Ende (heute) noch ausläuft, als Anteil der Achse. `growing`: Das Band fährt
 *  einmal von seinem Beginn her auf (Detailseite) — die Richtung der Zeit,
 *  nicht ein Füllstand. */
export function BandShape({ band, look, fade, large = false, growing = false, arriving = false }: {
  band: PlanBand; look: BandLook; fade: number; large?: boolean; growing?: boolean;
  /** Das Band der Planseite: Ziel des Übergangs aus der Übersicht (components/plans/band-transition.ts). */
  arriving?: boolean;
}) {
  const height = large ? "h-3.5" : "h-2.5";
  const openLeft = band.open_start;
  const openRight = band.beyond || band.open_end;
  return (
    <>
      {/* Außen die Lage (und die Bewegung), innen die Form: Eine Animation auf
          dem zentrierten Element überschriebe dessen eigenes `transform`. */}
      <span data-band-shape {...(arriving ? { "data-plan-band": "" } : {})}
        className={cn("absolute inset-y-0 min-w-1.5", growing && "gb-balken-auf", arriving && "[view-transition-name:plan-band]")}
        style={{ left: percent(band.x0), width: percent(band.x1 - band.x0) }}>
        <span
          className={cn("absolute inset-x-0 top-1/2 -translate-y-1/2", height, FILL[look],
            openLeft ? "border-l-0" : "rounded-l-full", openRight ? "border-r-0" : "rounded-r-full")}
          style={withMask(edgeMask(band))}
        />
      </span>
      {band.open_end && (
        <span className={cn("absolute inset-y-0", growing && "gb-einblenden [animation-delay:320ms]")}
          style={{ left: percent(band.x1), width: percent(Math.min(fade, 1 - band.x1)) }}>
          <span className={cn("absolute inset-x-0 top-1/2 -translate-y-1/2 border-x-0", height, FILL[look])}
            style={withMask("linear-gradient(to right, black, transparent)")} />
        </span>
      )}
    </>
  );
}

/** Das Zeichen einer Station — ohne Lage, die setzt die Aufrufstelle. */
export function MarkGlyph({ kind, oral, look, large = false, className }: {
  kind: MarkKind; oral: boolean; look: BandLook; large?: boolean; className?: string;
}) {
  if (kind === "adoption" || kind === "amendment") {
    return (
      <span className={cn("block rounded-full", look === "noted" ? "bg-muted-foreground" : "bg-primary",
        kind === "adoption" ? (large ? "h-6 w-[3px]" : "h-4 w-[2.5px]") : (large ? "h-[18px] w-[2px]" : "h-3 w-[2px]"),
        className)} />
    );
  }
  if (kind === "preparation") {
    return (
      <span className={cn("block rounded-full", large ? "h-[7px] w-[7px]" : "h-[5px] w-[5px]",
        oral ? "border border-muted-foreground bg-card" : "bg-muted-foreground/70", className)} />
    );
  }
  return (
    <span className={cn("block rounded-full", large ? "h-[11px] w-[11px]" : "h-[7px] w-[7px]",
      oral ? "border-[1.5px] border-primary bg-card" : "bg-primary ring-[1.5px] ring-card", className)} />
  );
}

/** Die Raute der vorgesehenen Überprüfung. */
export function Diamond({ large = false, className }: { large?: boolean; className?: string }) {
  return (
    <span className={cn("block rotate-45 border-[1.5px] border-primary bg-card",
      large ? "h-[10px] w-[10px]" : "h-[7px] w-[7px]", className)} />
  );
}

/** Jahreslinien und der Strich für heute — über die volle Höhe des Kastens,
 *  damit sie von Zeile zu Zeile durchlaufen. */
export function AxisGrid({ ticks, today }: { ticks: readonly { x: number }[]; today: number | null }) {
  return (
    <>
      {ticks.map((t) => (
        <span key={t.x} className="absolute inset-y-0 w-px bg-border/70" style={{ left: percent(t.x) }} />
      ))}
      {today != null && (
        <span className="absolute inset-y-0 w-[1.5px] -translate-x-1/2 bg-signal" style={{ left: percent(today) }} />
      )}
    </>
  );
}

/** Reihenfolge beim Zeichnen: Vorgeschichte unten, Beschlüsse darüber, Berichte obenauf. */
const LAYER: Record<MarkKind, number> = { preparation: 0, adoption: 1, amendment: 1, report: 2, evaluation: 2 };

/** Ein Band der Übersicht auf der gemeinsamen Achse. Rein bildlich: Was es
 *  zeigt, steht daneben als Text (Kicker, Zahl der Berichte, der Lücken-Satz). */
export function TimeBand({ lane, ticks, today, fade, className }: {
  lane: PlanLane; ticks: readonly { x: number }[]; today: number; fade: number; className?: string;
}) {
  const { band, predecessor } = lane;
  const marks = [...lane.marks].sort((a, b) => LAYER[a.kind] - LAYER[b.kind]);
  return (
    <div aria-hidden className={cn("relative", className)}>
      <AxisGrid ticks={ticks} today={today} />
      {predecessor && (
        <>
          <span className="absolute top-1/2 h-[2px] -translate-y-1/2 rounded-full bg-muted-foreground/45"
            style={{ left: percent(predecessor.x0), width: percent(predecessor.x1 - predecessor.x0) }} />
          {band && band.x0 > predecessor.x1 && (
            <span className="absolute top-1/2 h-0 -translate-y-1/2 border-t-[1.5px] border-dotted border-muted-foreground/60"
              style={{ left: percent(predecessor.x1), width: percent(band.x0 - predecessor.x1) }} />
          )}
        </>
      )}
      {band && <BandShape band={band} look={lane.style} fade={fade} />}
      {lane.review != null && (
        <span className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: percent(lane.review) }}>
          <Diamond />
        </span>
      )}
      {marks.map((m, i) => (
        <span key={`${m.date}-${m.kind}-${i}`} className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{ left: percent(m.x) }}>
          <MarkGlyph kind={m.kind} oral={m.oral} look={lane.style} />
        </span>
      ))}
    </div>
  );
}

/** Die Jahre an den Bändern, jede Zahl mittig an ihrer Linie; auf schmalen
 *  Achsen nur jede zweite. `below`: Die Achse steht UNTER dem Band
 *  (Detailseite) — dann hängt „heute“ über den Jahren statt darunter. */
export function TimeAxis({ ticks, today, below = false, className }: {
  ticks: readonly { label: string; x: number }[]; today: number | null; below?: boolean; className?: string;
}) {
  return (
    <div aria-hidden className={cn("relative h-9 font-mono text-[10px] leading-none text-muted-foreground", className)}>
      {ticks.map((t, i) => (
        <span key={t.label}
          className={cn("absolute", below ? "bottom-0.5" : "top-1", i % 2 === 1 && "hidden @md/axis:block",
            // Auf der Detailseite endet die Achse am Kartenrand: Die äußeren Zahlen bleiben innen.
            below && t.x < 0.03 ? "" : below && t.x > 0.97 ? "-translate-x-full" : "-translate-x-1/2")}
          style={{ left: percent(t.x) }}>
          {t.label}
        </span>
      ))}
      {today != null && (
        <span className={cn("absolute -translate-x-1/2 font-medium uppercase tracking-[0.08em] text-orange-800 dark:text-orange-300",
          below ? "top-1" : "bottom-0 pb-1")}
          style={{ left: percent(today) }}>
          heute
        </span>
      )}
    </div>
  );
}
