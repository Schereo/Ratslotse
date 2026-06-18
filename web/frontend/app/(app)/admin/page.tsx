"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Prompt, WebUser, TelegramUser } from "@/lib/types";
import { Badge, Button, Card, Spinner, Textarea, formatDate, toast } from "@/components/ui";

type Tab = "prompts" | "users" | "telegram";

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("prompts");

  if (loading) return <Spinner />;
  if (!user || user.role !== "admin") {
    if (!loading) router.replace("/dashboard");
    return <Spinner />;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-foreground">Admin</h1>
      <div className="mt-4 flex gap-1 border-b border-border">
        {([
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
        {tab === "prompts" && <PromptsTab />}
        {tab === "users" && <UsersTab currentUserId={user.id} />}
        {tab === "telegram" && <TelegramTab />}
      </div>
    </div>
  );
}

function PromptsTab() {
  const { data: prompts = [], isPending } = useQuery({
    queryKey: ["admin", "prompts"],
    queryFn: () => api.get<Prompt[]>("/admin/prompts"),
  });

  if (isPending) return <Spinner />;

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
  const { data: users = [], isPending } = useQuery({
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

  if (isPending) return <Spinner />;

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
              {u.nwz_verified_at ? <Badge color="green">NWZ</Badge> : null}
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
            </div>
          )}
        </div>
      ))}
    </Card>
  );
}

function TelegramTab() {
  const qc = useQueryClient();
  const { data: users = [], isPending } = useQuery({
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

  const remove = (chatId: number) => {
    if (!confirm("Diesen Telegram-Nutzer entfernen (inkl. seiner Themen)?")) return;
    removeMutation.mutate(chatId);
  };

  if (isPending) return <Spinner />;

  return (
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
            <Button variant="danger" size="sm" onClick={() => remove(u.chat_id)}>
              Entfernen
            </Button>
          </div>
        ))
      )}
    </Card>
  );
}
