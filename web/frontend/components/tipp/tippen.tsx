"use client";

// 1d — Tippen: 52 Sitze auf 16 Listen verteilen, optional die OB-Wahl.
// Der Rest wird live nachgeführt (segmentierte Leiste + Text); abgegeben
// wird erst auf Knopfdruck, und nur wenn beide Summen stimmen.

import { useMemo, useState } from "react";
import { apiUrl } from "@/lib/api";
import {
  restObText,
  restObTon,
  restSitze,
  restSitzeText,
  restSitzeTon,
  restOb,
  startverteilung,
  tippSegmente,
} from "@/lib/tipp";
import type { TippMeins, TippSetup } from "@/lib/tipp";
import { Aufklapp } from "@/components/aufklapp";
import { Switch } from "@/components/ui/switch";

export function Tippen({ setup, meins, onGespeichert }: {
  setup: TippSetup;
  meins: TippMeins;
  onGespeichert: () => void;
}) {
  const [seats, setSeats] = useState<Record<string, number>>(() =>
    meins.has_tip
      ? Object.fromEntries(meins.seats.map((s) => [s.slug, s.tip]))
      : startverteilung(setup.parties, setup.seats_total),
  );
  const [obOffen, setObOffen] = useState(meins.has_mayor_tip);
  const [ob, setOb] = useState<Record<string, number>>(() =>
    Object.fromEntries(meins.mayor.map((m) => [m.slug, m.tip])),
  );
  const [sendet, setSendet] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  const rest = restSitze(seats, setup.seats_total);
  const restText = restSitzeText(rest, setup.seats_total);
  const ton = restSitzeTon(rest);
  const segmente = useMemo(() => tippSegmente(seats, setup.parties, setup.seats_total), [seats, setup.parties, setup.seats_total]);

  const obRest = restOb(ob);
  const obTon = restObTon(obRest);
  const kannAbgeben = rest === 0 && (!obOffen || obTon === "ok") && !sendet;

  function setzeSitz(slug: string, wert: number) {
    const geklemmt = Math.max(0, Math.min(setup.seats_total, Math.round(Number.isFinite(wert) ? wert : 0)));
    setSeats((s) => ({ ...s, [slug]: geklemmt }));
  }

  function setzeOb(slug: string, wert: number) {
    const geklemmt = Math.max(0, Math.min(100, Number.isFinite(wert) ? wert : 0));
    setOb((o) => ({ ...o, [slug]: geklemmt }));
  }

  async function abgeben() {
    if (!kannAbgeben) return;
    setSendet(true);
    setFehler(null);
    try {
      const res = await fetch(apiUrl("/tipp"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seats, mayor: obOffen ? ob : null }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setFehler(typeof body?.detail === "string" ? body.detail : "Das hat nicht geklappt — versuch es noch einmal.");
        return;
      }
      onGespeichert();
    } catch {
      setFehler("Keine Verbindung zum Server — versuch es noch einmal.");
    } finally {
      setSendet(false);
    }
  }

  return (
    <div className="mx-auto min-h-[100dvh] max-w-md pb-8">
      <div className="sticky top-0 z-20 mx-4 mt-3 rounded-[14px] border border-border bg-card p-3 pt-[calc(env(safe-area-inset-top)+12px)] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
        <div className="flex items-baseline justify-between">
          <span className="font-display text-[17px] font-bold">Sitze im Rat</span>
          <span className={`font-mono text-xs ${ton === "ok" ? "text-emerald-600 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}>
            {restText}
          </span>
        </div>
        <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-muted">
          {segmente.map((s) => (
            <div key={s.slug} style={{ width: s.breite, background: s.farbe }} className="h-full transition-[width] duration-200" />
          ))}
        </div>
        <p className="mt-1.5 text-[11.5px] text-muted-foreground">
          {setup.seats_total} Sitze insgesamt. Listen, die du bei 0 lässt, tippst du auf „kein Sitz".
        </p>
      </div>

      <div className="mt-2 flex flex-col gap-1.5 px-4">
        {setup.parties.map((p) => (
          <div key={p.slug} className="flex items-center gap-2.5 rounded-xl border border-border bg-card py-2 pl-3 pr-2">
            <span
              className="h-2 w-2 flex-none rounded-full shadow-[inset_0_0_0_1px_rgba(0,0,0,0.15)]"
              style={{ background: p.color }}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold leading-tight">{p.short}</p>
              <p className="text-[11px] text-muted-foreground">
                {p.seats_2021 !== null ? `2021: ${p.seats_2021}` : "neu 2026"}
              </p>
            </div>
            <button
              type="button"
              aria-label={`${p.short}: einen Sitz weniger`}
              onClick={() => setzeSitz(p.slug, (seats[p.slug] ?? 0) - 1)}
              className="flex h-11 w-11 flex-none items-center justify-center rounded-[10px] border border-border bg-primary/5 text-xl text-primary"
            >
              −
            </button>
            <input
              type="number"
              inputMode="numeric"
              aria-label={`Sitze für ${p.short}`}
              value={seats[p.slug] ?? 0}
              onChange={(e) => setzeSitz(p.slug, Number(e.target.value))}
              className="h-11 w-[46px] flex-none rounded-[10px] border border-border bg-card text-center font-display text-lg font-bold text-foreground"
            />
            <button
              type="button"
              aria-label={`${p.short}: einen Sitz mehr`}
              onClick={() => setzeSitz(p.slug, (seats[p.slug] ?? 0) + 1)}
              className="flex h-11 w-11 flex-none items-center justify-center rounded-[10px] border border-border bg-primary/5 text-xl text-primary"
            >
              +
            </button>
          </div>
        ))}
      </div>

      <div className="mx-4 mt-4.5 rounded-[14px] border border-border bg-card p-3.5">
        <div className="flex items-center justify-between gap-2.5">
          <div>
            <p className="font-display text-base font-bold">OB-Wahl mittippen</p>
            <p className="mt-0.5 text-xs text-muted-foreground">Optional · bis 6 Bonuspunkte je Kandidatur</p>
          </div>
          <Switch checked={obOffen} onCheckedChange={setObOffen} aria-label="OB-Wahl mittippen" />
        </div>
        <Aufklapp offen={obOffen}>
          <div className="mt-3 flex flex-col gap-1.5">
            <div className="flex justify-between text-[11.5px] text-muted-foreground">
              <span>Prozent je Kandidatur, Summe max. 100</span>
              <span className={`font-mono ${obTon === "ok" ? "text-emerald-600 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}>
                {restObText(obRest)}
              </span>
            </div>
            {setup.mayor_candidates.map((o) => (
              <div key={o.slug} className="flex items-center gap-2.5 border-t border-muted py-1.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-semibold">{o.name}</p>
                  <p className="text-[11px] text-muted-foreground">{o.party}</p>
                </div>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    inputMode="decimal"
                    step={0.5}
                    aria-label={`Prozent für ${o.name}`}
                    value={ob[o.slug] ?? 0}
                    onChange={(e) => setzeOb(o.slug, Number(e.target.value))}
                    className="h-10 w-[58px] rounded-[10px] border border-border bg-card px-2 text-right font-display text-base font-bold text-foreground"
                  />
                  <span className="text-[13px] text-muted-foreground">%</span>
                </div>
              </div>
            ))}
          </div>
        </Aufklapp>
      </div>

      {fehler && <p className="mx-4 mt-3 text-[12.5px] font-medium text-destructive">{fehler}</p>}

      <div className="sticky bottom-0 mt-4 bg-gradient-to-t from-background from-30% px-4 pb-[calc(env(safe-area-inset-bottom)+16px)] pt-4">
        <button
          type="button"
          disabled={!kannAbgeben}
          onClick={() => void abgeben()}
          className="h-[50px] w-full rounded-xl text-base font-semibold text-primary-foreground transition-colors disabled:cursor-not-allowed"
          style={{ background: kannAbgeben ? "hsl(var(--primary))" : "hsl(var(--muted-foreground) / 0.4)" }}
        >
          {sendet ? "Speichert …" : meins.has_tip ? "Tipp aktualisieren" : "Tipp abgeben"}
        </button>
        <p className="mt-2 text-center text-[11.5px] text-muted-foreground">
          {setup.deadline_hint}
        </p>
      </div>
    </div>
  );
}
