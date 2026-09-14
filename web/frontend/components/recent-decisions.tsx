"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Clock3, ChevronRight } from "lucide-react";
import { formatDate } from "@/components/ui";
import { decisionHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { HeuteWidget, type WidgetSize } from "@/components/heute-widget";
import { cn } from "@/lib/utils";
import { getRecentDecisions, type RecentDecision } from "@/lib/recent";

/**
 * „Zuletzt angesehen" auf dem Dashboard — die letzten besuchten Beschlüsse aus
 * localStorage. Rendert nichts, solange es keine Historie gibt (Erstbesuch).
 *
 * Die Aufräum-Runde (#330) hat diese Datei zu Recht als toten Code entfernt:
 * Sie war fertig, wurde aber von keiner Seite gerendert. Design 28a/S5 nennt
 * genau das als Fundstelle — die Komponente gehört unter das „Heute"-Grid, dort
 * schließt sie eine Sackgasse. Wieder eingesetzt, jetzt mit Aufrufer.
 */
export function RecentDecisions({ className, size }: { className?: string; size?: WidgetSize }) {
  const [expanded, setExpanded] = useState(false);
  const [items, setItems] = useState<RecentDecision[]>([]);
  useEffect(() => {
    setItems(getRecentDecisions().slice(0, 5));
  }, []);

  if (items.length === 0) return null;
  return (
    <HeuteWidget id="zuletzt-angesehen" title="Zuletzt angesehen" icon={Clock3} size={size} className={className}>
      {detail => <>
        <div className={cn("divide-y divide-border/60", detail === "expanded" && items.length > 1 && "grid grid-cols-2 gap-x-6 divide-y-0")}>
          {items.slice(0, detail === "compact" && !expanded ? 3 : 5).map(d => (
            <Link key={d.id} href={decisionHref(d.id)}
              className="group flex min-w-0 items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
              <div className="min-w-0 flex-1">
                <p className={cn("text-quelle font-semibold text-foreground", detail === "expanded" ? "line-clamp-2" : "truncate")}>{d.title}</p>
                <p className="mt-1 text-meta text-muted-foreground">{shortCommittee(d.committee)} · {formatDate(d.session_date)}</p>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-safe:group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden />
            </Link>
          ))}
        </div>
        {detail === "compact" && !expanded && items.length > 3 && <button type="button" onClick={() => setExpanded(true)} className="mt-1 min-h-11 text-hinweis font-medium text-primary hover:underline">
          Weitere ansehen ({items.length - 3})
        </button>}
      </>}
    </HeuteWidget>
  );
}
