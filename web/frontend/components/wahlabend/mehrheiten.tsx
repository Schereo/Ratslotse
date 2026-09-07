"use client";

// Mehrheiten im Rat: ein Bündnis zusammenklicken und sehen, ob es reicht —
// dazu die Liste dessen, was rechnerisch reicht. Nur Rechnung, keine
// Politik: Die Reihenfolge ist Partnerzahl, dann Sitze; wer mit wem kann,
// steht hier nicht. Die Schwelle ist die absolute Mehrheit der 52 Sitze;
// der 53. Stimmberechtigte im Rat ist die Oberbürgermeisterin bzw. der
// Oberbürgermeister — gewählt am selben Tag, Stichwahl am 27.09.

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { koalitionen, mehrheit, type WahlabendPartei } from "@/lib/wahlabend";

type Feld = "seats" | "projected_seats";
const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

function Punkt({ p }: { p: WahlabendPartei }) {
  return (
    <span
      aria-hidden
      className="inline-block h-2 w-2 flex-none rounded-full bg-[var(--dot)] ring-1 ring-inset ring-black/10 dark:bg-[var(--dot-dark)]"
      style={{ "--dot": p.color, "--dot-dark": p.color_dark } as React.CSSProperties}
    />
  );
}

export function Mehrheiten({ parteien, gesamt, feld, hochrechnung }: { parteien: readonly WahlabendPartei[]; gesamt: number; feld: Feld; hochrechnung: boolean }) {
  const [gewaehlt, setGewaehlt] = useState<string[]>([]);
  const noetig = mehrheit(gesamt);
  const mitSitz = parteien.filter((p) => (p[feld] ?? 0) > 0);
  const nachSlug = new Map(parteien.map((p) => [p.slug, p]));
  const summe = gewaehlt.reduce((s, slug) => s + (nachSlug.get(slug)?.[feld] ?? 0), 0);
  const moeglich = useMemo(() => koalitionen(mitSitz.map((p) => ({ slug: p.slug, seats: p[feld] })), gesamt), [mitSitz, feld, gesamt]);
  const gruppen = [1, 2, 3].map((k) => ({ k, liste: moeglich.filter((m) => m.slugs.length === k) })).filter((g) => g.liste.length);
  const reicht = summe >= noetig;

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Mehrheiten im Rat</h2>
        <span className={KICKER}>{hochrechnung ? "Hochrechnung" : "Stand"} · Mehrheit ab {noetig} von {gesamt}</span>
      </div>
      <p className="mt-1 text-[12.5px] text-muted-foreground">
        Bündnis zusammenstellen — rein rechnerisch, ohne Aussage darüber, wer mit wem will.
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {mitSitz.map((p) => {
          const an = gewaehlt.includes(p.slug);
          return (
            <button
              key={p.slug}
              type="button"
              aria-pressed={an}
              onClick={() => setGewaehlt(an ? gewaehlt.filter((s) => s !== p.slug) : [...gewaehlt, p.slug])}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors duration-tipp",
                an ? "border-primary/30 bg-primary/5 text-primary" : "border-border bg-card text-foreground hover:bg-primary/5",
              )}
            >
              <Punkt p={p} />
              {p.short} <span className="tabular-nums text-muted-foreground">{p[feld]}</span>
            </button>
          );
        })}
      </div>

      {/* Die Leiste: Summe gegen die Basis, Mehrheitsmarke in Signal. */}
      <div className="relative mt-3 h-7 overflow-hidden rounded-md bg-muted">
        <div
          className={cn("h-full rounded-md transition-[width] duration-weg ease-out-strong", reicht ? "bg-primary" : "bg-foreground/35")}
          style={{ width: `${Math.min(100, (100 * summe) / gesamt)}%` }}
        />
        <div className="pointer-events-none absolute inset-y-0 w-0.5 -translate-x-1/2 bg-signal" style={{ left: `${(100 * noetig) / gesamt}%` }} />
        <span className="pointer-events-none absolute inset-y-0 left-2 flex items-center text-[11.5px] font-semibold tabular-nums text-foreground mix-blend-luminosity">
          {gewaehlt.length ? `${summe} von ${gesamt}` : "noch nichts gewählt"}
        </span>
      </div>
      <p className="mt-1.5 min-h-5 text-[12.5px] tabular-nums" aria-live="polite">
        {gewaehlt.length === 0 ? (
          <span className="text-muted-foreground">Listen antippen, um zu rechnen.</span>
        ) : reicht ? (
          <span className="font-semibold text-emerald-700 dark:text-emerald-300">Mehrheit — {summe - noetig + 1} {summe - noetig + 1 === 1 ? "Stimme" : "Stimmen"} über der Schwelle.</span>
        ) : (
          <span className="text-foreground">Keine Mehrheit — es fehlen {noetig - summe} {noetig - summe === 1 ? "Sitz" : "Sitze"}.</span>
        )}
      </p>

      {gruppen.length ? (
        <div className="mt-4 grid gap-4 @3xl:grid-cols-3">
          {gruppen.map((g) => (
            <div key={g.k}>
              <p className={KICKER}>
                {g.k === 1 ? "Allein" : g.k === 2 ? "Zu zweit" : "Zu dritt"} · {g.liste.length}
              </p>
              <ul className="mt-1.5 space-y-1">
                {g.liste.slice(0, 8).map((m) => (
                  <li key={m.slugs.join("+")}>
                    <button
                      type="button"
                      onClick={() => setGewaehlt(m.slugs)}
                      className="flex w-full items-center justify-between gap-2 rounded-lg px-1.5 py-1 text-left text-[12.5px] transition-colors duration-tipp hover:bg-primary/5"
                    >
                      <span className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5">
                        {m.slugs.map((slug, i) => {
                          const p = nachSlug.get(slug);
                          return p ? (
                            <span key={slug} className="inline-flex items-center gap-1">
                              {i > 0 ? <span className="text-muted-foreground">+</span> : null}
                              <Punkt p={p} />
                              {p.short}
                            </span>
                          ) : null;
                        })}
                      </span>
                      <span className={cn("flex-none tabular-nums", m.seats === noetig ? "font-semibold text-amber-700 dark:text-amber-300" : "text-muted-foreground")}>
                        {m.seats}
                        {m.seats === noetig ? " · knapp" : ""}
                      </span>
                    </button>
                  </li>
                ))}
                {g.liste.length > 8 ? <li className="px-1.5 text-[11.5px] text-muted-foreground">+ {g.liste.length - 8} weitere</li> : null}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-[12.5px] text-muted-foreground">Noch keine Sitze vergeben.</p>
      )}
      <p className="mt-3 text-[11px] text-muted-foreground">
        Gezählt werden die {gesamt} gewählten Sitze. Dazu kommt als 53. Stimme die Oberbürgermeisterin oder der
        Oberbürgermeister; wer das wird, entscheidet sich am selben Tag oder in der Stichwahl am 27. September.
      </p>
    </section>
  );
}
