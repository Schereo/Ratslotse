"use client";

// /haushalt/plan-ist — „Geplant und geworden" (Design H-16/H-17).
//
// Der Haushalt ist ein Plan; was daraus wurde, steht im Jahresabschluss.
// Beides nebeneinander zu zeigen ist die interessantere Hälfte des Bereichs:
// Oldenburg nimmt seit Jahren deutlich mehr ein als geplant — wer das weiß,
// liest das geplante Defizit anders.
//
// Reihenfolge: Kernaussage → Hantel je Bereich → woran es lag (Ertragsarten)
// → Zahlen. Bewertungsfarben gibt es nirgends (siehe components/hantel.tsx).

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { ErgebnisPosten, HaushaltDaten, deMio, mio } from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { Hantel, HantelMassstab } from "@/components/haushalt/hantel";
import { cn } from "@/lib/utils";

type Bereich = {
  nr: number; name: string;
  aufwPlan: number | null; aufwIst: number | null;
  ertrPlan: number | null; ertrIst: number | null;
};

function PlanIstInner() {
  const gewaehltesJahr = Number(useSearchParams().get("jahr")) || null;
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const [zahlenOffen, setZahlenOffen] = useState(false);
  const [massstab, setMassstab] = useState<HantelMassstab>("prozent");

  const jahre = data?.plan_ist_jahre ?? [];
  const jahr = gewaehltesJahr && jahre.includes(gewaehltesJahr) ? gewaehltesJahr : jahre.at(-1) ?? null;

  const { gesamt, bereiche, arten } = useMemo(() => {
    const leer = { gesamt: null as null | Record<string, number | null>, bereiche: [] as Bereich[], arten: [] as ErgebnisPosten[] };
    if (!data || !jahr) return leer;
    const zeilen = (data.ergebnisrechnung ?? []).filter((p) => p.jahr === jahr);
    const summe = (rows: ErgebnisPosten[], nr: number) => rows.find((p) => p.nr === nr);
    const g = zeilen.filter((p) => p.thh_nr == null);
    const e = summe(g, 12), a = summe(g, 20);

    const nrs = [...new Set(zeilen.filter((p) => p.thh_nr != null).map((p) => p.thh_nr))];
    const bereiche = nrs.map((nr) => {
      const teil = zeilen.filter((p) => p.thh_nr === nr);
      const te = summe(teil, 12), ta = summe(teil, 20);
      return {
        nr, name: teil[0]?.thh_name ?? `Teilhaushalt ${nr}`,
        aufwPlan: mio(ta?.ansatz), aufwIst: mio(ta?.ergebnis),
        ertrPlan: mio(te?.ansatz), ertrIst: mio(te?.ergebnis),
      };
    });
    type Aufw = { aufwPlan: number | null; aufwIst: number | null };
    const abw = (b: Aufw) => (b.aufwIst ?? 0) - (b.aufwPlan ?? 0);
    bereiche.sort((x, y) => massstab === "prozent"
      ? Math.abs(abw(y)) / Math.abs(y.aufwPlan || 1) - Math.abs(abw(x)) / Math.abs(x.aufwPlan || 1)
      : Math.abs(abw(y)) - Math.abs(abw(x)));

    // Woran es lag: die Ertragsarten (Posten 1–11) mit der größten Abweichung.
    const arten = g
      .filter((p) => p.nr >= 1 && p.nr <= 11 && p.abweichung != null)
      .sort((x, y) => Math.abs(y.abweichung ?? 0) - Math.abs(x.abweichung ?? 0))
      .slice(0, 5);

    return {
      gesamt: {
        ertrPlan: mio(e?.ansatz), ertrIst: mio(e?.ergebnis),
        aufwPlan: mio(a?.ansatz), aufwIst: mio(a?.ergebnis),
      },
      bereiche, arten,
    };
  }, [data, jahr, massstab]);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  if (!jahr || !gesamt) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für kein Jahr liegt bisher ein ausgelesener Jahresabschluss vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  const ertrDiff = (gesamt.ertrIst ?? 0) - (gesamt.ertrPlan ?? 0);
  const aufwDiff = (gesamt.aufwIst ?? 0) - (gesamt.aufwPlan ?? 0);
  const saldoPlan = (gesamt.ertrPlan ?? 0) - (gesamt.aufwPlan ?? 0);
  const saldoIst = (gesamt.ertrIst ?? 0) - (gesamt.aufwIst ?? 0);
  const quellen: QuellenSchluessel[] = ["jahresabschluss", "plan"];

  return (
    <Quellenkontext schluessel={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Geplant und geworden</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">
          Geplant und geworden
        </h1>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
          Ein Haushalt ist ein Plan. Was am Jahresende wirklich zusammenkam, steht erst im
          Jahresabschluss — hier beides nebeneinander.
        </p>
      </div>

      {/* Jahr-Umschalter: nur Jahre mit echtem Abschluss (scrollbar wie #497). */}
      {jahre.length > 1 && (
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Abgeschlossenes Haushaltsjahr
          </span>
          <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
            <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-card p-1">
              {jahre.map((j) => (
                <Link key={j} href={`/haushalt/plan-ist?jahr=${j}`} scroll={false}
                  className={cn("rounded-full px-3 py-1 text-[12.5px]",
                    j === jahr ? "bg-primary font-semibold text-primary-foreground" : "text-foreground/75 hover:bg-accent")}>
                  {j}
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Kernaussage — die Einnahmeseite ist die eigentliche Nachricht. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Das Jahr {jahr} in zwei Sätzen
        </p>
        <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-foreground/90">
          Die Stadt hat <strong>{deMio(gesamt.ertrIst)}&#8239;Mio.&nbsp;€ eingenommen</strong> —
          geplant waren {deMio(gesamt.ertrPlan)}<Beleg q="jahresabschluss" />
          {Math.abs(ertrDiff) >= 1 && (
            <>, also {deMio(Math.abs(ertrDiff))}&#8239;Mio. {ertrDiff > 0 ? "mehr" : "weniger"}</>
          )}. Ausgegeben hat sie <strong>{deMio(gesamt.aufwIst)}&#8239;Mio.</strong> statt der
          geplanten {deMio(gesamt.aufwPlan)}
          {Math.abs(aufwDiff) >= 1 && (
            <> ({aufwDiff > 0 ? "+" : "−"}{deMio(Math.abs(aufwDiff))})</>
          )}.
        </p>
        <div className="mt-3 grid gap-2.5 border-t border-border/60 pt-3 sm:grid-cols-2">
          <div>
            <p className="text-[11.5px] text-muted-foreground">Geplantes Jahresergebnis</p>
            <p className="font-display text-[20px] font-bold tabular-nums">
              {saldoPlan > 0 ? "+" : ""}{deMio(saldoPlan)}<span className="text-xs font-semibold text-muted-foreground">&#8239;Mio.</span>
            </p>
          </div>
          <div>
            <p className="text-[11.5px] text-muted-foreground">Tatsächliches Jahresergebnis</p>
            <p className={cn("font-display text-[20px] font-bold tabular-nums",
              saldoIst > saldoPlan && "text-[color:var(--hh-ein-0)]")}>
              {saldoIst > 0 ? "+" : ""}{deMio(saldoIst)}<span className="text-xs font-semibold text-muted-foreground">&#8239;Mio.</span>
            </p>
          </div>
        </div>
      </div>

      <LottiErklaert
        titel="Warum ein Haushalt nie punktgenau aufgeht"
        text="Ein Haushalt wird ein Jahr im Voraus beschlossen — niemand weiß dann, wie viel Gewerbesteuer hereinkommt, welche Tarife steigen oder wie viele Kinder einen Kitaplatz brauchen. Die Stadt plant deshalb vorsichtig: lieber etwas zu wenig Einnahmen ansetzen als zu viel. Abweichungen sind normal und für sich genommen weder gut noch schlecht."
      />

      {/* Hantel je Teilhaushalt (H-16) */}
      {bereiche.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Ausgaben je Bereich · {jahr}
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {bereiche.length} Teilhaushalte
            </span>
          </div>

          {/* Umschalter wie brutto/netto auf der Bereichsseite: Der Wechsel
              dreht die Reihenfolge, und darin steckt die Aussage. */}
          <div className="mb-3 flex flex-col gap-1.5">
            <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
              <div className="flex w-max flex-none items-center gap-1 rounded-full border border-border bg-muted/40 p-1">
                {([
                  ["prozent", "Abweichung in Prozent"],
                  ["betrag", "Abweichung in Millionen"],
                ] as [HantelMassstab, string][]).map(([wert, text]) => (
                  <button key={wert} type="button" onClick={() => setMassstab(wert)}
                    className={cn("whitespace-nowrap rounded-full px-3 py-1 text-[12.5px]",
                      massstab === wert
                        ? "bg-card font-semibold shadow-sm"
                        : "text-foreground/70 hover:text-foreground")}>
                    {text}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              {massstab === "prozent"
                ? "Gemessen am eigenen Plan — so lässt sich ein Bereich von 231 Mio. mit einem von 6 Mio. vergleichen. Vorn steht, wessen Plan am weitesten danebenlag."
                : "Gemessen in Euro — vorn steht, wo am meisten Geld anders floss als geplant. Kleine Bereiche verschwinden dabei fast."}
            </p>
          </div>

          <Hantel
            massstab={massstab}
            zeilen={bereiche.map((b) => ({ label: b.name, plan: b.aufwPlan, ist: b.aufwIst }))}
          />
        </div>
      )}

      {/* Woran es lag: Ertragsarten mit der größten Abweichung */}
      {arten.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Woher der Unterschied bei den Einnahmen kommt
          </p>
          <div className="mt-3 flex flex-col gap-2.5">
            {arten.map((p) => {
              const abw = mio(p.abweichung) ?? 0;
              const groesste = mio(Math.max(...arten.map((x) => Math.abs(x.abweichung ?? 0)))) ?? 1;
              return (
                <div key={p.nr} className="grid grid-cols-[minmax(110px,190px)_1fr_auto] items-center gap-x-3">
                  <span className="truncate text-[12.5px]">{p.bezeichnung}</span>
                  <div className="h-2.5 rounded-full bg-muted">
                    <div className="h-full rounded-full bg-signal/70"
                      style={{ width: `${Math.min((Math.abs(abw) / groesste) * 100, 100)}%` }} />
                  </div>
                  <span className="whitespace-nowrap text-right text-[12px] font-semibold tabular-nums">
                    {abw > 0 ? "+" : ""}{deMio(abw)}&#8239;Mio.
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
            Abweichung zwischen Ansatz und Ergebnis je Einnahmeart<Beleg q="jahresabschluss" />.
            Die größten Ausschläge erklären den Unterschied oben.
          </p>
        </div>
      )}

      {/* Nicht-Chart-Entsprechung (H-17 als Tabelle) */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <button type="button" onClick={() => setZahlenOffen((o) => !o)}
          className="text-[12.5px] font-semibold text-primary">
          {zahlenOffen ? "Zahlen ausblenden" : "Zahlen anzeigen"}
        </button>
        {zahlenOffen && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[420px] text-[12px] tabular-nums">
              <thead>
                <tr className="text-left font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  <th className="py-1 pr-2 font-medium">Bereich</th>
                  <th className="py-1 pr-2 text-right font-medium">geplant</th>
                  <th className="py-1 pr-2 text-right font-medium">tatsächlich</th>
                  <th className="py-1 text-right font-medium">Abweichung</th>
                </tr>
              </thead>
              <tbody>
                {bereiche.map((b) => {
                  const d = (b.aufwIst ?? 0) - (b.aufwPlan ?? 0);
                  const prozent = b.aufwPlan ? (d / b.aufwPlan) * 100 : 0;
                  return (
                    <tr key={b.nr} className="border-t border-border/60">
                      <td className="py-1 pr-2">{b.name}</td>
                      <td className="py-1 pr-2 text-right">{deMio(b.aufwPlan)}</td>
                      <td className="py-1 pr-2 text-right font-semibold">{deMio(b.aufwIst)}</td>
                      <td className={cn("py-1 text-right", Math.abs(prozent) >= 1 && "text-signal")}>
                        {d > 0 ? "+" : ""}{deMio(d)} ({prozent > 0 ? "+" : ""}
                        {prozent.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%)
                      </td>
                    </tr>
                  );
                })}
                <tr className="border-t-2 border-border font-semibold">
                  <td className="py-1 pr-2">Alle Ausgaben</td>
                  <td className="py-1 pr-2 text-right">{deMio(gesamt.aufwPlan)}</td>
                  <td className="py-1 pr-2 text-right">{deMio(gesamt.aufwIst)}</td>
                  <td className="py-1 text-right">{aufwDiff > 0 ? "+" : ""}{deMio(aufwDiff)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Es erscheinen nur Jahre, für die ein Jahresabschluss vorliegt und dessen Zahlen unsere
        Prüfung bestehen — die Summe der Teilhaushalte muss die Gesamtrechnung ergeben. Für das
        laufende und das kommende Haushaltsjahr gibt es naturgemäß noch keinen Abschluss.
      </p>

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}

export default function PlanIstPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}>
      <PlanIstInner />
    </Suspense>
  );
}
