"use client";

import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { Button, Card, ChartSkeleton, ErrorState } from "@/components/ui";
import { deZahl } from "@/components/grafik/format";
import { cn } from "@/lib/utils";
import { Veraenderung } from "./primitives";
import { jobAuffaellig, WeeklyActivity, type AdminGrowth, type AdminAnmeldungen, type AdminEreignisse, type AdminKohorten, type AdminJob } from "./statistics";

function Metric({ label, value, note, href, pending, error, children }: {
  label: string; value: string; note: string; href: string; pending: boolean; error: boolean; children?: React.ReactNode;
}) {
  return <a href={href} className="group min-w-0 rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40 hover:bg-primary/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
    <div className="flex items-start justify-between gap-2"><h3 className="text-sm font-medium text-muted-foreground">{label}</h3><ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden /></div>
    <div className="mt-4 flex min-h-10 flex-wrap items-baseline gap-2">
      <strong className="font-display text-4xl leading-none tracking-tight tabular-nums">{pending || error ? "–" : value}</strong>
      {!pending && !error && children}
    </div>
    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{pending ? "Wird geladen…" : error ? "Nicht geladen. Details öffnen oder oben aktualisieren." : note}</p>
  </a>;
}

function StatusLink({ title, text, href, value, alert, pending, error }: {
  title: string; text: string; href: string; value: number | undefined; alert?: boolean; pending: boolean; error: boolean;
}) {
  return <a href={href} className="group flex min-h-20 items-center gap-3 border-b border-border py-4 last:border-0 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
    <span className={cn("flex h-10 min-w-10 shrink-0 items-center justify-center rounded-xl px-2 font-display text-xl font-bold tabular-nums", alert ? "bg-amber-500/10 text-amber-800 dark:text-amber-300" : "bg-muted text-muted-foreground")}>{pending || error ? "–" : deZahl(value)}</span>
    <span className="min-w-0 flex-1"><span className="block text-sm font-semibold">{title}</span><span className="mt-1 block text-sm leading-snug text-muted-foreground">{pending ? "Wird geladen…" : error ? "Status nicht verfügbar. Details öffnen zum Wiederholen." : text}</span></span>
    <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1" aria-hidden />
  </a>;
}

export function AdminOverview() {
  const qc = useQueryClient();
  const fetching = useIsFetching({ predicate: (q) => typeof q.queryKey[0] === "string" && q.queryKey[0].startsWith("admin") });
  const growth = useQuery({ queryKey: ["admin", "growth", "90d"], queryFn: () => api.get<AdminGrowth>("/admin/stats/growth?range=90d") });
  const signups = useQuery({ queryKey: ["admin", "signups"], queryFn: () => api.get<AdminAnmeldungen>("/admin/stats/signups?days=30") });
  const cohorts = useQuery({ queryKey: ["admin", "cohorts"], queryFn: () => api.get<AdminKohorten>("/admin/stats/cohorts?weeks=8") });
  const events = useQuery({ queryKey: ["admin", "events"], queryFn: () => api.get<AdminEreignisse>("/admin/stats/events?days=30") });
  const jobs = useQuery({ queryKey: ["admin", "jobs"], queryFn: () => api.get<AdminJob[]>("/admin/jobs") });
  const errors = useQuery({ queryKey: ["admin-fehler-offen"], queryFn: () => api.get<ApiAntwort<"/admin/errors/open-count">>("/admin/errors/open-count") });
  const feedback = useQuery({ queryKey: ["admin-feedback-unread"], queryFn: () => api.get<ApiAntwort<"/admin/feedback/unread-count">>("/admin/feedback/unread-count") });

  const mails = useQuery({ queryKey: ["admin", "emails", 30], queryFn: () => api.get<ApiAntwort<"/admin/stats/emails">>("/admin/stats/emails?tage=30") });

  const k = cohorts.data;
  const e = events.data;
  const questions = e?.events.find((v) => v.key === "ai_question");
  const empty = e?.events.find((v) => v.key === "ai_answer_empty");
  const active = growth.data?.wau.at(-1);
  const previous = growth.data?.wau.at(-2);
  const jobIssues = jobs.data?.filter(jobAuffaellig).length;
  const unknownJobs = jobs.data?.filter((j) => j.state === "unknown").length ?? 0;
  const features = e?.events.filter((v) => v.key !== "session" && v.key !== "ai_question_chip" && v.key !== "ai_answer_empty")
    .sort((a, b) => b.users - a.users || b.n - a.n).slice(0, 4) ?? [];
  const largest = Math.max(1, ...features.map((v) => v.users));

  return <div className="@container space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="font-mono text-xs tracking-wide text-muted-foreground">RATSLOTSE IM BLICK</p><h2 className="mt-1 font-display text-2xl font-bold tracking-tight">Was bewegt sich gerade?</h2></div>
      <Button variant="secondary" size="sm" disabled={fetching > 0} onClick={() => void qc.invalidateQueries({ predicate: (q) => typeof q.queryKey[0] === "string" && q.queryKey[0].startsWith("admin") })}>
        <RefreshCw className={cn("h-4 w-4", fetching > 0 && "animate-spin")} aria-hidden />{fetching > 0 ? "Lädt…" : "Aktualisieren"}
      </Button>
    </div>
    <div className="grid gap-3 @xl:grid-cols-2 @5xl:grid-cols-4">
      <Metric label="Aktive Konten · 7 Tage" value={deZahl(active)} note="Einmal je Konto gezählt; einschließlich Betreiber-/Testkonten." href="#aktivitaet" pending={growth.isPending} error={growth.isError}>
        <Veraenderung jetzt={active ?? null} vorher={previous} klein />
      </Metric>
      <Metric label="Neue Konten · 30 Tage" value={deZahl(signups.data?.created)} note={`${deZahl(signups.data?.verified)} mit bestätigter E-Mail-Adresse. Alle Konten eingeschlossen.`} href="#konten" pending={signups.isPending} error={signups.isError} />
      <Metric label="Binnen 7 Tagen zurück" value={k?.kennzahlen.tag7 == null ? "–" : `${Math.round(k.kennzahlen.tag7 * 100)} %`} note={k?.kennzahlen.tag7 == null ? "Noch keine auswertbaren Konten. Neue Konten brauchen erst sieben Tage Zeit." : `${k?.basis.tag7[0]} von ${k?.basis.tag7[1]} auswertbaren Neuanmeldungen aus 8 Kalenderwochen; ohne Betreiber-/Testkonten.`} href="#konten" pending={cohorts.isPending} error={cohorts.isError} />
      <Metric label="Antworten ohne Quelle · 30 Tage" value={e?.empty_share == null ? "–" : `${Math.round(e.empty_share * 100)} %`} note={e?.empty_share == null ? "Noch keine erfassten Fragen im Zeitraum." : `${deZahl(empty?.n)} bei ${deZahl(questions?.n)} erfassten Fragen. Die Fälle lassen sich genauer ansehen.`} href="#antworten" pending={events.isPending} error={events.isError} />
    </div>

    <div className="grid items-start gap-5 @4xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
      <div className="min-w-0 space-y-5">
        {growth.isPending ? <ChartSkeleton /> : growth.isError || !growth.data ? <ErrorState title="Die Aktivität konnte nicht geladen werden" onRetry={() => void growth.refetch()} busy={growth.isFetching} /> : <WeeklyActivity data={growth.data} />}
        <Card className="p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="font-display text-lg font-bold">Was wird genutzt?</h3><a href="#aktivitaet" className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-primary">Alle Funktionen <ArrowUpRight className="h-4 w-4" aria-hidden /></a></div>
          <p className="text-sm text-muted-foreground">Die vier meistgenutzten Funktionen nach Konten · 30 Tage</p>
          {events.isPending ? <p className="py-5 text-sm text-muted-foreground">Wird geladen…</p> : events.isError ? <p role="alert" className="py-5 text-sm text-muted-foreground">Funktionen konnten nicht geladen werden. Oben kannst du die Daten erneut laden.</p> : features.length === 0 ? <p className="py-5 text-sm text-muted-foreground">Noch keine Nutzung erfasst.</p> : <div className="mt-4 space-y-4">{features.map((f) => <div key={f.key}>
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm"><span>{f.label}</span><span className="tabular-nums"><strong>{deZahl(f.users)} Konten</strong><span className="text-muted-foreground"> · {deZahl(f.n)} Aktionen</span></span></div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden><div className="h-full rounded-full bg-primary/65" style={{ width: `${f.users / largest * 100}%` }} /></div>
          </div>)}</div>}
        </Card>
      </div>
      <div className="min-w-0 space-y-5">
        <Card className="px-5 pb-1 pt-5">
          <h3 className="font-display text-lg font-bold">Was braucht einen Blick?</h3>
          <p className="mt-1 text-sm text-muted-foreground">Offene Meldungen und Hintergrundaufgaben</p>
          <StatusLink title="Offene Fehlerarten" text={errors.data?.total ? "Fehler aus Browser und Backend prüfen." : "Keine offenen Fehler gemeldet."} href="#fehler" value={errors.data?.total} alert={!!errors.data?.total} pending={errors.isPending} error={errors.isError} />
          <StatusLink title="Cron-Jobs mit Auffälligkeiten" text={`${jobIssues ? "Fehlgeschlagen, überfällig oder mit Warnungen." : "Kein erfasster Lauf auffällig."}${unknownJobs ? ` ${unknownJobs} Jobs noch ohne erfassten Lauf.` : ""}`} href="#jobs" value={jobIssues} alert={!!jobIssues} pending={jobs.isPending} error={jobs.isError} />
          <StatusLink title="Fehlgeschlagene Mails" text="Versandversuche mit Fehler in den letzten 30 Tagen." href="#emails" value={mails.data?.gescheitert} alert={!!mails.data?.gescheitert} pending={mails.isPending} error={mails.isError} />
          <StatusLink title="Offenes Feedback" text={feedback.data?.total ? "Rückmeldungen lesen und bearbeiten." : "Alle Rückmeldungen bearbeitet."} href="#feedback" value={feedback.data?.total} alert={!!feedback.data?.total} pending={feedback.isPending} error={feedback.isError} />
        </Card>
        <Card className="p-5">
          <h3 className="font-display text-lg font-bold">Wie intensiv wird gefragt?</h3>
          {cohorts.isPending ? <p className="mt-4 text-sm text-muted-foreground">Wird geladen…</p> : cohorts.isError ? <p role="alert" className="mt-4 text-sm text-muted-foreground">Noch nicht geladen. Bitte oben aktualisieren.</p> : <>
            <div className="mt-4 flex flex-wrap items-baseline gap-3"><strong className="font-display text-4xl tabular-nums">{deZahl(k?.kennzahlen.fragen_median, 1)}</strong><Veraenderung jetzt={k?.kennzahlen.fragen_median ?? null} vorher={k?.previous.fragen_median} neutral /></div>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">Fragen je aktivem Konto in 7 Tagen (Median), einschließlich Betreiber-/Testkonten. Die Hälfte der aktiven Konten liegt höchstens bei diesem Wert.</p>
          </>}
        </Card>
        <a href="#reichweite" className="group flex items-center justify-between gap-3 rounded-xl bg-primary/[0.06] p-5 text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><span><strong className="block font-display text-lg">Was zieht Menschen an?</strong><span className="mt-1 block text-sm">Seitenaufrufe und meistgesehene Inhalte</span></span><ArrowUpRight className="h-5 w-5 shrink-0 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden /></a>
      </div>
    </div>
    <p className="text-sm leading-relaxed text-muted-foreground">Die Zeiträume stehen an jeder Zahl. Rückkehrquoten betrachten neue Konten; Aktivität zählt auch bestehende Konten. Veränderungen beziehen sich jeweils auf den vorherigen Zeitraum.</p>
  </div>;
}
