"use client";

// 1e — „Mein Tipp": vor der ersten Zahl die Bestätigung („gespeichert"),
// danach Rang, Punkte und der Tipp Zeile für Zeile gegen den Stand.
//
// Solange getippt werden darf, führt „Tipp ändern" zurück ins Formular (1d).
// Nach dem Tipp-Schluss gibt es den Knopf nicht mehr: Dann ist der Tipp fest
// — für Spätstarter genauso, die ihren einen Tipp abgegeben haben.

import Link from "next/link";
import { useState } from "react";
import { rangDeltaText, rangPfeil, uhrzeitKurz } from "@/lib/tipp";
import type { TippMeins, TippSetup } from "@/lib/tipp";
import { Lotti } from "@/components/lotti";
import { Aufklapp } from "@/components/aufklapp";
import { BrandMark } from "@/components/brand";
import { Button } from "@/components/ui/button";

function punktTon(punkte: number, hoechst: number): string {
  if (punkte === hoechst) return "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
  if (punkte > 0) return "bg-primary/10 text-primary";
  return "bg-muted text-muted-foreground";
}

export function MeinTipp({ setup, meins, onAendern }: {
  setup: TippSetup; meins: TippMeins;
  /** Solange getippt werden darf: zurück ins Formular (1d). */
  onAendern?: () => void;
}) {
  const parteiVon: Record<string, TippSetup["parties"][number]> = Object.fromEntries(
    setup.parties.map((p) => [p.slug, p]),
  );
  const kandidaturVon: Record<string, TippSetup["mayor_candidates"][number]> = Object.fromEntries(
    setup.mayor_candidates.map((k) => [k.slug, k]),
  );
  const pfeil = rangPfeil(meins.rank, meins.rank_before);
  const score = meins.score;
  const nullAufNullListen = meins.seats.filter((s) => s.tip === 0 && s.actual === 0);
  const nachgetippt = meins.late_at !== null ? uhrzeitKurz(meins.late_at) : null;
  const [obOffen, setObOffen] = useState(false);
  // Vor dem ersten Ergebnis ist diese Seite die BESTÄTIGUNG (Plan, 1e): Dann
  // sind „Ist" und „Pkt" in jeder Zeile leer — die Spalten bleiben weg, statt
  // eine halbe Tabelle mit Strichen zu zeigen.
  const zeigeErgebnis = meins.seats.some((s) => s.actual !== null);
  const spalten = zeigeErgebnis ? "grid-cols-[8px_1fr_34px_34px_44px]" : "grid-cols-[8px_1fr_44px]";

  return (
    <div className="mx-auto min-h-[100dvh] max-w-md pb-8">
      <div className="flex items-center justify-between px-4 pt-[calc(env(safe-area-inset-top)+10px)]">
        <span className="flex items-center gap-2">
          <BrandMark className="h-6 w-6" />
          <span className="font-display text-[15px] font-bold">Tippspiel</span>
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/[0.08] px-2.5 py-1 text-[11.5px] font-semibold text-primary">
          {meins.phase !== "open" && <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-signal motion-reduce:animate-none" />}
          {meins.phase === "open"
            ? "Tippen offen"
            : `${meins.phase === "final" ? "Endstand" : "Live"} · ${meins.stand_label || "wartet"}`}
        </span>
      </div>

      {nachgetippt && (
        // Dasselbe Etikett wie auf dem Scoreboard (1f/1i): Wer nach dem
        // Tipp-Schluss kam, sieht es auch bei sich — sonst wundert sich die
        // Person, warum ihr Rang fehlt oder „außer Konkurrenz" ist.
        <div className="mx-4 mt-3 flex items-start gap-2.5 rounded-[12px] border border-amber-200 bg-amber-50 p-3 text-left dark:border-amber-900/50 dark:bg-amber-900/20">
          <span className="mt-0.5 flex-none rounded-full border border-amber-200 bg-card px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-amber-800 dark:border-amber-900/50 dark:text-amber-200">
            Nachgetippt {nachgetippt}
          </span>
          <p className="text-[12px] leading-relaxed text-amber-800 dark:text-amber-200">
            {meins.scored ? "Dein Tipp kam nach Tipp-Schluss und zählt trotzdem mit." : "Dein Tipp kam nach Tipp-Schluss und läuft außer Konkurrenz."}
          </p>
        </div>
      )}

      {!score ? (
        <div className="animate-fade-up mx-4 mt-3.5 flex items-center gap-3 rounded-2xl bg-primary p-4 text-primary-foreground">
          {/* `klatscht` heißt im Katalog „geschafft" — eine Regung, die an
              genau diesen Zustand gebunden ist (DESIGNSPRACHE §1). */}
          <Lotti regung="klatscht" className="h-16 w-16 flex-none" decorative />
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.11em] opacity-75">{meins.name}</p>
            <p className="mt-0.5 font-display text-lg font-bold">Dein Tipp ist gespeichert.</p>
            <p className="mt-1 text-[12.5px] leading-relaxed opacity-90">
              {meins.locked
                ? "Sobald die erste Zahl da ist, siehst du hier deinen Rang."
                : `Änderbar ${setup.deadline_hint}. Dann zählen wir aus.`}
            </p>
          </div>
        </div>
      ) : (
        <div className="mx-4 mt-3.5 overflow-hidden rounded-2xl bg-primary p-4 pb-4 text-primary-foreground">
          <p className="font-mono text-[10px] uppercase tracking-[0.11em] opacity-75">{meins.name} · Dein Rang</p>
          <div className="mt-1.5 flex items-end gap-3.5">
            <span className="font-display text-[64px] leading-[0.9] tracking-tight">{meins.rank ?? "–"}</span>
            <div className="flex-1 pb-1.5">
              <p className="text-sm opacity-85">von {setup.player_count}</p>
              {pfeil && <p className="mt-0.5 text-sm font-semibold">{rangDeltaText(pfeil)}</p>}
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
          <span>Dein Tipp{zeigeErgebnis ? " · Stand" : ""}</span>
          <span>{zeigeErgebnis ? meins.stand_label : `${meins.seats.length} Listen`}</span>
        </div>
        <div className="mt-2 overflow-hidden rounded-[14px] border border-border bg-card">
          {meins.seats.filter((s) => !(s.tip === 0 && s.actual === 0)).map((s) => {
            const p = parteiVon[s.slug];
            return (
              <div
                key={s.slug}
                className={`grid ${spalten} items-center gap-2.5 border-t border-muted px-3.5 py-2 text-[13px] first:border-t-0`}
              >
                <span className="h-2 w-2 rounded-full shadow-[inset_0_0_0_1px_rgba(0,0,0,0.15)]" style={{ background: p?.color }} />
                <span className="truncate font-semibold">{p?.short ?? s.slug}</span>
                {zeigeErgebnis ? (
                  <>
                    <span className="text-right font-mono text-muted-foreground">{s.tip}</span>
                    <span className="text-right font-display text-[15px] font-bold">{s.actual ?? "–"}</span>
                    <span className={`rounded-full py-0.5 text-center text-[11px] font-semibold ${punktTon(s.points, 5)}`}>
                      {s.actual === null ? "–" : s.points > 0 ? `+${s.points}` : "0"}
                    </span>
                  </>
                ) : (
                  <span className="text-right font-display text-[15px] font-bold tabular-nums">{s.tip}</span>
                )}
              </div>
            );
          })}
          <div className={`grid ${spalten} gap-2.5 px-3.5 pb-2 pt-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground`}>
            <span />
            <span />
            <span className="text-right">Tipp</span>
            {zeigeErgebnis && <><span className="text-right">Ist</span><span className="text-center">Pkt</span></>}
          </div>
        </div>
        {nullAufNullListen.length > 0 && (
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            {nullAufNullListen.length} Liste{nullAufNullListen.length === 1 ? "" : "n"} ohne Sitz:{" "}
            {nullAufNullListen.map((s) => parteiVon[s.slug]?.short ?? s.slug).join(", ")} — du hattest alle bei 0: je 5 Punkte.
          </p>
        )}
      </div>

      {meins.has_mayor_tip && (
        // Der eigene OB-Tipp gehört zu „Mein Tipp" — vorher führte der Knopf
        // auf den Beamer-Vergleich, der die Ø-Werte der Runde zeigt, nie den
        // eigenen Tipp.
        <div className="mt-3 px-4">
          <Aufklapp offen={obOffen}>
            <div className="overflow-hidden rounded-[14px] border border-border bg-card">
              {meins.mayor.map((m) => {
                const k = kandidaturVon[m.slug];
                return (
                  <div key={m.slug} className="grid grid-cols-[1fr_46px_46px_44px] items-center gap-2.5 border-t border-muted px-3.5 py-2 text-[13px] first:border-t-0">
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{k?.name ?? m.slug}</span>
                      <span className="block text-[11px] text-muted-foreground">{k?.party}</span>
                    </span>
                    <span className="text-right font-mono text-muted-foreground">{m.tip.toLocaleString("de-DE")} %</span>
                    <span className="text-right font-display text-[15px] font-bold">
                      {m.actual_pct !== null ? `${m.actual_pct.toLocaleString("de-DE", { maximumFractionDigits: 1 })} %` : "–"}
                    </span>
                    <span className={`rounded-full py-0.5 text-center text-[11px] font-semibold ${punktTon(m.points, 6)}`}>
                      {m.actual_pct === null ? "–" : m.points > 0 ? `+${m.points}` : "0"}
                    </span>
                  </div>
                );
              })}
              <div className="grid grid-cols-[1fr_46px_46px_44px] gap-2.5 px-3.5 pb-2 pt-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                <span>OB-Wahl</span>
                <span className="text-right">Tipp</span>
                <span className="text-right">Ist</span>
                <span className="text-center">Pkt</span>
              </div>
            </div>
          </Aufklapp>
        </div>
      )}

      {onAendern && (
        <div className="mt-3.5 px-4">
          <Button type="button" variant="primary" className="h-11 w-full text-sm" onClick={onAendern}>
            Tipp ändern
          </Button>
        </div>
      )}

      <div className="mt-2.5 flex gap-2.5 px-4">
        <Button asChild variant="secondary" className="h-11 flex-1 text-sm">
          <Link href="/tipp/live">Rangliste</Link>
        </Button>
        {meins.has_mayor_tip && (
          <Button type="button" variant="secondary" className="h-11 flex-1 text-sm" aria-expanded={obOffen} onClick={() => setObOffen((o) => !o)}>
            {obOffen ? "OB-Tipp zuklappen" : "OB-Tipp ansehen"}
          </Button>
        )}
      </div>
    </div>
  );
}
