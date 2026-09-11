"use client";

// Podium (Screen 1i) — Platz 2 / 1 / 3 als drei Karten im Raster
// `1fr 1.25fr 1fr`, Höhen 232 / 300 / 200 wie im Artboard. Nur Platz 1
// trägt den Verlauf, das Glanzband, den Leucht-Schatten, das FÜHRT-Etikett
// und Lotti mit dem Pokal. Feuert `ConfettiBurst` bei einem Führungswechsel
// und noch einmal am Endstand — beides höchstens alle 60 s und nie beim
// ersten Rendern (sonst feierte die Seite ihren eigenen Seitenaufbau).
//
// Alle Maße in px: Das Podium lebt auf der 1920×1080-Bühne (`buehne.tsx`),
// die als Ganzes skaliert wird.

import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import type { ApiAntwort } from "@/lib/vertrag";
import { ConfettiBurst } from "@/components/confetti";
import { Lotti } from "@/components/lotti";
import { cn } from "@/lib/utils";
import { useTween } from "./beamer-hooks";

type PredictionStand = ApiAntwort<"/tipp/stand">;
type Zeile = PredictionStand["rows"][number];

/** ▲▼-Chip zur Rangänderung — grün beim Aufstieg, neutral beim Abstieg
 *  (Designsprache: nichts Rotes, verlieren ist hier kein Fehler) und ein
 *  ruhiges „–", wenn sich nichts bewegt hat: Der Chip ist im Artboard immer
 *  da, damit die Zeile nicht springt, wenn er kommt oder geht. */
export function RangChip({ rank, rankBefore, className, hell }: {
  rank: number | null; rankBefore: number | null; className?: string;
  /** Auf dem blauen Platz-1-Feld: weiße Tönung statt Karte. */
  hell?: boolean;
}) {
  const bewegt = rank !== null && rankBefore !== null && rank !== rankBefore;
  const auf = bewegt && rank < rankBefore;
  const differenz = bewegt ? Math.abs(rank - rankBefore) : 0;
  return (
    <span
      // `key` an der Änderung: Eine neue fängt das 20-s-Verblassen frisch an.
      key={`${rank}-${rankBefore}`}
      className={cn(
        "inline-flex h-[34px] items-center gap-1 rounded-full px-3 text-[22px] font-semibold tabular-nums",
        !bewegt && (hell ? "bg-white/15 text-white/80" : "bg-muted text-muted-foreground"),
        bewegt && auf && (hell ? "bg-emerald-400/25 text-emerald-100" : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"),
        bewegt && !auf && (hell ? "bg-white/15 text-white/80" : "bg-muted text-muted-foreground"),
        bewegt && "animate-chip-verblasst",
        className,
      )}
      aria-label={bewegt ? (auf ? `${differenz} ${differenz === 1 ? "Platz" : "Plätze"} vorgerückt` : `${differenz} ${differenz === 1 ? "Platz" : "Plätze"} zurückgefallen`) : "unverändert"}
    >
      {!bewegt ? <Minus className="h-5 w-5" /> : auf ? <ArrowUp className="h-5 w-5" /> : <ArrowDown className="h-5 w-5" />}
      {bewegt && (auf ? `+${differenz}` : `−${differenz}`)}
    </span>
  );
}

function Punkte({ z, groesse, hell }: { z: Zeile; groesse: number; hell?: boolean }) {
  const punkte = useTween(z.score?.total ?? 0);
  return (
    <span
      style={{ fontSize: groesse }}
      className={cn("font-display font-semibold leading-none tabular-nums", hell ? "text-white" : "text-primary")}
    >
      {punkte}
    </span>
  );
}

export function Podium({ rows, phase }: { rows: Zeile[]; phase: string }) {
  const top3 = rows.filter((r) => r.rank !== null && r.rank <= 3).sort((a, b) => a.rank! - b.rank!);
  const platz1 = top3.find((r) => r.rank === 1) ?? null;
  const leaderId = platz1?.player_id ?? null;

  const [konfetti, setKonfetti] = useState(false);
  const leaderRef = useRef<number | null | undefined>(undefined);
  const phaseRef = useRef<string | undefined>(undefined);
  const letzteRef = useRef(0);

  useEffect(() => {
    const jetzt = Date.now();
    const wechsel = leaderRef.current !== undefined && leaderId !== null && leaderRef.current !== leaderId;
    const wurdeEndstand = phaseRef.current !== undefined && phaseRef.current !== "final" && phase === "final";
    if ((wechsel || wurdeEndstand) && jetzt - letzteRef.current > 60_000) {
      setKonfetti(true);
      letzteRef.current = jetzt;
    }
    leaderRef.current = leaderId;
    phaseRef.current = phase;
  }, [leaderId, phase]);

  const p1 = top3.find((r) => r.rank === 1);
  const p2 = top3.find((r) => r.rank === 2);
  const p3 = top3.find((r) => r.rank === 3);
  const endstand = phase === "final";

  return (
    <div data-testid="podium" className="mt-9 grid h-[300px] grid-cols-[1fr_1.25fr_1fr] items-end gap-7">

      {/* Platz 2 */}
      <Nebenplatz z={p2} rang={2} hoehe={232} nameGroesse={44} punkteGroesse={40} />

      {/* Platz 1 */}
      <div className="relative flex h-[300px] flex-col overflow-hidden rounded-[30px] border border-[hsl(202_90%_60%/0.5)] bg-gradient-to-br from-[hsl(205_92%_34%)] to-[hsl(205_92%_24%)] px-9 py-[30px] text-white shadow-[0_30px_80px_-30px_hsl(202_90%_60%/0.5)]">
        <span aria-hidden className="animate-podium-glanz pointer-events-none absolute inset-y-[-20%] left-0 w-[26%] bg-gradient-to-r from-transparent via-white/15 to-transparent" />
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-3.5">
            <span className="font-display text-[56px] font-semibold leading-none">1</span>
            <span className="font-mono text-[22px] uppercase tracking-[0.12em] text-[hsl(19_95%_65%)]">
              {endstand ? "Gewonnen" : "Führt"}
            </span>
          </div>
          {p1 && <RangChip rank={p1.rank} rankBefore={p1.rank_before} hell />}
        </div>
        <div className="animate-podium-schweben absolute right-[26px] top-[70px]">
          <Lotti regung="hebt-pokal" className="h-[120px] w-[120px]" decorative />
        </div>
        <p className="relative mt-auto truncate font-display text-[64px] font-bold leading-none tracking-[-0.025em]" title={p1?.name}>
          {p1?.name ?? "–"}
        </p>
        <div className="relative mt-2.5 flex items-baseline gap-3">
          {p1 ? <Punkte z={p1} groesse={56} hell /> : <span className="font-display text-[56px]">–</span>}
          {p1?.score && (
            <span className="text-[24px] text-white/80">
              Punkte · {p1.score.exact_lists} richtig{p1.score.mayor_points > 0 && ` · OB +${p1.score.mayor_points}`}
            </span>
          )}
        </div>
      </div>

      {/* Platz 3 */}
      <Nebenplatz z={p3} rang={3} hoehe={200} nameGroesse={40} punkteGroesse={36} />
      {/* Nach den drei Karten, nicht davor: Die Browsertests greifen die
          Plätze über ihre Reihenfolge im Raster — und ein Konfetti-Regen darf
          nicht zum „ersten Platz" werden. */}
      {konfetti && <ConfettiBurst onDone={() => setKonfetti(false)} />}
    </div>
  );
}

function Nebenplatz({ z, rang, hoehe, nameGroesse, punkteGroesse }: {
  z: Zeile | undefined; rang: number; hoehe: number; nameGroesse: number; punkteGroesse: number;
}) {
  return (
    <div style={{ height: hoehe }} className="flex flex-col rounded-[26px] border border-border bg-card px-[30px] py-[26px]">
      <div className="flex items-center justify-between">
        <span className="font-display text-[44px] font-semibold leading-none text-muted-foreground">{rang}</span>
        {z && <RangChip rank={z.rank} rankBefore={z.rank_before} />}
      </div>
      <p style={{ fontSize: nameGroesse }} className="mt-auto truncate font-display font-bold leading-[1.05] tracking-[-0.02em]" title={z?.name}>
        {z?.name ?? "–"}
      </p>
      <div className="mt-1.5 flex items-baseline gap-2.5">
        {z ? <Punkte z={z} groesse={punkteGroesse} /> : <span className="font-display text-[40px] text-muted-foreground">–</span>}
        {z?.score && <span className="text-[22px] text-muted-foreground">Punkte · {z.score.exact_lists} richtig</span>}
      </div>
    </div>
  );
}
