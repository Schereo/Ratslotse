"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus, Sparkles, Loader2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { Topic } from "@/lib/types";
import {
  Button, CardListSkeleton, EmptyState, ErrorState, Input, PageHeader, Textarea, toast,
} from "@/components/ui";
import { TopicSheet, type Described } from "@/components/topic-sheet";
import { ThemenKarte } from "@/components/themen-karte";
import { FollowedVorgaenge } from "@/components/followed-vorgaenge";

const HEADER_DESC = "Deine Suchaufträge an den Rat — wir prüfen jede neue Sitzung und melden Treffer.";

export function TopicsView() {
  const qc = useQueryClient();
  const router = useRouter();
  const sp = useSearchParams();

  const [formOffen, setFormOffen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [editing, setEditing] = useState<Topic | null>(null);
  const [loeschFrage, setLoeschFrage] = useState<number | null>(null);
  const [kiText, setKiText] = useState("");
  const nameInputRef = useRef<HTMLInputElement>(null);

  /* ?neu= aus der URL (KI-Frage ohne Treffer → „Als Thema anlegen"): Namen
     vorbefüllen UND das Formular aufklappen. */
  useEffect(() => {
    const neu = sp.get("neu");
    if (neu) {
      setName((prev) => prev || neu);
      setFormOffen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ?zeig=abos: Deep-Link aus Tagesordnungs-Mails, die vor dem 28.08.2026
     verschickt wurden — damals lag der Abo-Block auf DIESER Seite. Die Mails
     sind draußen und werden noch geöffnet, also führt der alte Weg weiter ans
     Ziel, statt auf einer Seite ohne Abo-Block zu enden. `replace`, damit der
     Zurück-Knopf nicht in die Weiterleitung zurückspringt. */
  useEffect(() => {
    if (sp.get("zeig") === "abos") router.replace("/abos");
  }, [sp, router]);

  const topicsQuery = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<Topic[]>("/topics"),
  });

  /* Ein Blick auf die Übersicht lässt die Bubble verstummen (Tims Wunsch
     18.08.). Fire-and-forget: Ein Fehler darf die Seite nicht stören. */
  useEffect(() => {
    api.post("/topics/uebersicht-gesehen", {})
      .then(() => qc.invalidateQueries({ queryKey: ["topics-unread"] }))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const suggestionsQuery = useQuery({
    queryKey: ["topic-suggestions"],
    queryFn: () =>
      api.get<{ suggestions: { name: string; description: string; n: number }[] }>("/topics/suggestions")
        .then((d) => d.suggestions),
  });

  const addMutation = useMutation({
    mutationFn: (body: { name: string; description: string }) => api.post("/topics", body),
    onSuccess: () => {
      toast.success("Thema hinzugefügt.");
      setName(""); setDescription(""); setKiText(""); setFormOffen(false);
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["topic-suggestions"] });
    },
    onError: (err: Error) => toast.error(err instanceof ApiError ? err.message : "Konnte Thema nicht anlegen."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del(`/topics/${id}`),
    onSuccess: () => {
      toast.success("Thema gelöscht.");
      setLoeschFrage(null);
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["topics-unread"] });
    },
    onError: () => toast.error("Löschen fehlgeschlagen."),
  });

  /* „Beschreibung vorschlagen": Der Text ist es, an dem der Wächter später
     jeden neuen Beschluss misst — er lohnt die Mühe, und niemand muss ihn aus
     dem Nichts formulieren. Derselbe Endpunkt wie im Bearbeiten-Blatt. */
  const beschreibungMutation = useMutation({
    mutationFn: (n: string) => api.post<Described>("/topics/describe", { name: n }),
    onSuccess: (d) => {
      if (d.description) setDescription(d.description);
      setKiText(d.verdict === "plausibel"
        ? "Zu diesem Thema hat der Rat bisher nichts entschieden — wir melden uns, sobald es so weit ist."
        : "Vorschlag — kurz prüfen und anpassen.");
    },
    onError: () => setKiText("Der Vorschlag kam gerade nicht durch. Schreib die Beschreibung selbst."),
  });

  /* RL-903: Alle Treffer eines Themas als gelesen markieren. Hängt am
     „n neue"-Abzeichen (ein Klick räumt es weg) und am Öffnen der
     Trefferliste. Fire-and-forget — ein Fehler darf weder den Seitenwechsel
     aufhalten noch die Seite stören; beim nächsten Laden steht der Zähler
     dann eben noch. */
  const alleGelesen = (t: Topic) => {
    if ((t.unread_count ?? 0) <= 0) return;
    api.post(`/topics/${t.id}/seen`, {}).then(() => {
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["topics-unread"] });
    }).catch(() => {});
  };

  const anlegen = () => {
    const n = name.trim();
    if (!n || !description.trim()) return;
    addMutation.mutate({ name: n, description: description.trim() });
  };

  if (topicsQuery.isPending) {
    return (
      <div>
        <PageHeader title="Meine Themen" description={HEADER_DESC} />
        <div className="mt-6"><CardListSkeleton rows={3} /></div>
      </div>
    );
  }
  if (topicsQuery.isError) {
    return (
      <div>
        <PageHeader title="Meine Themen" description={HEADER_DESC} />
        <div className="mt-6">
          <ErrorState title="Die Themen kamen nicht durch"
            onRetry={() => void topicsQuery.refetch()} busy={topicsQuery.isFetching} />
        </div>
      </div>
    );
  }

  // Array.isArray statt ?? []: schützt vor einem alt-persistierten Cache, in dem
  // die Query-Daten fälschlich ein Objekt sind (siehe push-primer.tsx).
  const topics = Array.isArray(topicsQuery.data) ? topicsQuery.data : [];
  const vorschlaege = suggestionsQuery.data ?? [];

  return (
    <div>
      {/* Der Knopf heißt mobil nur „Neu": Der volle Text nahm dem Kopf so viel
          Breite, dass die Erklärzeile daneben auf 390 px in drei Zeilen umbrach. */}
      <PageHeader
        title="Meine Themen"
        description={HEADER_DESC}
        action={
          <Button variant="signal" onClick={() => { setFormOffen((o) => !o); setTimeout(() => nameInputRef.current?.focus(), 60); }}>
            <Plus />
            <span className="sm:hidden">Neu</span>
            <span className="hidden sm:inline">Neues Thema</span>
          </Button>
        }
      />

      {formOffen && (
        <div className="mt-4 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
          <form onSubmit={(e) => { e.preventDefault(); anlegen(); }} className="flex flex-col gap-3">
            <Input ref={nameInputRef} autoFocus placeholder="Name (z. B. Radwege)"
              value={name} onChange={(e) => setName(e.target.value)} required />
            <Textarea
              placeholder="Beschreibung — je konkreter, desto besser (z. B. Ausbau und Planung von Radwegen in Oldenburg)"
              value={description} onChange={(e) => { setDescription(e.target.value); setKiText(""); }}
              rows={3} required
            />
            <div className="-mt-1 flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                disabled={beschreibungMutation.isPending || !name.trim()}
                onClick={() => beschreibungMutation.mutate(name.trim())}
                className="inline-flex h-[30px] items-center gap-1.5 rounded-full border border-border bg-card px-3 text-[12.5px] font-medium text-foreground transition-colors hover:border-signal/50 hover:bg-signal/[0.04] disabled:opacity-50"
              >
                {beschreibungMutation.isPending
                  ? <Loader2 className="h-3 w-3 animate-spin text-signal" />
                  : <Sparkles className="h-3 w-3 text-signal" />}
                {beschreibungMutation.isPending ? "Formuliere Vorschlag …" : "Beschreibung vorschlagen"}
              </button>
              {kiText && <span className="text-[10.5px] text-muted-foreground">{kiText}</span>}
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={addMutation.isPending || !name.trim() || !description.trim()}>
                {addMutation.isPending ? "Hinzufügen…" : "Thema hinzufügen"}
              </Button>
              <Button type="button" variant="secondary"
                onClick={() => { setFormOffen(false); setName(""); setDescription(""); setKiText(""); }}>
                Abbrechen
              </Button>
            </div>
          </form>
        </div>
      )}

      {vorschlaege.length > 0 && (
        <div className="mt-5">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
            Gerade aktuell im Rat — mit einem Klick übernehmen
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {vorschlaege.map((s) => (
              <button
                key={s.name} type="button" title={s.description} disabled={addMutation.isPending}
                onClick={() => addMutation.mutate({ name: s.name, description: s.description })}
                className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-[color,background-color,transform] duration-150 ease-out-strong hover:bg-primary/10 active:scale-[0.97] disabled:opacity-50"
              >
                <Plus className="h-3 w-3" /> {s.name}
                {/* „n im letzten Jahr" statt „n Beschlüsse": Diese Zahl kommt
                    aus der Entitäten-Erkennung der letzten 365 Tage und ist
                    etwas anderes als die Trefferzahl auf der Karte
                    („Fliegerhorst" hier 12, dort 40+). Zwei verschiedene Zahlen
                    dürfen nicht dasselbe Wort tragen — sonst steht die nächste
                    Verwirrung schon fertig da (Tims Befund 16.08.). */}
                <span className="text-primary/60">· {s.n} im letzten Jahr</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {topics.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            mascot="wave"
            title="Noch keine Themen"
            hint="Lege ein Thema an — wir melden uns, sobald der Rat etwas dazu beschließt."
            action={<Button size="sm" onClick={() => setFormOffen(true)}><Plus className="h-4 w-4" /> Erstes Thema anlegen</Button>}
          />
        </div>
      ) : (
        /* Zwei Spalten ab 768 px Container-Breite (nicht Fensterbreite: neben
           der 240-px-Seitenleiste meint dieselbe Fensterbreite ein anderes
           Platzangebot als auf dem iPad).

           Bewusst ein `grid` und nicht die sonst vorgeschriebenen
           Flex-Spalten: Die Spalten-Bauform hält die Lesereihenfolge nur
           breit durch — schmal stapelte sie erst Spalte A und dann B, aus
           1,2,3,4 würde also 1,3,2,4. Und die Löcher, gegen die sie gedacht
           ist, entstehen hier kaum: Jede Karte trägt höchstens fünf Zeilen,
           die Höhen liegen also nah beieinander. `items-start` hält die
           Karten trotzdem auf ihrer eigenen Höhe. */
        <div className="@container mt-6">
          <div className="grid grid-cols-1 items-start gap-4 @3xl:grid-cols-2">
            {topics.map((t) => (
              <ThemenKarte
                key={t.id}
                topic={t}
                onEdit={() => setEditing(t)}
                onDelete={() => deleteMutation.mutate(t.id)}
                loeschFrage={loeschFrage === t.id}
                onLoeschFrage={(offen) => setLoeschFrage(offen ? t.id : null)}
                onAlleGelesen={() => alleGelesen(t)}
              />
            ))}
            <button
              type="button" onClick={() => { setFormOffen(true); setTimeout(() => nameInputRef.current?.focus(), 60); }}
              className="flex min-h-[180px] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border text-[13.5px] font-medium text-muted-foreground transition-colors hover:border-primary/45 hover:text-primary"
            >
              <Plus className="h-5 w-5" />
              Neues Thema anlegen
            </button>
          </div>
        </div>
      )}

      {/* Design 28a/W1: Verfolgte Vorgänge sind eine dritte Art von Abo neben
          Themen (breit, semantisch) und Ausschüssen (institutionell) — die
          engste: EINE Vorlage auf ihrem Weg durch die Gremien. */}
      <FollowedVorgaenge />

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-muted/60 px-4 py-3.5">
        <p className="text-[13.5px] text-muted-foreground">
          Ganze Gremien im Blick behalten? Abos benachrichtigen dich bei jeder neuen Tagesordnung.
        </p>
        <Link href="/abos" className="whitespace-nowrap text-[13px] font-medium text-primary hover:underline">
          Zu den Ausschuss-Abos →
        </Link>
      </div>

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
