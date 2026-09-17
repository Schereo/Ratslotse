"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { Card, ChartSkeleton, ErrorState, formatDate } from "@/components/ui";
import { cn } from "@/lib/utils";
import { AbschnittKopf, Veraenderung } from "./primitives";

type Kohorten = ApiAntwort<"/admin/stats/cohorts">;
type Stufe = Kohorten["total"][number];

const LABELS: Record<string, string> = {
  registriert: "Registriert", bestaetigt: "E-Mail bestätigt", setup_begonnen: "Einrichtung begonnen",
  setup_fertig: "Einrichtung abgeschlossen", haken: "Früh ein Abo angelegt", frage: "Eine erste Frage gestellt",
  tag2: "Innerhalb von 2 Tagen", tag7: "Innerhalb von 7 Tagen", tag30: "Innerhalb von 30 Tagen",
};
const RETURN = ["tag2", "tag7", "tag30"] as const;

/** A stage is an independent observation, not a step in a funnel. In
 * particular, subtracting neighbours with different eligibility invents loss. */
function Beobachtung({ stage, total, previous }: { stage: Stufe; total: number; previous?: number | null }) {
  const pending = Math.max(0, total - stage.eligible);
  return (
    <div className="py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span>{LABELS[stage.key] ?? stage.label}</span>
        <span className="tabular-nums"><strong>{stage.n}</strong><span className="text-muted-foreground"> von {stage.eligible}</span></span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div className="h-full rounded-full bg-primary" style={{ width: `${stage.eligible ? stage.n / stage.eligible * 100 : 0}%` }} />
      </div>
      {stage.key === "haken" && <div className="mt-2 space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-sm"><span>{stage.eligible ? `${Math.round(stage.n / stage.eligible * 100)} % früh eingerichtet` : "Noch keine Quote"}</span>{previous !== undefined && <Veraenderung jetzt={stage.eligible ? stage.n / stage.eligible : null} vorher={previous} prozent klein />}</div>
        <p className="text-sm text-muted-foreground">Thema oder Gremium abonniert, spätestens am Folgetag der Anmeldung.</p>
      </div>}
      {pending > 0 && <p className="mt-1 text-sm text-muted-foreground">{pending} {pending === 1 ? "Konto ist" : "Konten sind"} dafür noch zu neu.</p>}
      {stage.eligible === 0 && <p className="mt-1 text-sm text-muted-foreground">Noch nicht auswertbar.</p>}
    </div>
  );
}

export function KohortenSection() {
  const [week, setWeek] = useState("all");
  const [window, setWindow] = useState<typeof RETURN[number]>("tag7");
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "cohorts"], queryFn: () => api.get<Kohorten>("/admin/stats/cohorts?weeks=8"),
  });
  if (isPending) return <ChartSkeleton />;
  if (isError || !data) return <ErrorState title="Neue Konten konnten nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />;

  const cohort = data.cohorts.find((c) => c.week === week);
  const stages = cohort?.stages ?? data.total;
  const total = stages.find((s) => s.key === "registriert")?.n ?? 0;
  const selected = stages.find((s) => s.key === window);
  const pending = Math.max(0, total - (selected?.eligible ?? 0));
  const quote = selected?.eligible ? selected.n / selected.eligible : null;
  const scope = cohort ? `Registriert in der Woche ab ${formatDate(cohort.week)}` : `Registriert in den letzten ${data.weeks} Kalenderwochen`;
  const colkeys = ["bestaetigt", "setup_begonnen", "setup_fertig", "haken", "frage", ...RETURN];

  return (
    <section className="space-y-5" aria-label="Entwicklung neuer Konten">
      <AbschnittKopf titel="Ankommen. Einrichten. Wiederkommen." rechts={`${data.weeks} Kalenderwochen`}>
        Was aus neuen Konten wird – mit getrenntem Blick auf den Einstieg und die spätere Nutzung.
      </AbschnittKopf>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-muted/60 p-3">
        <label className="flex w-full min-w-0 flex-wrap items-center gap-2 text-sm font-medium sm:w-auto">
          Anmeldegruppe
          <select value={cohort ? week : "all"} onChange={(e) => setWeek(e.target.value)} className="min-h-11 w-full min-w-0 max-w-full rounded-lg border border-border bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
            <option value="all">Alle {data.weeks} Wochen</option>
            {[...data.cohorts].reverse().map((c) => <option key={c.week} value={c.week}>Woche ab {formatDate(c.week)} · {c.n} Konten</option>)}
          </select>
        </label>
        <span className="text-sm text-muted-foreground">{data.excluded} Betreiber-/Testkonten ausgeschlossen</span>
      </div>
      <div className="@container">
        <div className="grid grid-cols-1 items-start gap-4 @3xl:grid-cols-2">
          <Card className="min-w-0 p-5 [overflow-wrap:anywhere]">
            <p className="text-sm font-medium text-muted-foreground">{scope}</p>
            <div className="mt-3 flex items-baseline gap-2"><strong className="font-display text-4xl tabular-nums">{total}</strong><span className="text-muted-foreground">{total === 1 ? "neues Konto" : "neue Konten"}</span></div>
            <h3 className="mt-6 font-display text-lg font-bold">Was wurde eingerichtet?</h3>
            <div className="mt-1 divide-y divide-border">
              {stages.filter((s) => !RETURN.includes(s.key as typeof RETURN[number]) && s.key !== "registriert").map((s) => <Beobachtung key={s.key} stage={s} total={total} previous={!cohort && s.key === "haken" ? (data.basis.vorher_n >= 3 ? data.previous.haken_quote : null) : undefined} />)}
            </div>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">Jede Zeile zählt für sich. Eine Frage setzt zum Beispiel kein Abo voraus.</p>
          </Card>
          <Card className="flex min-w-0 flex-col p-5 [overflow-wrap:anywhere]">
            <h3 className="font-display text-lg font-bold">Wer kommt wieder?</h3>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">Mindestens an einem weiteren Tag aktiv – innerhalb des gewählten Zeitfensters nach der Anmeldung.</p>
            <div role="group" aria-label="Zeitfenster für Rückkehr" className="mt-5 flex flex-wrap gap-1 rounded-xl bg-muted p-1">
              {RETURN.map((key) => <button type="button" key={key} aria-pressed={window === key} onClick={() => setWindow(key)}
                className={cn("min-h-11 flex-1 whitespace-nowrap rounded-lg px-2 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", window === key ? "bg-card font-semibold text-primary shadow-sm" : "text-muted-foreground hover:text-foreground")}>{key.slice(3)} Tage</button>)}
            </div>
            <div aria-live="polite" className="mt-6">
              <div className="flex flex-wrap items-end gap-3">
                <p className="font-display text-5xl font-bold tabular-nums tracking-tight">{quote == null ? "–" : `${Math.round(quote * 100)} %`}</p>
                {!cohort && <Veraenderung jetzt={quote} vorher={data.basis.vorher_n >= 3 ? data.previous[window] : null} prozent />}
              </div>
              <p className="mt-3 text-base"><strong>{selected?.n ?? 0} von {selected?.eligible ?? 0}</strong> auswertbaren Konten kamen wieder.</p>
              <div className="mt-4 h-3 overflow-hidden rounded-full bg-muted" aria-hidden><div className="h-full rounded-full bg-primary" style={{ width: `${(quote ?? 0) * 100}%` }} /></div>
              <dl className="mt-5 divide-y divide-border text-sm">
                <div className="flex justify-between gap-4 py-3"><dt>Im Zeitfenster nicht wiedergekommen</dt><dd className="font-semibold tabular-nums">{(selected?.eligible ?? 0) - (selected?.n ?? 0)}</dd></div>
                <div className="flex justify-between gap-4 py-3"><dt>Noch zu neu für die Auswertung</dt><dd className="font-semibold tabular-nums">{pending}</dd></div>
              </dl>
              {quote == null && <p className="mt-2 text-sm text-muted-foreground">Die Konten sind noch zu neu oder die Gruppe ist leer. Daraus lässt sich noch keine Rückkehrquote berechnen.</p>}
            </div>
            <div className="mt-5 rounded-xl bg-muted/60 p-4 text-sm leading-relaxed text-muted-foreground">
              <strong className="text-foreground">So liest du die Zahl:</strong> „7 Tage“ zählt eine Rückkehr irgendwann in den ersten sieben Tagen. Es bedeutet nicht, dass das Konto am siebten Tag noch aktiv war. Jüngere Konten warten auf die Auswertung.
            </div>
            {!cohort && <p className="mt-4 text-sm text-muted-foreground">Vergleich: {data.weeks} Kalenderwochen davor, {data.basis.vorher_n} Konten. Unter drei Konten wird keine Veränderung angezeigt.</p>}
            <a href="#users" className="mt-auto inline-flex min-h-11 items-center gap-1 pt-4 text-sm font-medium text-primary">Einzelne Konten ansehen <ArrowUpRight className="h-4 w-4" aria-hidden /></a>
          </Card>
        </div>
      </div>
      <details className="group rounded-xl border border-border bg-card p-4">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 font-medium">
          Alle Anmeldewochen vergleichen <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <p className="my-3 text-sm text-muted-foreground">Erreicht / auswertbar. „Noch offen“ bedeutet: kein Konto ist für dieses Zeitfenster alt genug. Alle Schritte bleiben einzeln ablesbar.</p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm tabular-nums">
            <caption className="sr-only">Alle Kennzahlen nach Registrierungswoche</caption>
            <thead><tr className="border-b border-border"><th className="min-w-32 p-3 font-medium">Woche ab</th><th className="p-3 font-medium">Neu</th>{colkeys.map((key) => <th key={key} className="min-w-28 p-3 font-medium">{LABELS[key]}</th>)}</tr></thead>
            <tbody>{[...data.cohorts].reverse().map((c) => <tr key={c.week} className="border-b border-border last:border-0"><th className="p-3 font-normal">{formatDate(c.week)}</th><td className="p-3 font-semibold">{c.n}</td>{colkeys.map((key) => {
              const s = c.stages.find((s) => s.key === key);
              return <td key={key} className="p-3">{s?.eligible ? <><span className="font-semibold">{s.n}</span><span className="text-muted-foreground"> / {s.eligible}</span></> : <span className="text-muted-foreground">Noch offen</span>}</td>;
            })}</tr>)}</tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
