"use client";

// Scoreboard (Screen 1i) — Kopf mit Live-Punkt, Podium, dann die
// zweispaltige Rangliste ab Platz 4. Positionierung über `top`/`left` statt
// einer FLIP-Messung: React schreibt bei jedem Poll die Zielposition direkt,
// eine CSS-`transition` erledigt den Rest — ruht bei prefers-reduced-motion
// von selbst, weil dann nur die `transition` wegfällt, nicht die Position.

import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";
import { Podium, RangChip } from "./podium";
import { useTween, useFrisch } from "./beamer-hooks";

type PredictionStand = ApiAntwort<"/tipp/stand">;
type Zeile = PredictionStand["rows"][number];

const ZEILEN_HOEHE = 82;
const ZEILEN_KARTE_HOEHE = 74;

function Zeitspaeter({ iso }: { iso: string }) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const hhmm = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
  return <span className="ml-1.5 flex-none text-[10px] font-medium text-amber-700 dark:text-amber-400">Nachgetippt {hhmm}</span>;
}

function Ranglistenzeile({ z, index, proSpalte }: { z: Zeile; index: number; proSpalte: number }) {
  const i = index % proSpalte;
  const spalte = Math.floor(index / proSpalte);
  const punkte = useTween(z.score?.total ?? 0);
  const frisch = useFrisch(z.rank !== null ? -z.rank : Number.NEGATIVE_INFINITY);
  const ohneTipp = !z.has_tip;

  return (
    <div
      // Die zweispaltige, animierte Positionierung ist für den Beamer gebaut
      // (feste 190px-Punktespalte, 74px hohe Zeilen) — auf dem Handy bräuchte
      // das mehr Breite, als 390px hergeben (gemessen: 116px Überbreite). Ab
      // `sm:` gilt `position:absolute` mit `top`/`left` aus den CSS-Variablen;
      // darunter bleibt die Zeile im normalen Fluss, einspaltig, ohne
      // Positions-Übergang — der Endzustand (wer wo steht) ist derselbe.
      style={{ "--zt": `${i * ZEILEN_HOEHE}px`, "--zl": spalte === 0 ? "0px" : "calc(50% + 14px)" } as React.CSSProperties}
      className={cn(
        "relative mb-2 grid w-full grid-cols-[40px_1fr_auto_70px] items-center gap-2 rounded-xl border border-border bg-card px-3 py-2.5",
        "sm:absolute sm:top-[var(--zt)] sm:left-[var(--zl)] sm:mb-0 sm:w-[calc(50%-14px)] sm:grid-cols-[70px_1fr_auto_190px] sm:py-0",
        "sm:transition-[top,left] sm:duration-[900ms] sm:ease-[cubic-bezier(.2,.8,.2,1)] motion-reduce:transition-none",
        "h-auto sm:h-[74px]",
        frisch && "animate-zeile-frisch",
        ohneTipp && "opacity-50",
      )}
    >
      <span className="font-display text-[19px] font-bold text-muted-foreground tabular-nums">{z.rank ?? "–"}</span>
      <span className="flex min-w-0 items-center">
        <span className="truncate font-semibold" title={z.name}>{z.name}</span>
        {z.late_at && <Zeitspaeter iso={z.late_at} />}
      </span>
      <span className="hidden text-[11px] text-muted-foreground sm:block">{ohneTipp && "kein Tipp"}</span>
      <span className="flex items-center justify-end gap-2 font-mono text-[15px] font-bold tabular-nums">
        {ohneTipp ? "–" : punkte}
        {/* `key` bindet das Element an genau DIESE Rangänderung — eine neue
            fängt die 20-s-Verblassen-Animation frisch von vorn an, ohne
            eigenen JS-Timer. */}
        {z.rank !== null && z.rank_before !== null && z.rank !== z.rank_before && (
          <span key={`${z.rank}-${z.rank_before}`} className="animate-chip-verblasst">
            <RangChip rank={z.rank} rankBefore={z.rank_before} />
          </span>
        )}
      </span>
    </div>
  );
}

export function Scoreboard({ stand }: { stand: PredictionStand }) {
  const rest = stand.rows.filter((r) => !(r.rank !== null && r.rank <= 3));
  const proSpalte = Math.ceil(rest.length / 2);
  const endstand = stand.phase === "final";

  return (
    <div className="flex h-full flex-col px-4 py-6 sm:px-10 sm:py-8">
      <header className="mx-auto flex w-full max-w-4xl items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5">
            {!endstand && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[hsl(19_95%_60%)] opacity-75 motion-reduce:hidden" />
            )}
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[hsl(19_95%_60%)]" />
          </span>
          <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
            {stand.area_label}
          </span>
        </div>
        <p className="font-display text-lg font-bold sm:text-xl">
          {endstand ? "Endstand" : stand.stand_label}
        </p>
      </header>

      <div className="mt-6 sm:mt-8">
        <Podium rows={stand.rows} phase={stand.phase} />
      </div>

      {/* `minHeight` nur ab `sm:` (per CSS-Variable) — darunter stehen die
          Zeilen im normalen Fluss und brauchen keine vorreservierte Höhe. */}
      <div
        style={{ "--sb-min-h": `${proSpalte * ZEILEN_HOEHE}px` } as React.CSSProperties}
        className="relative mx-auto mt-8 flex w-full max-w-4xl flex-1 flex-col sm:block sm:min-h-[var(--sb-min-h)]"
      >
        {rest.map((z, index) => (
          <Ranglistenzeile key={z.player_id} z={z} index={index} proSpalte={proSpalte} />
        ))}
      </div>

      <footer className="mx-auto mt-6 max-w-4xl text-center text-[12px] text-muted-foreground">
        5 Punkte für den exakten Sitz, 3 bei ±1, 1 bei ±2 · 6 Punkte für die exakte OB-Prozentzahl, 3 bei ±1,5, 1 bei ±3
        <span className="mx-1.5">·</span>
        ratslotse.de/tipp
      </footer>
    </div>
  );
}
