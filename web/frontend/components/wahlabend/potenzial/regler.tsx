"use client";

// Die Regler: je ausgeschiedener Kandidatur zwei Anteile (zu Rohr, zu
// Prange — der Rest geht zu keinem), dazu die CDU-Wählenden der Ratswahl und die
// Beteiligung der drei Lager. Bauform wie im Haushalts-Labor
// (`components/haushalt/regler.tsx`), nur schmaler: Hier stehen zwölf
// Schieber nebeneinander, ein Titel und eine Zahl je Schieber reichen.

import { RotateCcw } from "lucide-react";
import { KICKER } from "@/components/wahlabend/bausteine";
import { KANDIDATUREN, VORGABE, paarSetzen, type Paar, type Potenzial, type Regler } from "@/lib/potenzial";
import { cn } from "@/lib/utils";
import { prozent, zahl } from "@/lib/wahlabend";

function Schieber({ id, name, wert, min = 0, max = 100, step = 5, einheit = "%", onChange, ton = "signal", vorgabe }: {
  id: string;
  name: string;
  wert: number;
  min?: number;
  max?: number;
  step?: number;
  einheit?: string;
  onChange: (v: number) => void;
  /** Rohr in Orange, Prange in Grau, Beteiligung in Hafenblau. */
  ton?: "signal" | "grau" | "primary";
  vorgabe: number;
}) {
  const anteil = ((wert - min) / (max - min)) * 100;
  const farbe = ton === "signal" ? "hsl(var(--signal) / 0.85)" : ton === "primary" ? "hsl(var(--primary) / 0.75)" : "hsl(var(--foreground) / 0.35)";
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-[12.5px] font-medium">{name}</label>
        <span className={cn("whitespace-nowrap font-mono text-[12.5px] tabular-nums", wert !== vorgabe && "font-semibold")}>
          {wert} {einheit}
        </span>
      </div>
      <div className="relative mt-1 h-5">
        <div className="pointer-events-none absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-muted" />
        <div className="pointer-events-none absolute left-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full" style={{ width: `${anteil}%`, background: farbe }} />
        <div aria-hidden className="pointer-events-none absolute top-1/2 h-3 w-[2px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/30"
          style={{ left: `${((vorgabe - min) / (max - min)) * 100}%` }} title="Vorgabe" />
        <input
          id={id} type="range" min={min} max={max} step={step} value={wert}
          aria-label={name}
          onChange={(e) => onChange(Number(e.target.value))}
          className="hh-regler absolute inset-0 h-5 w-full"
        />
      </div>
    </div>
  );
}

function PaarKarte({ slug, titel, kurz, untertitel, paar, vorgabe, onChange }: {
  slug: string;
  titel: string;
  /** Der Name im Schieber: „Boldt zu Rohr". */
  kurz: string;
  untertitel: string;
  paar: Paar;
  vorgabe: Paar;
  onChange: (p: Paar) => void;
}) {
  const zuhause = Math.max(0, 100 - paar.rohr - paar.prange);
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-[14px] font-semibold">{titel}</h3>
        <span className="font-mono text-[11px] text-muted-foreground">{untertitel}</span>
      </div>
      <div className="mt-3 space-y-3">
        <Schieber id={`r-${slug}-rohr`} name={`${kurz} zu Rohr`} wert={paar.rohr} vorgabe={vorgabe.rohr}
          onChange={(v) => onChange(paarSetzen(paar, "rohr", v))} ton="signal" />
        <Schieber id={`r-${slug}-prange`} name={`${kurz} zu Prange`} wert={paar.prange} vorgabe={vorgabe.prange}
          onChange={(v) => onChange(paarSetzen(paar, "prange", v))} ton="grau" />
      </div>
      <p className="mt-2.5 font-mono text-[11px] text-muted-foreground">Für keinen der beiden: {zuhause} %</p>
    </div>
  );
}

export function ReglerTafel({ regler, onChange, annahmen, cduWaehlende, modellStimmenquote }: {
  regler: Regler;
  onChange: (r: Regler) => void;
  annahmen: Potenzial["assumptions"];
  /** CDU-Wählende der Ratswahl, aus den Stimmen geschätzt. */
  cduWaehlende: number;
  /** Gültige Stimmen für Rohr/Prange im Modell relativ zu allen gültigen OB-Stimmen im ersten Wahlgang. */
  modellStimmenquote: number;
}) {
  const stimmen = new Map(annahmen.map((a) => [a.slug, a.votes]));
  const unveraendert = JSON.stringify(regler) === JSON.stringify(VORGABE);
  return (
    <section className="mt-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className={KICKER}>Annahmen</div>
          <h2 className="mt-1 font-display text-[22px] font-bold tracking-tight">Annahmen für die Stichwahl</h2>
          <p className="mt-1 max-w-2xl text-[13.5px] leading-relaxed text-muted-foreground">
            Die Regler zeigen Einschätzungen, keine gemessenen Wechsel. Die Markierung auf jeder Skala zeigt die
            voreingestellte Annahme. Die Beteiligung bei der letzten Stichwahl ist wegen der gleichzeitigen Bundestagswahl kein direkter
            Maßstab. Der CDU-Regler berücksichtigt, dass diese Menschen im ersten Wahlgang bereits gewählt haben. Er
            verändert deshalb den Stimmenabstand, statt zusätzliche Ratswahlstimmen als Personen zu zählen.
          </p>
        </div>
        <button
          type="button"
          onClick={() => onChange(VORGABE)}
          disabled={unveraendert}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-border bg-card px-3.5 text-[13px] font-medium transition-colors hover:bg-primary/5 disabled:cursor-default disabled:opacity-40"
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden />
          Auf die Vorgaben
        </button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {KANDIDATUREN.map((k) => (
          <PaarKarte
            key={k.slug}
            slug={k.slug}
            titel={k.name}
            kurz={k.kurz}
            untertitel={`${zahl(stimmen.get(k.slug) ?? 0)} Stimmen`}
            paar={regler[k.slug]}
            vorgabe={VORGABE[k.slug]}
            onChange={(p) => onChange({ ...regler, [k.slug]: p })}
          />
        ))}
        <PaarKarte
          slug="cdu"
          titel="CDU-Wählende der Ratswahl"
          kurz="CDU"
          untertitel={`≈ ${zahl(cduWaehlende)} Personen`}
          paar={regler.cdu}
          vorgabe={VORGABE.cdu}
          onChange={(p) => onChange({ ...regler, cdu: p })}
        />
      </div>

      <div className="mt-3 rounded-2xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-baseline gap-2">
          <h3 className="text-[14px] font-semibold">Beteiligung der Ausgangsgruppen</h3>
          <span className="font-mono text-[11px] text-muted-foreground">im Verhältnis zum ersten Wahlgang</span>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Schieber id="r-turnout-rohr" name="Rohr-Basis" wert={regler.turnoutRohr} vorgabe={VORGABE.turnoutRohr} min={60} max={120} step={1}
            onChange={(v) => onChange({ ...regler, turnoutRohr: v })} ton="signal" />
          <Schieber id="r-turnout-prange" name="Prange-Basis" wert={regler.turnoutPrange} vorgabe={VORGABE.turnoutPrange} min={60} max={120} step={1}
            onChange={(v) => onChange({ ...regler, turnoutPrange: v })} ton="grau" />
          <Schieber id="r-turnout-pool" name="Stimmen für Ausgeschiedene" wert={regler.turnoutPool} vorgabe={VORGABE.turnoutPool} min={60} max={120} step={1}
            onChange={(v) => onChange({ ...regler, turnoutPool: v })} ton="primary" />
        </div>
        <p className="mt-2.5 text-[12px] leading-relaxed text-muted-foreground">
          Die Vorgabe nimmt an: Von 100 Menschen, die im ersten Wahlgang Rohr, Prange oder eine ausgeschiedene Kandidatur
          gewählt haben, gehen jeweils {VORGABE.turnoutRohr} auch zur Stichwahl. Das ist eine Annahme, keine Messung.
          Von den Stimmen für ausgeschiedene Kandidaturen wird außerdem nicht jede Rohr oder Prange zugerechnet.
        </p>
        <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
          Mit den gewählten Annahmen ergeben sich für Rohr und Prange zusammen rund {prozent(modellStimmenquote, 0)} der
          gültigen OB-Stimmenzahl aus dem ersten Wahlgang. Das ist keine exakte Wahlbeteiligung, weil ungültige Stimmen
          fehlen. Der Anstieg bei der letzten Stichwahl ist wegen der gleichzeitigen Bundestagswahl kein Ausgangswert für dieses Modell.
        </p>
      </div>
    </section>
  );
}
