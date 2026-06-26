"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Prompt, WebUser, TelegramUser, AdminStats } from "@/lib/types";
import { Badge, Button, Card, ConfirmDialog, PageHeader, Spinner, Textarea, formatDate, toast } from "@/components/ui";
import { cn } from "@/lib/utils";
import { categoryLabel } from "@/lib/categories";

type Tab = "stats" | "llm" | "prompts" | "users" | "telegram";

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
      <PageHeader title="Admin" description="Prompts, Web-Nutzer und Telegram-Whitelist verwalten." />
      <div className="mt-4 flex gap-1 border-b border-border">
        {([
          ["stats", "Statistik"],
          ["llm", "LLM-Kosten"],
          ["prompts", "Prompts"],
          ["users", "Web-Nutzer"],
          ["telegram", "Telegram-Whitelist"],
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
        {tab === "telegram" && <TelegramTab />}
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

  const range =
    data.articles.oldest && data.articles.newest
      ? `${formatDate(data.articles.oldest)} – ${formatDate(data.articles.newest)}`
      : "—";

  return (
    <div className="space-y-8">
      <StatSection title="Artikel-Archiv">
        <Stat label="Artikel" value={data.articles.total} />
        <Stat label="Ausgaben" value={data.articles.editions} />
        <Stat label="Volltext-Index" value={data.articles.fts} />
        <Stat label="Zeitraum" value={range} wide />
      </StatSection>

      <StatSection title="Web-Nutzer">
        <Stat label="Gesamt" value={data.web_users.total} />
        <Stat label="Admins" value={data.web_users.admins} />
        <Stat label="Aktiv" value={data.web_users.active} />
        <Stat label="Warten auf Freischaltung" value={data.web_users.pending} />
        <Stat label="NWZ-verifiziert" value={data.web_users.nwz_verified} />
        <Stat label="Telegram verknüpft" value={data.web_users.linked} />
      </StatSection>

      <StatSection title="Telegram & Themen">
        <Stat label="Telegram-Nutzer" value={data.telegram_users} />
        <Stat label="Themen" value={data.topics.total} />
        <Stat label="Nutzer mit Themen" value={data.topics.users_with_topics} />
        <Stat label="Artikel-Treffer" value={data.topics.matches} />
        <Stat label="Klassifizierte Editionen" value={data.topics.classified_editions} />
        <Stat label="Ausschuss-Abos" value={data.topics.subscriptions} />
      </StatSection>

      <StatSection title="Ratsinformationssystem">
        <Stat label="Sitzungen" value={data.council.sessions} />
        <Stat label="davon kommend" value={data.council.upcoming} />
        <Stat label="Tagesordnungspunkte" value={data.council.agenda_items} />
        <Stat label="Ausschüsse" value={data.council.committees} />
      </StatSection>

      {data.categories.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-muted-foreground">Top-Rubriken (Artikel-Archiv)</h3>
          <Card className="divide-y divide-border">
            {data.categories.map((cat) => (
              <div key={cat.name} className="flex items-center justify-between px-4 py-2 text-sm">
                <span className="text-foreground">{categoryLabel(cat.name)}</span>
                <span className="font-medium text-muted-foreground">{cat.count.toLocaleString("de-DE")}</span>
              </div>
            ))}
          </Card>
        </div>
      )}
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
type LlmUsage = { features: LlmFeature[]; total_cost: number; total_calls: number };

const FEATURE_LABELS: Record<string, string> = {
  protokoll_extraktion: "Protokoll-Extraktion",
  themen_klassifikation: "Themenfeld-Klassifikation",
  ziel_bewertung: "Ziel-Bewertung",
  entitaeten_ner: "Entitäten-Erkennung",
  entitaeten_beschreibung: "Themen-Beschreibungen",
  qa_query_expansion: "Frag den Rat — Suchbegriffe",
  qa_antwort: "Frag den Rat — Antwort",
  nwz_klassifikation: "NWZ-Artikel-Klassifikation",
};

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

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Geschätzte Kosten gesamt" value={`$${data.total_cost.toFixed(2)}`} />
        <Stat label="LLM-Aufrufe gesamt" value={data.total_calls} />
        <Stat label="Features" value={data.features.length} />
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

function PromptsTab() {
  const { data: prompts = [], isPending, isError } = useQuery({
    queryKey: ["admin", "prompts"],
    queryFn: () => api.get<Prompt[]>("/admin/prompts"),
  });

  if (isPending) return <Spinner />;
  if (isError) return <p className="text-sm text-destructive">Fehler beim Laden der Prompts.</p>;

  return (
    <div className="space-y-4">
      {prompts.map((p) => (
        <PromptEditor key={p.key} prompt={p} />
      ))}
    </div>
  );
}

function PromptEditor({ prompt }: { prompt: Prompt }) {
  const qc = useQueryClient();
  const [content, setContent] = useState(prompt.content);
  const dirty = content !== prompt.content;

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
        </div>
        <code className="text-xs text-muted-foreground">{prompt.key}</code>
      </div>
      <Textarea className="mt-3" rows={Math.min(16, content.split("\n").length + 1)} value={content} onChange={(e) => setContent(e.target.value)} />
      <div className="mt-3 flex items-center gap-2">
        <Button size="sm" onClick={() => saveMutation.mutate(content)} disabled={busy || !dirty}>
          {saveMutation.isPending ? "Speichern…" : "Speichern"}
        </Button>
        {prompt.is_overridden && (
          <Button variant="secondary" size="sm" onClick={() => resetMutation.mutate()} disabled={busy}>
            Auf Standard zurücksetzen
          </Button>
        )}
        {dirty && <span className="text-xs text-amber-600">Ungespeicherte Änderungen</span>}
      </div>
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
      toast.success(vars.status === "active" ? "Nutzer freigeschaltet." : "Nutzer gesperrt.");
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: () => toast.error("Status konnte nicht geändert werden."),
  });

  const fulltextMutation = useMutation({
    mutationFn: ({ id, allowed }: { id: number; allowed: boolean }) =>
      api.put(`/admin/users/${id}/nwz-fulltext`, { allowed }),
    onSuccess: (_, vars) => {
      toast.success(vars.allowed ? "NWZ-Volltext freigeschaltet." : "NWZ-Volltext entzogen.");
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: () => toast.error("Volltext-Freigabe konnte nicht geändert werden."),
  });

  if (isPending) return <Spinner />;
  if (isError) return <p className="text-sm text-destructive">Fehler beim Laden der Nutzer.</p>;

  return (
    <Card className="divide-y divide-border">
      {users.map((u) => (
        <div key={u.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-foreground">{u.email}</span>
              <Badge color={u.role === "admin" ? "blue" : "slate"}>{u.role}</Badge>
              {u.status === "active" ? <Badge color="green">aktiv</Badge> : <Badge color="amber">wartet</Badge>}
              {u.telegram_chat_id ? <Badge color="green">Telegram</Badge> : null}
              {u.nwz_fulltext_allowed ? <Badge color="blue">Volltext</Badge> : null}
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
                {u.role === "admin" ? "Zu Nutzer" : "Zu Admin"}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => fulltextMutation.mutate({ id: u.id, allowed: !u.nwz_fulltext_allowed })}
              >
                {u.nwz_fulltext_allowed ? "Volltext entziehen" : "Volltext erlauben"}
              </Button>
            </div>
          )}
        </div>
      ))}
    </Card>
  );
}

function TelegramTab() {
  const qc = useQueryClient();
  const [confirmChatId, setConfirmChatId] = useState<number | null>(null);

  const { data: users = [], isPending, isError } = useQuery({
    queryKey: ["admin", "telegram-users"],
    queryFn: async () => {
      const data = await api.get<{ users: TelegramUser[] }>("/admin/telegram-users");
      return data.users;
    },
  });

  const removeMutation = useMutation({
    mutationFn: (chatId: number) => api.del(`/admin/telegram-users/${chatId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "telegram-users"] }),
    onError: () => toast.error("Entfernen fehlgeschlagen."),
  });

  if (isPending) return <Spinner />;
  if (isError) return <p className="text-sm text-destructive">Fehler beim Laden der Telegram-Nutzer.</p>;

  return (
    <>
      <ConfirmDialog
        open={confirmChatId !== null}
        onOpenChange={(o) => !o && setConfirmChatId(null)}
        title="Telegram-Nutzer entfernen"
        description="Dadurch werden auch alle Themen dieses Nutzers gelöscht. Diese Aktion kann nicht rückgängig gemacht werden."
        confirmLabel="Entfernen"
        onConfirm={() => confirmChatId !== null && removeMutation.mutate(confirmChatId)}
      />
      <Card className="divide-y divide-border">
        {users.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-muted-foreground">Keine Telegram-Nutzer.</p>
        ) : (
          users.map((u) => (
            <div key={u.chat_id} className="flex items-center justify-between px-4 py-3">
              <div>
                <span className="font-medium text-foreground">{u.username || "(ohne Name)"}</span>
                <p className="text-xs text-muted-foreground">
                  Chat-ID {u.chat_id} · {u.topic_count} Thema(en) · seit {formatDate(u.added_at.slice(0, 10))}
                </p>
              </div>
              <Button variant="danger" size="sm" onClick={() => setConfirmChatId(u.chat_id)}>
                Entfernen
              </Button>
            </div>
          ))
        )}
      </Card>
    </>
  );
}
