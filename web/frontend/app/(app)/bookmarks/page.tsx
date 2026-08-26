"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Bookmark, CalendarDays, ChevronRight, FileCheck2, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { BookmarkEntry } from "@/lib/types";
import {
  Badge, Button, Card, CardListSkeleton, EmptyState, ErrorState, PageHeader, Switch,
  formatDate, toast,
} from "@/components/ui";
import { OutcomeDot, OUTCOME_META } from "@/components/decision-ui";

function status(entry: BookmarkEntry): { label: string; color: "slate" | "blue" | "green" | "amber" } {
  if (entry.decision?.outcome) {
    return { label: OUTCOME_META[entry.decision.outcome]?.label ?? "Entschieden", color: "green" };
  }
  if (entry.state === "upcoming") return { label: "Steht an", color: "blue" };
  if (entry.state === "protocol") return { label: "Protokoll liegt vor", color: "amber" };
  if (entry.state === "waiting") return { label: "Ergebnis folgt", color: "amber" };
  if (entry.kind === "session") return { label: "Sitzung", color: "slate" };
  return { label: "Gespeichert", color: "slate" };
}

function preview(entry: BookmarkEntry): string | null {
  const d = entry.decision;
  if (!d) return entry.agenda_item?.summary ?? null;
  return d.simple_summary || d.summary || d.beschluss || null;
}

function BookmarkCard({ entry, onDelete, onNotify, busy }: {
  entry: BookmarkEntry;
  onDelete: (id: number) => void;
  onNotify: (id: number, enabled: boolean) => void;
  busy: boolean;
}) {
  const meta = status(entry);
  const canNotify = entry.kind === "agenda_item" && !entry.decision;
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-start gap-2 p-4">
        <Link href={entry.url} className="group min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {entry.item_number && <span className="font-mono text-xs font-semibold text-muted-foreground">{entry.item_number}</span>}
            <Badge color={meta.color}>{meta.label}</Badge>
            {entry.kind === "session" && <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />}
            {entry.decision?.outcome && <OutcomeDot outcome={entry.decision.outcome} />}
          </div>
          <h2 className="mt-1.5 text-sm font-semibold leading-snug text-foreground group-hover:text-primary">
            {entry.title}
          </h2>
          {entry.session && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {entry.session.committee} · {formatDate(entry.session.session_date)}
            </p>
          )}
          {preview(entry) && (
            <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-muted-foreground">{preview(entry)}</p>
          )}
        </Link>
        <div className="flex shrink-0 items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => onDelete(entry.id)} disabled={busy}
            aria-label="Aus der Merkliste entfernen" title="Aus der Merkliste entfernen"
            className="h-8 w-8 text-muted-foreground hover:text-destructive">
            <Trash2 />
          </Button>
          <Button asChild variant="ghost" size="icon" className="h-8 w-8">
            <Link href={entry.url} aria-label="Eintrag öffnen" title="Eintrag öffnen"><ChevronRight /></Link>
          </Button>
        </div>
      </div>
      {canNotify && (
        <div className="flex items-center gap-3 border-t border-border bg-muted/30 px-4 py-3">
          <Bell className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-foreground">Beim Ergebnis benachrichtigen</p>
            <p className="text-xs text-muted-foreground">Sobald das öffentliche Protokoll verarbeitet ist.</p>
          </div>
          <Switch checked={entry.notify_result}
            onCheckedChange={(enabled) => onNotify(entry.id, enabled)}
            disabled={busy} aria-label="Beim Ergebnis benachrichtigen" />
        </div>
      )}
    </Card>
  );
}
function Section({ title, icon: Icon, entries, ...actions }: {
  title: string;
  icon: typeof Bookmark;
  entries: BookmarkEntry[];
  onDelete: (id: number) => void;
  onNotify: (id: number, enabled: boolean) => void;
  busy: boolean;
}) {
  if (!entries.length) return null;
  return (
    <section className="mt-7">
      <h2 className="flex items-center gap-2 font-display text-lg font-bold text-foreground">
        <Icon className="h-5 w-5 text-primary" aria-hidden /> {title}
        <span className="text-sm font-medium text-muted-foreground">{entries.length}</span>
      </h2>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {entries.map((entry) => <BookmarkCard key={entry.id} entry={entry} {...actions} />)}
      </div>
    </section>
  );
}

export default function BookmarksPage() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["bookmarks"],
    queryFn: () => api.get<{ bookmarks: BookmarkEntry[] }>("/bookmarks").then((d) => d.bookmarks),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/bookmarks/${id}`),
    onSuccess: () => { toast.success("Aus der Merkliste entfernt."); qc.invalidateQueries({ queryKey: ["bookmarks"] }); },
    onError: () => toast.error("Entfernen hat nicht geklappt."),
  });
  const notification = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      api.put(`/bookmarks/${id}/notification`, { notify_result: enabled }),
    onSuccess: (_data, variables) => {
      toast.success(variables.enabled ? "Du bekommst Bescheid, wenn das Ergebnis da ist." : "Ergebnis-Hinweis ausgeschaltet.");
      qc.invalidateQueries({ queryKey: ["bookmarks"] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Einstellung konnte nicht gespeichert werden."),
  });

  if (query.isPending) return <><PageHeader title="Merkliste" description="Deine gespeicherten Ratsinhalte an einem Ort." /><div className="mt-6"><CardListSkeleton rows={4} /></div></>;
  if (query.isError) return <><PageHeader title="Merkliste" description="Deine gespeicherten Ratsinhalte an einem Ort." /><div className="mt-6"><ErrorState title="Die Merkliste kam nicht durch" onRetry={() => void query.refetch()} busy={query.isFetching} /></div></>;

  const entries = query.data ?? [];
  const decided = entries.filter((e) => !!e.decision);
  const open = entries.filter((e) => e.kind === "agenda_item" && !e.decision);
  const saved = entries.filter((e) => e.kind === "session" || (e.kind === "decision" && !e.decision));
  const busy = remove.isPending || notification.isPending;
  const actions = {
    busy,
    onDelete: (id: number) => remove.mutate(id),
    onNotify: (id: number, enabled: boolean) => notification.mutate({ id, enabled }),
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Merkliste" description="TOPs entwickeln sich hier automatisch zum dokumentierten Ergebnis weiter." />
      {!entries.length ? (
        <div className="mt-6">
          <EmptyState icon={Bookmark} title="Deine Merkliste ist noch leer"
            hint="Merke dir Sitzungen, einzelne Tagesordnungspunkte oder Beschlüsse, die du später wiederfinden möchtest."
            action={<Button asChild variant="secondary"><Link href="/council?tab=sessions">Sitzungen ansehen</Link></Button>} />
        </div>
      ) : (
        <>
          <Section title="Offen" icon={Bookmark} entries={open} {...actions} />
          <Section title="Entschieden" icon={FileCheck2} entries={decided} {...actions} />
          <Section title="Gespeicherte Sitzungen" icon={CalendarDays} entries={saved} {...actions} />
        </>
      )}
    </div>
  );
}
