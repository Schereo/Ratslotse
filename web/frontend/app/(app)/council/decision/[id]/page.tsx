"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink, FileText, FileDown, Users, Scale } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { DecisionDetail, CouncilDecision } from "@/lib/types";
import { Card, Spinner, EmptyState, formatDate, toast } from "@/components/ui";
import { OutcomeBadge, VoteBar } from "@/components/decision-ui";
import { cn } from "@/lib/utils";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <h2 className="text-sm font-semibold text-muted-foreground">{title}</h2>
      <div className="mt-2.5">{children}</div>
    </div>
  );
}

function presentMembers(att: DecisionDetail["attendance"]): number {
  return att.filter((a) => a.role === "vorsitz" || a.role === "mitglied" || !a.role).length;
}

export default function DecisionDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [data, setData] = useState<DecisionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get<DecisionDetail>(`/council/decision/${params.id}`)
      .then(setData)
      .catch((err) => { setError(true); if (err instanceof ApiError && err.status !== 404) toast.error(err.message); })
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) return <div className="py-10"><Spinner /></div>;
  if (error || !data) return <EmptyState icon={Scale} title="Beschluss nicht gefunden" />;

  const d = data.decision;
  const present = presentMembers(data.attendance);
  const byParty: Record<string, number> = {};
  for (const a of data.attendance) {
    if (a.role === "verwaltung" || a.role === "protokoll" || a.role === "gast") continue;
    const p = a.party || "—";
    byParty[p] = (byParty[p] ?? 0) + 1;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => router.back()} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Zurück
      </button>

      <div className="mt-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            {d.committee} · {formatDate(d.session_date)}{d.item_number ? ` · TOP ${d.item_number}` : ""}
          </p>
          <h1 className="mt-1 text-xl font-semibold text-foreground">{d.title}</h1>
        </div>
        <OutcomeBadge outcome={d.outcome} />
      </div>

      {d.beschluss && (
        <div className="mt-4 rounded-lg bg-muted/60 p-4 text-sm leading-relaxed text-foreground">{d.beschluss}</div>
      )}

      {(d.outcome === "angenommen" || d.outcome === "abgelehnt" || d.vote) && (
        <Section title="Abstimmung">
          <VoteBar d={d} presentCount={present || undefined} />
          {d.raw_result && (
            <p className="mt-2 text-xs italic text-muted-foreground">
              „{d.raw_result.replace(/^[-\s]+|[-\s]+$/g, "")}"
              {data.attendance.length > 0 ? " · keine namentliche Abstimmung im Protokoll" : ""}
            </p>
          )}
        </Section>
      )}

      {data.sub_votes.length > 0 && (
        <Section title="Anträge & Teilabstimmungen">
          <div className="flex flex-col gap-2">
            {data.sub_votes.map((s: CouncilDecision) => (
              <div key={s.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="min-w-0 text-sm">
                  {s.title}
                  {s.factions.length > 0 && (
                    <span className="ml-2 text-xs text-muted-foreground">({s.factions.join(", ")})</span>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {s.gegenstimmen ? <span className="text-xs text-muted-foreground">{s.gegenstimmen} Gegen</span> : null}
                  <OutcomeBadge outcome={s.outcome} />
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {data.vorlage_journey.length > 1 && (
        <Section title={`Weg der Vorlage ${d.vorlage_nr ?? ""}`}>
          <div className="ml-1 flex flex-col gap-3 border-l-2 border-border pl-4">
            {data.vorlage_journey.map((stop) => {
              const current = stop.ksinr === d.ksinr;
              return (
                <div key={`${stop.ksinr}-${stop.item_number}`} className="relative">
                  <span className={cn(
                    "absolute -left-[21px] top-1.5 h-2 w-2 rounded-full",
                    current ? "bg-primary" : "bg-border",
                  )} />
                  <span className={cn("text-sm", current && "font-medium text-foreground")}>
                    {stop.committee}
                  </span>
                  <span className="text-xs text-muted-foreground"> · {formatDate(stop.session_date)}{current ? " (hier)" : ""}</span>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {Object.keys(byParty).length > 0 && (
        <Section title={`Anwesenheit (${data.attendance.length})`}>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(byParty).sort((a, b) => b[1] - a[1]).map(([p, n]) => (
              <span key={p} className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{p} {n}</span>
            ))}
          </div>
        </Section>
      )}

      <div className="mt-6 flex flex-wrap gap-2 border-t border-border pt-5">
        {data.vorlage_url && (
          <a href={data.vorlage_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs text-foreground hover:bg-muted">
            <FileText className="h-3.5 w-3.5" /> Vorlage {d.vorlage_nr}
          </a>
        )}
        {d.protocol_url && (
          <a href={d.protocol_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs text-foreground hover:bg-muted">
            <FileDown className="h-3.5 w-3.5" /> Protokoll (PDF)
          </a>
        )}
        <a href={data.ratsinfo_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs text-foreground hover:bg-muted">
          <ExternalLink className="h-3.5 w-3.5" /> Im Ratsinfo
        </a>
        <Link href="/council" className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs text-foreground hover:bg-muted">
          <Users className="h-3.5 w-3.5" /> Alle Beschlüsse
        </Link>
      </div>
    </div>
  );
}
