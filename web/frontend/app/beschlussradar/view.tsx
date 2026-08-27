"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, CalendarDays, CheckCircle2, ClipboardList, Clock3, ExternalLink, Loader2 } from "lucide-react";
import { BackLink } from "@/components/back-link";
import { BrandMark } from "@/components/brand";
import { Mascot } from "@/components/mascot";
import { api } from "@/lib/api";
import { decisionHref, sessionHref } from "@/lib/routes";

type Station = {
  date?: string | null;
  committee?: string | null;
  top?: string | null;
  result?: string | null;
  ksinr?: number | null;
};

type Ergebnis = {
  id?: number | null;
  title?: string | null;
  outcome?: string | null;
  raw_result?: string | null;
  item_number?: string | null;
  date?: string | null;
  committee?: string | null;
};

type Karte = {
  kvonr: number;
  vorlage_nr?: string | null;
  title: string;
  art?: string | null;
  status: "geplant" | "in_beratung" | "entschieden";
  reason: string;
  vorlage_url?: string | null;
  next_station?: Station | null;
  last_station?: Station | null;
  latest_result?: Ergebnis | null;
};

type Spalte = {
  key: Karte["status"];
  title: string;
  description?: string;
  count: number;
  items: Karte[];
};

type Radar = {
  today: string;
  window_days: number;
  columns: Spalte[];
};

const ICONS = {
  geplant: CalendarDays,
  in_beratung: Clock3,
  entschieden: CheckCircle2,
};

const TINTS = {
  geplant: "border-primary/20 bg-primary/[0.04] text-primary",
  in_beratung: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200",
  entschieden: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200",
};

function datum(iso?: string | null): string {
  if (!iso) return "ohne Datum";
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

function outcomeLabel(outcome?: string | null): string | null {
  if (!outcome) return null;
  const labels: Record<string, string> = {
    angenommen: "angenommen",
    abgelehnt: "abgelehnt",
    vertagt: "vertagt",
    zur_kenntnis: "zur Kenntnis genommen",
    kein_beschluss: "kein Beschluss",
  };
  return labels[outcome] ?? outcome.replace(/_/g, " ");
}

function StationZeile({ station, fallback }: { station?: Station | null; fallback: string }) {
  if (!station) return <span>{fallback}</span>;
  const ziel = station.ksinr ? sessionHref(station.ksinr, station.top ? [station.top] : undefined) : null;
  const text = `${datum(station.date)} · ${station.committee || "Gremium offen"}${station.top ? ` · ${station.top}` : ""}`;
  return ziel ? (
    <Link href={ziel} className="inline-flex items-center gap-1 text-primary hover:underline">
      {text}<ArrowUpRight className="h-3 w-3" aria-hidden />
    </Link>
  ) : <span>{text}</span>;
}

function RadarKarte({ item }: { item: Karte }) {
  const station = item.status === "geplant" ? item.next_station : item.last_station || item.next_station;
  const label = outcomeLabel(item.latest_result?.outcome);
  return (
    <article className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {item.vorlage_nr || `KVo ${item.kvonr}`}{item.art ? ` · ${item.art}` : ""}
          </p>
          <h3 className="mt-1.5 font-display text-[16px] font-bold leading-snug text-foreground">
            {item.title}
          </h3>
        </div>
        <span className={`shrink-0 rounded-full border px-2 py-1 text-[10px] font-semibold ${TINTS[item.status]}`}>
          {label || item.status.replace("_", " ")}
        </span>
      </div>

      <dl className="mt-4 space-y-2 text-[13px] leading-relaxed">
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">Warum hier?</dt>
          <dd className="mt-0.5 text-foreground">{item.reason}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
            {item.status === "geplant" ? "Nächste Station" : "Letzte Station"}
          </dt>
          <dd className="mt-0.5 text-muted-foreground">
            <StationZeile station={station} fallback="Quelle noch nicht verknüpft" />
          </dd>
        </div>
        {item.latest_result?.raw_result && (
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">Ergebniswortlaut</dt>
            <dd className="mt-0.5 text-muted-foreground">{item.latest_result.raw_result}</dd>
          </div>
        )}
      </dl>

      <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3 text-[12px] font-semibold">
        {item.vorlage_url && (
          <a href={item.vorlage_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-muted-foreground hover:text-primary">
            Vorlage <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        )}
        {item.latest_result?.id && (
          <Link href={decisionHref(item.latest_result.id)} className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-primary hover:bg-primary/10">
            Beschluss ansehen <ArrowUpRight className="h-3 w-3" aria-hidden />
          </Link>
        )}
      </div>
    </article>
  );
}

function SpalteView({ column }: { column: Spalte }) {
  const Icon = ICONS[column.key];
  return (
    <section className="min-w-0 rounded-[22px] border border-border bg-background/60 p-3 @container sm:p-4">
      <div className="mb-3 flex items-start gap-3 px-1">
        <span className={`rounded-xl border p-2 ${TINTS[column.key]}`}>
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 className="font-display text-lg font-bold text-foreground">{column.title}</h2>
          <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">{column.description}</p>
        </div>
        <span className="ml-auto rounded-full bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground">{column.count}</span>
      </div>
      {column.items.length ? (
        <div className="space-y-3">
          {column.items.map((item) => <RadarKarte key={item.kvonr} item={item} />)}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border bg-card p-5 text-sm text-muted-foreground">
          In diesem Zeitraum liegt hier nichts. Das ist ein Befund, keine ausgeblendete Liste.
        </div>
      )}
    </section>
  );
}

export default function BeschlussradarView() {
  const [data, setData] = useState<Radar | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.get<Radar>("/council/beschlussradar")
      .then((radar) => { if (alive) setData(radar); })
      .catch((err) => { if (alive) setError(err instanceof Error ? err.message : "Beschlussradar konnte nicht geladen werden."); });
    return () => { alive = false; };
  }, []);

  return (
    <div className="min-h-[100dvh] bg-background">
      <header className="border-b border-border bg-card/90 pt-[env(safe-area-inset-top)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-5 py-4">
          <div className="flex items-center gap-3">
            <BackLink />
            <Link href="/" className="flex items-center gap-2"><BrandMark /><span className="hidden font-semibold text-foreground sm:inline">Ratslotse</span></Link>
          </div>
          <Link href="/council" className="text-sm font-medium text-muted-foreground hover:text-foreground">Zur Suche →</Link>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="rounded-[26px] border border-border bg-card p-5 shadow-sm sm:p-7">
          <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
            <div className="max-w-3xl">
              <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">Dev-Vorschau · Beschlussradar</p>
              <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-foreground sm:text-5xl">
                Was bewegt sich gerade im Rat?
              </h1>
              <p className="mt-3 max-w-[78ch] text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
                Das Radar sortiert Vorlagen der letzten 90 Tage nach ihrem belegten Verfahrensstand:
                geplant, in Beratung oder entschieden. Ob ein Beschluss draußen schon umgesetzt ist,
                behauptet diese Ansicht nicht — dafür braucht es später einen eigenen Nachweis-Workflow.
              </p>
            </div>
            <Mascot pose="search" bob decorative className="hidden h-28 w-28 md:block" />
          </div>
        </section>

        {error && (
          <div className="mt-6 rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {!data && !error && (
          <div className="mt-8 flex items-center gap-2 rounded-2xl border border-dashed border-border bg-card p-5 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Beschlussradar wird geladen …
          </div>
        )}

        {data && (
          <>
            <div className="mt-5 flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
              <span className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-3 py-1.5">
                <ClipboardList className="h-3.5 w-3.5" aria-hidden />
                {data.window_days} Tage Rückblick plus kommende Stationen
              </span>
              <span className="rounded-full border border-border bg-card px-3 py-1.5">Stand: {datum(data.today)}</span>
            </div>
            <div className="mt-6 grid gap-4 lg:grid-cols-3 lg:items-start">
              {data.columns.map((column) => <SpalteView key={column.key} column={column} />)}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
