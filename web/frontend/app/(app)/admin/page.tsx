"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Prompt, AdminUserRow, AdminUserDetail, AdminGrowth, AdminJob, QuizFlagged, AdminQuizStats, EntityAlias } from "@/lib/types";
import { Badge, Button, Card, ConfirmDialog, PageHeader, Spinner, Textarea, formatDate, toast } from "@/components/ui";
import { AreaSparkline, MiniBars, StatKicker } from "@/components/admin-charts";
import { cn } from "@/lib/utils";

type Tab = "stats" | "llm" | "prompts" | "users" | "quiz" | "themen";

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("stats");

  if (loading) return <Spinner />;
  if (!user || user.role !== "admin") {
    if (!loading) router.replace("/dashboard");
    return <Spinner />;
  }

  return (
    <div>
      <PageHeader title="Admin" description="Prompts und Web-Nutzer:innen verwalten." />
      <div className="mt-4 flex gap-1 border-b border-border">
        {([
          ["stats", "Statistik"],
          ["llm", "LLM-Kosten"],
          ["prompts", "Prompts"],
          ["users", "Web-Nutzer:innen"],
          ["quiz", "Quiz"],
          ["themen", "Themen-Dubletten"],
        ] as [Tab, string][]).map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium ${
              tab === t ? "border-b-2 border-primary text-primary" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="mt-6">
        {tab === "stats" && <StatsTab />}
        {tab === "llm" && <LlmUsageTab />}
        {tab === "prompts" && <PromptsTab />}
        {tab === "users" && <UsersTab currentUserId={user.id} />}
        {tab === "quiz" && <QuizModerationTab />}
        {tab === "themen" && <EntityAliasTab />}
      </div>
    </div>
  );
}

const GROWTH_RANGES: [string, string][] = [["30d", "30 T"], ["90d", "90 T"], ["12m", "12 M"], ["all", "Alles"]];

function TrendChip({ delta }: { delta: number }) {
  if (delta <= 0) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-500/[0.12] px-2 py-0.5 text-[11px] font-semibold text-green-700 dark:text-green-400">
      <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7" /><path d="M7 7h10v10" /></svg>
      +{delta}
    </span>
  );
}

function GrowthCard({ kicker, total, delta, series, days, color }: { kicker: string; total: number; delta: number; series: number[]; days: string[]; color: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <StatKicker>{kicker}</StatKicker>
          <p className="mt-1.5 font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">{total.toLocaleString("de-DE")}</p>
        </div>
        <TrendChip delta={delta} />
      </div>
      <AreaSparkline values={series.length ? series : [0, 0]} days={days} color={color} height={64} className="mt-3" />
    </Card>
  );
}

/** Scraper-Ampel: Läufe um 8 und 14 Uhr, also sind bis zu ~18 h Abstand normal.
 *  Grün bis 26 h, danach ist mindestens ein Lauf ausgefallen. */
function fetchTone(hours: number | null): string {
  if (hours == null) return "bg-muted-foreground/40";
  if (hours < 26) return "bg-green-500";
  return hours < 72 ? "bg-amber-500" : "bg-red-500";
}

function fetchAge(hours: number): string {
  if (hours < 1) return "wenigen Minuten";
  if (hours < 48) return `${Math.round(hours)} h`;
  return `${Math.round(hours / 24)} Tagen`;
}

function StatsTab() {
  const [range, setRange] = useState("90d");
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "growth", range],
    queryFn: () => api.get<AdminGrowth>(`/admin/stats/growth?range=${range}`),
  });

  if (isPending) return <Spinner />;
  if (isError || !data) return <p className="text-sm text-destructive">Fehler beim Laden der Statistiken.</p>;

  const c = data.council;
  return (
    <div className="space-y-4">
      {/* Kopf: „Wachstum“ + Zeitraum-Umschalter (20a). */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-[15px] font-bold text-foreground">Wachstum</h3>
        <div role="group" className="inline-flex gap-0.5 rounded-[10px] bg-muted p-0.5">
          {GROWTH_RANGES.map(([v, label]) => (
            <button
              key={v}
              onClick={() => setRange(v)}
              className={cn(
                "rounded-lg px-3 py-1 text-[12.5px] transition-colors",
                range === v ? "bg-card font-semibold text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Zwei Verlaufs-Karten. */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <GrowthCard kicker="Registrierte Nutzer:innen" total={data.users.total} delta={data.users.delta} series={data.users.series} days={data.users.days} color="hsl(var(--primary))" />
        <GrowthCard kicker="Angelegte Themen" total={data.topics.total} delta={data.topics.delta} series={data.topics.series} days={data.topics.days} color="hsl(var(--signal))" />
      </div>

      {/* WAU + Ratsinfo-Import. */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.4fr_1fr]">
        <Card className="p-4">
          <div className="flex items-baseline justify-between">
            <StatKicker>Aktive Nutzer:innen je Woche</StatKicker>
            <span className="text-[11.5px] text-muted-foreground">WAU · 8 Wochen</span>
          </div>
          <MiniBars values={data.wau.length ? data.wau : [0]} days={data.wau_days} height={70} className="mt-3.5" />
        </Card>
        <Card className="p-4">
          <StatKicker>Ratsinfo-Import</StatKicker>
          <div className="mt-3 flex flex-col gap-2.5">
            {[["Sitzungen", c.sessions], ["Tagesordnungspunkte", c.agenda_items], ["Beschlüsse mit KI-Feldern", c.decisions_with_ki]].map(([label, val]) => (
              <div key={label as string} className="flex items-baseline justify-between">
                <span className="text-[13px] text-foreground">{label}</span>
                <span className="font-display text-base font-bold tabular-nums text-foreground">{(val as number).toLocaleString("de-DE")}</span>
              </div>
            ))}
            <div className="mt-1 space-y-1.5 border-t border-border pt-2.5">
              <div className="flex items-center gap-2">
                <span className={cn("h-2 w-2 shrink-0 rounded-full", fetchTone(c.hours_since_fetch))} />
                <span className="text-xs text-muted-foreground">
                  {c.last_fetch ? `Letzter Scraper-Lauf: ${formatDate(c.last_fetch.slice(0, 10))}` : "Noch kein Lauf"}
                  {c.hours_since_fetch != null && ` · vor ${fetchAge(c.hours_since_fetch)}`}
                </span>
              </div>
              {/* Getrennt ausweisen: in der sitzungsfreien Zeit stockt die
                  Tagesordnung, während der Scraper weiterläuft. */}
              <p className="pl-4 text-xs text-muted-foreground">
                {c.last_session_import
                  ? `Neueste Tagesordnung: ${formatDate(c.last_session_import.slice(0, 10))}`
                  : "Noch keine Tagesordnung"}
                {c.next_session && ` · nächste Sitzung ${formatDate(c.next_session)}`}
              </p>
            </div>
          </div>
        </Card>
      </div>

      <JobsSection />
    </div>
  );
}

const JOB_STATE: Record<AdminJob["state"], { dot: string; label: string }> = {
  ok: { dot: "bg-green-500", label: "läuft" },
  stale: { dot: "bg-amber-500", label: "überfällig" },
  error: { dot: "bg-red-500", label: "fehlgeschlagen" },
  unknown: { dot: "bg-muted-foreground/40", label: "noch kein Lauf erfasst" },
};

/** Cron-Übersicht: was läuft wann, wie lange, und was kam dabei heraus. */
function JobsSection() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "jobs"],
    queryFn: () => api.get<AdminJob[]>("/admin/jobs"),
  });

  if (isPending || isError || !data) return null;

  return (
    <div className="space-y-3 pt-2">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="font-display text-[15px] font-bold text-foreground">Cron-Jobs</h3>
        <span className="text-[11.5px] text-muted-foreground">Erfassung ab dem jeweils nächsten Lauf</span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {data.map((job) => {
          const tone = JOB_STATE[job.state];
          const stats = job.last?.stats ?? null;
          return (
            <Card key={job.key} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={cn("h-2 w-2 shrink-0 rounded-full", tone.dot)} />
                    <p className="truncate text-[13.5px] font-semibold text-foreground">{job.label}</p>
                  </div>
                  <p className="mt-1 pl-4 text-xs text-muted-foreground">{job.schedule}</p>
                </div>
                <span className="shrink-0 whitespace-nowrap text-[11.5px] text-muted-foreground">
                  {job.age_h != null ? `vor ${fetchAge(job.age_h)}` : tone.label}
                  {job.last?.duration_s != null && ` · ${formatDuration(job.last.duration_s)}`}
                </span>
              </div>

              {job.state === "error" && job.last?.error && (
                <p className="mt-2.5 rounded-lg bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
                  {job.last.error}
                </p>
              )}

              {stats && Object.keys(stats).length > 0 ? (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {Object.entries(stats).map(([label, value]) => (
                    <span key={label} className="inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-[11.5px] text-muted-foreground">
                      {label}
                      <strong className="font-semibold tabular-nums text-foreground">
                        {typeof value === "number" ? value.toLocaleString("de-DE") : value}
                      </strong>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-2.5 text-xs text-muted-foreground">{job.description}</p>
              )}

              {job.history.length > 1 && (
                <div className="mt-3 flex items-end gap-1" aria-hidden>
                  {job.history.map((h, i) => (
                    <span
                      key={i}
                      title={`${formatDate(h.started_at.slice(0, 10))} · ${h.status}`}
                      className={cn("h-1.5 flex-1 rounded-full", h.status === "ok" ? "bg-primary/45" : "bg-destructive/60")}
                    />
                  ))}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

type LlmFeature = {
  feature: string; calls: number; prompt_tokens: number; completion_tokens: number;
  cost: number; models: string[]; first: string; last: string;
};
type LlmUsage = {
  features: LlmFeature[]; total_cost: number; total_calls: number;
  // Design 21a: Verlauf, Monat + Hochrechnung, Budget-Ampel.
  series: { date: string; cost: number; calls: number }[];
  cost_month: number; projected_month: number;
  calls_30d: number; avg_cost_per_call: number;
  budget_monthly: number; budget_pct: number; budget_level: "ok" | "warn" | "over";
};

const FEATURE_LABELS: Record<string, string> = {
  protokoll_extraktion: "Protokoll-Extraktion",
  themen_klassifikation: "Themenfeld-Klassifikation",
  ziel_bewertung: "Ziel-Bewertung",
  entitaeten_ner: "Entitäten-Erkennung",
  entitaeten_beschreibung: "Themen-Beschreibungen",
  qa_query_expansion: "Frag den Rat — Suchbegriffe",
  qa_antwort: "Frag den Rat — Antwort",
};

const BUDGET_TONE: Record<LlmUsage["budget_level"], { dot: string; text: string; bar: string; ring: string }> = {
  ok:   { dot: "bg-green-500",  text: "text-green-700 dark:text-green-400",   bar: "bg-green-500",  ring: "border-green-500/30 bg-green-500/5" },
  warn: { dot: "bg-amber-500",  text: "text-amber-700 dark:text-amber-400",   bar: "bg-amber-500",  ring: "border-amber-500/35 bg-gradient-to-br from-amber-500/[0.08] to-transparent" },
  over: { dot: "bg-destructive", text: "text-destructive",                    bar: "bg-destructive", ring: "border-destructive/40 bg-destructive/5" },
};

/** Kennzahl-Karte im 20a/21a-Stil: Kicker + große Bricolage-Zahl + Unterzeile. */
function KpiCard({ kicker, value, sub }: { kicker: string; value: string; sub?: React.ReactNode }) {
  return (
    <Card className="p-4">
      <StatKicker>{kicker}</StatKicker>
      <p className="mt-1.5 font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </Card>
  );
}

function LlmUsageTab() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "llm-usage"],
    queryFn: () => api.get<LlmUsage>("/admin/llm-usage"),
  });

  if (isPending) return <Spinner />;
  if (isError || !data) return <p className="text-sm text-destructive">Fehler beim Laden der LLM-Nutzung.</p>;
  if (data.features.length === 0) {
    return <p className="text-sm text-muted-foreground">Noch keine LLM-Nutzung erfasst — die Erfassung beginnt mit dem nächsten Lauf (Klassifikation, Entitäten, Frag den Rat …).</p>;
  }

  const tone = BUDGET_TONE[data.budget_level];
  const maxFeatureCost = Math.max(...data.features.map((f) => f.cost), 0.0001);

  return (
    <div className="space-y-5">
      {/* Drei KPI-Karten: Monat + Hochrechnung · Aufrufe · Budget-Ampel (21a). */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard
          kicker="Kosten diesen Monat"
          value={`$${data.cost_month.toFixed(2)}`}
          sub={<>Hochrechnung Monat: <strong className="font-semibold text-foreground">${data.projected_month.toFixed(2)}</strong></>}
        />
        <KpiCard
          kicker="Aufrufe (30 T)"
          value={data.calls_30d.toLocaleString("de-DE")}
          sub={`⌀ $${data.avg_cost_per_call.toFixed(3)} je Aufruf`}
        />
        <Card className={cn("border p-4", tone.ring)}>
          <div className="flex items-center justify-between gap-2">
            <StatKicker>Budget ${data.budget_monthly.toFixed(0)}/Mon</StatKicker>
            <span className={cn("inline-flex items-center gap-1.5 text-xs font-semibold", tone.text)}>
              <span className={cn("h-2 w-2 rounded-full", tone.dot)} /> {data.budget_pct} %
            </span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
            <span className={cn("block h-full rounded-full", tone.bar)} style={{ width: `${Math.min(100, data.budget_pct)}%` }} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Warnung ab 80 %{data.budget_level === "over" && " · Budget überschritten"}</p>
        </Card>
      </div>

      {/* Verlauf + Kostentreiber (21a). */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.5fr_1fr]">
        <Card className="p-4">
          <StatKicker>Täglicher Kostenverlauf (30 T)</StatKicker>
          <AreaSparkline values={data.series.map((d) => d.cost)} days={data.series.map((d) => d.date)} axisTicks={6} color="hsl(var(--primary))" height={110} className="mt-3" />
          <p className="mt-1.5 text-[11px] text-muted-foreground/80">Spitzen = wöchentlicher Enrichment-Lauf (Klassifikation, Interest, Fundstück).</p>
        </Card>
        <Card className="p-4">
          <StatKicker>Kostentreiber — Feature</StatKicker>
          <div className="mt-3 flex flex-col gap-2.5">
            {data.features.slice(0, 5).map((f) => (
              <div key={f.feature}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="truncate text-foreground">{FEATURE_LABELS[f.feature] ?? f.feature}</span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">${f.cost.toFixed(2)}</span>
                </div>
                <div className="mt-1 h-[7px] overflow-hidden rounded-full bg-muted">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(3, (f.cost / maxFeatureCost) * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Feature</th>
              <th className="px-4 py-2.5 text-right font-medium">Aufrufe</th>
              <th className="px-4 py-2.5 text-right font-medium">Input-Tokens</th>
              <th className="px-4 py-2.5 text-right font-medium">Output-Tokens</th>
              <th className="px-4 py-2.5 text-right font-medium">Kosten (gesch.)</th>
            </tr>
          </thead>
          <tbody>
            {data.features.map((f) => (
              <tr key={f.feature} className="border-b border-border last:border-0">
                <td className="px-4 py-2.5">
                  <span className="font-medium text-foreground">{FEATURE_LABELS[f.feature] ?? f.feature}</span>
                  {f.models.length > 0 && <span className="ml-2 text-xs text-muted-foreground">{f.models.join(", ")}</span>}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">{f.calls.toLocaleString("de-DE")}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">{f.prompt_tokens.toLocaleString("de-DE")}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">{f.completion_tokens.toLocaleString("de-DE")}</td>
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-foreground">${f.cost.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-xs leading-relaxed text-muted-foreground/70">
        Kosten geschätzt aus den erfassten Token-Zahlen × hinterlegten Modellpreisen. Die Erfassung läuft ab
        Einführung dieser Seite (frühere Läufe sind nicht enthalten). Streaming-Antworten liefern je nach Anbieter
        nicht immer eine Token-Angabe.
      </p>
    </div>
  );
}

/** Prompt-key → Feature-Gruppe (Design 21a: nach Feature gruppiert). Reihenfolge
 *  = Anzeigereihenfolge; unbekannte Präfixe landen unter „Weitere“. */
const PROMPT_GROUPS: { label: string; match: (k: string) => boolean }[] = [
  { label: "Frag den Rat", match: (k) => k.startsWith("qa_") },
  { label: "Stadtrat", match: (k) => k.startsWith("council_") || k.startsWith("protokoll") || k.startsWith("committee_summary") || k.startsWith("ziel") },
  { label: "Anreicherung", match: (k) => k.startsWith("interest") || k.startsWith("impact") || k.startsWith("entitaeten") || k.startsWith("recap") || k.startsWith("simple_summary") },
  { label: "Quiz", match: (k) => k.startsWith("quiz") },
  { label: "Themen", match: (k) => k.startsWith("vagueness") || k.startsWith("topic") },
];
function promptGroup(key: string): string {
  return PROMPT_GROUPS.find((g) => g.match(key))?.label ?? "Weitere";
}

/** Einfacher Zeilen-Diff content↔default (Design 21a Diff-Vorschau): gleiche
 *  Zeilen als Kontext, Rest als −/+ (grobe, aber ausreichende Vorschau). */
function lineDiff(oldText: string, newText: string): { type: "ctx" | "del" | "add"; text: string }[] {
  const a = oldText.split("\n");
  const b = newText.split("\n");
  const bSet = new Set(b);
  const aSet = new Set(a);
  const out: { type: "ctx" | "del" | "add"; text: string }[] = [];
  for (const line of a) if (!bSet.has(line)) out.push({ type: "del", text: line });
  for (const line of b) out.push({ type: aSet.has(line) ? "ctx" : "add", text: line });
  return out;
}

function PromptsTab() {
  const [q, setQ] = useState("");
  const { data: prompts = [], isPending, isError } = useQuery({
    queryKey: ["admin", "prompts"],
    queryFn: () => api.get<Prompt[]>("/admin/prompts"),
  });

  if (isPending) return <Spinner />;
  if (isError) return <p className="text-sm text-destructive">Fehler beim Laden der Prompts.</p>;

  const needle = q.trim().toLowerCase();
  const filtered = needle
    ? prompts.filter((p) => (p.title + p.key + p.description).toLowerCase().includes(needle))
    : prompts;
  const groups = PROMPT_GROUPS.map((g) => g.label).concat("Weitere");

  return (
    <div className="space-y-5">
      <div className="relative max-w-md">
        <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Prompt suchen…"
          className="h-9 w-full rounded-[10px] border border-input bg-card pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>
      {groups.map((label) => {
        const items = filtered.filter((p) => promptGroup(p.key) === label);
        if (!items.length) return null;
        return (
          <div key={label} className="space-y-3">
            <StatKicker>{label}</StatKicker>
            {items.map((p) => <PromptEditor key={p.key} prompt={p} />)}
          </div>
        );
      })}
      {filtered.length === 0 && <p className="text-sm text-muted-foreground">Kein Prompt passt zu „{q}".</p>}
    </div>
  );
}

function metaLine(prompt: Prompt): string | null {
  if (!prompt.is_overridden) return null;
  const who = prompt.updated_by ? `von ${prompt.updated_by.split("@")[0]}@` : null;
  let when: string | null = null;
  if (prompt.updated_at) {
    const days = Math.round((Date.now() - new Date(prompt.updated_at + "Z").getTime()) / 86400000);
    when = days <= 0 ? "heute" : days === 1 ? "gestern" : `vor ${days} Tagen`;
  }
  return ["geändert", who, when].filter(Boolean).join(" · ");
}

function PromptEditor({ prompt }: { prompt: Prompt }) {
  const qc = useQueryClient();
  const [content, setContent] = useState(prompt.content);
  const [showDiff, setShowDiff] = useState(false);
  const dirty = content !== prompt.content;
  const diff = lineDiff(prompt.default, content);
  const changed = content !== prompt.default;

  const saveMutation = useMutation({
    mutationFn: (c: string) => api.put(`/admin/prompts/${prompt.key}`, { content: c }),
    onSuccess: () => {
      toast.success("Gespeichert.");
      qc.invalidateQueries({ queryKey: ["admin", "prompts"] });
    },
    onError: (err: Error) => toast.error(err.message || "Fehler beim Speichern."),
  });

  const resetMutation = useMutation({
    mutationFn: () => api.post(`/admin/prompts/${prompt.key}/reset`),
    onSuccess: () => {
      setContent(prompt.default);
      qc.invalidateQueries({ queryKey: ["admin", "prompts"] });
    },
    onError: () => toast.error("Zurücksetzen fehlgeschlagen."),
  });

  const busy = saveMutation.isPending || resetMutation.isPending;

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-foreground">{prompt.title}</h3>
            {prompt.is_overridden ? <Badge color="amber">angepasst</Badge> : <Badge color="green">Standard</Badge>}
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">{prompt.description}</p>
          {metaLine(prompt) && <p className="mt-0.5 text-xs text-muted-foreground/80">{metaLine(prompt)}</p>}
        </div>
        <code className="text-xs text-muted-foreground">{prompt.key}</code>
      </div>
      {/* Prompt-Templates sind „Code" — hier ist Mono gewollt (Platzhalter, Einrückung). */}
      <Textarea className="mt-3 font-mono" rows={Math.min(16, content.split("\n").length + 1)} value={content} onChange={(e) => setContent(e.target.value)} />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => saveMutation.mutate(content)} disabled={busy || !dirty}>
          {saveMutation.isPending ? "Speichern…" : "Speichern"}
        </Button>
        {changed && (
          <Button variant="secondary" size="sm" onClick={() => setShowDiff((s) => !s)}>
            {showDiff ? "Diff ausblenden" : "Diff zu Standard"}
          </Button>
        )}
        {prompt.is_overridden && (
          <Button variant="secondary" size="sm" onClick={() => resetMutation.mutate()} disabled={busy}>
            Auf Standard zurücksetzen
          </Button>
        )}
        {dirty && <span className="text-xs text-amber-600">Ungespeicherte Änderungen</span>}
      </div>
      {showDiff && changed && (
        <div className="mt-3 overflow-hidden rounded-xl border border-border">
          <p className="border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground">Diff-Vorschau · {prompt.key}</p>
          <div className="max-h-72 overflow-auto font-mono text-[11px] leading-relaxed">
            {diff.map((d, i) => (
              <div
                key={i}
                className={cn(
                  "whitespace-pre-wrap px-3 py-0.5",
                  d.type === "del" && "bg-destructive/10 text-destructive",
                  d.type === "add" && "bg-green-500/10 text-green-700 dark:text-green-400",
                  d.type === "ctx" && "text-muted-foreground",
                )}
              >
                {d.type === "del" ? "− " : d.type === "add" ? "+ " : "  "}{d.text || " "}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

/** Aktivitäts-Ampel aus dem letzten Aktivitätstag (Design 20a). */
function activitySignal(lastSeen: string | null): { dot: string; label: string } {
  if (!lastSeen) return { dot: "bg-muted-foreground/40", label: "nie aktiv" };
  const days = Math.round((Date.now() - new Date(lastSeen + "T12:00:00").getTime()) / 86400000);
  if (days <= 0) return { dot: "bg-green-500", label: "heute aktiv" };
  if (days < 7) return { dot: "bg-amber-500", label: `vor ${days} ${days === 1 ? "Tag" : "Tagen"}` };
  const w = Math.round(days / 7);
  return { dot: "bg-muted-foreground/50", label: w <= 1 ? "vor 1 Woche" : `vor ${w} Wochen` };
}

const USER_FEATURE_LABEL: [keyof AdminUserDetail["features"], string][] = [
  ["ki_frage", "KI-Frage"], ["suche", "Beschluss-Suche"], ["quiz", "Quiz"], ["analyse", "Analyse"], ["karte", "Stadtkarte"],
];

function UsersTab({ currentUserId }: { currentUserId: number }) {
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const { data: users = [], isPending, isError } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api.get<AdminUserRow[]>("/admin/users"),
  });

  if (isPending) return <Spinner />;
  if (isError) return <p className="text-sm text-destructive">Fehler beim Laden der Nutzer:innen.</p>;

  const needle = q.trim().toLowerCase();
  const filtered = needle ? users.filter((u) => u.email.toLowerCase().includes(needle)) : users;

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[1fr_minmax(0,420px)]">
      <Card className="overflow-hidden p-0">
        <div className="flex items-center gap-3 border-b border-border bg-muted/30 px-4 py-3">
          <div className="relative flex-1">
            <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="E-Mail suchen…"
              className="h-9 w-full rounded-[9px] border border-input bg-card pl-9 pr-3 text-[12.5px] text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </div>
          <span className="shrink-0 text-xs text-muted-foreground">{users.length} Nutzer:innen</span>
        </div>
        <div className="divide-y divide-border">
          {filtered.map((u) => {
            const sig = activitySignal(u.last_seen);
            const chips = [
              u.n_topics > 0 && `${u.n_topics} Themen`,
              u.n_ki > 0 && `${u.n_ki} KI-Fragen`,
              u.n_abos > 0 && `${u.n_abos} Abos`,
              u.n_quiz > 0 && "Quiz",
            ].filter(Boolean) as string[];
            return (
              <button key={u.id} onClick={() => setSelected(u.id)}
                className={cn("grid w-full grid-cols-[1fr_auto_auto] items-center gap-2.5 px-4 py-2.5 text-left transition-colors hover:bg-accent",
                  selected === u.id && "bg-accent")}>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-[13.5px] font-semibold text-foreground">{u.email}</span>
                    {u.role === "admin" && <span className="shrink-0 rounded bg-primary/10 px-1.5 text-[10px] font-semibold text-primary">admin</span>}
                    {u.status !== "active" && <span className="shrink-0 rounded bg-amber-500/15 px-1.5 text-[10px] font-semibold text-amber-700 dark:text-amber-500">wartet</span>}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {chips.length ? chips.map((c) => (
                      <span key={c} className="rounded bg-muted px-1.5 py-px text-[10px] text-muted-foreground">{c}</span>
                    )) : <span className="rounded bg-muted px-1.5 py-px text-[10px] text-muted-foreground">noch nichts angelegt</span>}
                  </div>
                </div>
                <span className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground"><span className={cn("h-[7px] w-[7px] rounded-full", sig.dot)} />{sig.label}</span>
                <svg className="h-4 w-4 text-muted-foreground/50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
              </button>
            );
          })}
          {!filtered.length && <p className="px-4 py-6 text-center text-sm text-muted-foreground">Keine Nutzer:in passt zu „{q}".</p>}
        </div>
      </Card>

      {selected != null
        ? <UserDetailPanel userId={selected} isSelf={selected === currentUserId} onClose={() => setSelected(null)} />
        : <Card className="hidden p-8 text-center text-sm text-muted-foreground lg:block">Nutzer:in wählen, um Details zu sehen.</Card>}
    </div>
  );
}

function UserDetailPanel({ userId, isSelf, onClose }: { userId: number; isSelf: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: () => api.get<AdminUserDetail>(`/admin/users/${userId}`),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "user", userId] });
    qc.invalidateQueries({ queryKey: ["admin", "users"] });
  };
  const roleMutation = useMutation({
    mutationFn: (role: "user" | "admin") => api.put(`/admin/users/${userId}/role`, { role }),
    onSuccess: () => { toast.success("Rolle aktualisiert."); invalidate(); },
    onError: () => toast.error("Rolle konnte nicht geändert werden."),
  });
  const statusMutation = useMutation({
    mutationFn: (status: "active" | "pending") => api.put(`/admin/users/${userId}/status`, { status }),
    onSuccess: (_, status) => { toast.success(status === "active" ? "Freigeschaltet." : "Gesperrt."); invalidate(); },
    onError: () => toast.error("Status konnte nicht geändert werden."),
  });

  if (isPending || !data) return <Card className="p-6"><Spinner /></Card>;

  const sig = activitySignal(data.last_seen);
  const login = data.apple_linked ? "Apple-Login" : data.has_password ? "Passwort" : "Apple-Login";
  return (
    <Card className="bg-muted/20 p-5">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary/10 font-display text-base font-bold text-primary">{data.email[0].toUpperCase()}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-bold text-foreground">{data.email}</p>
          <p className="text-xs text-muted-foreground">seit {formatDate(data.created_at.slice(0, 10))} · {sig.label} · {login}</p>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground lg:hidden" aria-label="Schließen">
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
        </button>
      </div>

      <StatKickerSpaced>Genutzte Features</StatKickerSpaced>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {USER_FEATURE_LABEL.map(([key, label]) => {
          const n = data.features[key];
          const suffix = key === "quiz" ? (n === 1 ? "1 Runde" : `${n} Runden`) : `${n}×`;
          return n > 0
            ? <span key={key} className="rounded-full bg-primary/[0.08] px-2.5 py-1 text-xs font-medium text-primary">{label} · {suffix}</span>
            : <span key={key} className="rounded-full border border-dashed border-border px-2.5 py-1 text-xs text-muted-foreground">{label} · nie</span>;
        })}
      </div>

      <StatKickerSpaced>Angelegt</StatKickerSpaced>
      <div className="mt-2 flex flex-col gap-1.5">
        <DetailRow label={`${data.topics.length} ${data.topics.length === 1 ? "Thema" : "Themen"}`} value={data.topics.slice(0, 4).join(", ") || "—"} />
        <DetailRow label={`${data.abos.length} Ausschuss-${data.abos.length === 1 ? "Abo" : "Abos"}`} value={data.abos.slice(0, 4).join(", ") || "—"} />
        <DetailRow label="Zustellung" value={data.delivery_channel === "both" ? "Push + E-Mail" : data.delivery_channel === "push" ? "Push" : "E-Mail"} />
      </div>

      <StatKickerSpaced>Aktivität (30 Tage)</StatKickerSpaced>
      <MiniBars values={data.verlauf} days={data.verlauf_days} height={38} highlightLast={false} className="mt-2" />

      {!isSelf && (
        <div className="mt-4 flex gap-2 border-t border-border pt-4">
          <Button variant="secondary" size="sm"
            onClick={() => statusMutation.mutate(data.status === "active" ? "pending" : "active")}>
            {data.status === "active" ? "Sperren" : "Freischalten"}
          </Button>
          <Button variant="secondary" size="sm"
            onClick={() => roleMutation.mutate(data.role === "admin" ? "user" : "admin")}>
            {data.role === "admin" ? "Zu Nutzer:in" : "Zu Admin"}
          </Button>
        </div>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground/70">
        Alles server-aggregiert & nur für Admins; nur eigene App-Aktivität, keine Dritt-Analytics.
      </p>
    </Card>
  );
}

function StatKickerSpaced({ children }: { children: React.ReactNode }) {
  return <p className="mt-4 text-[11px] font-bold uppercase tracking-[0.06em] text-muted-foreground">{children}</p>;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2">
      <span className="shrink-0 text-[12.5px] text-foreground">{label}</span>
      <span className="truncate text-[11.5px] text-muted-foreground">{value}</span>
    </div>
  );
}

/** Schlecht bewertete Quizfragen (👎) sichten und ausmustern. Ausgemusterte
 *  Fragen fliegen aus künftigen Runden; der nächste Generierungslauf füllt das
 *  Gebiet wieder auf. Datenquelle: GET /admin/quiz/flagged. */
const AREA_TYPE_LABEL: Record<string, string> = { stadtteil: "", wahlbereich: "Wahlbereich ", thema: "" };

function QuizModerationTab() {
  const qc = useQueryClient();
  const statsQuery = useQuery({
    queryKey: ["admin", "quiz", "stats"],
    queryFn: () => api.get<AdminQuizStats>("/admin/quiz/stats"),
  });
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "quiz", "flagged"],
    queryFn: () => api.get<{ flagged: QuizFlagged[] }>("/admin/quiz/flagged"),
  });

  const retire = useMutation({
    mutationFn: (id: number) => api.post(`/admin/quiz/${id}/retire`),
    onSuccess: () => {
      toast.success("Frage ausgemustert. Der nächste Generierungslauf erzeugt Ersatz.");
      qc.invalidateQueries({ queryKey: ["admin", "quiz", "flagged"] });
      qc.invalidateQueries({ queryKey: ["admin", "quiz", "stats"] });
    },
    onError: () => toast.error("Frage konnte nicht ausgemustert werden."),
  });

  if (isPending) return <Spinner />;
  if (isError) return <p className="text-sm text-destructive">Fehler beim Laden der Bewertungen.</p>;
  const flagged = data?.flagged ?? [];
  const stats = statsQuery.data;
  const low = stats?.gebiete_niedrig ?? [];

  return (
    <div className="space-y-5">
      {/* Kennzahlen (21a). */}
      {stats && (
        <div className="grid grid-cols-3 gap-3">
          <Card className="p-3.5"><p className="font-display text-xl font-extrabold leading-none tabular-nums">{stats.fragen_aktiv.toLocaleString("de-DE")}</p><p className="mt-1 text-[11px] text-muted-foreground">Fragen aktiv</p></Card>
          <Card className="p-3.5"><p className="font-display text-xl font-extrabold leading-none tabular-nums">{stats.avg_accuracy} %</p><p className="mt-1 text-[11px] text-muted-foreground">⌀ Trefferquote</p></Card>
          <Card className="p-3.5"><p className="font-display text-xl font-extrabold leading-none tabular-nums">{stats.gemeldet}</p><p className="mt-1 text-[11px] text-muted-foreground">gemeldet 👎</p></Card>
        </div>
      )}

      {/* Gebiets-Warnung (21a). */}
      {low.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/[0.06] p-3">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>
          <div className="min-w-0">
            <p className="text-[12.5px] font-semibold text-amber-700 dark:text-amber-500">{low.length} {low.length === 1 ? "Gebiet" : "Gebiete"} bald leer</p>
            <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
              {low.slice(0, 6).map((g) => `${AREA_TYPE_LABEL[g.area_type] ?? ""}${g.area_key} (${g.n})`).join(", ")}
              {low.length > 6 && ` … +${low.length - 6}`} offene Fragen. Der nächste Generierungslauf füllt sie auf.
            </p>
          </div>
        </div>
      )}

      {flagged.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">Keine schlecht bewerteten Fragen. 🎉</Card>
      ) : (<>
      <p className="text-sm text-muted-foreground">
        Von Nutzer:innen als „schlecht" markierte Fragen, meist-gemeldete zuerst.
        Ausmustern nimmt die Frage aus künftigen Runden.
      </p>
      <Card className="divide-y divide-border">
        {flagged.map((f) => (
          <div key={f.question_id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge color="slate">{f.area_type}: {f.area_key}</Badge>
                <Badge color="red">👎 {f.bad}</Badge>
                {f.good > 0 && <Badge color="green">👍 {f.good}</Badge>}
              </div>
              <p className="mt-1.5 text-sm font-medium text-foreground">{f.question}</p>
              {f.options[f.correct_index] && (
                <p className="mt-0.5 text-xs text-muted-foreground">Richtige Antwort: {f.options[f.correct_index]}</p>
              )}
              {f.comments && (
                <p className="mt-1 text-xs italic text-muted-foreground">„{f.comments}"</p>
              )}
            </div>
            <Button variant="danger" size="sm" className="shrink-0"
                    disabled={retire.isPending}
                    onClick={() => retire.mutate(f.question_id)}>
              Ausmustern
            </Button>
          </div>
        ))}
      </Card>
      </>)}
    </div>
  );
}


/** Zusammengeführte Themen-Dubletten: durchsehen und bei Bedarf trennen.
 *  Die Zusammenführung ist umkehrbar — die Roh-Beobachtungen bleiben erhalten,
 *  die Themen werden daraus neu abgeleitet. */
function EntityAliasTab() {
  const qc = useQueryClient();
  const [undoing, setUndoing] = useState<EntityAlias | null>(null);
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "entity-aliases"],
    queryFn: () => api.get<{ aliases: EntityAlias[] }>("/admin/entity-aliases"),
  });

  const undo = useMutation({
    mutationFn: (slug: string) => api.del(`/admin/entity-aliases/${encodeURIComponent(slug)}`),
    onSuccess: () => {
      toast.success("Zusammenführung aufgehoben. Das Thema steht wieder für sich.");
      qc.invalidateQueries({ queryKey: ["admin", "entity-aliases"] });
    },
    onError: () => toast.error("Zusammenführung konnte nicht aufgehoben werden."),
  });

  if (isPending) return <Spinner />;
  if (isError) return <p className="text-sm text-destructive">Fehler beim Laden der Zusammenführungen.</p>;

  const aliases = data?.aliases ?? [];
  const byLlm = aliases.filter((a) => a.source === "llm").length;
  const manual = aliases.filter((a) => a.source === "manuell").length;

  // Nach Ziel-Thema gruppieren: „vier Namen für den Bäderbetrieb“ gehört zusammen.
  const groups = new Map<string, EntityAlias[]>();
  for (const a of aliases) {
    const list = groups.get(a.canonical_slug) ?? [];
    list.push(a);
    groups.set(a.canonical_slug, list);
  }
  const sorted = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-3.5">
          <p className="font-display text-xl font-extrabold leading-none tabular-nums">{groups.size}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">Themen zusammengeführt</p>
        </Card>
        <Card className="p-3.5">
          <p className="font-display text-xl font-extrabold leading-none tabular-nums">{aliases.length}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">eingesparte Seiten</p>
        </Card>
        <Card className="p-3.5">
          <p className="font-display text-xl font-extrabold leading-none tabular-nums">{manual}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">von Hand · {byLlm} per KI</p>
        </Card>
      </div>

      {aliases.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          Noch keine Zusammenführungen. Der Lauf <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
          scripts/merge_entity_aliases.py</code> sucht Dubletten und legt sie hier ab.
        </Card>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Diese Namen zeigen auf dasselbe Thema, damit Beschlüsse und Beträge an einer Stelle stehen.
            Trennen macht das rückgängig — die Beschlüsse selbst gehen dabei nie verloren.
          </p>
          <div className="space-y-3">
            {sorted.map(([canonicalSlug, list]) => (
              <Card key={canonicalSlug} className="p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-semibold">
                    {list[0].canonical_name ?? canonicalSlug}
                    {list[0].canonical_n != null && (
                      <span className="ml-2 text-xs font-normal text-muted-foreground tabular-nums">
                        {list[0].canonical_n} Beschlüsse
                      </span>
                    )}
                  </p>
                  <Badge color="slate">{list.length} zusammengeführt</Badge>
                </div>
                <ul className="mt-3 divide-y divide-border/60">
                  {list.map((a) => (
                    <li key={a.slug} className="flex flex-wrap items-start justify-between gap-3 py-2">
                      <div className="min-w-0">
                        <p className="text-sm">
                          <span className="text-muted-foreground line-through">{a.alias_name ?? a.slug}</span>
                          <span className="mx-2 text-muted-foreground">→</span>
                          <span>{a.canonical_name ?? a.canonical_slug}</span>
                        </p>
                        <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                          {a.source === "manuell" ? "von Hand" : "per KI"}
                          {a.reason ? ` · ${a.reason}` : ""}
                          {/* created_at ist ein voller Zeitstempel; formatDate erwartet YYYY-MM-DD. */}
                          {a.created_at ? ` · ${formatDate(a.created_at.slice(0, 10))}` : ""}
                        </p>
                      </div>
                      <Button variant="ghost" size="sm" onClick={() => setUndoing(a)}>
                        Trennen
                      </Button>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        </>
      )}

      <ConfirmDialog
        open={undoing !== null}
        onOpenChange={(open) => !open && setUndoing(null)}
        title="Zusammenführung aufheben?"
        description={
          undoing
            ? `„${undoing.alias_name ?? undoing.slug}“ bekommt wieder eine eigene Themen-Seite, ` +
              `getrennt von „${undoing.canonical_name ?? undoing.canonical_slug}“. ` +
              `Die Beschlüsse bleiben erhalten und verteilen sich wieder auf beide Seiten.`
            : ""
        }
        confirmLabel="Trennen"
        onConfirm={() => {
          if (undoing) undo.mutate(undoing.slug);
          setUndoing(null);
        }}
      />
    </div>
  );
}
