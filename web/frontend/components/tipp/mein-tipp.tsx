"use client";

// 1e — „Mein Tipp": vor der ersten Zahl eine Bestätigung, danach Rang,
// Punkte und der Tipp Zeile für Zeile gegen den Stand. Reine Anzeige — wer
// rechtzeitig getippt hat, kann seinen Tipp nach Tipp-Schluss nicht mehr
// ändern (das übernimmt Screen 1d, solange offen ist).

import Link from "next/link";
import { rangDeltaText, rangPfeil } from "@/lib/tipp";
import type { TippMeins, TippSetup } from "@/lib/tipp";
import { Button } from "@/components/ui/button";

function punktTon(punkte: number, hoechst: number): string {
  if (punkte === hoechst) return "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
  if (punkte > 0) return "bg-primary/10 text-primary";
  return "bg-muted text-muted-foreground";
}

export function MeinTipp({ setup, meins }: { setup: TippSetup; meins: TippMeins }) {
  const parteiVon: Record<string, TippSetup["parties"][number]> = Object.fromEntries(
    setup.parties.map((p) => [p.slug, p]),
  );
  const pfeil = rangPfeil(meins.rank, meins.rank_before);
  const score = meins.score;
  const nullAufNullListen = meins.seats.filter((s) => s.tip === 0 && s.actual === 0);

  return (
    <div className="mx-auto min-h-[100dvh] max-w-md pb-8">
      <div className="flex items-center justify-between px-4 pt-[calc(env(safe-area-inset-top)+10px)]">
        <span className="font-display text-[15px] font-bold">Tippspiel</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/[0.08] px-2.5 py-1 text-[11.5px] font-semibold text-primary">
          <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-signal" />
          {meins.phase === "final" ? "Endstand" : "Live"} · {meins.stand_label || "wartet"}
        </span>
      </div>

      {!score ? (
        <div className="mx-4 mt-3.5 rounded-2xl bg-primary p-4 text-primary-foreground">
          <p className="font-mono text-[10px] uppercase tracking-[0.11em] opacity-75">{meins.name} · Dein Tipp</p>
          <p className="mt-2 text-sm leading-relaxed opacity-90">
            Dein Tipp ist gespeichert. Sobald die erste Zahl veröffentlicht ist, siehst du hier deinen Rang.
          </p>
        </div>
      ) : (
        <div className="mx-4 mt-3.5 overflow-hidden rounded-2xl bg-primary p-4 pb-4 text-primary-foreground">
          <p className="font-mono text-[10px] uppercase tracking-[0.11em] opacity-75">{meins.name} · Dein Rang</p>
          <div className="mt-1.5 flex items-end gap-3.5">
            <span className="font-display text-[64px] leading-[0.9] tracking-tight">{meins.rank ?? "–"}</span>
            <div className="flex-1 pb-1.5">
              {pfeil && <p className="text-sm font-semibold">{rangDeltaText(pfeil)}</p>}
            </div>
            <div className="pb-1 text-right">
              <p className="font-display text-[34px] leading-none">{score.total}</p>
              <p className="text-xs opacity-80">Punkte</p>
            </div>
          </div>
          <p className="mt-3 text-[12.5px] opacity-85">
            Sitze {score.seat_points} · OB-Bonus {score.mayor_points} · {score.exact_lists} Listen exakt
          </p>
        </div>
      )}

      <div className="mt-4 px-4">
        <div className="flex justify-between font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          <span>Dein Tipp · Stand</span>
          <span>{meins.stand_label || "wartet"}</span>
        </div>
        <div className="mt-2 overflow-hidden rounded-[14px] border border-border bg-card">
          {meins.seats.map((s) => {
            const p = parteiVon[s.slug];
            return (
              <div
                key={s.slug}
                className="grid grid-cols-[8px_1fr_34px_34px_44px] items-center gap-2.5 border-t border-muted px-3.5 py-2 text-[13px] first:border-t-0"
              >
                <span className="h-2 w-2 rounded-full shadow-[inset_0_0_0_1px_rgba(0,0,0,0.15)]" style={{ background: p?.color }} />
                <span className="truncate font-semibold">{p?.short ?? s.slug}</span>
                <span className="text-right font-mono text-muted-foreground">{s.tip}</span>
                <span className="text-right font-display text-[15px] font-bold">{s.actual ?? "–"}</span>
                <span className={`rounded-full py-0.5 text-center text-[11px] font-semibold ${punktTon(s.points, 5)}`}>
                  {s.points}
                </span>
              </div>
            );
          })}
          <div className="grid grid-cols-[8px_1fr_34px_34px_44px] gap-2.5 px-3.5 pb-2 pt-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
            <span />
            <span />
            <span className="text-right">Tipp</span>
            <span className="text-right">Ist</span>
            <span className="text-center">Pkt</span>
          </div>
        </div>
        {nullAufNullListen.length > 0 && (
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            {nullAufNullListen.length} Liste{nullAufNullListen.length === 1 ? "" : "n"} ohne Sitz:{" "}
            {nullAufNullListen.map((s) => parteiVon[s.slug]?.short ?? s.slug).join(", ")} — du hattest alle bei 0: je 5 Punkte.
          </p>
        )}
      </div>

      <div className="mt-3.5 flex gap-2.5 px-4">
        <Button asChild variant="secondary" className="h-11 flex-1 text-sm">
          <Link href="/tipp/live">Rangliste</Link>
        </Button>
        <Button asChild variant="secondary" className="h-11 flex-1 text-sm">
          <Link href="/tipp/live?ansicht=vergleich">OB-Tipp ansehen</Link>
        </Button>
      </div>
    </div>
  );
}
