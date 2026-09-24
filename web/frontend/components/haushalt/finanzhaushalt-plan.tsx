"use client";

// Investitionen laut Gesamtfinanzhaushalt (Anlage 006 der Haushaltspläne) —
// der Block „Was die Pläne vorsehen, bis 2029" auf /haushalt/investitionen.
//
// Die Open-Data-Dateien darüber tragen je Plan nur EIN Jahr. Anlage 006 trägt
// den Ansatz UND die Finanzplanung für drei Folgejahre, und das über acht
// Pläne (2019–2026). Daraus werden zwei Bilder:
//
// 1. Die Reihe: je Jahr der Ansatz aus dem Plan DIESES Jahres (voll), dahinter
//    die Finanzplanung des jüngsten Plans (schraffiert). Nie zwei Pläne für
//    dasselbe Jahr in einer Säule — der Ansatz schlägt die Vorausschau.
// 2. Die Gegenüberstellung: was ein Plan drei Jahre im Voraus für ein Jahr
//    vorsah, gegen den Ansatz, der dann kam. Das ist die Aussage, die nur
//    diese Quelle kann — und sie ist deutlich: In jedem der fünf Jahre lag
//    der Ansatz höher (gemessen 24.09.2026). Die Seite rechnet den Satz
//    aus den Daten, schreibt ihn nicht fest.
//
// KEINE BEWERTUNGSFARBE (components/grafik/hantel.tsx): Dass der spätere
// Ansatz höher liegt, ist weder gut noch schlecht — eine Finanzplanung
// schreibt nur fest, was schon beschlossen ist.
//
// Es ist der Entwurf: Anlage 006 hängt an der Einbringungs-Vorlage. Die
// Open-Data-Dateien darüber nennen für dasselbe Jahr andere Beträge (2025:
// 80,8 gegen 93,5 Mio. €); welche Fassung sie abbilden, sagen sie nicht —
// der Satz unter der Tabelle nennt den Unterschied, ohne ihn zu deuten.

import { useMemo } from "react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deMio } from "@/lib/haushalt";
import { Beleg } from "@/components/haushalt/source";
import { Hantel, type HantelZeile } from "@/components/grafik/hantel";

type Antwort = ApiAntwort<"/council/budget/investments">;
type Zeile = NonNullable<Antwort["finance_budget"]>[number];

/** Die Summenzeile „Auszahlungen für Investitionstätigkeit" eines Plans für ein Jahr. */
function auszahlung(zeilen: Zeile[], plan: number, year: number): number | null {
  const z = zeilen.find((r) => r.plan_budget_year === plan && r.year === year
    && r.role === "total_out_capital");
  return z ? z.amount : null;
}

export function FinanzhaushaltPlan() {
  const { data } = useFetch<Antwort>("/council/budget/investments");
  const zeilen = useMemo(() => data?.finance_budget ?? [], [data]);

  const plaene = useMemo(
    () => [...new Set(zeilen.map((z) => z.plan_budget_year))].sort((a, b) => a - b),
    [zeilen]);
  const juengster = plaene[plaene.length - 1];

  // Die Säulen: Ansatz je Planjahr, dann die Finanzplanung des jüngsten Plans.
  const saeulen = useMemo(() => {
    if (!juengster) return [];
    const aus = plaene.map((p) => ({ year: p, betrag: auszahlung(zeilen, p, p), plan: false }));
    for (const y of [juengster + 1, juengster + 2, juengster + 3]) {
      aus.push({ year: y, betrag: auszahlung(zeilen, juengster, y), plan: true });
    }
    return aus.filter((s): s is { year: number; betrag: number; plan: boolean } => s.betrag != null);
  }, [zeilen, plaene, juengster]);

  // Vorausschau drei Jahre vorher gegen den Ansatz des Jahres.
  const vergleich = useMemo(() => plaene
    .map((y) => ({ year: y, vorher: auszahlung(zeilen, y - 3, y), ansatz: auszahlung(zeilen, y, y) }))
    .filter((v): v is { year: number; vorher: number; ansatz: number } =>
      v.vorher != null && v.ansatz != null), [zeilen, plaene]);

  const arten = useMemo(() => {
    if (!juengster) return [];
    const jahre = [juengster, juengster + 1, juengster + 2, juengster + 3];
    const namen = [...new Set(zeilen
      .filter((z) => z.plan_budget_year === juengster && !z.role && z.label.match(/^(Erwerb|Bau|Aktiv|Sonstige)/))
      .map((z) => z.label))];
    return namen.map((label) => ({
      label,
      werte: jahre.map((y) => zeilen.find((z) => z.plan_budget_year === juengster
        && z.year === y && z.label === label)?.amount ?? 0),
    })).filter((a) => a.werte.some((w) => w > 0))
      .sort((a, b) => b.werte[0] - a.werte[0]);
  }, [zeilen, juengster]);

  if (!juengster || saeulen.length < 2) return null;

  const max = Math.max(...saeulen.map((s) => s.betrag));
  const hoeher = vergleich.filter((v) => v.ansatz > v.vorher);
  const spanne = hoeher.map((v) => v.ansatz - v.vorher);
  const hantel: HantelZeile[] = vergleich.map((v) => ({
    label: String(v.year),
    plan: v.vorher / 1e6,
    ist: v.ansatz / 1e6,
    einordnung: null,
  }));

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Gesamtfinanzhaushalt · Pläne {plaene[0]}–{juengster}
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          Investitionen laut Plan, bis {juengster + 3}
        </h2>
        <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
          Jeder Haushaltsplan setzt die Investitionen für sein Jahr an und schreibt drei
          Jahre Finanzplanung dahinter. Für {juengster} sind {deMio(saeulen.find((s) => s.year === juengster)?.betrag
            ? saeulen.find((s) => s.year === juengster)!.betrag / 1e6 : null)}&#8239;Mio.&nbsp;€
          Auszahlungen für Investitionen angesetzt<Beleg q="finance_budget" />; bis {juengster + 3} sieht
          die Finanzplanung {deMio(saeulen[saeulen.length - 1].betrag / 1e6)}&#8239;Mio.&nbsp;€ vor.
        </p>
      </div>

      <div className="flex flex-col gap-1.5" role="img"
        aria-label={`Auszahlungen für Investitionen je Jahr, ${saeulen.map((s) =>
          `${s.year}: ${deMio(s.betrag / 1e6)} Mio. Euro${s.plan ? " (Finanzplanung)" : ""}`).join(", ")}`}>
        {saeulen.map((s) => (
          <div key={s.year} className="flex items-center gap-2.5">
            <span className="w-9 flex-none font-mono text-[10.5px] tabular-nums text-muted-foreground">{s.year}</span>
            <div className="h-5 min-w-0 flex-1">
              <div className={`h-full rounded-[3px] ${s.plan ? "hh-schraffur" : ""}`}
                style={{ width: `${(s.betrag / max) * 100}%`,
                  background: s.plan ? undefined : "var(--hh-aus-0)" }} />
            </div>
            <span className="w-[74px] flex-none text-right font-mono text-[10.5px] tabular-nums text-muted-foreground">
              {deMio(s.betrag / 1e6)}
            </span>
          </div>
        ))}
        <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
          Mio.&nbsp;€, Auszahlungen für Investitionstätigkeit. Voll: Ansatz im Plan des jeweiligen
          Jahres. Schraffiert: Finanzplanung im Plan {juengster} — eine Vorausschau, kein Beschluss.
        </p>
      </div>

      {vergleich.length >= 2 && (
        <div className="flex flex-col gap-2 border-t border-dashed border-border pt-3">
          <h3 className="text-[14.5px] font-semibold leading-snug text-foreground">
            {hoeher.length === vergleich.length
              ? `In allen ${vergleich.length} Jahren lag der Ansatz über der Vorausschau von drei Jahren zuvor`
              : `In ${hoeher.length} von ${vergleich.length} Jahren lag der Ansatz über der Vorausschau von drei Jahren zuvor`}
          </h3>
          {spanne.length > 0 && (
            <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Der Unterschied betrug {deMio(Math.min(...spanne) / 1e6)} bis {deMio(Math.max(...spanne) / 1e6)}&#8239;Mio.&nbsp;€.
              Eine Finanzplanung enthält vor allem, was schon beschlossen ist; neue Vorhaben kommen
              erst mit dem Plan ihres Jahres dazu. Die Schraffur oben ist deshalb eher eine
              Untergrenze als eine Prognose.
            </p>
          )}
          <Hantel
            zeilen={hantel}
            massstab="amount"
            sortierung="alpha"
            wovon="das Jahr"
            planLabel="drei Jahre vorher geplant"
            istLabel="angesetzt"
            planKurz="vorher"
            istKurz="Ansatz"
            keineWertung="Die Farbe bewertet nicht: Ein höherer Ansatz heißt, dass mehr Vorhaben dazugekommen sind, nicht dass geplant falsch war."
            beleg={<Beleg q="finance_budget" />}
          />
        </div>
      )}

      {arten.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-dashed border-border pt-3">
          <h3 className="text-[14.5px] font-semibold leading-snug text-foreground">
            Wofür, im Plan {juengster}
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-[12.5px] tabular-nums">
              <thead>
                <tr className="text-left font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                  <th className="py-1.5 pr-3 font-medium">Auszahlungsart</th>
                  <th className="py-1.5 pr-3 text-right font-medium">{juengster}</th>
                  <th className="py-1.5 pr-3 text-right font-medium">{juengster + 1}</th>
                  <th className="py-1.5 pr-3 text-right font-medium">{juengster + 2}</th>
                  <th className="py-1.5 text-right font-medium">{juengster + 3}</th>
                </tr>
              </thead>
              <tbody>
                {arten.map((a) => (
                  <tr key={a.label} className="border-t border-border/70">
                    <td className="py-1.5 pr-3 text-foreground">{a.label}</td>
                    {a.werte.map((w, i) => (
                      <td key={i} className={`py-1.5 text-right ${i < 3 ? "pr-3" : ""} ${i === 0 ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
                        {w ? deMio(w / 1e6) : "–"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11.5px] leading-relaxed text-muted-foreground">
            Mio.&nbsp;€. Die erste Spalte ist der Ansatz, die übrigen sind Finanzplanung.
            Die Zahlen stammen aus dem Entwurf der Verwaltung (Stand der Einbringung). Die Datei
            des Open-Data-Portals oben nennt für dasselbe Jahr andere Beträge; welche Fassung sie
            abbildet, sagt sie nicht.
          </p>
        </div>
      )}
    </section>
  );
}
