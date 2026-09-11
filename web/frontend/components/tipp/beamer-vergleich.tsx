"use client";

// Vergleich (Screen 1g) — links der Halbkreis mit dem veröffentlichten
// Stand und die Tafel mit dem Server-Satz, rechts Liste/Ist/Ø-Tipp/Exakt
// und der OB-Block.
//
// Der Halbkreis übernimmt NUR die reine Geometrie aus
// `components/wahlabend/halbkreis.tsx` (`halbkreis()`/`mehrheit()`) statt der
// ganzen React-Komponente: Die trägt `WahlabendPartei`/`ElectionParty` als
// Typ (Stimmen, Kandidatenzahl, Vorjahresvergleich — nichts davon hat der
// Tippspiel-Vertrag) UND Zeiger-Interaktion, die auf einem Beamer ohnehin
// niemand bedient. Ein künstliches `ElectionParty`-Objekt mit Platzhaltern
// aufzufüllen wäre fragiler als die paar Zeilen SVG hier neu zu schreiben.

import { useId, useState } from "react";
import { halbkreis, mehrheit } from "@/lib/wahlabend";
import type { ApiAntwort } from "@/lib/vertrag";
import { Lotti } from "@/components/lotti";
import { cn } from "@/lib/utils";

type PredictionStand = ApiAntwort<"/tipp/stand">;
type Zeile = PredictionStand["compare"][number];

function MiniHalbkreis({ zeilen, gesamt }: { zeilen: Zeile[]; gesamt: number }) {
  const [aktiv, setAktiv] = useState<string | null>(null);
  const id = useId();
  const punkte = halbkreis(gesamt);
  const mitSitz = zeilen.filter((z) => (z.actual ?? 0) > 0);
  const belegung: (Zeile | null)[] = [];
  for (const z of mitSitz) for (let i = 0; i < (z.actual ?? 0); i++) belegung.push(z);
  while (belegung.length < gesamt) belegung.push(null);
  const noetig = mehrheit(gesamt);

  return (
    <svg viewBox="-0.08 -0.1 2.16 1.15" className="block w-full" role="img" aria-labelledby={`${id}-t`}>
      <title id={`${id}-t`}>
        {mitSitz.map((z) => `${z.short} ${z.actual}`).join(", ")}. Mehrheit ab {noetig} von {gesamt} Sitzen.
      </title>
      <line x1="1" y1="0.42" x2="1" y2="1.02" className="stroke-signal" strokeWidth="0.012" strokeDasharray="0.03 0.02" />
      {punkte.map((q, i) => {
        const z = belegung[i];
        return (
          <circle
            key={i}
            cx={q.x} cy={q.y} r={q.r}
            className={cn(z ? "fill-[var(--dot)] dark:fill-[var(--dot-dark)]" : "fill-foreground/10")}
            style={{ "--dot": z?.color, "--dot-dark": z?.color_dark } as React.CSSProperties}
            onMouseEnter={() => z && setAktiv(z.slug)}
            onMouseLeave={() => setAktiv(null)}
          />
        );
      })}
      {aktiv && (() => {
        const z = zeilen.find((x) => x.slug === aktiv);
        return z ? (
          <text x="1" y="0.65" textAnchor="middle" className="fill-foreground font-sans" style={{ fontSize: 0.09, fontWeight: 700 }}>
            {z.short} {z.actual}
          </text>
        ) : null;
      })()}
    </svg>
  );
}

function ObZeile({ z }: { z: PredictionStand["mayor"][number] }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-muted py-1.5 text-[13px]">
      <span className="truncate font-semibold" title={z.name}>{z.name}</span>
      <span className="flex items-center gap-3 font-mono tabular-nums text-muted-foreground">
        <span title="Hochrechnung">{z.actual_pct !== null ? `${z.actual_pct.toFixed(1)} %` : "–"}</span>
        <span className="text-foreground/40">◇</span>
        <span title="Ø-Tipp">{z.avg_tip !== null ? `${z.avg_tip.toFixed(1)} %` : "–"}</span>
      </span>
    </div>
  );
}

export function BeamerVergleich({ stand }: { stand: PredictionStand }) {
  // Kein Server-Satz für "ohne Sitz" — im Gegensatz zu `compare_sentence`
  // trägt `PredictionStand.notes` die Hinweise des WAHLABENDS (Losfälle,
  // fehlende Personenstimmen), keinen tippspiel-eigenen Text dafür. Aus
  // `compare` selbst berechnet: exakt 0 Sitze laut Hochrechnung.
  const ohneSitz = stand.compare.filter((c) => c.actual === 0).map((c) => c.short);

  return (
    <div className="grid h-full grid-cols-1 gap-8 px-4 py-6 sm:px-10 sm:py-8 lg:grid-cols-[700px_1fr]">
      <div className="flex flex-col justify-center gap-5">
        <div>
          <MiniHalbkreis zeilen={stand.compare} gesamt={stand.seats_total} />
          <p className="mt-2 text-center font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">
            {stand.seats_total} Sitze
          </p>
        </div>
        <div className="hh-tafel flex items-start gap-4 rounded-2xl p-5">
          <Lotti regung="sucht" className="h-16 w-16 flex-none" decorative />
          <div className="min-w-0">
            <p className="font-display text-[17px] font-bold leading-snug sm:text-lg">{stand.compare_sentence}</p>
            <p className="mt-2 text-[12px] text-muted-foreground">
              Ø-Tipp = Mittel aller {stand.tip_count} Tipps vor Tipp-Schluss.
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-col">
        <div className="grid grid-cols-[1fr_70px_70px_60px] gap-2 border-b border-muted pb-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          <span>Liste</span><span className="text-right">Ist ▮</span><span className="text-right">Ø-Tipp ◇</span><span className="text-right">Exakt</span>
        </div>
        {stand.compare.map((z) => (
          <div key={z.slug} className="grid grid-cols-[1fr_70px_70px_60px] items-center gap-2 border-b border-muted py-2 text-[13.5px]">
            <span className="flex min-w-0 items-center gap-2">
              <span
                aria-hidden
                className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--dot)] dark:bg-[var(--dot-dark)]"
                style={{ "--dot": z.color, "--dot-dark": z.color_dark } as React.CSSProperties}
              />
              <span className="truncate font-semibold">{z.short}</span>
            </span>
            <span className="text-right font-mono tabular-nums">{z.actual ?? "–"}</span>
            <span className="text-right font-mono tabular-nums text-muted-foreground">{z.avg_tip !== null ? z.avg_tip.toFixed(1) : "–"}</span>
            <span className="text-right font-mono tabular-nums text-muted-foreground">{z.exact_count}</span>
          </div>
        ))}
        {ohneSitz.length > 0 && (
          <p className="mt-2 text-[12px] text-muted-foreground">Ohne Sitz laut Hochrechnung: {ohneSitz.join(", ")}.</p>
        )}

        {stand.mayor.length > 0 && (
          <div className="mt-6">
            <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">OB-Wahl · Prozent</p>
            {stand.mayor.map((z) => <ObZeile key={z.slug} z={z} />)}
          </div>
        )}
      </div>
    </div>
  );
}
