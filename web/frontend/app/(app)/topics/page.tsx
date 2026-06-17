"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Trash2, FileText } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { Topic, TopicMatch } from "@/lib/types";
import {
  Badge, Button, Card, EmptyState, Input, Spinner, Textarea, formatDate,
  Dialog, DialogContent, DialogHeader, DialogTitle, toast,
} from "@/components/ui";

export default function TopicsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [matchesFor, setMatchesFor] = useState<{ topic: Topic; matches: TopicMatch[] } | null>(null);

  const topicsQuery = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<Topic[]>("/topics"),
  });

  const subsQuery = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => api.get<{ subscriptions: string[] }>("/subscriptions").then((d) => d.subscriptions),
  });

  const committeesQuery = useQuery({
    queryKey: ["committees"],
    queryFn: () => api.get<{ committees: string[] }>("/council/committees").then((d) => d.committees),
  });

  const addMutation = useMutation({
    mutationFn: ({ name, description }: { name: string; description: string }) =>
      api.post("/topics", { name, description }),
    onSuccess: () => {
      toast.success("Thema hinzugefügt.");
      setName("");
      setDescription("");
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
    onError: (err: Error) => toast.error(err instanceof ApiError ? err.message : "Konnte Thema nicht anlegen."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del(`/topics/${id}`),
    onSuccess: () => {
      toast.success("Thema gelöscht.");
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
    onError: () => toast.error("Löschen fehlgeschlagen."),
  });

  const subMutation = useMutation({
    mutationFn: ({ committee, subscribed }: { committee: string; subscribed: boolean }) =>
      subscribed
        ? api.del("/subscriptions", { committee_name: committee })
        : api.post("/subscriptions", { committee_name: committee }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
    onError: () => toast.error("Abo konnte nicht geändert werden."),
  });

  const viewMatches = async (topic: Topic) => {
    try {
      const data = await api.get<{ matches: TopicMatch[] }>(`/topics/${topic.id}/matches`);
      setMatchesFor({ topic, matches: data.matches });
    } catch {
      toast.error("Treffer konnten nicht geladen werden.");
    }
  };

  const loading = topicsQuery.isPending;
  const needsLink = topicsQuery.error instanceof ApiError && (topicsQuery.error as ApiError).status === 409;

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

  const topics = topicsQuery.data ?? [];
  const subscriptions = subsQuery.data ?? [];
  const committees = committeesQuery.data ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-foreground">Meine Themen</h1>
      <p className="mt-1 text-sm text-muted-foreground">Themen, nach denen der Bot täglich die NWZ durchsucht.</p>

      <Card className="mt-6 p-4">
        <form
          onSubmit={(e) => { e.preventDefault(); addMutation.mutate({ name, description }); }}
          className="space-y-3"
        >
          <Input placeholder="Name (z. B. Radwege)" value={name} onChange={(e) => setName(e.target.value)} required />
          <Textarea
            placeholder="Beschreibung — je konkreter, desto besser (z. B. Ausbau und Planung von Radwegen in Oldenburg)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            required
          />
          <Button type="submit" disabled={addMutation.isPending}>
            <Plus className="h-4 w-4" /> {addMutation.isPending ? "Hinzufügen…" : "Thema hinzufügen"}
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
                  <Button variant="danger" size="sm" onClick={() => deleteMutation.mutate(t.id)} disabled={deleteMutation.isPending}>
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
              <Button
                variant={subscribed ? "secondary" : "primary"}
                size="sm"
                onClick={() => subMutation.mutate({ committee: c, subscribed })}
                disabled={subMutation.isPending}
              >
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
