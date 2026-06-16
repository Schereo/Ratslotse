"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Plus, Trash2, FileText } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Topic, TopicMatch } from "@/lib/types";
import {
  Badge, Button, Card, EmptyState, Input, Spinner, Textarea, formatDate,
  Dialog, DialogContent, DialogHeader, DialogTitle, toast,
} from "@/components/ui";

export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [needsLink, setNeedsLink] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
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
      else toast.error(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addTopic = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/topics", { name, description });
      setName("");
      setDescription("");
      toast.success("Thema hinzugefügt.");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Konnte Thema nicht anlegen.");
    } finally {
      setBusy(false);
    }
  };

  const deleteTopic = async (id: number) => {
    try {
      await api.del(`/topics/${id}`);
      toast.success("Thema gelöscht.");
      await load();
    } catch {
      toast.error("Löschen fehlgeschlagen.");
    }
  };

  const viewMatches = async (topic: Topic) => {
    try {
      const data = await api.get<{ matches: TopicMatch[] }>(`/topics/${topic.id}/matches`);
      setMatchesFor({ topic, matches: data.matches });
    } catch {
      toast.error("Treffer konnten nicht geladen werden.");
    }
  };

  const toggleSub = async (committee: string) => {
    try {
      if (subscriptions.includes(committee)) {
        await api.del("/subscriptions", { committee_name: committee });
      } else {
        await api.post("/subscriptions", { committee_name: committee });
      }
      const subs = await api.get<{ subscriptions: string[] }>("/subscriptions");
      setSubscriptions(subs.subscriptions);
    } catch {
      toast.error("Abo konnte nicht geändert werden.");
    }
  };

  if (loading) return <Spinner />;

  if (needsLink) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-foreground">Meine Themen</h1>
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
      <h1 className="text-2xl font-bold text-foreground">Meine Themen</h1>
      <p className="mt-1 text-sm text-muted-foreground">Themen, nach denen der Bot täglich die NWZ durchsucht.</p>

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
          <Button type="submit" disabled={busy}>
            <Plus className="h-4 w-4" /> {busy ? "Hinzufügen…" : "Thema hinzufügen"}
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-3">
        {topics.length === 0 ? (
          <EmptyState title="Noch keine Themen" hint="Füge oben dein erstes Thema hinzu." />
        ) : (
          topics.map((t) => (
            <Card key={t.id} className="p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-foreground">{t.name}</h3>
                    <Badge color="blue">{t.match_count} Treffer</Badge>
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground">{t.description}</p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button variant="secondary" size="sm" onClick={() => viewMatches(t)}>
                    <FileText className="h-4 w-4" /> Treffer
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => deleteTopic(t.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      <h2 className="mt-10 text-lg font-bold text-foreground">Ausschuss-Abos</h2>
      <p className="mt-1 text-sm text-muted-foreground">Benachrichtigungen, sobald eine Tagesordnung veröffentlicht wird.</p>
      <Card className="mt-3 divide-y divide-border">
        {committees.map((c) => {
          const subscribed = subscriptions.includes(c);
          return (
            <div key={c} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="min-w-0 text-sm text-foreground">{c}</span>
              <Button variant={subscribed ? "secondary" : "primary"} size="sm" onClick={() => toggleSub(c)}>
                {subscribed ? "✓ Abonniert" : "Abonnieren"}
              </Button>
            </div>
          );
        })}
      </Card>

      <Dialog open={!!matchesFor} onOpenChange={(o) => !o && setMatchesFor(null)}>
        <DialogContent>
          {matchesFor && (
            <>
              <DialogHeader>
                <DialogTitle>Treffer: {matchesFor.topic.name}</DialogTitle>
              </DialogHeader>
              {matchesFor.matches.length === 0 ? (
                <p className="text-sm text-muted-foreground">Noch keine archivierten Treffer.</p>
              ) : (
                <ul className="space-y-3">
                  {matchesFor.matches.map((m, i) => (
                    <li key={i} className="border-b border-border pb-3 last:border-0">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span>{formatDate(m.pub_date)}</span>
                        {m.is_continuation ? <Badge color="amber">Fortsetzung</Badge> : null}
                      </div>
                      <p className="mt-0.5 font-medium text-foreground">{m.title}</p>
                      <p className="text-sm text-muted-foreground">{m.summary}</p>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
