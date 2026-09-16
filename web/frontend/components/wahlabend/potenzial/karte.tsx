"use client";

// Die Karte des Potenzials: die 91 Urnenbezirke, je nach Ansicht getönt —
// nach der Strategie (Halten / Überzeugen / Beides / Liegenlassen) oder nach
// einer Zahl (Ertrag je Tür, Rohr-Anteil, Umworbene, CDU, Nichtwählende).
// Ein Tipp öffnet die Bezirkstafel: alles, was die Rechnung über diesen
// Bezirk weiß, samt der Frage „wen hat man hier zu überzeugen?".
//
// Die Strategie-Farben sind KEINE Parteifarben: Orange (`--signal`) steht
// für Rohrs Basis, Hafenblau (`--primary`) für die Umworbenen — die
// Zahlenansichten tönen wie jede Karte im Wahlabend mit `--primary`.

import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { KICKER } from "@/components/wahlabend/bausteine";
import { Gebietskarte } from "@/components/wahlabend/gebietskarte";
import { Segmented } from "@/components/ui/segmented";
import {
  KANDIDATUREN, STRATEGIE, STRATEGIE_FARBE, TOENUNG, toenungWert,
  type PotenzialBezirk, type ToenungKey,
} from "@/lib/potenzial";
import { cn } from "@/lib/utils";
import { prozent, zahl } from "@/lib/wahlabend";
import { ladeWahlbezirke, roemisch, type Wahlbezirkflaeche } from "@/lib/wahlgebiete";

type Modus = "strategie" | ToenungKey;

const REIHENFOLGE = ["both", "hold", "persuade", "skip"] as const;

function Zeile({ name, wert, stark }: { name: string; wert: string; stark?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-[13px]">
      <span className="text-muted-foreground">{name}</span>
      <span className={cn("font-mono tabular-nums", stark && "font-semibold")}>{wert}</span>
    </div>
  );
}

/** Ein Bezirk, ganz: die Lage im ersten Wahlgang, wer hier ausgeschieden
 *  ist, was die Regler daraus machen — und die Einstufung mit ihrem Satz. */
function Bezirkstafel({ z, schliessen }: { z: PotenzialBezirk; schliessen: () => void }) {
  const s = STRATEGIE[z.strategy];
  const poolMax = Math.max(1, ...Object.values(z.eliminated));
  return (
    <div data-testid="potenzial-bezirk" className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className={KICKER}>Wahlbezirk {z.number} · WB {z.area_roman} · {z.district_name}</div>
          <h3 className="mt-1 font-display text-[17px] font-bold leading-snug tracking-tight">{z.name}</h3>
        </div>
        <button type="button" onClick={schliessen} aria-label="Bezirk schließen"
          className="-mr-1 -mt-1 flex h-8 w-8 flex-none items-center justify-center rounded-full text-muted-foreground hover:bg-muted">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-3 rounded-xl px-3 py-2.5" style={{ background: STRATEGIE_FARBE[z.strategy] ?? "hsl(var(--muted))" }}>
        <div className="text-[13px] font-semibold">{s?.title ?? z.strategy}</div>
        <div className="mt-0.5 text-[12px] leading-relaxed">{s?.sentence}</div>
      </div>

      <div className="mt-3 divide-y divide-border">
        <Zeile name="Wahlberechtigte" wert={zahl(z.eligible)} />
        <Zeile name="Nichtwählende, geschätzt" wert={`${zahl(z.non_voters)} · ${prozent(z.eligible ? (100 * z.non_voters) / z.eligible : null, 0)}`} />
        <Zeile name="Rohr · Prange, 1. Wahlgang" wert={`${zahl(z.rohr)} · ${zahl(z.prange)}`} />
        <Zeile name="Rohr-Anteil der beiden" wert={prozent(z.rohr_pct_of_two)} stark />
        <Zeile name="CDU (Ratswahl)" wert={`${zahl(z.cdu_council)} Stimmen · ≈ ${zahl(z.cdu_voters_est)}`} />
      </div>

      <div className="mt-3">
        <div className={KICKER}>Umworbene: {zahl(z.pool)} · {prozent(z.pool_pct)} der gültigen</div>
        <ul className="mt-1.5 space-y-1">
          {KANDIDATUREN.map((k) => {
            const n = z.eliminated[k.slug] ?? 0;
            return (
              <li key={k.slug} className="flex items-center gap-2 text-[12.5px]">
                <span className="w-16 flex-none text-muted-foreground">{k.kurz}</span>
                <span className="h-2 flex-none rounded-full" style={{ width: `${Math.max(2, (100 * n) / poolMax) * 0.9}px`, background: "hsl(var(--primary) / 0.6)" }} aria-hidden />
                <span className="font-mono tabular-nums">{zahl(n)}</span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="mt-3 divide-y divide-border border-t border-border pt-1">
        <Zeile name="Mit den Reglern: Rohr · Prange" wert={`${zahl(z.projected_rohr)} · ${zahl(z.projected_prange)}`} />
        <Zeile name="Vorsprung gewonnen" wert={`${z.net_total >= 0 ? "+" : "−"}${zahl(Math.abs(Math.round(z.net_total)))}`} stark />
        <Zeile name="je 1.000 Wahlberechtigte" wert={z.yield_per_1000 === null ? "–" : z.yield_per_1000.toFixed(1).replace(".", ",")} />
      </div>
    </div>
  );
}

export function PotenzialKarte({ bezirke, zaehler }: { bezirke: PotenzialBezirk[]; zaehler: Record<string, number> }) {
  const [flaechen, setFlaechen] = useState<Wahlbezirkflaeche[]>([]);
  const [modus, setModus] = useState<Modus>("strategie");
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);

  useEffect(() => {
    let lebt = true;
    ladeWahlbezirke().then((f) => { if (lebt) setFlaechen(f); });
    return () => { lebt = false; };
  }, []);

  const nachNummer = useMemo(() => new Map(bezirke.map((z) => [z.number, z])), [bezirke]);
  const werte = useMemo(() => {
    if (modus === "strategie") return undefined;
    const m = new Map<number, number>();
    for (const z of bezirke) {
      const w = toenungWert(z, modus);
      if (w !== null) m.set(z.number, w);
    }
    return m;
  }, [bezirke, modus]);
  const spanne = useMemo(() => {
    const v = werte ? [...werte.values()] : [];
    return v.length ? [Math.min(...v), Math.max(...v)] : null;
  }, [werte]);
  const toenung = TOENUNG.find((t) => t.key === modus);
  const ausgewaehlt = gewaehlt === null ? null : nachNummer.get(gewaehlt) ?? null;
  const top = useMemo(() => [...bezirke].sort((a, b) => (b.yield_per_1000 ?? 0) - (a.yield_per_1000 ?? 0)).slice(0, 6), [bezirke]);

  return (
    <section data-testid="potenzial-karte" className="mt-10">
      <div className={KICKER}>Karte</div>
      <h2 className="mt-1 font-display text-[22px] font-bold tracking-tight">Wo halten, wo überzeugen</h2>
      <p className="mt-1 max-w-2xl text-[13.5px] leading-relaxed text-muted-foreground">
        Jeder Urnenbezirk trägt eine Einstufung aus zwei Fragen: Liegt Rohr hier vorn (dann muss die Basis kommen), und
        wohnen hier viele Umworbene (dann lohnt das Gespräch)? Die Briefwahl hat keine Fläche — sie steht weiter unten.
      </p>

      <div className="mt-4 overflow-x-auto">
        <Segmented<Modus>
          value={modus}
          onChange={(m) => setModus(m)}
          options={[{ value: "strategie", label: "Strategie" }, ...TOENUNG.map((t) => ({ value: t.key, label: t.title }))]}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="rounded-2xl border border-border bg-card p-3 sm:p-4">
          <Gebietskarte
            flaechen={flaechen}
            werte={werte}
            farbe={modus === "strategie" ? (nr) => STRATEGIE_FARBE[nachNummer.get(nr)?.strategy ?? "skip"] ?? null : undefined}
            gewaehlt={gewaehlt}
            onWaehlen={(nr) => setGewaehlt((g) => (g === nr ? null : nr))}
            titel={(e) => {
              const z = nachNummer.get(e.nr);
              return z ? `${z.number} ${z.name} · ${STRATEGIE[z.strategy]?.title ?? ""}` : `${e.nr} · Wahlbereich ${roemisch(e.wb)}`;
            }}
            hoehe={420}
          />
          {modus === "strategie" ? (
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
              {REIHENFOLGE.map((s) => (
                <li key={s} className="flex items-center gap-1.5 text-[12px]">
                  <span aria-hidden className="inline-block h-3 w-5 rounded-sm border border-border" style={{ background: STRATEGIE_FARBE[s] ?? "hsl(var(--muted))" }} />
                  <span className="font-medium">{STRATEGIE[s].title}</span>
                  <span className="font-mono text-muted-foreground">{zaehler[s] ?? 0}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-[12px] text-muted-foreground">
              Getönt nach {toenung?.legend}
              {spanne ? ` — von ${spanne[0].toFixed(1).replace(".", ",")} bis ${spanne[1].toFixed(1).replace(".", ",")}` : ""}.
              Kräftiger ist mehr; gemessen zwischen dem schwächsten und dem stärksten Bezirk.
            </p>
          )}
        </div>

        {ausgewaehlt ? (
          <Bezirkstafel z={ausgewaehlt} schliessen={() => setGewaehlt(null)} />
        ) : (
          <div className="rounded-2xl border border-dashed border-border p-4">
            <div className={KICKER}>Die sechs ergiebigsten Türen</div>
            <p className="mt-1 text-[12.5px] text-muted-foreground">Netto je 1.000 Wahlberechtigte. Ein Tipp auf die Karte öffnet jeden Bezirk.</p>
            <ol className="mt-3 space-y-1.5">
              {top.map((z) => (
                <li key={z.number}>
                  <button type="button" onClick={() => setGewaehlt(z.number)}
                    className="flex w-full items-baseline gap-2 rounded-lg px-1.5 py-1 text-left text-[13px] hover:bg-muted">
                    <span className="w-9 flex-none font-mono text-[12px] text-muted-foreground">{z.number}</span>
                    <span className="min-w-0 flex-1 truncate">{z.name}</span>
                    <span className="flex-none font-mono text-[12px] tabular-nums">{z.yield_per_1000?.toFixed(0)}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </section>
  );
}
