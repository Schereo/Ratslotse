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
  Button, Card, CardListSkeleton, ConfirmDialog, EmptyState, ErrorState, Input, PageHeader, Textarea,
  Dialog, DialogContent, DialogHeader, DialogTitle, Switch, formatDate, toast,
} from "@/components/ui";
import { decisionHref } from "@/lib/routes";
import { TopicSheet } from "@/components/topic-sheet";
import { committeeExplains, committeeRank, shortCommittee } from "@/lib/committees";
import { FollowedVorgaenge } from "@/components/followed-vorgaenge";

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
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [editing, setEditing] = useState<Topic | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const topicsQuery = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<Topic[]>("/topics"),
  });

  /* Ein Blick auf die Übersicht lässt die Bubble verstummen (Tims Wunsch
     18.08.): Vorher blieb der Zähler an „Meine Themen" stehen, bis man JEDES
     Thema einzeln geöffnet hatte. Was neu ist, sagt weiterhin das „n neu" an
     den Themen selbst — das hängt am Öffnen des jeweiligen Themas.
     Fire-and-forget: Ein Fehler darf die Seite nicht stören. */
  useEffect(() => {
    api.post("/topics/uebersicht-gesehen", {})
      .then(() => qc.invalidateQueries({ queryKey: ["topics-unread"] }))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // ?zeig=abos aus der URL (Deep-Link aus den Tagesordnungs-Mails: „Gremien-
  // Abos verwalten"): zum Ausschuss-Abo-Block springen und ihn kurz
  // hervorheben. Query statt #-Anker, weil nur Pfad + Query den Login-Umweg
  // über ?weiter= überleben (app/(app)/layout.tsx nimmt den Hash nicht mit).
  const [flashAbos, setFlashAbos] = useState(false);
  const jumpedAbos = useRef(false);
  const committeesData = committeesQuery.data;
  useEffect(() => {
    if (jumpedAbos.current || spNeu.get("zeig") !== "abos") return;
    if (!committeesData) return; // der Block existiert erst mit Daten
    jumpedAbos.current = true;
    setTimeout(() => {
      document.getElementById("ausschuss-abos")?.scrollIntoView({ behavior: "smooth", block: "start" });
      setFlashAbos(true);
      setTimeout(() => setFlashAbos(false), 2200);
    }, 50);
  }, [spNeu, committeesData]);

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

  // Bearbeitet wird im geteilten „Thema anpassen"-Blatt (components/topic-sheet.tsx)
  // — dasselbe, das auch das Onboarding zeigt. Es speichert selbst; hier bleibt
  // nur das Aufräumen danach.
  const startEdit = (t: Topic) => setEditing(t);

  const subMutation = useMutation({
    mutationFn: ({ committee, subscribed }: { committee: string; subscribed: boolean }) =>
      subscribed
        ? api.del("/subscriptions", { committee_name: committee })
        : api.post("/subscriptions", { committee_name: committee }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
    onError: () => toast.error("Abo konnte nicht geändert werden."),
  });

  /* RL-903: Die Trefferliste zu öffnen gilt als gesehen — bisher hing das am
     Dialog, den 28a/S4 durch den Sprung in die Suche ersetzt. Deshalb hier
     beim Klick, bevor navigiert wird (fire-and-forget: der Wechsel soll nicht
     auf den Server warten). */
  const markTopicSeen = (topic: Topic) => {
    if ((topic.unread_count ?? 0) <= 0) return;
    api.post(`/topics/${topic.id}/seen`, {}).then(() => {
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["topics-unread"] });
    }).catch(() => {});
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
        <PageHeader title="Meine Themen" description={HEADER_DESC} />
        <div className="mt-6">
          <ErrorState
            title="Die Themen kamen nicht durch"
            onRetry={() => void topicsQuery.refetch()}
            busy={topicsQuery.isFetching}
          />
        </div>
      </div>
    );
  }

  // Array.isArray statt ?? []: schützt vor einem alt-persistierten Cache, in dem
  // die Query-Daten fälschlich ein Objekt sind (siehe push-primer.tsx) — ein
  // .includes()/.map() darauf würde sonst die ganze Seite in die Boundary reißen.
  const topics = Array.isArray(topicsQuery.data) ? topicsQuery.data : [];
  const subscriptions = Array.isArray(subsQuery.data) ? subsQuery.data : [];
  const committees = Array.isArray(committeesQuery.data) ? committeesQuery.data : [];
  // Alltagsbezug zuerst, wie im Einrichtungs-Assistenten (Design 28a/R3).
  const sortedCommittees = committees.slice()
    .sort((a, b) => committeeRank(a) - committeeRank(b) || shortCommittee(a).localeCompare(shortCommittee(b), "de"));

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
                {/* „n im letzten Jahr" statt „n Beschlüsse": Diese Zahl kommt aus
                    der Entitäten-Erkennung der letzten 365 Tage und ist etwas
                    anderes als die Trefferzahl auf der Karte („Fliegerhorst"
                    hier 12, dort 40+). Zwei verschiedene Zahlen dürfen nicht
                    dasselbe Wort tragen — sonst steht die nächste Verwirrung
                    schon fertig da. */}
                <span className="text-primary/60">· {s.n} im letzten Jahr</span>
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
                  /* Design 28a/S4: führt in die echte Suche statt in einen Dialog.
                     Der Dialog konnte weder filtern noch sortieren noch teilen und
                     war mobil eine Scroll-Wand — die Suchseite kann das alles längst.

                     `cat=all` ist Pflicht, nicht Geschmack: Die Suchseite steht
                     sonst auf „nur Beschlüsse" und wirft alle Berichte aus der
                     Liste, die diese Zahl mitzählt. Genau das war Tims Befund
                     (Build 12): Karte „40+", Liste 25. */
                  <Link
                    href={`/council?tab=decisions&cat=all&topic=${t.id}`}
                    onClick={() => markTopicSeen(t)}
                    className="text-sm font-medium text-primary hover:underline"
                  >
                    {/* „insgesamt" behauptete Vollständigkeit, die der
                        Treffer-Deckel nicht einlöst — und stand im Widerspruch
                        zur Live-Zahl im Bearbeiten-Blatt (Tim, 15.08.). Das
                        „+" sagt jetzt offen, wann die Zahl der Deckel ist:
                        vorher trug JEDES Thema dieselbe glatte 25. */}
                    {t.decision_count}{t.decision_count_capped ? "+" : ""}{" "}
                    {t.decision_count === 1 && !t.decision_count_capped ? "Beschluss" : "Beschlüsse"} · alle ansehen
                  </Link>
                ) : t.matched === false ? (
                  /* Zwei Nullen, die gleich aussahen — und von denen eine log:
                     Bis zum 28.08.2026 schrieb nur der Wochenlauf Treffer, ein
                     neues Thema stand also tagelang auf 0. Darunter stand
                     „Noch keine Treffer — wir melden uns, sobald der Rat dazu
                     entscheidet", und bei „Schulbegleitung" (34 Beschlüsse seit
                     2018) war das keine fehlende Zahl, sondern eine falsche
                     Aussage über den Rat: als sei das Thema mit dem Anlegen
                     entstanden. Jetzt wird beim Anlegen gerechnet; bleibt die
                     Rechnung doch einmal aus, sagt die Karte genau das. */
                  <p className="text-xs text-muted-foreground">Treffer werden noch gezählt.</p>
                ) : (
                  <p className="text-xs text-muted-foreground">Der Rat hat dazu bisher nichts entschieden — Lotti meldet sich, sobald das passiert.</p>
                )}
              </div>
            </Card>
          ))
        )}
      </div>

      {/* Design 28a/W1: Verfolgte Vorgänge sind eine dritte Art von Abo neben
          Themen (breit, semantisch) und Ausschüssen (institutionell) — die
          engste: EINE Vorlage auf ihrem Weg durch die Gremien. Der Abschnitt
          erscheint erst, wenn es etwas zu zeigen gibt; angelegt wird ein
          Follow auf der Beschluss-Seite, nicht hier. */}
      <FollowedVorgaenge />

      <h2 id="ausschuss-abos" className="mt-10 scroll-mt-24 text-lg font-bold text-foreground">Ausschuss-Abos</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Benachrichtigungen, sobald eine Tagesordnung veröffentlicht wird — und noch einmal, wenn sie sich danach ändert.
      </p>
      <Card className={`mt-3 divide-y divide-border transition-shadow ${flashAbos ? "ring-2 ring-primary" : ""}`}>
        {/* Design 28a/R3: Dieselbe Liste steht im Einrichtungs-Assistenten mit
            Kurznamen, Alltags-Reihenfolge und einem erklärenden Satz — hier
            standen bis zuletzt die amtlichen Langnamen in Ratsinfo-Reihenfolge.
            Wer den Assistenten gerade durchlaufen hatte, fand seine Auswahl
            nicht wieder. Die Helfer lagen fertig in lib/committees.ts. */}
        {sortedCommittees.map((c) => {
          const subscribed = subscriptions.includes(c);
          const explain = committeeExplains(c);
          return (
            <div key={c} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <div className="min-w-0">
                {/* Der amtliche Name bleibt im title erreichbar. */}
                <p className="truncate text-sm font-medium text-foreground" title={c}>{shortCommittee(c)}</p>
                {explain && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{explain}</p>}
              </div>
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

      {editing && (
        <TopicSheet topic={editing} nameEditable onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            toast.success("Thema aktualisiert.");
            qc.invalidateQueries({ queryKey: ["topics"] });
          }} />
      )}

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
