"use client";

// „Oldenburg im Bundesvergleich" — Block auf /haushalt/vergleich (Plan
// Haushalt-Blickwinkel, B3). Quelle: Wegweiser Kommune (council/
// bundesvergleich.py); Kennwerte der Verteilung rechnet das Backend.
//
// JE KENNZAHL EIN STREIFEN: jede Stadt ein Punkt auf einer Achse von
// kleinstem bis größtem Wert, die mittlere Hälfte als Band, der Median als
// Strich, Oldenburg größer und beschriftet, die Städte Niedersachsens als
// Ring. Städte mit (fast) gleichem Wert stapeln sich — bei den
// Liquiditätskrediten liegt mehr als die Hälfte auf der Null.
//
// KEIN RANG, KEINE BEWERTUNGSFARBE (Tims Entscheidung 24.09.2026): Die
// Antwort nennt keinen Platz, der Satz darunter keinen, und die Punkte sind
// neutral. Ob eine hohe Einkommensteuer je Kopf Stärke ist oder nur viele
// Pendler*innen mit Wohnsitz in der Stadt, lässt der Block offen.

import { useMemo, useState } from "react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deZahl } from "@/components/grafik/format";
import { Beleg } from "@/components/haushalt/source";
import { cn } from "@/lib/utils";

type Antwort = ApiAntwort<"/council/budget/federal-comparison">;
type Kennzahl = Antwort["indicators"][number];
type Jahr = Kennzahl["years"][number];

/** Was die Kennzahl misst und warum sie bundesweit vergleichbar ist. */
const ERKLAERT: Record<string, string> = {
  income_tax:
    "Der Anteil der Stadt an der Lohn- und Einkommensteuer ihrer Einwohner*innen: 15 % davon " +
    "gehen nach einem bundesweit gleichen Schlüssel an die Wohnortgemeinden. Der Rat kann ihn " +
    "nicht beeinflussen; er zeigt, was am Wohnort verdient wird.",
  property_tax_b:
    "Was die Grundsteuer auf bebaute und bebaubare Grundstücke je Kopf einbringt. Die Steuer " +
    "ist überall dieselbe, den Hebesatz beschließt jeder Rat selbst — Oldenburg lag 2019–2023 " +
    "bei 445 %.",
  liquidity_loans:
    "Kurzfristige Kredite, mit denen eine Stadt ihre laufenden Zahlungen überbrückt — gedacht " +
    "für Tage, in manchen Städten über Jahre aufgelaufen. Stand jeweils zum Jahresende.",
};

const euro = (v: number | null | undefined) => (v == null ? "—" : `${deZahl(v, 0)} €`);
const ZEILEN = 5; // höchstens so viele Punkte übereinander, der Rest als Zahl daneben

function Streifen({ j, label }: { j: Jahr; label: string }) {
  const { min, max, p25, p75, median } = j.stats;
  const lo = min ?? 0;
  const hi = max ?? 1;
  const x = (v: number) => (hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100);
  // Punkte in Fächern von 2 % Breite stapeln — Überdeckung wäre Unterschlagung.
  const faecher = useMemo(() => {
    const m = new Map<number, typeof j.cities>();
    for (const c of j.cities) {
      const f = Math.round(x(c.value) / 2);
      m.set(f, [...(m.get(f) ?? []), c]);
    }
    return [...m.entries()].map(([f, cs]) => ({
      f, cs: cs.slice().sort((a, b) => Number(b.is_oldenburg) - Number(a.is_oldenburg)),
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [j]);
  const ol = j.cities.find((c) => c.is_oldenburg);
  const satz = `${label} ${j.year}: ${j.cities.length} Städte zwischen ${euro(min)} und ${euro(max)} je ` +
    `Einwohner*in, Median ${euro(median)}` + (ol ? `, Oldenburg ${euro(ol.value)}.` : ".");

  return (
    <div role="img" aria-label={satz} className="relative mt-3 h-[112px] select-none">
      {/* Oldenburgs Beschriftung oben, am Punkt ausgerichtet */}
      {ol && (
        <span className="absolute top-0 -translate-x-1/2 whitespace-nowrap text-[11.5px] font-semibold text-primary"
          style={{ left: `clamp(40px, ${x(ol.value)}%, calc(100% - 40px))` }}>
          Oldenburg {euro(ol.value)}
        </span>
      )}
      <div className="absolute inset-x-0 bottom-6 top-5">
        {p25 != null && p75 != null && (
          <div className="absolute inset-y-0 rounded bg-muted"
            style={{ left: `${x(p25)}%`, width: `${Math.max(0.6, x(p75) - x(p25))}%` }} />
        )}
        {median != null && (
          <div className="absolute inset-y-0 w-px bg-foreground/60" style={{ left: `${x(median)}%` }} />
        )}
        {faecher.map(({ f, cs }) => (
          <div key={f} className="absolute bottom-1 flex -translate-x-1/2 flex-col-reverse items-center gap-[2px]"
            style={{ left: `${x(cs[0].value)}%` }}>
            {cs.slice(0, ZEILEN).map((c) => (
              <span key={c.key} title={`${c.city}: ${euro(c.value)}`}
                className={cn(
                  "block rounded-full",
                  c.is_oldenburg ? "h-3.5 w-3.5 bg-primary ring-2 ring-card"
                    : c.lower_saxony ? "h-2 w-2 border-[1.5px] border-foreground/70 bg-card"
                      : "h-2 w-2 bg-muted-foreground/45")} />
            ))}
            {cs.length > ZEILEN && (
              <span className="absolute left-full top-0 ml-1 font-mono text-[9.5px] leading-none text-muted-foreground">
                +{cs.length - ZEILEN}
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="absolute inset-x-0 bottom-0 flex justify-between font-mono text-[10px] tabular-nums text-muted-foreground">
        <span>{euro(min)}</span>
        {median != null && <span>Median {euro(median)}</span>}
        <span>{euro(max)}</span>
      </div>
    </div>
  );
}

function Einordnung({ k, j }: { k: Kennzahl; j: Jahr }) {
  const s = j.stats;
  if (k.key === "liquidity_loans" && j.oldenburg === 0) {
    return (
      <>
        Oldenburg hatte Ende {j.year} keine Liquiditätskredite. So war es bei {s.zero} der {s.n}{" "}
        Städte, Oldenburg eingeschlossen; bei den übrigen reichten sie bis {euro(s.max)} je Einwohner*in.
      </>
    );
  }
  return (
    <>
      Oldenburg {j.year}: {euro(j.oldenburg)} je Einwohner*in. Die mittlere Hälfte der {s.n} Städte
      liegt zwischen {euro(s.p25)} und {euro(s.p75)}, der Median bei {euro(s.median)}.
    </>
  );
}

export function Bundesvergleich() {
  const { data } = useFetch<Antwort>("/council/budget/federal-comparison");
  const jahre = useMemo(
    () => [...new Set((data?.indicators ?? []).flatMap((k) => k.years.map((y) => y.year)))].sort(),
    [data]);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  if (!data || jahre.length === 0) return null;
  const jahr = gewaehlt ?? jahre[jahre.length - 1];
  const g = data.group;

  return (
    <section className="@container/bund rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Oldenburg im Bundesvergleich
        </p>
        <div role="group" aria-label="Jahr wählen" className="flex flex-wrap gap-1">
          {jahre.map((y) => (
            <button key={y} type="button" aria-pressed={y === jahr} onClick={() => setGewaehlt(y)}
              className={cn(
                "min-h-[28px] rounded-full border px-2.5 font-mono text-[11px] tabular-nums",
                y === jahr ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:border-primary/40")}>
              {y}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
        Drei Kennzahlen, die sich auch über Landesgrenzen vergleichen lassen, für {g.n} kreisfreie
        Städte: alle mit {deZahl(g.population_min, 0)} bis {deZahl(g.population_max, 0)} Einwohner*innen
        und alle {g.lower_saxony} Niedersachsens<Beleg q="bundesvergleich" />. Kein Platz, keine
        Wertung — nur, wo Oldenburg in der Verteilung liegt.
      </p>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-primary" />Oldenburg</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full border-[1.5px] border-foreground/70" />Niedersachsen</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-muted-foreground/45" />übrige Städte</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-muted" />mittlere Hälfte</span>
      </div>

      <div className="mt-2 grid gap-x-8 gap-y-5 @4xl/bund:grid-cols-3">
        {data.indicators.map((k) => {
          const j = k.years.find((y) => y.year === jahr);
          return (
            <div key={k.key} className="min-w-0 border-t border-border pt-3">
              <h3 className="text-[14px] font-semibold text-foreground">{k.label} je Einwohner*in</h3>
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{ERKLAERT[k.key]}</p>
              {j ? (
                <>
                  <Streifen j={j} label={k.label} />
                  <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90"><Einordnung k={k} j={j} /></p>
                </>
              ) : (
                <p className="mt-3 text-[12px] text-muted-foreground">
                  Für {jahr} nicht dabei: Oldenburgs Wert bestand die Probe gegen die eigenen Zahlen nicht.
                </p>
              )}
            </div>
          );
        })}
      </div>

      <details className="mt-4 text-[12.5px]">
        <summary className="cursor-pointer font-semibold text-primary">Alle Werte {jahr} (alphabetisch)</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[480px] text-left tabular-nums">
            <thead className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              <tr>
                <th className="py-1 pr-3 font-medium">Stadt</th>
                {data.indicators.map((k) => <th key={k.key} className="py-1 pr-3 text-right font-medium">{k.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {(data.indicators[0]?.years.find((y) => y.year === jahr)?.cities ?? []).map((c) => (
                <tr key={c.key} className={cn("border-t border-border", c.is_oldenburg && "font-semibold")}>
                  <td className="py-1 pr-3">{c.city}{c.lower_saxony ? " · NI" : ""}</td>
                  {data.indicators.map((k) => (
                    <td key={k.key} className="py-1 pr-3 text-right">
                      {euro(k.years.find((y) => y.year === jahr)?.cities.find((x) => x.key === c.key)?.value)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <p className="mt-3 max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Aus dem Wegweiser Kommune, der die Zahlen der Statistischen Ämter für alle Kommunen aufbereitet.
        Jede Kennzahl steht nur für die Jahre, in denen Oldenburgs Wert zu den eigenen Zahlen der
        Stadt passt (auf 3 % genau). Die Gewerbesteuer fehlt, weil genau das nicht gelingt: Das
        Portal zählt sie netto nach der Kassenstatistik, das Statistische Jahrbuch der Stadt anders,
        und der Abstand wechselt von Jahr zu Jahr die Richtung.
      </p>
    </section>
  );
}
