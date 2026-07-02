"use client";

import { useState, useRef } from "react";
import { Plus, Trash2, Landmark, Pencil } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { Topic, TopicDecision } from "@/lib/types";
import { DecisionLinkCard } from "@/components/decision-ui";
import {
  Badge, Button, Card, CardListSkeleton, ConfirmDialog, EmptyState, Input, PageHeader, Textarea,
  Dialog, DialogContent, DialogHeader, DialogTitle, toast,
} from "@/components/ui";

export default function TopicsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [decisionsFor, setDecisionsFor] = useState<{ topic: Topic; decisions: TopicDecision[] } | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [editing, setEditing] = useState<Topic | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const nameInputRef = useRef<HTMLInputElement>(null);

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

  const viewDecisions = async (topic: Topic) => {
    try {
      const data = await api.get<{ decisions: TopicDecision[] }>(`/topics/${topic.id}/decisions`);
      setDecisionsFor({ topic, decisions: data.decisions });
    } catch {
      toast.error("Beschlüsse konnten nicht geladen werden.");
    }
  };

  const loading = topicsQuery.isPending;
  const isError = topicsQuery.isError;

  const HEADER_DESC = "Themen, über deren neue Ratsbeschlüsse du benachrichtigt wirst.";

  if (loading) {
    return (
      <div>
        <PageHeader title="Meine Themen" description={HEADER_DESC} />
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

  const topics = topicsQuery.data ?? [];
  const subscriptions = subsQuery.data ?? [];
  const committees = committeesQuery.data ?? [];

  return (
    <div>
      <ConfirmDialog
        open={confirmDeleteId !== null}
        onOpenChange={(o) => !o && setConfirmDeleteId(null)}
        title="Thema löschen"
        description="Das Thema und seine Benachrichtigungen werden entfernt."
        confirmLabel="Löschen"
        onConfirm={() => confirmDeleteId !== null && deleteMutation.mutate(confirmDeleteId)}
      />
      <PageHeader title="Meine Themen" description={HEADER_DESC} />

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
            mascot="wave"
            title="Noch keine Themen"
            hint="Lege ein Thema an — wir melden uns, sobald der Rat etwas dazu beschließt."
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
                    {t.decision_count > 0 && <Badge color="green">{t.decision_count} Beschlüsse</Badge>}
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground">{t.description}</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {t.decision_count > 0 && (
                    <Button variant="secondary" size="sm" onClick={() => viewDecisions(t)}>
                      <Landmark className="h-4 w-4" /> Beschlüsse
                    </Button>
                  )}
                  <Button variant="secondary" size="sm" onClick={() => startEdit(t)}>
                    <Pencil className="h-4 w-4" /> Bearbeiten
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
        </DialogContent>
      </Dialog>

      <Dialog open={!!decisionsFor} onOpenChange={(o) => !o && setDecisionsFor(null)}>
        <DialogContent>
          {decisionsFor && (
            <>
              <DialogHeader>
                <DialogTitle>Beschlüsse: {decisionsFor.topic.name}</DialogTitle>
              </DialogHeader>
              {decisionsFor.decisions.length === 0 ? (
                <p className="text-sm text-muted-foreground">Noch keine passenden Beschlüsse.</p>
              ) : (
                <div className="space-y-2">
                  {decisionsFor.decisions.map((d) => (
                    <DecisionLinkCard key={d.id} id={d.id} title={d.title} committee={d.committee}
                      session_date={d.session_date} field={d.policy_field} score={d.score} />
                  ))}
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
