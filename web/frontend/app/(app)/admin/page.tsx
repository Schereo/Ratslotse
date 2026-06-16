"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Prompt, WebUser, TelegramUser } from "@/lib/types";
import { Badge, Button, Card, Spinner, Textarea, formatDate } from "@/components/ui";

type Tab = "prompts" | "users" | "telegram";

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("prompts");

  useEffect(() => {
    if (!loading && user && user.role !== "admin") router.replace("/dashboard");
  }, [user, loading, router]);

  if (loading || user?.role !== "admin") return <Spinner />;

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Admin</h1>
      <div className="mt-4 flex gap-1 border-b border-slate-200">
        {([
          ["prompts", "Prompts"],
          ["users", "Web-Nutzer"],
          ["telegram", "Telegram-Whitelist"],
        ] as [Tab, string][]).map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium ${
              tab === t ? "border-b-2 border-brand-600 text-brand-700" : "text-slate-500 hover:text-slate-700"
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
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setPrompts(await api.get<Prompt[]>("/admin/prompts"));
    setLoading(false);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      {prompts.map((p) => (
        <PromptEditor key={p.key} prompt={p} onChanged={load} />
      ))}
    </div>
  );
}

function PromptEditor({ prompt, onChanged }: { prompt: Prompt; onChanged: () => void }) {
  const [content, setContent] = useState(prompt.content);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const dirty = content !== prompt.content;

  const save = async () => {
    setBusy(true);
    try {
      await api.put(`/admin/prompts/${prompt.key}`, { content });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      await api.post(`/admin/prompts/${prompt.key}/reset`);
      setContent(prompt.default);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-900">{prompt.title}</h3>
            {prompt.is_overridden ? <Badge color="amber">angepasst</Badge> : <Badge color="green">Standard</Badge>}
          </div>
          <p className="mt-0.5 text-xs text-slate-400">{prompt.description}</p>
        </div>
        <code className="text-xs text-slate-400">{prompt.key}</code>
      </div>
      <Textarea className="mt-3" rows={Math.min(16, content.split("\n").length + 1)} value={content} onChange={(e) => setContent(e.target.value)} />
      <div className="mt-3 flex items-center gap-2">
        <Button size="sm" onClick={save} disabled={busy || !dirty}>
          {saved ? "✓ Gespeichert" : "Speichern"}
        </Button>
        {prompt.is_overridden && (
          <Button variant="secondary" size="sm" onClick={reset} disabled={busy}>
            Auf Standard zurücksetzen
          </Button>
        )}
        {dirty && <span className="text-xs text-amber-600">Ungespeicherte Änderungen</span>}
      </div>
    </Card>
  );
}

function UsersTab({ currentUserId }: { currentUserId: number }) {
  const [users, setUsers] = useState<WebUser[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setUsers(await api.get<WebUser[]>("/admin/users"));
    setLoading(false);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const setRole = async (id: number, role: "user" | "admin") => {
    await api.put(`/admin/users/${id}/role`, { role });
    load();
  };

  if (loading) return <Spinner />;

  return (
    <Card className="divide-y divide-slate-100">
      {users.map((u) => (
        <div key={u.id} className="flex items-center justify-between px-4 py-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-900">{u.email}</span>
              <Badge color={u.role === "admin" ? "blue" : "slate"}>{u.role}</Badge>
              {u.telegram_chat_id ? <Badge color="green">verbunden</Badge> : <Badge color="amber">nicht verbunden</Badge>}
            </div>
            <p className="text-xs text-slate-400">seit {formatDate(u.created_at.slice(0, 10))}</p>
          </div>
          {u.id !== currentUserId && (
            <Button variant="secondary" size="sm" onClick={() => setRole(u.id, u.role === "admin" ? "user" : "admin")}>
              {u.role === "admin" ? "Zu Nutzer" : "Zu Admin"}
            </Button>
          )}
        </div>
      ))}
    </Card>
  );
}

function TelegramTab() {
  const [users, setUsers] = useState<TelegramUser[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const data = await api.get<{ users: TelegramUser[] }>("/admin/telegram-users");
    setUsers(data.users);
    setLoading(false);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const remove = async (chatId: number) => {
    if (!confirm("Diesen Telegram-Nutzer entfernen (inkl. seiner Themen)?")) return;
    await api.del(`/admin/telegram-users/${chatId}`);
    load();
  };

  if (loading) return <Spinner />;

  return (
    <Card className="divide-y divide-slate-100">
      {users.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">Keine Telegram-Nutzer.</p>
      ) : (
        users.map((u) => (
          <div key={u.chat_id} className="flex items-center justify-between px-4 py-3">
            <div>
              <span className="font-medium text-slate-900">{u.username || "(ohne Name)"}</span>
              <p className="text-xs text-slate-400">
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
