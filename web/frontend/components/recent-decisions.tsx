"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { History, ChevronRight } from "lucide-react";
import { Card, formatDate } from "@/components/ui";
import { decisionHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { getRecentDecisions, type RecentDecision } from "@/lib/recent";

/**
 * „Zuletzt angesehen" auf dem Dashboard — die letzten besuchten Beschlüsse aus
 * localStorage. Rendert nichts, solange es keine Historie gibt (Erstbesuch).
 */
export function RecentDecisions({ className }: { className?: string }) {
  const [items, setItems] = useState<RecentDecision[]>([]);
  useEffect(() => {
    setItems(getRecentDecisions().slice(0, 5));
  }, []);

  if (items.length === 0) return null;
  return (
    <div className={className}>
      <h2 className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
        <History className="h-4 w-4" /> Zuletzt angesehen
      </h2>
      <Card className="mt-3 divide-y divide-border p-0">
        {items.map((d) => (
          <Link
            key={d.id}
            href={decisionHref(d.id)}
            className="group flex items-center gap-3 p-3 transition-colors first:rounded-t-xl last:rounded-b-xl hover:bg-muted/50"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">{d.title}</p>
              <p className="text-xs text-muted-foreground">
                {shortCommittee(d.committee)} · {formatDate(d.session_date)}
              </p>
            </div>
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/40 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
          </Link>
        ))}
      </Card>
    </div>
  );
}
