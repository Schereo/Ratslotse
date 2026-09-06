"use client";

// Der Halbkreis: ein Punkt je Sitz, in Stimmzettel-Reihenfolge der Listen von
// links nach rechts gefüllt, die Mehrheitslinie in der Mitte. Parteifarben
// nur als Punkte (Designsprache: Dots, nie Flächen). Zeiger oder Fokus auf
// einer Liste hebt ihre Punkte, die übrigen treten zurück — der Zustand
// kommt aus React, damit er auch für die Tastatur gilt.

import { useId, useState } from "react";
import { cn } from "@/lib/utils";
import { halbkreis, mehrheit, type WahlabendPartei } from "@/lib/wahlabend";

type Feld = "seats" | "projected_seats";

export function Halbkreis({
  parteien,
  gesamt,
  feld,
  titel,
}: {
  parteien: readonly WahlabendPartei[];
  gesamt: number;
  feld: Feld;
  titel: string;
}) {
  const [aktiv, setAktiv] = useState<string | null>(null);
  const id = useId();
  const plaetze = halbkreis(gesamt);
  const mitSitz = parteien.filter((p) => (p[feld] ?? 0) > 0);
  // Reihenfolge der Punkte = Stimmzettel-Reihenfolge (Index).
  const belegung: (WahlabendPartei | null)[] = [];
  for (const p of mitSitz) for (let i = 0; i < (p[feld] ?? 0); i++) belegung.push(p);
  while (belegung.length < gesamt) belegung.push(null);
  const noetig = mehrheit(gesamt);
  const vergeben = belegung.filter(Boolean).length;
  const aktive = mitSitz.find((p) => p.slug === aktiv) ?? null;

  return (
    <figure className="rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <figcaption className="flex items-baseline justify-between gap-3">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {gesamt} Sitze · {titel}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">Mehrheit ab {noetig}</span>
      </figcaption>
      <svg
        viewBox="-0.08 -0.1 2.16 1.22"
        className="mt-2 block w-full"
        role="img"
        aria-labelledby={`${id}-t`}
        onMouseLeave={() => setAktiv(null)}
      >
        <title id={`${id}-t`}>
          {titel}: {mitSitz.map((p) => `${p.short} ${p[feld]}`).join(", ")}. Mehrheit ab {noetig} von {gesamt} Sitzen.
        </title>
        {/* Mehrheitslinie: senkrecht durch die Mitte, zwischen Platz 26 und 27. */}
        <line x1="1" y1="0.42" x2="1" y2="1.02" className="stroke-signal" strokeWidth="0.012" strokeDasharray="0.03 0.02" />
        {plaetze.map((q, i) => {
          const p = belegung[i];
          const gedimmt = aktiv !== null && p?.slug !== aktiv;
          return (
            <circle
              key={i}
              cx={q.x}
              cy={q.y}
              r={q.r}
              className={cn(
                "gb-auf transition-opacity duration-fluss",
                p ? "fill-[var(--dot)] dark:fill-[var(--dot-dark)]" : "fill-foreground/10",
                gedimmt && "opacity-25",
              )}
              style={{ "--dot": p?.color, "--dot-dark": p?.color_dark, animationDelay: `${i * 12}ms` } as React.CSSProperties}
              onMouseEnter={() => p && setAktiv(p.slug)}
            />
          );
        })}
      </svg>
      {/* Ablesezeile: nie leer — ohne Wahl die Summe. */}
      <p className="mt-1 min-h-5 text-center text-[12.5px] tabular-nums" aria-live="polite">
        {aktive ? (
          <>
            <strong className="font-semibold">{aktive.short}</strong> {aktive[feld]} {aktive[feld] === 1 ? "Sitz" : "Sitze"}
            {(aktive[feld] ?? 0) >= noetig ? " · allein die Mehrheit" : ` · ${noetig - (aktive[feld] ?? 0)} bis zur Mehrheit`}
          </>
        ) : (
          <span className="text-muted-foreground">
            {vergeben} von {gesamt} Sitzen vergeben
          </span>
        )}
      </p>
      <ul className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1">
        {mitSitz.map((p) => (
          <li key={p.slug}>
            <button
              type="button"
              onMouseEnter={() => setAktiv(p.slug)}
              onFocus={() => setAktiv(p.slug)}
              onBlur={() => setAktiv(null)}
              onClick={() => setAktiv(aktiv === p.slug ? null : p.slug)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-1.5 py-0.5 text-[11.5px] text-muted-foreground transition-colors duration-tipp",
                aktiv === p.slug && "bg-primary/8 text-foreground",
              )}
            >
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-full bg-[var(--dot)] ring-1 ring-inset ring-black/10 dark:bg-[var(--dot-dark)]"
                style={{ "--dot": p.color, "--dot-dark": p.color_dark } as React.CSSProperties}
              />
              {p.short} <strong className="font-semibold text-foreground">{p[feld]}</strong>
            </button>
          </li>
        ))}
      </ul>
    </figure>
  );
}
