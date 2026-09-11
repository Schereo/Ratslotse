"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { History, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { sitzungHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { Button, formatDate } from "@/components/ui";
import { HeuteWidget } from "@/components/heute-widget";
import styles from "./seit-besuch-widget.module.css";

type Updates = ApiAntwort<"/today/updates">;
type Update = Updates["items"][number];
type Group = Updates["groups"][number];
type Kind = Group["kind"];
const labels: Record<Kind, string> = { protocol: "Protokolle & Ergebnisse", agenda: "Neue Tagesordnungen", agenda_change: "Tagesordnungen geändert" };
const order: Kind[] = ["agenda", "agenda_change", "protocol"];

function range(first: string, last: string) {
  return first === last ? formatDate(first) : `${formatDate(first)} – ${formatDate(last)}`;
}

export function SeitBesuchWidget() {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["today-updates", user?.id],
    queryFn: async () => {
      await api.post("/today/visit", {});
      return vertrag.get("/today/updates");
    },
    enabled: !!user,
  });
  const data = query.data;
  return (
    <HeuteWidget id="seit-besuch" title={data?.first_visit ? "Neu bei Ratslotse" : "Seit deinem letzten Besuch"}
      icon={<History className="h-5 w-5" />}>
      {query.isPending && <p role="status" className="text-hinweis text-muted-foreground">Dein Rückblick wird geladen.</p>}
      {query.isError && <div role="alert">
        <p className="text-hinweis text-muted-foreground">Der Rückblick konnte nicht {data ? "aktualisiert" : "geladen"} werden.</p>
        <Button variant="ghost" onClick={() => query.refetch()} disabled={query.isFetching} className="min-h-11 h-auto whitespace-normal">Erneut versuchen</Button>
      </div>}
      {data && <>
        <p className="text-hinweis text-muted-foreground">
          {data.first_visit ? "Dein erster Rückblick: die letzten sieben Tage." : `Seit ${formatDate(data.since)} – auch außerhalb deiner Themen.`}
        </p>
        {data.total > 0 ? <div className="mt-3 divide-y divide-border">
          {order.map(kind => {
            const groups = data.groups.filter(group => group.kind === kind);
            return groups.length > 0 && <UpdateSection key={`${data.until}-${kind}`} kind={kind} groups={groups} window={data} userId={user!.id} />;
          })}
        </div> : <div className="mt-3">
          <p className="text-quelle font-medium">Keine neuen relevanten Ratsunterlagen in diesem Zeitraum.</p>
          <p className="mt-1 text-hinweis text-muted-foreground">Hier erscheinen Tagesordnungen für Sitzungen ab heute und ergänzte Protokolle mit ihren Ergebnissen.</p>
        </div>}
      </>}
    </HeuteWidget>
  );
}

function UpdateSection({ kind, groups, window, userId }: { kind: Kind; groups: Group[]; window: Updates; userId: number }) {
  const [expanded, setExpanded] = useState(false);
  const [visible, setVisible] = useState(4);
  const id = useId();
  const count = groups.reduce((n, group) => n + group.count, 0);
  const firstDate = groups.map(group => group.first_session_date).sort()[0];
  const lastDate = groups.map(group => group.last_session_date).sort().at(-1)!;
  return <div>
    <button type="button" aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(!expanded)}
      className={`-mx-2 flex w-[calc(100%+1rem)] items-center gap-3 rounded-lg px-2 py-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${styles.row}`}>
      <span className="min-w-[3ch] shrink-0 font-display text-3xl font-bold tabular-nums text-primary" aria-hidden>{count}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-quelle font-semibold"><span className="sr-only">{count} </span>{labels[kind]}</span>
        <span className="mt-1 block text-meta text-muted-foreground">
          {kind === "protocol" ? `${groups.length} ${groups.length === 1 ? "Gremium" : "Gremien"} · ${range(firstDate, lastDate)}` : `Für Sitzungen ab heute · nächster Termin ${formatDate(firstDate)}`}
        </span>
      </span>
      <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground ${styles.chevron} ${expanded ? styles.expanded : ""}`} aria-hidden />
    </button>
    <div id={id} hidden={!expanded}>
      {expanded && <div className={`pb-3 ${styles.arrival}`}>
        <ul className="divide-y divide-border/60">
          {groups.slice(0, visible).map(group => <li key={group.committee}>
            <UpdateGroup group={group} window={window} userId={userId} />
          </li>)}
        </ul>
        {visible < groups.length && <Button variant="ghost" className="min-h-11 h-auto whitespace-normal" onClick={() => setVisible(visible + 4)}>
          Weitere Gremien ({groups.length - visible})
        </Button>}
      </div>}
    </div>
  </div>;
}

function UpdateGroup({ group, window, userId }: { group: Group; window: Updates; userId: number }) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  if (group.count === 1) return <UpdateLink item={group.latest} />;
  return <div>
    <button type="button" aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(!expanded)}
      className={`flex w-full items-center gap-3 rounded-lg py-3 text-left text-quelle focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${styles.row}`}>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold" title={group.committee}>{shortCommittee(group.committee)}</span>
        <span className="mt-1 block text-meta text-muted-foreground">
          {group.count} {group.kind === "protocol" ? "Protokolle" : "Sitzungen"} · {range(group.first_session_date, group.last_session_date)}
        </span>
      </span>
      <ChevronDown className={`h-4 w-4 shrink-0 ${styles.chevron} ${expanded ? styles.expanded : ""}`} aria-hidden />
    </button>
    <div id={id} hidden={!expanded}>
      {expanded && <GroupEntries group={group} window={window} userId={userId} />}
    </div>
  </div>;
}

function GroupEntries({ group, window, userId }: { group: Group; window: Updates; userId: number }) {
  const nextFocus = useRef<number | null>(null);
  const id = useId();
  const query = useInfiniteQuery({
    queryKey: ["today-update-group", userId, window.since, window.until, group.kind, group.committee],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => vertrag.get(`/today/updates?offset=${pageParam}&limit=3&since=${encodeURIComponent(window.since)}&until=${encodeURIComponent(window.until)}&kind=${group.kind}&committee=${encodeURIComponent(group.committee)}`),
    getNextPageParam: (last, pages) => {
      const shown = pages.reduce((n, page) => n + page.items.length, 0);
      return shown < last.total ? shown : undefined;
    },
  });
  const items = useMemo(() => query.data?.pages.flatMap(page => page.items) ?? [], [query.data]);
  useEffect(() => {
    if (nextFocus.current !== null && items.length > nextFocus.current) {
      document.getElementById(`${id}-${items[nextFocus.current].id}`)?.focus();
      nextFocus.current = null;
    }
  }, [items, id]);
  return <div className={`ml-2 border-l border-border pl-3 ${styles.arrival}`}>
    {query.isPending && <p role="status" className="py-3 text-hinweis text-muted-foreground">Sitzungen werden geladen.</p>}
    {query.isError && <div role="alert" className="py-2 text-hinweis text-muted-foreground">
      <p>Die Sitzungen konnten nicht {items.length ? "aktualisiert" : "geladen"} werden.</p>
      <Button variant="ghost" className="min-h-11 h-auto whitespace-normal" disabled={query.isFetching}
        onClick={() => query.isFetchNextPageError ? query.fetchNextPage() : query.refetch()}>Erneut versuchen</Button>
    </div>}
    <ul className="divide-y divide-border/60">{items.map(item => <li key={item.id}><UpdateLink item={item} id={`${id}-${item.id}`} inGroup /></li>)}</ul>
    {query.hasNextPage && <Button variant="ghost" className="min-h-11 h-auto whitespace-normal" disabled={query.isFetching}
      onClick={() => { nextFocus.current = items.length; void query.fetchNextPage(); }}>
      {query.isFetchingNextPage ? "Wird geladen …" : `Weitere Sitzungen (${query.data!.pages[0].total - items.length})`}
      {query.isFetchingNextPage && <Loader2 className="ml-2 h-4 w-4 motion-safe:animate-spin" aria-hidden />}
    </Button>}
  </div>;
}

function UpdateLink({ item, inGroup = false, id }: { item: Update; inGroup?: boolean; id?: string }) {
  return <Link id={id} href={sitzungHref(item.ksinr)}
    aria-label={`${item.committee}. Sitzung vom ${formatDate(item.session_date)}${item.decision_count ? `. ${item.decision_count} Ergebnisse` : ""}. Bei Ratslotse ergänzt am ${formatDate(item.arrived)}.`}
    className={`group flex items-center gap-3 rounded-lg py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${styles.row}`}>
    <span className="min-w-0 flex-1">
      <span className="block text-quelle font-semibold group-hover:text-primary">{inGroup ? `Sitzung vom ${formatDate(item.session_date)}` : shortCommittee(item.committee)}</span>
      <span className="mt-1 block text-meta text-muted-foreground">
        {inGroup ? `Ergänzt am ${formatDate(item.arrived)}` : `Sitzung vom ${formatDate(item.session_date)}`}
        {item.kind === "protocol" && item.decision_count > 0 ? ` · ${item.decision_count} ${item.decision_count === 1 ? "Ergebnis" : "Ergebnisse"}` : ""}
      </span>
    </span>
    <ChevronRight className={`h-4 w-4 shrink-0 text-muted-foreground ${styles.arrow}`} aria-hidden />
  </Link>;
}
