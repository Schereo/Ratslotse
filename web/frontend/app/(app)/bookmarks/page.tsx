"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell, Bookmark, CalendarDays, ChevronDown, ChevronRight, FileCheck2,
  Search, Trash2, X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { BookmarkEntry, CouncilSession } from "@/lib/types";
import {
  Badge, Button, Card, CardListSkeleton, EmptyState, ErrorState, Input, PageHeader,
  Segmented, Switch, formatDate, toast,
} from "@/components/ui";
import { OutcomeDot, OUTCOME_META } from "@/components/decision-ui";

type Filter = "all" | "open" | "decided" | "sessions";
type Actions = {
  onDelete: (id: number) => void;
  onNotify: (id: number, enabled: boolean) => void;
  busy: boolean;
};

function status(entry: BookmarkEntry): { label: string; color: "slate" | "blue" | "green" | "amber" } {
  if (entry.decision?.outcome) {
    return { label: OUTCOME_META[entry.decision.outcome]?.label ?? "Entschieden", color: "green" };
  }
  if (entry.state === "group") return { label: "Sammelpunkt", color: "slate" };
  if (entry.state === "upcoming") return { label: "Steht an", color: "blue" };
  if (entry.state === "protocol") return { label: "Protokoll liegt vor", color: "amber" };
  if (entry.state === "waiting") return { label: "Sitzung vorbei · Protokoll ausstehend", color: "amber" };
  if (entry.kind === "session") return { label: "Sitzung", color: "slate" };
  return { label: "Gespeichert", color: "slate" };
}

function preview(entry: BookmarkEntry): string | null {
  const d = entry.decision;
  // Der Kartentext kennt Vorlage und Anlagen, die Kurzfassung nur den Titel —
  // dieselbe Reihenfolge wie in der Tagesordnung (`kurzfassung` in council/view).
  if (!d) return entry.agenda_item?.social_text || entry.agenda_item?.summary || null;
  return d.simple_summary || d.summary || d.official_text || null;
}

function category(entry: BookmarkEntry): Exclude<Filter, "all"> | "other" {
  if (entry.kind === "session") return "sessions";
  if (entry.decision) return "decided";
  if (entry.kind === "agenda_item") return "open";
  return "other";
}

function BookmarkCard({ entry, onDelete, onNotify, busy, showSession = true }: {
  entry: BookmarkEntry;
  showSession?: boolean;
} & Actions) {
  const meta = status(entry);
  const canNotify = entry.kind === "agenda_item" && !entry.decision && !entry.is_group;
  return (
    <Card className="flex h-full flex-col overflow-hidden p-0">
      <div className="flex flex-1 items-start gap-2 p-4">
        <Link href={entry.url} className="group min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {entry.item_number && <span className="font-mono text-xs font-semibold text-muted-foreground">{entry.item_number}</span>}
            <Badge color={meta.color}>{meta.label}</Badge>
            {entry.kind === "session" && <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />}
            {entry.decision?.outcome && <OutcomeDot outcome={entry.decision.outcome} />}
          </div>
          <h3 className="mt-1.5 text-wrap-pretty text-sm font-semibold leading-snug text-foreground group-hover:text-primary">
            {entry.title}
          </h3>
          {showSession && entry.session && (
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
      {entry.is_group && !entry.decision && (
        <div className="mt-auto border-t border-border bg-muted/30 px-4 py-3">
          <p className="text-sm font-medium text-foreground">Dieser TOP fasst Unterpunkte zusammen</p>
          <p className="text-xs text-muted-foreground">Bitte merke stattdessen den konkreten Antrag oder Unterpunkt, der dich interessiert.</p>
        </div>
      )}
      {canNotify && (
        <div data-notification-row className="mt-auto flex items-center gap-3 border-t border-border bg-muted/30 px-4 py-3">
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

function sessionSummary(entries: BookmarkEntry[]): string {
  const open = entries.filter((entry) => category(entry) === "open").length;
  const decided = entries.filter((entry) => category(entry) === "decided").length;
  const sessions = entries.filter((entry) => category(entry) === "sessions").length;
  return [
    open ? `${open} offen` : "",
    decided ? `${decided} entschieden` : "",
    sessions ? `${sessions} Sitzung${sessions === 1 ? "" : "en"}` : "",
  ].filter(Boolean).join(" · ");
}

function SessionCluster({ groupKey, session, entries, forceExpanded, ...actions }: {
  groupKey: string;
  session: CouncilSession | null;
  entries: BookmarkEntry[];
  forceExpanded: boolean;
} & Actions) {
  const [open, setOpen] = useState(false);
  const expanded = forceExpanded || open;
  const panelId = `bookmark-group-${groupKey.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  const committee = session?.committee || entries[0]?.subtitle || "Sitzung";
  const date = session?.session_date;
  const countLabel = `${entries.length} ${entries.length === 1 ? "Eintrag" : "Einträge"}`;

  return (
    <section>
      <button type="button" onClick={() => setOpen((value) => !value)}
        aria-expanded={expanded} aria-controls={panelId}
        aria-label={`${committee}${date ? ` vom ${formatDate(date)}` : ""}, ${countLabel} ${expanded ? "einklappen" : "anzeigen"}`}
        className="group flex w-full items-center gap-3 rounded-xl border border-border bg-card px-4 py-3.5 text-left shadow-sm transition-[border-color,background-color,transform] duration-150 hover:border-primary/30 hover:bg-muted/20 active:scale-[0.995]">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <CalendarDays className="h-5 w-5" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-display text-sm font-bold text-foreground sm:text-base">{committee}</span>
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">
            {date ? formatDate(date) : "Datum nicht verfügbar"}
            {session?.session_time ? ` · ${session.session_time} Uhr` : ""}
            {session?.location ? ` · ${session.location}` : ""}
          </span>
        </span>
        <span className="hidden shrink-0 text-right sm:block">
          <span className="block text-sm font-semibold tabular-nums text-foreground">{countLabel}</span>
          <span className="block text-xs text-muted-foreground">{sessionSummary(entries)}</span>
        </span>
        <span className="shrink-0 sm:hidden"><Badge>{entries.length}</Badge></span>
        <ChevronDown className={`h-5 w-5 shrink-0 text-muted-foreground transition-transform duration-200 ${expanded ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {expanded && (
        <div id={panelId} className="mt-2 grid gap-3 lg:grid-cols-2">
          {entries.map((entry) => (
            <BookmarkCard key={entry.id} entry={entry} showSession={false} {...actions} />
          ))}
        </div>
      )}
    </section>
  );
}

function groupBySession(entries: BookmarkEntry[]) {
  const groups = new Map<string, { session: CouncilSession | null; entries: BookmarkEntry[] }>();
  for (const entry of entries) {
    const key = entry.ksinr != null ? `session-${entry.ksinr}` : `entry-${entry.id}`;
    const current = groups.get(key);
    if (current) current.entries.push(entry);
    else groups.set(key, { session: entry.session, entries: [entry] });
  }
  return Array.from(groups, ([key, value]) => ({ key, ...value }));
}

export default function BookmarksPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
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

  const entries = query.data ?? [];
  const counts = useMemo(() => ({
    all: entries.length,
    open: entries.filter((entry) => category(entry) === "open").length,
    decided: entries.filter((entry) => category(entry) === "decided").length,
    sessions: entries.filter((entry) => category(entry) === "sessions").length,
  }), [entries]);
  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("de");
    return entries.filter((entry) => {
      if (filter !== "all" && category(entry) !== filter) return false;
      if (!needle) return true;
      const haystack = [
        entry.title, entry.subtitle, entry.item_number,
        entry.session?.committee, entry.session?.location,
        entry.agenda_item?.template_number, preview(entry),
      ].filter(Boolean).join(" ").toLocaleLowerCase("de");
      return haystack.includes(needle);
    });
  }, [entries, filter, search]);
  const grouped = useMemo(() => groupBySession(filtered), [filtered]);
  const busy = remove.isPending || notification.isPending;
  const actions: Actions = {
    busy,
    onDelete: (id) => remove.mutate(id),
    onNotify: (id, enabled) => notification.mutate({ id, enabled }),
  };

  if (query.isPending) return <><PageHeader title="Merkliste" description="Deine gespeicherten Ratsinhalte an einem Ort." /><div className="mt-6"><CardListSkeleton rows={4} /></div></>;
  if (query.isError) return <><PageHeader title="Merkliste" description="Deine gespeicherten Ratsinhalte an einem Ort." /><div className="mt-6"><ErrorState title="Die Merkliste kam nicht durch" onRetry={() => void query.refetch()} busy={query.isFetching} /></div></>;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Merkliste" description="Nach Sitzung gebündelt – damit auch viele gemerkte TOPs übersichtlich bleiben." />
      {!entries.length ? (
        <div className="mt-6">
          <EmptyState icon={Bookmark} title="Deine Merkliste ist noch leer"
            hint="Merke dir Sitzungen, einzelne Tagesordnungspunkte oder Beschlüsse, die du später wiederfinden möchtest."
            action={<Button asChild variant="secondary"><Link href="/council?tab=sessions">Sitzungen ansehen</Link></Button>} />
        </div>
      ) : (
        <>
          <Card className="mt-6 p-3 sm:p-4">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input data-search value={search} onChange={(event) => setSearch(event.target.value)}
                placeholder="Merkliste durchsuchen …" aria-label="Merkliste durchsuchen" className="pl-9 pr-10" />
              {search && (
                <button type="button" onClick={() => setSearch("")} aria-label="Suche leeren"
                  className="absolute right-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">
                  <X className="h-4 w-4" aria-hidden />
                </button>
              )}
            </div>
            <div className="mt-3">
              <Segmented value={filter} onChange={setFilter} tone="primary" className="grid w-full grid-cols-2 sm:flex"
                options={[
                  { value: "all", label: <>Alle <span className="tabular-nums opacity-75">{counts.all}</span></>, icon: Bookmark },
                  { value: "open", label: <>Offen <span className="tabular-nums opacity-75">{counts.open}</span></>, icon: Bell },
                  { value: "decided", label: <>Entschieden <span className="tabular-nums opacity-75">{counts.decided}</span></>, icon: FileCheck2 },
                  { value: "sessions", label: <>Sitzungen <span className="tabular-nums opacity-75">{counts.sessions}</span></>, icon: CalendarDays },
                ]} />
            </div>
          </Card>

          {filtered.length ? (
            <section className="mt-6" aria-label="Gefilterte Merkliste">
              <div className="mb-3 flex items-baseline justify-between gap-3">
                <h2 className="font-display text-lg font-bold text-foreground">
                  {filtered.length} {filtered.length === 1 ? "gemerkter Eintrag" : "gemerkte Einträge"}
                </h2>
                <p className="text-xs text-muted-foreground">
                  {grouped.length} {grouped.length === 1 ? "Sitzung" : "Sitzungen"}
                </p>
              </div>
              <div className="space-y-3">
                {grouped.map((group) => group.session || group.entries[0]?.ksinr != null ? (
                  <SessionCluster key={group.key} groupKey={group.key} session={group.session}
                    entries={group.entries} forceExpanded={Boolean(search.trim())} {...actions} />
                ) : (
                  <BookmarkCard key={group.key} entry={group.entries[0]} {...actions} />
                ))}
              </div>
            </section>
          ) : (
            <div className="mt-6">
              <EmptyState icon={Search} title="Nichts Passendes in deiner Merkliste"
                hint="Ändere den Filter oder suche mit einem anderen Begriff."
                action={<Button variant="secondary" onClick={() => { setSearch(""); setFilter("all"); }}>Filter zurücksetzen</Button>} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
