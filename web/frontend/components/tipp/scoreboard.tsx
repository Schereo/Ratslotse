"use client";

// Scoreboard (Screen 1i) — das Herzstück: Kopf, Podium, die zweispaltige
// Rangliste ab Platz 4, Fußzeile. Maße aus dem Artboard (1920×1080), die
// Bühne skaliert das Ganze (`buehne.tsx`).
//
// Die Zeilen sind absolut positioniert (`top`/`left` je Rang), eine
// CSS-`transition` erledigt die Bewegung — kein FLIP, kein JS-Timer. Bei
// `prefers-reduced-motion` fällt nur die Transition weg, die Position bleibt.
//
// Passt die Runde nicht in zwei Spalten (mehr als 12 ab Platz 4), werden es
// drei, und die Zeilen rücken enger zusammen — die Fläche ist fest, die
// Runde nicht.

import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";
import { Podium, RangChip } from "./podium";
import { useTween, useFrisch } from "./beamer-hooks";
import { BeamerKopf, LivePunkt } from "./buehne";
import { mitRunde, uhrzeitKurz } from "@/lib/tipp";

type PredictionStand = ApiAntwort<"/tipp/stand">;
type Zeile = PredictionStand["rows"][number];

//: Der Platz, den die Rangliste auf der Bühne hat: 1080 − Ränder − Kopf −
//: Podium − Fußzeile (alle Werte aus dem Artboard).
const LISTEN_HOEHE = 1080 - 48 - 40 - 44 - 36 - 300 - 34 - 22 - 30;
const ZEILE_VOLL = 74;
const ABSTAND = 14;

function Ranglistenzeile({ z, index, proSpalte, spalten, hoehe, gewertet }: {
  z: Zeile; index: number; proSpalte: number; spalten: number; hoehe: number;
  /** Steht schon ein Ergebnis? Sonst ist die Liste nur „wer mitspielt" —
   *  dann ohne Rang, Chip und Punkte, denn die gibt es noch nicht. */
  gewertet: boolean;
}) {
  const i = index % proSpalte;
  const spalte = Math.floor(index / proSpalte);
  const punkte = useTween(z.score?.total ?? 0);
  const frisch = useFrisch(z.rank !== null ? -z.rank : Number.NEGATIVE_INFINITY);
  const ohneTipp = !z.has_tip;
  const kompakt = hoehe < 64;
  const breite = `calc((100% - ${(spalten - 1) * 28}px) / ${spalten})`;
  const left = `calc((100% + 28px) / ${spalten} * ${spalte})`;

  return (
    <div
      style={{ top: i * (hoehe + ABSTAND), left, width: breite, height: hoehe }}
      className={cn(
        "absolute grid items-center gap-4 rounded-[18px] border border-border bg-card pl-5 pr-6",
        gewertet
          ? (kompakt ? "grid-cols-[52px_1fr_auto_150px]" : "grid-cols-[70px_1fr_auto_190px]")
          : (kompakt ? "grid-cols-[34px_1fr]" : "grid-cols-[44px_1fr]"),
        "transition-[top,left,background-color] duration-[900ms] ease-[cubic-bezier(.2,.8,.2,1)] motion-reduce:transition-none",
        frisch && "animate-zeile-frisch",
        ohneTipp && "opacity-50",
      )}
    >
      {gewertet ? (
        <span className={cn("font-display font-semibold text-muted-foreground tabular-nums", kompakt ? "text-[26px]" : "text-[36px]")}>
          {z.rank ?? "–"}
        </span>
      ) : (
        <span aria-hidden className="h-3 w-3 rounded-full bg-primary/40" />
      )}
      <span className="flex min-w-0 items-center gap-3.5">
        <span className={cn("truncate font-semibold", kompakt ? "text-[22px]" : "text-[30px]")} title={z.name}>{z.name}</span>
        {z.late_at && (
          <span className="flex-none rounded-full border border-[#92400e] px-2.5 py-0.5 font-mono text-[18px] uppercase tracking-[0.08em] text-[#fcd34d]">
            Später Tipp {uhrzeitKurz(z.late_at)}
          </span>
        )}
      </span>
      {gewertet && (
        <>
          <RangChip rank={z.rank} rankBefore={z.rank_before} className={cn(kompakt && "h-[28px] text-[18px]")} />
          <span className="flex items-baseline justify-end gap-2 whitespace-nowrap">
            <span className={cn("font-display font-semibold tabular-nums text-primary", kompakt ? "text-[26px]" : "text-[36px]")}>
              {ohneTipp ? "–" : punkte}
            </span>
            {!ohneTipp && z.score && (
              <span className={cn("text-muted-foreground", kompakt ? "text-[16px]" : "text-[20px]")}>{z.score.exact_lists} richtig</span>
            )}
          </span>
        </>
      )}
    </div>
  );
}

export function Scoreboard({ stand, runde }: { stand: PredictionStand; runde: string | null }) {
  // Vor dem ersten Ergebnis hat niemand einen Rang: Dann ist diese Seite die
  // Liste der Mitspielenden — kein Podium, keine Punkte, keine Striche, wo
  // Zahlen stehen sollten.
  const gewertet = stand.rows.some((r) => r.rank !== null);
  const rest = stand.rows.filter((r) => !(r.rank !== null && r.rank <= 3));
  const spalten = rest.length > 12 ? 3 : 2;
  const proSpalte = Math.max(1, Math.ceil(rest.length / spalten));
  const platz = gewertet ? LISTEN_HOEHE : LISTEN_HOEHE + 300 + 34;
  const hoehe = Math.max(44, Math.min(ZEILE_VOLL, Math.floor(platz / proSpalte) - ABSTAND));
  const endstand = stand.phase === "final";

  return (
    <div className="flex h-full flex-col bg-[radial-gradient(900px_500px_at_50%_-10%,hsl(205_92%_34%/0.12),transparent_70%)] px-20 pb-10 pt-12 text-foreground dark:bg-[radial-gradient(900px_500px_at_50%_-10%,hsl(205_92%_34%/0.35),transparent_70%)]">
      <BeamerKopf
        untertitel={gewertet ? "Tippspiel · Rangliste" : `Tippspiel · ${rest.length} dabei`}
        rechts={gewertet ? (
          <>
            <LivePunkt endstand={endstand} />
            {stand.area_label && <span>{stand.area_label}</span>}
            <span>·</span>
            <span className="font-mono">{stand.stand_label || "–"}</span>
          </>
        ) : (
          // Ohne Ergebnis wäre „Live · –" eine Zusage, die keine Zahl deckt.
          <span>{stand.phase === "open" ? "Tippen möglich" : "Warten auf die erste Hochrechnung"}</span>
        )}
      />

      {gewertet && <Podium rows={stand.rows} phase={stand.phase} />}

      <div className={cn("relative flex-1", gewertet ? "mt-[34px]" : "mt-10")}>
        {rest.map((z, index) => (
          <Ranglistenzeile key={z.player_id} z={z} index={index} proSpalte={proSpalte} spalten={spalten} hoehe={hoehe} gewertet={gewertet} />
        ))}
      </div>

      <div className="mt-[22px] flex items-center justify-between text-[22px] text-muted-foreground">
        <span>
          {gewertet
            ? "Je Liste: 5 Punkte für die richtige Sitzzahl, 3 bei 1 Sitz daneben, 1 bei 2 Sitzen daneben. OB-Bonus: bis zu 6 pro Person."
            : "Mit der ersten Hochrechnung siehst du hier, wer vorne liegt."}
        </span>
        <span className="font-mono">ratslotse.de{mitRunde("/tipp", runde, "runde")}</span>
      </div>
    </div>
  );
}

/** Die Rangliste fürs Handy — ohne Bühne, ohne Podium-Treppe: eine Liste,
 *  die man in der Hand scrollt. Dieselben Zeilen, dieselben Chips. */
export function HandyRangliste({ stand, probe }: { stand: PredictionStand; probe?: boolean }) {
  const endstand = stand.phase === "final";
  const mitRang = stand.rows.filter((r) => r.rank !== null);
  const ohne = stand.rows.filter((r) => r.rank === null);
  return (
    <div className="mx-auto max-w-md px-4 pb-8 pt-[calc(env(safe-area-inset-top)+14px)]">
      {/* Die rechte obere Ecke gehört dem Erscheinungsbild-Schalter
          (`live.tsx`): 56 px breit, 16 px vom Rand. 72 px Freiraum lassen
          dazwischen noch 16 px Luft — bei 56 px stießen Abzeichen und
          Schalter auf 0 px aneinander (gemessen bei 390 und 320 px). */}
      <div className="flex items-center justify-between gap-2 pr-[72px]">
        <span className="truncate font-display text-[15px] font-bold">Tippspiel · Rangliste</span>
        <span className="inline-flex flex-none items-center gap-1.5 rounded-full border border-primary/20 bg-primary/[0.08] px-2.5 py-1 text-[11.5px] font-semibold text-primary">
          {/* Der pulsierende Punkt sagt „hier bewegt sich etwas" — ohne Stand
              bewegt sich nichts, dann bleibt er weg. */}
          {stand.stand_label && <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-signal motion-reduce:animate-none" />}
          {stand.stand_label ? `${endstand ? "Endstand" : "Live"} · ${stand.stand_label}` : "Noch kein Ergebnis"}
        </span>
      </div>
      {probe && (
        <p className="mt-3 rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-center font-mono text-[10px] uppercase tracking-[0.08em] text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200">
          Generalprobe · Zahlen von 2021
        </p>
      )}
      {mitRang.length === 0 && (
        <p className="mt-6 text-sm leading-relaxed text-muted-foreground">
          Noch kein Ergebnis — sobald die erste Hochrechnung da ist, steht hier die Rangliste.
        </p>
      )}
      <div className="mt-3 flex flex-col gap-2">
        {mitRang.map((z) => (
          <div key={z.player_id} className={cn(
            "grid grid-cols-[34px_1fr_auto_auto] items-center gap-2.5 rounded-xl border border-border bg-card px-3 py-2.5",
            z.rank === 1 && "border-primary/30 bg-primary/5",
          )}>
            <span className="font-display text-[19px] font-bold text-muted-foreground tabular-nums">{z.rank}</span>
            <span className="flex min-w-0 items-center gap-2">
              <span className="truncate text-[15px] font-semibold">{z.name}</span>
              {z.late_at && <span className="flex-none rounded-full border border-amber-300 px-1.5 font-mono text-[9px] uppercase text-amber-700 dark:border-amber-500/40 dark:text-amber-300">später Tipp</span>}
            </span>
            <RangChip rank={z.rank} rankBefore={z.rank_before} className="h-6 px-2 text-[12px]" />
            <span className="font-display text-[19px] font-bold tabular-nums text-primary">{z.score?.total ?? "–"}</span>
          </div>
        ))}
        {ohne.map((z) => (
          <div key={z.player_id} className="grid grid-cols-[34px_1fr] items-center gap-2.5 rounded-xl border border-border bg-card px-3 py-2.5 opacity-60">
            <span className="text-muted-foreground">–</span>
            <span className="truncate text-[15px] font-semibold">{z.name}</span>
          </div>
        ))}
      </div>
      <p className="mt-4 text-center text-[11.5px] text-muted-foreground">
        Je Liste: 5 Punkte für die richtige Sitzzahl, 3 bei 1 Sitz daneben, 1 bei 2 Sitzen daneben. OB-Bonus: bis zu 6 pro Person.
      </p>
    </div>
  );
}
