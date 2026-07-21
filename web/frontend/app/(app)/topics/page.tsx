"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Plus, Trash2, Pencil } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { Topic, TopicDecision } from "@/lib/types";
import { DecisionLinkCard } from "@/components/decision-ui";
import {
  Button, Card, CardListSkeleton, ConfirmDialog, EmptyState, Input, PageHeader, Textarea,
  Dialog, DialogContent, DialogHeader, DialogTitle, Switch, formatDate, toast,
} from "@/components/ui";
import { decisionHref } from "@/lib/routes";

function TopicsInner() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  // ?neu= aus der URL (KI-Frage ohne Treffer → „Als Thema anlegen"):
  // Namen vorbefüllen UND den Anlege-Dialog direkt öffnen.
  const spNeu = useSearchParams();
  useEffect(() => {
    const neu = spNeu.get("neu");
    if (neu) {
      setName((prev) => prev || neu);
      setCreateOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
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

  // Anklickbare Vorschläge aus den echten Daten: die häufigsten
  // Beschluss-Schlagworte der letzten sechs Monate (Backend filtert
  // bereits angelegte Themen heraus).
  const suggestionsQuery = useQuery({
    queryKey: ["topic-suggestions"],
    queryFn: () =>
      api
        .get<{ suggestions: { name: string; description: string; n: number }[] }>("/topics/suggestions")
        .then((d) => d.suggestions),
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
      qc.invalidateQueries({ queryKey: ["topic-suggestions"] });
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
      // RL-903: Öffnen der Liste = gesehen. Badge/Zähler frisch ziehen.
      if ((topic.unread_count ?? 0) > 0) {
        api.post(`/topics/${topic.id}/seen`, {}).then(() => {
          qc.invalidateQueries({ queryKey: ["topics"] });
          qc.invalidateQueries({ queryKey: ["topics-unread"] });
        }).catch(() => {});
      }
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
      <PageHeader
        title="Meine Themen"
        description={HEADER_DESC}
        action={
          <Button variant="signal" onClick={() => setCreateOpen(true)}>
            <Plus /> Neues Thema
          </Button>
        }
      />

      {(suggestionsQuery.data?.length ?? 0) > 0 && (
        <div className="mt-6">
          <p className="text-sm font-medium text-foreground">
            Gerade aktuell im Rat — mit einem Klick als eigenes Thema übernehmen:
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {suggestionsQuery.data!.map((s) => (
              <button
                key={s.name}
                type="button"
                title={s.description}
                disabled={addMutation.isPending}
                onClick={() => addMutation.mutate({ name: s.name, description: s.description })}
                className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-[color,background-color,transform] duration-150 ease-out-strong hover:bg-primary/10 active:scale-[0.97] disabled:opacity-50"
              >
                <Plus className="h-3 w-3" /> {s.name}
                <span className="text-primary/60">· {s.n} Beschlüsse</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={(o) => { setCreateOpen(o); if (!o) { setName(""); setDescription(""); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Neues Thema</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => { e.preventDefault(); addMutation.mutate({ name, description }, { onSuccess: () => setCreateOpen(false) }); }}
            className="space-y-3"
          >
            <Input ref={nameInputRef} autoFocus placeholder="Name (z. B. Radwege)" value={name} onChange={(e) => setName(e.target.value)} required />
            <Textarea
              placeholder="Beschreibung — je konkreter, desto besser (z. B. Ausbau und Planung von Radwegen in Oldenburg)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              required
            />
            <div className="flex items-center justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={addMutation.isPending}>
                {addMutation.isPending ? "Hinzufügen…" : "Thema anlegen"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {topics.length === 0 ? (
          <EmptyState
            mascot="wave"
            title="Noch keine Themen"
            hint="Lege ein Thema an — wir melden uns, sobald der Rat etwas dazu beschließt."
            action={
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" /> Erstes Thema anlegen
              </Button>
            }
          />
        ) : (
          topics.map((t) => (
            <Card key={t.id} className="flex flex-col p-4">
              <div className="flex items-start justify-between gap-2">
                <h3 className="flex min-w-0 items-center gap-2 font-display text-base font-bold text-foreground">
                  <span className="truncate">{t.name}</span>
                  {(t.unread_count ?? 0) > 0 && (
                    <span className="shrink-0 rounded-full bg-signal px-2 py-0.5 text-[11px] font-bold text-signal-foreground">
                      {t.unread_count} neu
                    </span>
                  )}
                </h3>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    aria-label={`Thema „${t.name}" bearbeiten`}
                    onClick={() => startEdit(t)}
                    className="flex h-[30px] w-[30px] items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Thema „${t.name}" löschen`}
                    onClick={() => setConfirmDeleteId(t.id)}
                    disabled={deleteMutation.isPending}
                    className="flex h-[30px] w-[30px] items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{t.description}</p>
              {t.last_hit_title && (
                <Link
                  href={t.last_hit_id ? decisionHref(t.last_hit_id) : "#"}
                  className="mt-3 flex items-start gap-2 rounded-lg bg-muted/40 px-2.5 py-2 transition-colors hover:bg-muted"
                >
                  <span className="mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full bg-signal" aria-hidden />
                  <span className="min-w-0">
                    <span className="line-clamp-2 text-sm text-foreground">{t.last_hit_title}</span>
                    {t.last_hit_date && (
                      <span className="text-xs text-muted-foreground">{formatDate(t.last_hit_date)}</span>
                    )}
                  </span>
                </Link>
              )}
              <div className="mt-auto pt-3">
                {t.decision_count > 0 ? (
                  <button
                    type="button"
                    onClick={() => viewDecisions(t)}
                    className="text-sm font-medium text-primary hover:underline"
                  >
                    {t.decision_count} {t.decision_count === 1 ? "Beschluss" : "Beschlüsse"} insgesamt · alle ansehen
                  </button>
                ) : (
                  <p className="text-xs text-muted-foreground">Noch keine Treffer — wir melden uns, sobald der Rat dazu entscheidet.</p>
                )}
              </div>
            </Card>
          ))
        )}
      </div>

      <h2 className="mt-10 text-lg font-bold text-foreground">Ausschuss-Abos</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Benachrichtigungen, sobald eine Tagesordnung veröffentlicht wird — und noch einmal, wenn sie sich danach ändert.
      </p>
      <Card className="mt-3 divide-y divide-border">
        {committees.map((c) => {
          const subscribed = subscriptions.includes(c);
          return (
            <div key={c} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="min-w-0 text-sm text-foreground">{c}</span>
              <Switch
                checked={subscribed}
                aria-label={`${c} ${subscribed ? "abbestellen" : "abonnieren"}`}
                onCheckedChange={() => subMutation.mutate({ committee: c, subscribed })}
                disabled={subMutation.isPending}
              />
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

export default function TopicsPage() {
  // useSearchParams (Vorbefüllung ?neu=) braucht eine Suspense-Grenze.
  return (
    <Suspense>
      <TopicsInner />
    </Suspense>
  );
}
