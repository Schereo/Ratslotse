"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import Link from "next/link";
import { History, ArrowDown, ChevronRight, FileText, CalendarDays, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { vertrag } from "@/lib/vertrag";
import { sitzungHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { Button, formatDate } from "@/components/ui";
import { HeuteWidget } from "@/components/heute-widget";
import styles from "./seit-besuch-widget.module.css";

const labels = { protocol: "Protokoll ergänzt", agenda: "Neue Tagesordnung", agenda_change: "Tagesordnung geändert" };

export function SeitBesuchWidget() {
  const { user } = useAuth();
  const nextFocus = useRef<number | null>(null);
  const query = useInfiniteQuery({
    queryKey: ["today-updates", user?.id],
    initialPageParam: { offset: 0, since: "", until: "" },
    queryFn: async ({ pageParam }) => {
      // Explizites, idempotentes Besuchssignal; GET selbst bleibt lesend.
      if (pageParam.offset === 0) await api.post("/today/visit", {});
      const bounds = pageParam.since ? `&since=${encodeURIComponent(pageParam.since)}&until=${encodeURIComponent(pageParam.until)}` : "";
      return vertrag.get(`/today/updates?offset=${pageParam.offset}&limit=3${bounds}`);
    },
    getNextPageParam: (last, pages) => {
      const count = pages.reduce((n, page) => n + page.items.length, 0);
      return count < last.total ? { offset: count, since: last.since, until: last.until } : undefined;
    },
    enabled: !!user,
  });
  const data = query.data?.pages[0];
  const items = useMemo(() => query.data?.pages.flatMap(page => page.items) ?? [], [query.data]);
  useEffect(() => {
    if (nextFocus.current !== null && items.length > nextFocus.current) {
      document.getElementById("today-update-" + items[nextFocus.current].id)?.focus();
      nextFocus.current = null;
    }
  }, [items]);
  const counts = data ? [
    data.counts.protocol ? `${data.counts.protocol} ${data.counts.protocol === 1 ? "Protokoll" : "Protokolle"} ergänzt` : "",
    data.counts.agenda ? `${data.counts.agenda} neue ${data.counts.agenda === 1 ? "Tagesordnung" : "Tagesordnungen"}` : "",
    data.counts.agenda_change ? `${data.counts.agenda_change} ${data.counts.agenda_change === 1 ? "Tagesordnung" : "Tagesordnungen"} geändert` : "",
  ].filter(Boolean) : [];

  return (
    <HeuteWidget id="seit-besuch" title={data?.first_visit ? "Neu bei Ratslotse" : "Seit deinem letzten Besuch"}
      icon={<History className="h-5 w-5" />}>
      {query.isPending && <p role="status" className="text-hinweis text-muted-foreground">Dein Rückblick wird geladen.</p>}
      {query.isError && <div role="alert">
        <p className="text-hinweis text-muted-foreground">Der Rückblick konnte nicht {data ? "aktualisiert" : "geladen"} werden.</p>
        <Button variant="ghost" onClick={() => query.isFetchNextPageError ? query.fetchNextPage() : query.refetch()}
          disabled={query.isFetching} className="min-h-11 h-auto whitespace-normal">Erneut versuchen</Button>
      </div>}
      {data && <>
        <p className="text-hinweis text-muted-foreground">
          {data.first_visit ? "Dein erster Rückblick: die letzten sieben Tage." : `Seit ${formatDate(data.since)} – auch außerhalb deiner Themen.`}
        </p>
        {counts.length > 0 ? <>
          <p className="mt-3 flex flex-wrap items-baseline gap-x-2">
            <span className="font-display text-3xl font-bold tabular-nums">{data.total}</span>
            <span className="text-quelle text-muted-foreground">{data.total === 1 ? "Neuigkeit im Rat" : "Neuigkeiten im Rat"}</span>
          </p>
          <p className="mt-1 text-meta text-muted-foreground">{counts.join(" · ")}</p>
          <ul className="mt-3 divide-y divide-border">
            {items.map((item, index) => <li key={item.id} className={styles.arrival}>
              {(index === 0 || formatDate(items[index - 1].arrived) !== formatDate(item.arrived)) &&
                <p className="pt-3 text-meta text-muted-foreground">{formatDate(item.arrived)} · Bei Ratslotse ergänzt</p>}
              <Link id={"today-update-" + item.id} href={sitzungHref(item.ksinr)}
                aria-label={`${labels[item.kind]}: ${item.committee}. Sitzung vom ${formatDate(item.session_date)}. Bei Ratslotse seit ${formatDate(item.arrived)}.`}
                className={`group -mx-2 flex items-start gap-3 rounded-lg px-2 py-3.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${styles.row}`}>
                {item.kind === "protocol" ? <FileText className="mt-0.5 h-[18px] w-[18px] shrink-0 text-primary" aria-hidden /> : <CalendarDays className="mt-0.5 h-[18px] w-[18px] shrink-0 text-primary" aria-hidden />}
                <div className="min-w-0 flex-1">
                <p className="text-meta text-primary">{labels[item.kind]}</p>
                <p className="mt-1 text-quelle font-semibold group-hover:text-primary">{shortCommittee(item.committee)}</p>
                <p className="mt-1 text-meta text-muted-foreground">
                  Sitzung vom {formatDate(item.session_date)}
                  {item.kind === "protocol" && item.decision_count > 0 ? ` · ${item.decision_count} ${item.decision_count === 1 ? "Ergebnis" : "Ergebnisse"}` : ""}
                </p>
                </div>
                <ChevronRight className={`mt-0.5 h-4 w-4 shrink-0 text-muted-foreground ${styles.arrow}`} aria-hidden />
              </Link>
            </li>)}
          </ul>
          {query.hasNextPage && <Button variant="ghost" className="min-h-11 h-auto whitespace-normal"
            disabled={query.isFetching} onClick={() => { nextFocus.current = items.length; void query.fetchNextPage(); }}>
            {query.isFetchingNextPage ? "Wird geladen …" : `Weitere Neuigkeiten (${data.total - items.length})`}
            {query.isFetchingNextPage ? <Loader2 className="ml-2 h-4 w-4 motion-safe:animate-spin" aria-hidden /> : <ArrowDown className="ml-2 h-4 w-4" aria-hidden />}
          </Button>}
        </> : <div className="mt-3">
          <p className="text-quelle font-medium">Keine neuen Ratsunterlagen in diesem Zeitraum.</p>
          <p className="mt-1 text-hinweis text-muted-foreground">Hier erscheinen neue und geänderte Tagesordnungen sowie ergänzte Protokolle mit ihren Ergebnissen.</p>
        </div>}
      </>}
    </HeuteWidget>
  );
}
