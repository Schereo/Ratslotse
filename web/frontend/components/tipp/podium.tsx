"use client";

// Podium als Treppe (Screen 1i) — Platz 2 / 1 / 3 in einem Raster
// `1fr 1.25fr 1fr`, nur Platz 1 mit Verlauf, Leucht-Schatten, Glanzband und
// Lotti. Feuert `ConfettiBurst` bei einem Führungswechsel und noch einmal am
// Endstand — beides höchstens alle 60 s und nie beim ersten Rendern (sonst
// feierte die Seite ihren eigenen Seitenaufbau).

import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import type { ApiAntwort } from "@/lib/vertrag";
import { ConfettiBurst } from "@/components/confetti";
import { Lotti } from "@/components/lotti";
import { cn } from "@/lib/utils";
import { useTween } from "./beamer-hooks";

type PredictionStand = ApiAntwort<"/tipp/stand">;
type Zeile = PredictionStand["rows"][number];

/** ▲▼-Chip zur Rangänderung — grün beim Aufstieg, neutrales Grau beim
 *  Abstieg (Designsprache: nichts Rotes, verlieren ist hier kein Fehler).
 *  Geteilt mit `scoreboard.tsx`. */
export function RangChip({ rank, rankBefore, className }: {
  rank: number | null; rankBefore: number | null; className?: string;
}) {
  if (rank === null || rankBefore === null || rank === rankBefore) return null;
  const auf = rank < rankBefore;
  const differenz = Math.abs(rank - rankBefore);
  return (
    <span className={cn(
      "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-mono text-[11px] font-semibold tabular-nums",
      auf ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" : "bg-muted text-muted-foreground",
      className,
    )}>
      {auf ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
      {/* Vorzeichen als Text, nicht nur die Pfeilfarbe — auf einem Beamer aus
          fünf Metern trägt eine Zahl allein die Richtung nicht zuverlässig,
          und „−" ist bewusst das Minuszeichen (U+2212), nicht der Bindestrich. */}
      {auf ? `+${differenz}` : `−${differenz}`}
    </span>
  );
}

function PunktZeile({ z }: { z: Zeile }) {
  const punkte = useTween(z.score?.total ?? 0);
  return (
    <>
      <p className="mt-1 truncate font-display text-[15px] font-bold sm:text-[17px]" title={z.name}>{z.name}</p>
      <p className="mt-0.5 flex items-center justify-center gap-1.5 font-mono text-[13px] tabular-nums text-muted-foreground sm:text-sm">
        {punkte} Punkte
        <RangChip rank={z.rank} rankBefore={z.rank_before} />
      </p>
    </>
  );
}

const SPALTE: Record<number, { hoehe: number; rang: string }> = {
  0: { hoehe: 232, rang: "2." },
  1: { hoehe: 300, rang: "1." },
  2: { hoehe: 200, rang: "3." },
};
// Spalte → Rang: Mitte (1) zeigt Platz 1, links (0) Platz 2, rechts (2) Platz 3.
const RANG_JE_SPALTE = [2, 1, 3];

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

  if (top3.length === 0) return null;

  return (
    <div className="mx-auto grid w-full max-w-4xl grid-cols-3 items-end gap-3 px-4 sm:gap-5">
      {konfetti && <ConfettiBurst onDone={() => setKonfetti(false)} />}
      {[0, 1, 2].map((spalte) => {
        const rang = RANG_JE_SPALTE[spalte];
        const z = top3.find((r) => r.rank === rang);
        const { hoehe } = SPALTE[spalte];
        const istErster = rang === 1;
        return (
          <div
            key={spalte}
            style={{ height: hoehe }}
            className={cn(
              "relative flex flex-col items-center justify-end overflow-hidden rounded-t-2xl border px-3 pb-4 pt-8 text-center",
              istErster
                ? "border-primary/30 bg-gradient-to-b from-primary to-primary/70 text-primary-foreground shadow-[0_0_50px_-12px_hsl(var(--primary)/0.65)]"
                : "border-border bg-card text-foreground",
            )}
          >
            {istErster && (
              <span
                aria-hidden
                className="animate-podium-glanz pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-white/25 to-transparent"
              />
            )}
            {istErster && (
              <Lotti
                regung="hebt-pokal"
                className="animate-podium-schweben absolute -top-14 h-[120px] w-[120px]"
                decorative
              />
            )}
            <span className={cn(
              "font-display text-[34px] font-black leading-none sm:text-[40px]",
              istErster ? "text-primary-foreground" : "text-foreground/25",
            )}>
              {rang}
            </span>
            {z ? <PunktZeile z={z} /> : (
              <p className="mt-1 text-[13px] text-muted-foreground/70">–</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
