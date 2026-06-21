"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { Plus, Trash2, FileText, Tags, Pencil, RefreshCw } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { Topic, TopicMatch, Article } from "@/lib/types";
import {
  Badge, Button, Card, CardListSkeleton, ConfirmDialog, EmptyState, Input, PageHeader, Textarea, formatDate,
  Dialog, DialogContent, DialogHeader, DialogTitle, toast,
} from "@/components/ui";

export default function TopicsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [matchesFor, setMatchesFor] = useState<{ topic: Topic; matches: TopicMatch[] } | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [editing, setEditing] = useState<Topic | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [reclassifyEndsAt, setReclassifyEndsAt] = useState<number | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const topicsQuery = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<Topic[]>("/topics"),
    refetchInterval: () => (reclassifyEndsAt && Date.now() < reclassifyEndsAt ? 5000 : false),
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

  const editMutation = useMutation({
    mutationFn: (vars: { id: number; name: string; description: string }) =>
      api.put(`/topics/${vars.id}`, { name: vars.name, description: vars.description }),
    onSuccess: () => {
      toast.success("Thema aktualisiert.");
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
    onError: (err: Error) => toast.error(err instanceof ApiError ? err.message : "Konnte Thema nicht ändern."),
  });

  const reclassifyMutation = useMutation({
    mutationFn: (id: number) => api.post(`/topics/${id}/reclassify`),
    onSuccess: () => {
      toast.success("Neu-Klassifizierung gestartet — das dauert 1–2 Min. Die Treffer aktualisieren sich automatisch.");
      setReclassifyEndsAt(Date.now() + 180_000);
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
    onError: (err: Error) => toast.error(err instanceof ApiError ? err.message : "Konnte nicht neu klassifizieren."),
  });

  const startEdit = (t: Topic) => {
    setEditing(t);
    setEditName(t.name);
    setEditDescription(t.description);
  };

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
  const isError = topicsQuery.isError && !needsLink;

  if (loading) {
    return (
      <div>
        <PageHeader title="Meine Themen" description="Themen, nach denen der Bot täglich die NWZ durchsucht." />
        <div className="mt-6">
          <CardListSkeleton rows={3} />
        </div>
      </div>
    );
  }
  if (isError) {
    return (
      <div>
        <PageHeader title="Meine Themen" />
        <p className="mt-6 text-sm text-destructive">Fehler beim Laden der Themen. Bitte Seite neu laden.</p>
      </div>
    );
  }

  if (needsLink) {
    return (
      <div>
        <PageHeader title="Meine Themen" />
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
      <ConfirmDialog
        open={confirmDeleteId !== null}
        onOpenChange={(o) => !o && setConfirmDeleteId(null)}
        title="Thema löschen"
        description="Alle gespeicherten Treffer für dieses Thema werden ebenfalls gelöscht."
        confirmLabel="Löschen"
        onConfirm={() => confirmDeleteId !== null && deleteMutation.mutate(confirmDeleteId)}
      />
      <PageHeader title="Meine Themen" description="Themen, nach denen der Bot täglich die NWZ durchsucht." />

      <Card className="mt-6 p-4">
        <form
          onSubmit={(e) => { e.preventDefault(); addMutation.mutate({ name, description }); }}
          className="space-y-3"
        >
          <Input ref={nameInputRef} placeholder="Name (z. B. Radwege)" value={name} onChange={(e) => setName(e.target.value)} required />
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
          <EmptyState
            icon={Tags}
            title="Noch keine Themen"
            hint="Lege ein Thema an, nach dem der Bot täglich die NWZ durchsucht."
            action={
              <Button size="sm" onClick={() => { nameInputRef.current?.focus(); nameInputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>
                <Plus className="h-4 w-4" /> Erstes Thema anlegen
              </Button>
            }
          />
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
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button variant="secondary" size="sm" onClick={() => viewMatches(t)}>
                    <FileText className="h-4 w-4" /> Treffer
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => startEdit(t)}>
                    <Pencil className="h-4 w-4" /> Bearbeiten
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => reclassifyMutation.mutate(t.id)}
                    disabled={reclassifyMutation.isPending}
                  >
                    <RefreshCw className="h-4 w-4" /> Neu klassifizieren
                  </Button>
                  <Button variant="danger" size="sm" aria-label="Löschen" onClick={() => setConfirmDeleteId(t.id)} disabled={deleteMutation.isPending}>
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

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Thema bearbeiten</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => { e.preventDefault(); if (editing) editMutation.mutate({ id: editing.id, name: editName, description: editDescription }); }}
            className="space-y-3"
          >
            <Input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Name" required />
            <Textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} rows={3} placeholder="Beschreibung" required />
            <div className="flex items-center justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setEditing(null)}>Abbrechen</Button>
              <Button type="submit" disabled={editMutation.isPending}>{editMutation.isPending ? "Speichern…" : "Speichern"}</Button>
            </div>
          </form>
          <p className="mt-2 text-xs text-muted-foreground">
            Tipp: Nach dem Ändern „Neu klassifizieren", damit die Treffer zur neuen Beschreibung passen.
          </p>
        </DialogContent>
      </Dialog>

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
                    <MatchItem key={i} m={m} />
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

function MatchItem({ m }: { m: TopicMatch }) {
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(false);
  const [shown, setShown] = useState(false);

  const toggle = async () => {
    if (shown) { setShown(false); return; }
    if (article) { setShown(true); return; }
    setLoading(true);
    try {
      const a = await api.get<Article>(`/nwz/article/${m.catalog}?refid=${encodeURIComponent(m.refid)}`);
      setArticle(a);
      setShown(true);
    } catch (err) {
      toast.error(
        err instanceof ApiError && err.status === 403
          ? "Hinterlege deine NWZ-Zugangsdaten, um den ganzen Artikel zu sehen."
          : "Artikel konnte nicht geladen werden.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <li className="border-b border-border pb-3 last:border-0">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{formatDate(m.pub_date)}</span>
        {m.is_continuation ? <Badge color="amber">Fortsetzung</Badge> : null}
      </div>
      <p className="mt-0.5 font-medium text-foreground">{m.title}</p>
      <p className="text-sm text-muted-foreground">{m.summary}</p>
      <button type="button" onClick={toggle} className="mt-1 text-xs font-medium text-primary hover:underline">
        {loading ? "Lädt…" : shown ? "Artikel ausblenden" : "Ganzen Artikel anzeigen"}
      </button>
      {shown && article && (
        <div className="mt-2 whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-sm leading-relaxed text-foreground/90">
          {article.content_text}
        </div>
      )}
    </li>
  );
}
