"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Prompt, WebUser, AdminStats, QuizFlagged, AdminQuizStats } from "@/lib/types";
import { Badge, Button, Card, ConfirmDialog, PageHeader, Spinner, Textarea, formatDate, toast } from "@/components/ui";
import { AreaSparkline, StatKicker } from "@/components/admin-charts";
import { cn } from "@/lib/utils";

type Tab = "stats" | "llm" | "prompts" | "users" | "quiz";

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
      </div>
    </div>
  );
}

function StatsTab() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => api.get<AdminStats>("/admin/stats"),
  });

  if (isPending) return <Spinner />;
  if (isError || !data) return <p className="text-sm text-destructive">Fehler beim Laden der Statistiken.</p>;

  return (
    <div className="space-y-8">
      <StatSection title="Web-Nutzer:innen">
        <Stat label="Gesamt" value={data.web_users.total} />
        <Stat label="Admins" value={data.web_users.admins} />
        <Stat label="Aktiv" value={data.web_users.active} />
        <Stat label="Nicht aktiv (unbestätigt/gesperrt)" value={data.web_users.pending} />
      </StatSection>

      <StatSection title="Themen">
        <Stat label="Themen" value={data.topics.total} />
        <Stat label="Nutzer:innen mit Themen" value={data.topics.users_with_topics} />
        <Stat label="Ausschuss-Abos" value={data.topics.subscriptions} />
      </StatSection>

      <StatSection title="Ratsinformationssystem">
        <Stat label="Sitzungen" value={data.council.sessions} />
        <Stat label="davon kommend" value={data.council.upcoming} />
        <Stat label="Tagesordnungspunkte" value={data.council.agenda_items} />
        <Stat label="Ausschüsse" value={data.council.committees} />
      </StatSection>
    </div>
  );
}

function StatSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-muted-foreground">{title}</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{children}</div>
    </div>
  );
}

function Stat({ label, value, wide }: { label: string; value: number | string; wide?: boolean }) {
  return (
    <Card className={cn("p-4", wide && "col-span-2")}>
      <p className="text-2xl font-bold text-foreground">
        {typeof value === "number" ? value.toLocaleString("de-DE") : value}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
    </Card>
  );
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
          <AreaSparkline values={data.series.map((d) => d.cost)} color="hsl(var(--primary))" height={110} className="mt-3" />
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

function UsersTab({ currentUserId }: { currentUserId: number }) {
  const qc = useQueryClient();
  const { data: users = [], isPending, isError } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api.get<WebUser[]>("/admin/users"),
  });

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: number; role: "user" | "admin" }) =>
      api.put(`/admin/users/${id}/role`, { role }),
    onSuccess: () => {
      toast.success("Rolle aktualisiert.");
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: () => toast.error("Rolle konnte nicht geändert werden."),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "active" | "pending" }) =>
      api.put(`/admin/users/${id}/status`, { status }),
    onSuccess: (_, vars) => {
      toast.success(vars.status === "active" ? "Nutzer:in freigeschaltet." : "Nutzer:in gesperrt.");
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: () => toast.error("Status konnte nicht geändert werden."),
  });

  if (isPending) return <Spinner />;
  if (isError) return <p className="text-sm text-destructive">Fehler beim Laden der Nutzer:innen.</p>;

  return (
    <Card className="divide-y divide-border">
      {users.map((u) => (
        <div key={u.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-foreground">{u.email}</span>
              <Badge color={u.role === "admin" ? "blue" : "slate"}>{u.role}</Badge>
              {u.status === "active" ? <Badge color="green">aktiv</Badge> : <Badge color="amber">wartet</Badge>}
            </div>
            <p className="text-xs text-muted-foreground">seit {formatDate(u.created_at.slice(0, 10))}</p>
          </div>
          {u.id !== currentUserId && (
            <div className="flex shrink-0 gap-2">
              {u.status === "active" ? (
                <Button variant="secondary" size="sm" onClick={() => statusMutation.mutate({ id: u.id, status: "pending" })}>
                  Sperren
                </Button>
              ) : (
                <Button variant="primary" size="sm" onClick={() => statusMutation.mutate({ id: u.id, status: "active" })}>
                  Freischalten
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => roleMutation.mutate({ id: u.id, role: u.role === "admin" ? "user" : "admin" })}
              >
                {u.role === "admin" ? "Zu Nutzer:in" : "Zu Admin"}
              </Button>
            </div>
          )}
        </div>
      ))}
    </Card>
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

