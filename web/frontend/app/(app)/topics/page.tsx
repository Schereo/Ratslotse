"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Topic, TopicMatch } from "@/lib/types";
import { Badge, Button, Card, EmptyState, Input, Spinner, Textarea, formatDate } from "@/components/ui";

export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [needsLink, setNeedsLink] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [committees, setCommittees] = useState<string[]>([]);
  const [subscriptions, setSubscriptions] = useState<string[]>([]);
  const [matchesFor, setMatchesFor] = useState<{ topic: Topic; matches: TopicMatch[] } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, subs, com] = await Promise.all([
        api.get<Topic[]>("/topics"),
        api.get<{ subscriptions: string[] }>("/subscriptions"),
        api.get<{ committees: string[] }>("/council/committees"),
      ]);
      setTopics(t);
      setSubscriptions(subs.subscriptions);
      setCommittees(com.committees);
      setNeedsLink(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setNeedsLink(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addTopic = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.post("/topics", { name, description });
      setName("");
      setDescription("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Konnte Thema nicht anlegen.");
    } finally {
      setBusy(false);
    }
  };

  const deleteTopic = async (id: number) => {
    await api.del(`/topics/${id}`);
    await load();
  };

  const viewMatches = async (topic: Topic) => {
    const data = await api.get<{ matches: TopicMatch[] }>(`/topics/${topic.id}/matches`);
    setMatchesFor({ topic, matches: data.matches });
  };

  const toggleSub = async (committee: string) => {
    if (subscriptions.includes(committee)) {
      await api.del("/subscriptions", { committee_name: committee });
    } else {
      await api.post("/subscriptions", { committee_name: committee });
    }
    const subs = await api.get<{ subscriptions: string[] }>("/subscriptions");
    setSubscriptions(subs.subscriptions);
  };

  if (loading) return <Spinner />;

  if (needsLink) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Meine Themen</h1>
        <Card className="mt-6 border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-amber-800">Verknüpfe zuerst dein Konto mit Telegram, um Themen zu verwalten.</p>
          <Link href="/link" className="mt-2 inline-block font-semibold text-amber-900 underline">
            Jetzt verbinden →
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Meine Themen</h1>
      <p className="mt-1 text-sm text-slate-500">Themen, nach denen der Bot täglich die NWZ durchsucht.</p>

      <Card className="mt-6 p-4">
        <form onSubmit={addTopic} className="space-y-3">
          <Input placeholder="Name (z. B. Radwege)" value={name} onChange={(e) => setName(e.target.value)} required />
          <Textarea
            placeholder="Beschreibung — je konkreter, desto besser (z. B. Ausbau und Planung von Radwegen in Oldenburg)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            required
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={busy}>
            {busy ? "Hinzufügen…" : "Thema hinzufügen"}
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-3">
        {topics.length === 0 ? (
          <EmptyState title="Noch keine Themen" hint="Füge oben dein erstes Thema hinzu." />
        ) : (
          topics.map((t) => (
            <Card key={t.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-slate-900">{t.name}</h3>
                    <Badge color="blue">{t.match_count} Treffer</Badge>
                  </div>
                  <p className="mt-0.5 text-sm text-slate-500">{t.description}</p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button variant="secondary" size="sm" onClick={() => viewMatches(t)}>
                    Treffer
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => deleteTopic(t.id)}>
                    Löschen
                  </Button>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      <h2 className="mt-10 text-lg font-bold text-slate-900">Ausschuss-Abos</h2>
      <p className="mt-1 text-sm text-slate-500">Benachrichtigungen, sobald eine Tagesordnung veröffentlicht wird.</p>
      <Card className="mt-3 divide-y divide-slate-100">
        {committees.map((c) => {
          const subscribed = subscriptions.includes(c);
          return (
            <div key={c} className="flex items-center justify-between px-4 py-2.5">
              <span className="text-sm text-slate-700">{c}</span>
              <Button variant={subscribed ? "secondary" : "primary"} size="sm" onClick={() => toggleSub(c)}>
                {subscribed ? "✓ Abonniert" : "Abonnieren"}
              </Button>
            </div>
          );
        })}
      </Card>

      {matchesFor && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={() => setMatchesFor(null)}>
          <Card className="my-8 w-full max-w-2xl p-6">
            <div onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-slate-900">Treffer: {matchesFor.topic.name}</h2>
                <Button variant="ghost" size="sm" onClick={() => setMatchesFor(null)}>
                  ✕
                </Button>
              </div>
              {matchesFor.matches.length === 0 ? (
                <p className="mt-4 text-sm text-slate-500">Noch keine archivierten Treffer.</p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {matchesFor.matches.map((m, i) => (
                    <li key={i} className="border-b border-slate-100 pb-3 last:border-0">
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <span>{formatDate(m.pub_date)}</span>
                        {m.is_continuation ? <Badge color="amber">Fortsetzung</Badge> : null}
                      </div>
                      <p className="mt-0.5 font-medium text-slate-900">{m.title}</p>
                      <p className="text-sm text-slate-600">{m.summary}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
