"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ArrowLeft, User, ExternalLink, Gavel } from "lucide-react";
import { MemberDetail } from "@/lib/types";
import { Card, Spinner, EmptyState, formatDate } from "@/components/ui";
import { PartyBadge } from "@/components/decision-ui";
import { useFetch } from "@/lib/use-fetch";

const sessionUrl = (ksinr: number) => `https://buergerinfo.oldenburg.de/si0057.php?__ksinr=${ksinr}`;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <h2 className="text-sm font-semibold text-muted-foreground">{title}</h2>
      <div className="mt-2.5">{children}</div>
    </div>
  );
}

function PersonInner() {
  const slug = useSearchParams().get("slug");
  const router = useRouter();
  const { data, loading } = useFetch<MemberDetail>(slug ? `/council/person/${slug}` : null);

  if (loading) return <div className="py-10"><Spinner /></div>;
  if (!data) return <EmptyState icon={User} title="Ratsmitglied nicht gefunden" hint="Zu diesem Namen gibt es keine Anwesenheitsdaten." />;

  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => router.back()} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Zurück
      </button>

      <div className="mt-3 flex items-center gap-2.5">
        <User className="h-6 w-6 shrink-0 text-muted-foreground" />
        <h1 className="text-xl font-semibold text-foreground">{data.name}</h1>
        {data.party && <PartyBadge party={data.party} />}
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">
        {data.n_sessions} {data.n_sessions === 1 ? "Sitzung" : "Sitzungen"} besucht
        {data.active_from && data.active_to && <> · aktiv {formatDate(data.active_from)} – {formatDate(data.active_to)}</>}
      </p>

      <div className="mt-4 rounded-lg border border-border bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
        Aus den Anwesenheitslisten der Protokolle (erfasst ab 2018). Präsenz zeigt Aktivität, nicht das Stimmverhalten —
        Protokolle nennen namentliche Einzelstimmen nur selten.
      </div>

      {data.committees.length > 0 && (
        <Section title="Gremien">
          <div className="space-y-2">
            {data.committees.map((c) => (
              <div key={c.committee} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm text-foreground">{c.committee}</span>
                  {c.chair && (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-primary/10 px-1.5 py-0.5 text-[11px] font-medium text-primary">
                      <Gavel className="h-3 w-3" /> Vorsitz
                    </span>
                  )}
                </div>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{c.n} {c.n === 1 ? "Sitzung" : "Sitzungen"}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {data.recent.length > 0 && (
        <Section title="Zuletzt anwesend">
          <div className="space-y-1.5">
            {data.recent.map((r) => (
              <a key={`${r.ksinr}-${r.session_date}`} href={sessionUrl(r.ksinr)} target="_blank" rel="noreferrer"
                className="group flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted">
                <span className="min-w-0 truncate text-foreground">{r.committee}</span>
                <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                  {formatDate(r.session_date)}
                  <ExternalLink className="h-3 w-3 text-muted-foreground/40 group-hover:text-primary" />
                </span>
              </a>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

export default function PersonPage() {
  return (
    <Suspense fallback={<div className="py-10"><Spinner /></div>}>
      <PersonInner />
    </Suspense>
  );
}
