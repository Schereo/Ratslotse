"use client";

// Vergleich (Screen 1g) — links der Halbkreis mit der Hochrechnung und die
// Karte mit dem Server-Satz, rechts je Liste ein Balken (Ist) mit Raute
// (Ø-Tipp), die Zahlen daneben, darunter die OB-Wahl als fünf Kacheln.
// Maße aus dem Artboard (1920×1080), skaliert von `buehne.tsx`.
//
// Für eine OB- oder Stichwahl (`tip_kind === "pct"`, seit 19.09.2026) gibt
// es keinen Halbkreis und keine Listen: Dann steht links je Kandidatur eine
// große Kachel (Ist gegen Ø-Tipp als zwei Balken auf einer Skala), rechts
// die Wahlbeteiligung und der Server-Satz. Dieselbe Bühne, derselbe Kopf.
//
// Der Halbkreis nimmt NUR die Geometrie aus `lib/wahlabend.ts`
// (`halbkreis()`), nicht die Wahlabend-Komponente: Die trägt einen anderen
// Datenvertrag und eine Zeiger-Interaktion, die aus fünf Metern niemand
// bedient. Vier Reihen statt drei, damit die Punkte auf 640 px Breite die
// 30 px des Entwurfs treffen und nicht zu Klötzen werden.

import { useId } from "react";
import { halbkreis } from "@/lib/wahlabend";
import type { ApiAntwort } from "@/lib/vertrag";
import { Lotti } from "@/components/lotti";
import { cn } from "@/lib/utils";
import { prozentText } from "@/lib/tipp";
import { BeamerKopf, LivePunkt, dezimal } from "./buehne";

type PredictionStand = ApiAntwort<"/tipp/stand">;
type Zeile = PredictionStand["compare"][number];

function Halbkreis({ zeilen, gesamt }: { zeilen: Zeile[]; gesamt: number }) {
  const id = useId();
  const punkte = halbkreis(gesamt, 4, 0.46);
  const mitSitz = zeilen.filter((z) => (z.actual ?? 0) > 0);
  const belegung: (Zeile | null)[] = [];
  for (const z of mitSitz) for (let i = 0; i < (z.actual ?? 0); i++) belegung.push(z);
  while (belegung.length < gesamt) belegung.push(null);

  return (
    <svg viewBox="-0.05 -0.06 2.1 1.1" className="block h-[340px] w-[640px]" role="img" aria-labelledby={`${id}-t`}>
      <title id={`${id}-t`}>{mitSitz.map((z) => `${z.short} ${z.actual}`).join(", ")}</title>
      {punkte.map((q, i) => {
        const z = belegung[i];
        return (
          <circle
            key={i}
            cx={q.x} cy={q.y} r={q.r * 0.78}
            className={cn("transition-[fill] duration-500", z ? "fill-[var(--dot)] dark:fill-[var(--dot-dark)]" : "fill-foreground/10")}
            style={{ "--dot": z?.color, "--dot-dark": z?.color_dark } as React.CSSProperties}
          />
        );
      })}
    </svg>
  );
}

const QUELLE: Record<string, string> = {
  votemanager: "votemanager Oldenburg",
  manuell: "Manuell eingetragen",
  gemischt: "votemanager + manuelle Eingaben",
};

const OB_STATUS: Record<string, string> = { before: "noch nicht ausgezählt", counting: "Auszählung", complete: "Ergebnis" };

/** Die Wahlbeteiligung als Kachel — auf beiden Vergleichs-Screens dieselbe. */
function BeteiligungKachel({ stand, gross }: { stand: PredictionStand; gross?: boolean }) {
  const t = stand.turnout;
  return (
    <div className={cn("rounded-[14px] border border-border bg-card", gross ? "px-6 py-5" : "px-3.5 py-3")}>
      <p className={cn("font-mono uppercase tracking-[0.11em] text-muted-foreground", gross ? "text-[22px]" : "text-[18px]")}>Wahlbeteiligung</p>
      <p className={cn("mt-1 font-display font-bold leading-none tabular-nums", gross ? "text-[64px]" : "text-[34px]")}>
        {t.actual_pct !== null ? dezimal(t.actual_pct) : "–"}{t.actual_pct !== null && <span className={cn("ml-1 text-muted-foreground", gross ? "text-[32px]" : "text-[20px]")}>%</span>}
      </p>
      <p className={cn("mt-0.5 text-muted-foreground", gross ? "text-[24px]" : "text-[20px]")}>
        Ø-Tipp {t.avg_tip !== null ? prozentText(t.avg_tip) : "–"}{t.tip_count > 0 ? ` · ${t.tip_count} ${t.tip_count === 1 ? "Tipp" : "Tipps"}` : ""}
      </p>
    </div>
  );
}

/** Der Vergleich einer OB- oder Stichwahl: zwei (oder neun) Kandidaturen als
 *  Kacheln, je Kachel zwei Balken — Ist (Listenfarbe) und Ø-Tipp (Kontur) —
 *  auf einer gemeinsamen Skala, die bei 100 % endet. */
function VergleichProzent({ stand, rechtzeitig }: { stand: PredictionStand; rechtzeitig: number }) {
  const hatZahl = stand.mayor.some((m) => m.actual_pct !== null);
  const endstand = stand.phase === "final";
  const kandidaturen = [...stand.mayor]
    .sort((a, b) => (b.actual_pct ?? -1) - (a.actual_pct ?? -1) || (b.avg_tip ?? -1) - (a.avg_tip ?? -1));
  const zweikampf = kandidaturen.length <= 2;
  return (
    <div className="flex h-full flex-col px-20 py-14 text-foreground">
      <BeamerKopf
        untertitel="Tippspiel · Tipps im Vergleich"
        rechts={hatZahl ? (
          <>
            <LivePunkt endstand={endstand} />
            {stand.area_label && <span>{stand.area_label}</span>}
            <span>·</span>
            <span className="font-mono">{stand.stand_label || "–"}</span>
            {stand.source_label && (
              <>
                <span>·</span>
                <span>{QUELLE[stand.source_label] ?? stand.source_label}</span>
              </>
            )}
          </>
        ) : (
          <span>{stand.phase === "open" ? "Tippen möglich" : "Warten auf den ersten Auszählungsstand"}</span>
        )}
      />

      {/* Beide Spalten mittig in der Höhe: Zwei Kachel-Reihen füllen die
          Bühne nicht wie sechzehn Listen — oben angeklebt bliebe die untere
          Hälfte leer. */}
      <div className="mt-6 grid min-h-0 flex-1 grid-cols-[1fr_620px] items-center gap-16">
        <div className="flex flex-col">
          <p className="font-mono text-[22px] uppercase tracking-[0.11em] text-muted-foreground">
            {hatZahl ? `Stimmenanteile · ${OB_STATUS[stand.mayor_status] ?? stand.mayor_status}` : "Stimmenanteile · noch keine Zahlen"}
          </p>
          <div className={cn("mt-6 grid gap-6", zweikampf ? "grid-cols-2" : "grid-cols-3")}>
            {kandidaturen.map((k) => {
              const ist = k.actual_pct ?? 0;
              const avg = k.avg_tip ?? 0;
              return (
                <div key={k.slug} className={cn("rounded-[22px] border border-border bg-card", zweikampf ? "px-8 py-7" : "px-5 py-4")}>
                  <p className={cn("truncate font-semibold leading-tight", zweikampf ? "text-[40px]" : "text-[26px]")} title={k.name}>{k.name}</p>
                  <p className={cn("mt-1 text-muted-foreground", zweikampf ? "text-[24px]" : "text-[18px]")}>
                    {k.party === "Einzelwahlvorschlag" ? k.party : `vorgeschlagen von ${k.party}`}
                  </p>
                  <div className={cn("flex items-end gap-6", zweikampf ? "mt-8" : "mt-4")}>
                    <div>
                      <p className={cn("font-mono uppercase tracking-[0.1em] text-muted-foreground", zweikampf ? "text-[20px]" : "text-[16px]")}>Stand</p>
                      <p className={cn("font-display font-bold leading-none tabular-nums", zweikampf ? "text-[96px]" : "text-[52px]")}>
                        {k.actual_pct !== null ? dezimal(k.actual_pct) : "–"}
                      </p>
                    </div>
                    <div className="pb-2">
                      <p className={cn("font-mono uppercase tracking-[0.1em] text-muted-foreground", zweikampf ? "text-[20px]" : "text-[16px]")}>Ø-Tipp</p>
                      <p className={cn("font-display font-semibold leading-none tabular-nums text-muted-foreground", zweikampf ? "text-[48px]" : "text-[30px]")}>
                        {k.avg_tip !== null ? dezimal(k.avg_tip) : "–"}
                      </p>
                    </div>
                  </div>
                  {/* Zwei Balken auf EINER Skala (0–100 %): oben das Ist in
                      Primärfarbe, darunter der Ø-Tipp als Kontur. */}
                  <div className={cn("flex flex-col gap-2", zweikampf ? "mt-7" : "mt-4")}>
                    <div className="h-[18px] w-full overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${Math.min(100, ist)}%` }} />
                    </div>
                    <div className="h-[18px] w-full overflow-hidden rounded-full border-2 border-dashed border-border">
                      <div className="h-full rounded-full bg-foreground/25 transition-[width] duration-700" style={{ width: `${Math.min(100, avg)}%` }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-5 flex items-center gap-6 text-[20px] text-muted-foreground">
            <span className="inline-flex items-center gap-2"><span className="inline-block h-3 w-8 rounded-full bg-primary" /> Stand</span>
            <span className="inline-flex items-center gap-2"><span className="inline-block h-3 w-8 rounded-full border-2 border-dashed border-border bg-foreground/25" /> Ø-Tipp</span>
          </p>
        </div>

        <div className="flex flex-col gap-6">
          <BeteiligungKachel stand={stand} gross />
          <div data-testid="vergleich-satz" className="flex items-center gap-[22px] rounded-[22px] border border-border bg-card px-[26px] py-[22px]">
            <Lotti regung="sucht" className="h-24 w-24 flex-none" decorative />
            <div>
              <p className="text-[24px] leading-[1.45] text-foreground/85">{stand.compare_sentence}</p>
              <p className="mt-1.5 text-[22px] text-muted-foreground">Ø-Tipp = Durchschnitt der {rechtzeitig} rechtzeitig abgegebenen Tipps.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function BeamerVergleich({ stand }: { stand: PredictionStand }) {
  if (stand.tip_kind === "pct") {
    return <VergleichProzent stand={stand} rechtzeitig={stand.rows.filter((r) => r.has_tip && r.late_at === null).length} />;
  }
  return <VergleichSitze stand={stand} />;
}

function VergleichSitze({ stand }: { stand: PredictionStand }) {
  // Der Satz verspricht „vor Tipp-Schluss" — `tip_count` zählt aber ALLE
  // Tipps, auch nachgetippte, die in den Ø nicht eingehen (service._avg).
  const rechtzeitig = stand.rows.filter((r) => r.has_tip && r.late_at === null).length;
  const mitSitz = stand.compare.filter((c) => (c.actual ?? 0) > 0);
  const ohneSitz = stand.compare.filter((c) => c.actual === 0).map((c) => c.short);
  // Balken und Raute teilen sich eine Skala: die größte Zahl der Tafel.
  const maximum = Math.max(1, ...stand.compare.map((c) => Math.max(c.actual ?? 0, c.avg_tip ?? 0)));
  // Fünf Kacheln unten: die Wahlbeteiligung und die vier OB-Kandidaturen
  // mit dem meisten Ist (davor: Ø).
  const ob = [...stand.mayor]
    .sort((a, b) => (b.actual_pct ?? -1) - (a.actual_pct ?? -1) || (b.avg_tip ?? -1) - (a.avg_tip ?? -1))
    .slice(0, 5);
  const endstand = stand.phase === "final";

  return (
    <div className="flex h-full flex-col px-20 py-14 text-foreground">
      <BeamerKopf
        untertitel="Tippspiel · Tipps im Vergleich"
        rechts={mitSitz.length ? (
          <>
            <LivePunkt endstand={endstand} />
            {stand.area_label && <span>{stand.area_label}</span>}
            <span>·</span>
            <span className="font-mono">{stand.stand_label || "–"}</span>
            {stand.source_label && (
              <>
                <span>·</span>
                <span>{QUELLE[stand.source_label] ?? stand.source_label}</span>
              </>
            )}
          </>
        ) : (
          <span>{stand.phase === "open" ? "Tippen möglich" : "Warten auf die erste Hochrechnung"}</span>
        )}
      />

      <div className="mt-10 grid min-h-0 flex-1 grid-cols-[700px_1fr] gap-20">
        {/* Links: Halbkreis + Satz */}
        <div className="flex flex-col">
          <p className="font-mono text-[22px] uppercase tracking-[0.11em] text-muted-foreground">
            {mitSitz.length ? "Sitzverteilung · Hochrechnung" : "Sitzverteilung · noch keine Zahlen"}
          </p>
          <div className="relative mt-[22px] h-[340px] w-[640px]">
            <Halbkreis zeilen={stand.compare} gesamt={stand.seats_total} />
            <div data-testid="sitze-gesamt" className="absolute inset-x-0 bottom-[-14px] text-center">
              <span className="font-display text-[60px] font-bold leading-none">{stand.seats_total}</span>
              <span className="ml-2.5 text-[24px] text-muted-foreground">Sitze</span>
            </div>
          </div>
          <div data-testid="vergleich-satz" className="mt-14 flex items-center gap-[22px] rounded-[22px] border border-border bg-card px-[26px] py-[22px]">
            <Lotti regung="sucht" className="h-24 w-24 flex-none" decorative />
            <div>
              <p className="text-[24px] leading-[1.45] text-foreground/85">{stand.compare_sentence}</p>
              <p className="mt-1.5 text-[22px] text-muted-foreground">Ø-Tipp = Durchschnitt der {rechtzeitig} rechtzeitig abgegebenen Tipps.</p>
            </div>
          </div>
        </div>

        {/* Rechts: Tabelle + OB */}
        <div className="flex min-h-0 flex-col">
          <div className="grid grid-cols-[1fr_90px_110px_90px] gap-5 pb-3 font-mono text-[22px] uppercase tracking-[0.11em] text-muted-foreground">
            <span>Liste · Stand ▮ / Ø-Tipp ◇</span>
            <span className="text-right">Stand</span>
            <span className="text-right">Ø-Tipp</span>
            <span className="text-right">Exakt</span>
          </div>
          <div className={cn("flex flex-col", mitSitz.length > 10 ? "gap-2.5" : "gap-3.5")}>
            {(mitSitz.length ? mitSitz : stand.compare.slice(0, 10)).map((c) => {
              const ist = c.actual ?? 0;
              const avg = c.avg_tip ?? 0;
              const mehrheitExakt = rechtzeitig > 0 && c.exact_count * 2 > rechtzeitig;
              return (
                <div key={c.slug} className="grid h-[38px] grid-cols-[1fr_90px_110px_90px] items-center gap-5">
                  <div className="flex items-center gap-3.5">
                    <span
                      className="h-3.5 w-3.5 flex-none rounded-full bg-[var(--dot)] shadow-[inset_0_0_0_1.5px_rgba(255,255,255,0.2)] dark:bg-[var(--dot-dark)]"
                      style={{ "--dot": c.color, "--dot-dark": c.color_dark } as React.CSSProperties}
                    />
                    <span className="w-[215px] flex-none truncate text-[26px] font-semibold leading-tight">{c.short}</span>
                    <div className="relative h-[26px] flex-1">
                      <div
                        className="absolute inset-y-0 left-0 rounded-[6px] bg-[var(--dot)] opacity-90 transition-[width] duration-700 dark:bg-[var(--dot-dark)]"
                        style={{ width: `${(ist / maximum) * 100}%`, "--dot": c.color, "--dot-dark": c.color_dark } as React.CSSProperties}
                      />
                      {c.avg_tip !== null && (
                        <div
                          aria-hidden
                          className="absolute top-[-6px] h-[38px] w-3.5 -translate-x-1/2 rotate-45 rounded-[3px] border-[3px] border-foreground bg-background transition-[left] duration-700"
                          style={{ left: `${(avg / maximum) * 100}%` }}
                        />
                      )}
                    </div>
                  </div>
                  <span className="text-right font-display text-[32px] font-bold leading-none tabular-nums">{c.actual ?? "–"}</span>
                  <span className="text-right text-[26px] leading-none tabular-nums text-muted-foreground">{c.avg_tip !== null ? dezimal(c.avg_tip) : "–"}</span>
                  <span className={cn("text-right text-[24px] leading-none tabular-nums", mehrheitExakt ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground")}>
                    {c.exact_count}/{rechtzeitig}
                  </span>
                </div>
              );
            })}
          </div>
          {ohneSitz.length > 0 && (
            <p className="mt-3.5 text-[22px] text-muted-foreground">Ohne Sitz laut Hochrechnung: {ohneSitz.join(" · ")}</p>
          )}

          {ob.length > 0 && (
            <div className="mt-auto border-t border-border pt-5">
              <p className="mb-3 font-mono text-[22px] uppercase tracking-[0.11em] text-muted-foreground">
                OB-Wahl · {OB_STATUS[stand.mayor_status] ?? stand.mayor_status}{stand.mayor_status !== "before" && stand.stand_label ? ` ${stand.stand_label}` : ""}
              </p>
              <div className="grid grid-cols-5 gap-3.5">
                <BeteiligungKachel stand={stand} />
                {ob.slice(0, 4).map((o) => (
                  <div key={o.slug} className="rounded-[14px] border border-border bg-card px-3.5 py-3">
                    <p className="truncate text-[22px] font-semibold" title={o.name}>{o.name}</p>
                    <p className="mt-1 font-display text-[34px] font-bold leading-none tabular-nums">
                      {o.actual_pct !== null ? dezimal(o.actual_pct) : "–"}
                    </p>
                    <p className="mt-0.5 text-[20px] text-muted-foreground">
                      Ø-Tipp {o.avg_tip !== null ? `${dezimal(o.avg_tip)} %` : "–"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
