"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowUpRight, ChevronDown } from "lucide-react";
import { scaleLinear } from "d3-scale";
import { line } from "d3-shape";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { Card, CardListSkeleton, ErrorState, Select } from "@/components/ui";
import { StatKicker } from "@/components/admin-charts";
import { AbleseBeschreibung, AbleseFlaeche, Ableseleiste, useAblesen, useAbleseId } from "@/components/grafik/ablesen";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";
import {
  KENNZAHL_NAMEN, LAEUFT, STATUS, UMGEBUNG, commitLink, datumText, grundText, kostenText, modellKurz, rohLink, wertText,
  type Benchmark, type BenchmarkUebersicht, type LaufZeile, type Pipeline,
} from "@/lib/benchmarks";
import { Veraenderung } from "./primitives";

type LaufVoll = ApiAntwort<"/admin/benchmarks/{key}">["runs"][number];

/** Der Benchmark-Bereich: je KI-Pipeline, wie gut sie gerade ist, und jede
 *  Messung mit ihren Bedingungen. Bewertet wird im Backend
 *  (`kern/benchmarks.py`), hier nur gezeigt. */
export function BenchmarksTab({ view, route }: { view: "pipelines" | "laeufe"; route: string }) {
  const q = useQuery({ queryKey: ["admin", "benchmarks"], queryFn: () => api.get<BenchmarkUebersicht>("/admin/benchmarks") });
  const params = new URLSearchParams(route);
  if (q.isPending) return <CardListSkeleton rows={4} />;
  if (q.isError || !q.data) return <ErrorState title="Die Benchmarks konnten nicht geladen werden" onRetry={() => void q.refetch()} busy={q.isFetching} />;
  if (view === "laeufe") return <AlleLaeufe data={q.data} />;
  const p = q.data.pipelines.find((x) => x.key === params.get("p"));
  return p ? <PipelineDetail data={q.data} pipeline={p} offen={params.get("b")} /> : <PipelineUebersicht data={q.data} />;
}

// --------------------------------------------------------------------------- //

function StatusMarke({ status }: { status: Benchmark["status"] }) {
  const s = STATUS[status];
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
      s.ton === "gruen" && "bg-green-500/10 text-green-800 dark:text-green-300",
      s.ton === "gelb" && "bg-amber-500/10 text-amber-800 dark:text-amber-300",
      s.ton === "leer" && "border border-dashed border-border text-muted-foreground")}>
      {s.ton !== "leer" && <span className={cn("h-1.5 w-1.5 rounded-full", s.ton === "gruen" ? "bg-green-600" : "bg-amber-500")} aria-hidden />}
      {s.text}
    </span>
  );
}

/** Stufen-Namen je Pipeline — ein Benchmark, der Lotti mitmisst, nennt deren Stufen. */
function useStufen(data: BenchmarkUebersicht) {
  return useMemo(() => {
    const je = new Map(data.pipelines.map((p) => [p.key, new Map(p.steps.map((s) => [s.key, s.label]))]));
    return (b: Benchmark) => (key: string) => {
      for (const p of [b.pipeline, ...b.also]) {
        const l = je.get(p)?.get(key);
        if (l) return l;
      }
      return key;
    };
  }, [data]);
}

function Kopf({ kicker, titel, rechts }: { kicker: string; titel: string; rechts?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="font-mono text-xs tracking-wide text-muted-foreground">{kicker}</p><h2 className="mt-1 font-display text-2xl font-bold tracking-tight">{titel}</h2></div>
      {rechts && <p className="font-mono text-xs text-muted-foreground">{rechts}</p>}
    </div>
  );
}

// ---- Übersicht ------------------------------------------------------------- //

function PipelineUebersicht({ data }: { data: BenchmarkUebersicht }) {
  const benchmarks = new Map(data.benchmarks.map((b) => [b.key, b]));
  const gemessen = data.pipelines.filter((p) => p.status !== "none");
  const offen = data.pipelines.filter((p) => p.status === "none");
  return (
    <div className="@container space-y-5">
      <Kopf kicker="KI-PIPELINES" titel="Wie gut sind sie gerade?"
        rechts={`${data.pipelines.length} Pipelines · ${data.benchmarks.length} Benchmarks · ${data.runs_total.toLocaleString("de-DE")} Läufe`} />
      {data.invalid.length > 0 && <UngueltigeLaeufe data={data} />}
      <div className="grid gap-3 @2xl:grid-cols-2">
        {gemessen.map((p) => <PipelineKarte key={p.key} p={p} b={p.headline ? benchmarks.get(p.headline) : undefined} />)}
      </div>
      {offen.length > 0 && (
        <Card className="p-4">
          <StatKicker>Noch ohne Messung</StatKicker>
          <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
            {offen.map((p) => <li key={p.key}><a href={`#pipelines?p=${p.key}`} className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-foreground hover:text-primary">
              {p.title}<span className="font-mono text-xs text-muted-foreground">{p.steps.length} Stufen</span></a></li>)}
          </ul>
        </Card>
      )}
      <p className="text-sm text-muted-foreground">Ein Lauf ist eine Datei unter <code className="font-mono text-xs">eval/runs/</code>, auf dem Server zusätzlich <code className="font-mono text-xs">data/eval_runs/</code> · Format und Katalog: <code className="font-mono text-xs">kern/benchmarks.py</code></p>
    </div>
  );
}

function PipelineKarte({ p, b }: { p: Pipeline; b?: Benchmark }) {
  const l = b?.latest;
  return (
    <a href={`#pipelines?p=${p.key}`} className="group flex min-w-0 flex-col rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40 hover:bg-primary/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-lg font-bold leading-tight">{p.title}</h3>
        <StatusMarke status={p.status} />
      </div>
      <p className="mt-1 text-sm leading-snug text-muted-foreground">{p.summary}</p>
      <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <strong className="font-display text-4xl leading-none tracking-tight tabular-nums">{b && l && b.metric.unit !== "none" ? wertText(l.value, b.metric.unit) : "–"}</strong>
        {b && <span className="text-sm text-muted-foreground">{b.metric.label} · {b.title}</span>}
      </div>
      <p className="mt-2 font-mono text-xs text-muted-foreground">
        {l ? `${datumText(l.started_at)} · ${UMGEBUNG[l.environment] ?? l.environment}${l.model ? ` · ${modellKurz(l.model)}` : ""}` : "noch kein vergleichbarer Lauf"}
      </p>
      <p className="mt-auto flex items-center justify-between gap-2 pt-4 text-xs text-muted-foreground">
        <span>{p.measured_steps} von {p.steps.length} Stufen gemessen · {p.benchmarks.length} {p.benchmarks.length === 1 ? "Benchmark" : "Benchmarks"}</span>
        <ArrowUpRight className="h-4 w-4 shrink-0 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden />
      </p>
    </a>
  );
}

function UngueltigeLaeufe({ data }: { data: BenchmarkUebersicht }) {
  return (
    <div role="alert" className="rounded-xl border border-amber-500/35 bg-amber-500/[0.06] p-4 text-sm">
      <p className="font-semibold text-amber-800 dark:text-amber-300">{data.invalid.length} Läufe sind ungültig und fehlen in der Auswertung</p>
      <ul className="mt-2 space-y-1 font-mono text-xs text-muted-foreground">
        {data.invalid.slice(0, 8).map((r) => <li key={`${r.origin}:${r.id}`}>{r.id}: {r.problems.join("; ")}</li>)}
      </ul>
    </div>
  );
}

// ---- Eine Pipeline --------------------------------------------------------- //

function PipelineDetail({ data, pipeline: p, offen }: { data: BenchmarkUebersicht; pipeline: Pipeline; offen: string | null }) {
  const stufen = useStufen(data);
  const alle = p.benchmarks.map((k) => data.benchmarks.find((b) => b.key === k)).filter((b): b is Benchmark => !!b);
  return (
    <div className="@container space-y-6">
      <a href="#pipelines" className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary"><ArrowLeft className="h-4 w-4" aria-hidden />Alle Pipelines</a>
      <div>
        <div className="flex flex-wrap items-center gap-3"><h2 className="font-display text-2xl font-bold tracking-tight">{p.title}</h2><StatusMarke status={p.status} /></div>
        <p className="mt-1 max-w-[62ch] text-sm text-muted-foreground">{p.summary}</p>
      </div>
      <Stufen p={p} />
      <section aria-labelledby="bm-titel" className="space-y-3">
        <h3 id="bm-titel" className="font-display text-lg font-bold">Benchmarks</h3>
        {alle.length === 0 ? <p className="text-sm text-muted-foreground">Für diese Pipeline gibt es noch keinen Benchmark.</p>
          : alle.map((b) => <BenchmarkKarte key={b.key} b={b} p={p} data={data} stufe={stufen(b)} offen={offen === b.key} />)}
      </section>
    </div>
  );
}

function Stufen({ p }: { p: Pipeline }) {
  return (
    <Card className="px-4 py-1 sm:px-5">
      <h3 className="pt-4 font-display text-lg font-bold">Stufen</h3>
      <p className="text-sm text-muted-foreground">Modell laut Konfiguration dieses Servers · Nutzung der letzten 30 Tage</p>
      <ol className="mt-2">
        {p.steps.map((s, i) => {
          const abweichend = s.models_30d[0] && s.model && s.models_30d[0] !== s.model ? s.models_30d[0] : null;
          return (
            <li key={s.key} className="grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-start gap-x-3 border-t border-border py-3 first:border-0">
              <span className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-muted font-mono text-xs text-muted-foreground" aria-hidden>{i + 1}</span>
              <div className="min-w-0">
                <p className="text-sm font-semibold">{s.label}</p>
                <p className="break-words font-mono text-xs text-muted-foreground" title={s.model ?? undefined}>{s.llm ? modellKurz(s.model) : `ohne Sprachmodell${s.model ? ` · ${modellKurz(s.model)}` : ""}`}</p>
                {abweichend && <p className="mt-0.5 text-xs text-amber-800 dark:text-amber-300">im Betrieb zuletzt {modellKurz(abweichend)}</p>}
              </div>
              <div className="text-right text-sm">
                {s.benchmarks.length ? <p>{s.benchmarks.length} {s.benchmarks.length === 1 ? "Benchmark" : "Benchmarks"}</p>
                  : <p className="text-amber-800 dark:text-amber-300">ungemessen</p>}
                {s.llm && <p className="whitespace-nowrap font-mono text-xs text-muted-foreground">{s.calls_30d.toLocaleString("de-DE")} Aufrufe · {kostenText(s.cost_30d)}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function BenchmarkKarte({ b, p, data, stufe, offen }: {
  b: Benchmark; p: Pipeline; data: BenchmarkUebersicht; stufe: (k: string) => string; offen: boolean;
}) {
  const [auf, setAuf] = useState(offen);
  useEffect(() => {
    if (offen) document.getElementById(`b-${b.key}`)?.scrollIntoView({ block: "start" });
  }, [offen, b.key]);
  const l = b.latest;
  const v = b.previous;
  const fremd = b.pipeline !== p.key ? data.pipelines.find((x) => x.key === b.pipeline)?.title : null;
  const punkte = b.runs.filter((r) => r.comparable && r.value != null);
  return (
    <Card id={`b-${b.key}`} className="scroll-mt-20 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-display text-base font-bold">{b.title}{fremd && <span className="ml-2 font-sans text-xs font-normal text-muted-foreground">aus {fremd}</span>}</h4>
          <p className="mt-0.5 max-w-[70ch] text-sm text-muted-foreground">{b.measures}</p>
        </div>
        <StatusMarke status={b.status} />
      </div>
      <div className="mt-4 grid items-end gap-x-8 gap-y-3 @3xl:grid-cols-[minmax(11rem,auto)_minmax(0,1fr)]">
        <div>
          {b.metric.unit !== "none" && <StatKicker>{b.metric.label}</StatKicker>}
          <div className="mt-1.5 flex flex-wrap items-baseline gap-2">
            {b.metric.unit === "none"
              ? <span className="text-sm text-muted-foreground">Gegenüberstellung im Rohergebnis, ohne Kennzahl</span>
              : <strong className={cn("font-display text-[32px] font-extrabold leading-none tracking-tight tabular-nums", !l && "text-muted-foreground")}>{l ? wertText(l.value, b.metric.unit) : "–"}</strong>}
            {l && b.metric.unit !== "none" && <Veraenderung jetzt={l.value} vorher={v?.value} prozent={b.metric.unit === "share"} invers={!b.metric.higher_is_better} klein />}
          </div>
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            {l ? [datumText(l.started_at), UMGEBUNG[l.environment] ?? l.environment, l.label, l.model && modellKurz(l.model)].filter(Boolean).join(" · ") : "noch kein Lauf"}
          </p>
        </div>
        {b.metric.unit !== "none" && punkte.length >= 2 && <LaufVerlauf b={b} zeilen={punkte} />}
      </div>
      {b.reasons.length > 0 && (
        <p className="mt-3 text-sm text-amber-800 dark:text-amber-300">{b.reasons.map((g) => grundText(g, stufe)).join(" · ")}</p>
      )}
      <button type="button" aria-expanded={auf} onClick={() => setAuf(!auf)}
        className="mt-3 flex min-h-11 items-center gap-2 text-sm font-medium text-primary">
        <ChevronDown className={cn("h-4 w-4 transition-transform", auf && "rotate-180")} aria-hidden />
        Bedingungen{b.runs.length ? ` und ${b.runs.length} ${b.runs.length === 1 ? "Lauf" : "Läufe"}` : ""}
      </button>
      {auf && <>
        <Bedingungen b={b} stufe={stufe} />
        {b.runs.length > 0 && <LaufTabelle zeilen={[...b.runs].reverse()} data={data} />}
      </>}
    </Card>
  );
}

function Bedingungen({ b, stufe }: { b: Benchmark; stufe: (k: string) => string }) {
  const zeilen: [string, React.ReactNode][] = [
    ["Fälle", b.cases.length ? b.cases.map((c) => `${c.cases ?? "?"} · ${c.path}`).join(" · ") : "keine Falldatei"],
    ["Erwartung", b.truth || "–"],
    ["Richter", b.judge ? modellKurz(b.judge) : "kein Modell"],
    ["Stufen", b.steps.map(stufe).join(" · ") || "–"],
    ["Läuft", LAEUFT[b.runs_on] ?? b.runs_on],
  ];
  if (b.noise) zeilen.push(["Streuung", b.noise]);
  if (b.hard) zeilen.push(["Harter Befund", b.hard]);
  if (b.log) zeilen.push(["Messbuch", b.log]);
  return (
    <div className="mt-1 rounded-lg bg-muted/40 p-3">
      <dl className="grid gap-x-4 gap-y-2 text-sm @2xl:grid-cols-[8rem_minmax(0,1fr)]">
        {zeilen.map(([k, w]) => <Fragment key={k}><dt className="text-muted-foreground">{k}</dt><dd className="min-w-0 break-words">{w}</dd></Fragment>)}
        <dt className="text-muted-foreground">Befehl</dt>
        <dd className="min-w-0"><code className="block overflow-x-auto whitespace-pre rounded bg-card px-2 py-1 font-mono text-xs">{b.command}</code></dd>
      </dl>
    </div>
  );
}

/** Die Hauptkennzahl über die vergleichbaren Läufe. Gefüllt: heutige
 *  Besetzung; hohl: Kandidaten und Varianten. Abstände nach Reihenfolge,
 *  nicht nach Zeit — es geht um die Folge der Messungen. */
function LaufVerlauf({ b, zeilen }: { b: Benchmark; zeilen: LaufZeile[] }) {
  const { box, breite } = useBreite(520, 120);
  const steuerung = useAblesen(zeilen.length, zeilen.length - 1);
  const id = useAbleseId();
  const hoehe = 92;
  const links = 44;
  const rechts = breite - 8;
  const werte = zeilen.map((z) => z.value ?? 0);
  const max = b.metric.unit === "share" || b.metric.unit === "ratio" ? 1 : Math.max(1, ...werte);
  const y = scaleLinear().domain([0, max]).nice(2).range([hoehe - 6, 8]);
  const schritt = (rechts - links) / Math.max(zeilen.length - 1, 1);
  const x = (i: number) => links + schritt * i;
  const heutig = zeilen.map((z, i) => [z, i] as const).filter(([z]) => z.current);
  const stellen = zeilen.map((z) => {
    const wert = wertText(z.value, b.metric.unit);
    const titel = `${datumText(z.started_at)} · ${UMGEBUNG[z.environment] ?? z.environment}`;
    return {
      title: titel,
      werte: [{ label: b.metric.label, value: wert, farbe: "hsl(var(--primary))" },
        { label: !z.current ? "Kandidat/Variante" : z.model ? "heutige Besetzung" : "Modell nicht erfasst",
          value: [z.label, z.model && modellKurz(z.model), z.variant].filter(Boolean).join(" · ") || "–" }],
      vorlesen: `${titel}: ${b.metric.label} ${wert}${z.model ? `, ${z.model}` : ""}`,
    };
  });
  const ticks = y.ticks(2);
  return (
    <div ref={box} className="min-w-0">
      <AbleseBeschreibung id={id}>{b.metric.label} über {zeilen.length} Läufe. Mit Pfeiltasten, Maus oder Antippen einzelne Läufe lesen.</AbleseBeschreibung>
      <svg width="100%" height={hoehe} viewBox={`0 0 ${breite} ${hoehe}`} role="group" aria-label={`${b.metric.label} über die Läufe`} aria-describedby={id}>
        <g aria-hidden>
          {ticks.map((t) => <g key={t}>
            <line x1={links} x2={rechts} y1={y(t)} y2={y(t)} className="stroke-border" strokeDasharray={t === 0 ? undefined : "3 4"} />
            <text x={links - 6} y={y(t) + 4} textAnchor="end" className="fill-muted-foreground text-[11px] tabular-nums">{wertText(t, b.metric.unit)}</text>
          </g>)}
          {heutig.length > 1 && <path d={line<readonly [LaufZeile, number]>().x(([, i]) => x(i)).y(([z]) => y(z.value ?? 0))(heutig) ?? ""}
            fill="none" className="stroke-primary/50" strokeWidth={1.5} />}
          {zeilen.map((z, i) => <circle key={z.id} cx={x(i)} cy={y(z.value ?? 0)} r={z.current ? 3.5 : 3}
            className={z.current ? "fill-primary" : "fill-card stroke-muted-foreground"} strokeWidth={1.25} />)}
        </g>
        <AbleseFlaeche stellen={stellen} steuerung={steuerung} x={x} xVon={links} xBis={rechts} yVon={8} hoehe={hoehe - 14}
          gruppe="Läufe" marken={(i) => [{ y: y(zeilen[i].value ?? 0), farbe: "hsl(var(--primary))" }]} />
      </svg>
      <Ableseleiste stelle={stellen[steuerung.aktiv]} steuerung={steuerung} haftet={false} note="Antippen oder mit ← → ablesen" />
    </div>
  );
}

// ---- Läufe ----------------------------------------------------------------- //

function LaufTabelle({ zeilen, data, mitBenchmark }: { zeilen: LaufZeile[]; data: BenchmarkUebersicht; mitBenchmark?: boolean }) {
  const [offen, setOffen] = useState<string | null>(null);
  const [n, setN] = useState(25);
  const benchmarks = new Map(data.benchmarks.map((b) => [b.key, b]));
  const spalten = mitBenchmark ? 7 : 6;
  return (
    <div className="mt-3">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[40rem] text-left text-sm tabular-nums">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="p-2.5 font-medium">Datum</th>
              {mitBenchmark && <th className="p-2.5 font-medium">Benchmark</th>}
              <th className="p-2.5 font-medium">Umgebung</th>
              <th className="p-2.5 font-medium">Lauf</th>
              <th className="p-2.5 font-medium">Modell</th>
              <th className="p-2.5 text-right font-medium">Wert</th>
              <th className="p-2.5 text-right font-medium">Kosten</th>
            </tr>
          </thead>
          <tbody>
            {zeilen.slice(0, n).map((z) => {
              const b = benchmarks.get(z.benchmark);
              if (!b) return null;
              const auf = offen === z.id;
              return (
                <Fragment key={`${z.origin}:${z.id}`}>
                  <tr className={cn("border-t border-border", !z.comparable && "text-muted-foreground")}>
                    <td className="whitespace-nowrap p-2.5">
                      <button type="button" aria-expanded={auf} onClick={() => setOffen(auf ? null : z.id)}
                        className="inline-flex min-h-8 items-center gap-1.5 font-medium text-primary">
                        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", auf && "rotate-180")} aria-hidden />{datumText(z.started_at)}
                      </button>
                    </td>
                    {mitBenchmark && <td className="p-2.5"><a href={`#pipelines?p=${b.pipeline}&b=${b.key}`} className="hover:text-primary">{b.title}</a>
                      <span className="block text-xs text-muted-foreground">{data.pipelines.find((p) => p.key === b.pipeline)?.title}</span></td>}
                    <td className="p-2.5">{UMGEBUNG[z.environment] ?? z.environment}</td>
                    <td className="p-2.5">
                      <span className="flex flex-wrap items-center gap-1.5">
                        {z.current && <span className="h-1.5 w-1.5 rounded-full bg-primary" title="heutige Besetzung" aria-label="heutige Besetzung" />}
                        {[z.label, z.variant].filter(Boolean).join(" · ") || "–"}
                        {z.sample ? <span className="text-xs text-muted-foreground">{z.comparable ? "Stichprobe" : "Teillauf"} {z.sample}</span>
                          : !z.comparable && <span className="text-xs text-muted-foreground">nicht vergleichbar</span>}
                        {z.origin === "server" && <span className="text-xs text-muted-foreground">nur hier</span>}
                      </span>
                    </td>
                    <td className="p-2.5 font-mono text-xs" title={z.model ?? undefined}>{modellKurz(z.model)}</td>
                    <td className="whitespace-nowrap p-2.5 text-right font-semibold">{wertText(z.value, b.metric.unit)}</td>
                    <td className="whitespace-nowrap p-2.5 text-right text-muted-foreground">{kostenText(z.cost_usd)}</td>
                  </tr>
                  {auf && <tr><td colSpan={spalten} className="bg-muted/30 p-3"><LaufDetails zeile={z} b={b} data={data} /></td></tr>}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {zeilen.length > n && <button type="button" onClick={() => setN(n + 50)} className="mt-2 min-h-11 text-sm font-medium text-primary">Weitere {Math.min(50, zeilen.length - n)} von {zeilen.length - n} zeigen</button>}
    </div>
  );
}

function LaufDetails({ zeile, b, data }: { zeile: LaufZeile; b: Benchmark; data: BenchmarkUebersicht }) {
  const q = useQuery({ queryKey: ["admin", "benchmarks", b.key], queryFn: () => api.get<ApiAntwort<"/admin/benchmarks/{key}">>(`/admin/benchmarks/${encodeURIComponent(b.key)}`) });
  const stufe = useStufen(data)(b);
  if (q.isPending) return <p className="text-sm text-muted-foreground">Wird geladen…</p>;
  const r = q.data?.runs.find((x) => x.id === zeile.id && x.origin === zeile.origin) as LaufVoll | undefined;
  if (q.isError || !r) return <p role="alert" className="text-sm text-muted-foreground">Der Lauf konnte nicht geladen werden.</p>;
  const rec = r as Record<string, unknown>;
  const text = (k: string) => (typeof rec[k] === "string" && rec[k] ? String(rec[k]) : null);
  const code = (rec.code ?? null) as { commit?: string; branch?: string | null; dirty?: boolean | null; checked_in?: boolean; from?: string } | null;
  const ds = (rec.dataset ?? null) as { path?: string; sha256?: string | null; cases?: number | null; sample?: number } | null;
  const modelle = Object.entries((rec.models ?? {}) as Record<string, string>);
  const metriken = Object.entries((rec.metrics ?? {}) as Record<string, unknown>).filter(([k, w]) => w != null && k !== "cases");
  const latenz = (rec.latency_ms ?? null) as { p50?: number | null; p95?: number | null } | null;
  const flags = (rec.flags ?? null) as string[] | null;
  const extra = (rec.raw_extra ?? null) as string[] | null;
  const benannt = new Map([b.metric, ...b.secondary].map((m) => [m.key, m]));
  const commit = commitLink(code?.commit, data.github);
  const roh = rohLink(text("raw"), data.github);

  const zeilen: [string, React.ReactNode][] = [];
  if (text("purpose")) zeilen.push(["Zweck", text("purpose")]);
  if (text("conclusion")) zeilen.push(["Fazit", <strong key="f" className="font-semibold">{text("conclusion")}</strong>]);
  zeilen.push(["Code", code?.commit ? <>
    {commit ? <a href={commit} target="_blank" rel="noreferrer" className="font-mono text-primary">{code.commit}</a> : <span className="font-mono">{code.commit}</span>}
    <span className="text-muted-foreground">{code.checked_in ? " · eingecheckt mit diesem Commit" : code.from === "workflow" ? " · laut Workflow" : `${code.branch ? ` · ${code.branch}` : ""}${code.dirty ? " · mit lokalen Änderungen" : ""}`}</span>
  </> : "nicht erfasst"]);
  zeilen.push(["Modelle", modelle.length ? modelle.map(([s, m]) => `${stufe(s)}: ${m}`).join(" · ") : "nicht erfasst"]);
  if (text("judge")) zeilen.push(["Richter", text("judge")]);
  if (text("variant")) zeilen.push(["Variante", text("variant")]);
  if (flags) zeilen.push(["Schalter", flags.length ? flags.join(", ") : "keine"]);
  zeilen.push(["Fälle", ds?.path ? `${ds.cases ?? "?"} · ${ds.path}${ds.sha256 ? ` · ${ds.sha256}` : ""}${ds.sample ? ` · Stichprobe ${ds.sample}` : ""}` : zeile.cases ? `${zeile.cases}` : "–"]);
  if (text("data")) zeilen.push(["Daten", text("data")]);
  zeilen.push(["Kennzahlen", metriken.map(([k, w]) => {
    const m = benannt.get(k);
    return `${m?.label ?? KENNZAHL_NAMEN[k] ?? k} ${typeof w === "number" ? wertText(w, m?.unit ?? (w <= 1 && !Number.isInteger(w) ? "ratio" : "count")) : String(w)}`;
  }).join(" · ") || "–"]);
  const dauer = typeof rec.duration_s === "number" ? `${Math.round(rec.duration_s).toLocaleString("de-DE")} s` : null;
  if (dauer || latenz?.p50) zeilen.push(["Dauer", [dauer && `Lauf ${dauer}`, latenz?.p50 && `je Aufruf p50 ${latenz.p50.toLocaleString("de-DE")} ms`, latenz?.p95 && `p95 ${latenz.p95.toLocaleString("de-DE")} ms`].filter(Boolean).join(" · ")]);
  zeilen.push(["Kosten", kostenText(zeile.cost_usd)]);
  if (text("note")) zeilen.push(["Notiz", text("note")]);
  zeilen.push(["Rohdaten", <span key="r" className="break-all font-mono text-xs">
    {roh ? <a href={roh} target="_blank" rel="noreferrer" className="text-primary">{text("raw")}</a> : text("raw") ?? "–"}
    {extra?.length ? <span className="text-muted-foreground"> · {extra.join(" · ")}</span> : null}
  </span>]);
  zeilen.push(["Datei", <span key="d" className="break-all font-mono text-xs">{zeile.origin === "server" ? "data/eval_runs/" : "eval/runs/"}{zeile.id}.json</span>]);
  return (
    <dl className="grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[7rem_minmax(0,1fr)]">
      {zeilen.map(([k, w]) => <Fragment key={k}><dt className="text-muted-foreground">{k}</dt><dd className="min-w-0 break-words">{w}</dd></Fragment>)}
    </dl>
  );
}

// ---- Alle Läufe ------------------------------------------------------------ //

function AlleLaeufe({ data }: { data: BenchmarkUebersicht }) {
  const [pipeline, setPipeline] = useState("");
  const [umgebung, setUmgebung] = useState("");
  const pipelineVon = new Map(data.benchmarks.map((b) => [b.key, [b.pipeline, ...b.also]]));
  const alle = useMemo(() => data.benchmarks.flatMap((b) => b.runs).sort((a, b) => b.started_at.localeCompare(a.started_at)), [data]);
  const zeilen = alle.filter((z) => (!pipeline || pipelineVon.get(z.benchmark)?.includes(pipeline)) && (!umgebung || z.environment === umgebung));
  const umgebungen = [...new Set(alle.map((z) => z.environment))];
  return (
    <div className="@container space-y-4">
      <Kopf kicker="MESSBUCH" titel="Alle Läufe" rechts={`${zeilen.length.toLocaleString("de-DE")} von ${alle.length.toLocaleString("de-DE")}`} />
      <div className="flex flex-wrap gap-3">
        <label className="min-w-0 flex-1 basis-56 text-sm"><span className="mb-1 block text-muted-foreground">Pipeline</span>
          <Select value={pipeline} onChange={(e) => setPipeline(e.target.value)}>
            <option value="">Alle</option>
            {data.pipelines.filter((p) => p.status !== "none").map((p) => <option key={p.key} value={p.key}>{p.title}</option>)}
          </Select></label>
        <label className="min-w-0 basis-40 text-sm"><span className="mb-1 block text-muted-foreground">Umgebung</span>
          <Select value={umgebung} onChange={(e) => setUmgebung(e.target.value)}>
            <option value="">Alle</option>
            {umgebungen.map((u) => <option key={u} value={u}>{UMGEBUNG[u] ?? u}</option>)}
          </Select></label>
      </div>
      {zeilen.length === 0 ? <p className="text-sm text-muted-foreground">Keine Läufe für diese Auswahl.</p>
        : <LaufTabelle zeilen={zeilen} data={data} mitBenchmark />}
    </div>
  );
}
