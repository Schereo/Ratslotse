"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink, FileText, FileDown, Users, Newspaper, Tag } from "lucide-react";
import { DecisionDetail, CouncilDecision } from "@/lib/types";
import { Card, DetailSkeleton, EmptyState, formatDate } from "@/components/ui";
import { OutcomeBadge, VoteBar, FieldBadge, PartyBadge, DecisionLinkCard, formatEuro, normalizeParty, PartyAttendanceBadge } from "@/components/decision-ui";
import { decisionHref, themaHref } from "@/lib/routes";
import { ShareButton } from "@/components/share-button";
import { cn } from "@/lib/utils";
import { useFetch } from "@/lib/use-fetch";

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

function DecisionDetailInner() {
  const id = useSearchParams().get("id");
  const router = useRouter();
  const { data, loading } = useFetch<DecisionDetail>(id ? `/council/decision/${id}` : null);

  if (loading) return <DetailSkeleton />;
  if (!data) return <EmptyState mascot="confused" title="Beschluss nicht gefunden" />;

  const d = data.decision;
  const unanimous = d.outcome === "angenommen"
    && (d.vote === "einstimmig" || ((d.gegenstimmen ?? 0) === 0 && (d.enthaltungen ?? 0) === 0));
  const present = presentMembers(data.attendance);
  const byParty: Record<string, number> = {};
  for (const a of data.attendance) {
    if (a.role === "verwaltung" || a.role === "protokoll" || a.role === "gast") continue;
    const p = normalizeParty(a.party || "—");
    byParty[p] = (byParty[p] ?? 0) + 1;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center justify-between gap-3">
        <button onClick={() => router.back()} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Zurück
        </button>
        <ShareButton path={decisionHref(d.id)} title={d.title ?? "Beschluss des Oldenburger Stadtrats"} />
      </div>

      <div className="mt-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            {d.committee} · {formatDate(d.session_date)}{d.item_number ? ` · TOP ${d.item_number}` : ""}
          </p>
          <h1 className="mt-1 text-xl font-semibold text-foreground">{d.title}</h1>
          {(d.policy_field || d.policy_tags.length > 0) && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <FieldBadge field={d.policy_field} />
              {d.policy_tags.map((t) => (
                <span key={t} className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{t}</span>
              ))}
            </div>
          )}
          {data.entities.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {data.entities.map((e) => (
                <Link key={e.slug} href={themaHref(e.slug)}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs text-foreground transition-colors hover:bg-muted"
                  title={`Alle Beschlüsse zu „${e.name}"`}>
                  <Tag className="h-3 w-3 text-muted-foreground" />{e.name}
                </Link>
              ))}
            </div>
          )}
        </div>
        <OutcomeBadge outcome={d.outcome} />
      </div>

      {d.beschluss && (
        <div className="mt-4 rounded-lg bg-muted/60 p-4 text-sm leading-relaxed text-foreground">{d.beschluss}</div>
      )}

      {d.amount_eur != null && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-sm font-semibold text-emerald-700 dark:text-emerald-400">
            {formatEuro(d.amount_eur)}
          </span>
          <span className="text-xs text-muted-foreground">im Beschlusstext genannter Betrag (automatisch erkannt)</span>
        </div>
      )}

      {d.parties.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Antrag von:</span>
          {d.parties.map((p) => <PartyBadge key={p} party={p} />)}
        </div>
      )}

      {(d.outcome === "angenommen" || d.outcome === "abgelehnt" || d.vote) && (
        <Section title="Abstimmung">
          <VoteBar d={d} presentCount={present || undefined} />
          {unanimous && data.present_parties.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Einstimmig — dafür stimmten die anwesenden Fraktionen:</span>
              {data.present_parties.map((p) => <PartyBadge key={p} party={p} />)}
            </div>
          )}
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
              <PartyAttendanceBadge key={p} party={p} n={n} />
            ))}
          </div>
        </Section>
      )}

      {data.similar.length > 0 && (
        <Section title="Ähnliche Beschlüsse">
          <div className="space-y-2">
            {data.similar.map((s) => (
              <DecisionLinkCard key={s.id} id={s.id} title={s.title} committee={s.committee}
                session_date={s.session_date} field={s.policy_field} score={s.score} />
            ))}
          </div>
        </Section>
      )}

      {data.news.length > 0 && (
        <Section title="In der Presse">
          <div className="space-y-2">
            {data.news.map((n) => (
              <Link key={`${n.catalog}-${n.refid}`} href={`/nwz?catalog=${n.catalog}&refid=${encodeURIComponent(n.refid)}`} className="block">
                <Card className="card-interactive group flex items-center gap-3 p-3">
                  <Newspaper className="h-4 w-4 shrink-0 self-center text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">{n.title}</p>
                    <p className="text-xs text-muted-foreground">NWZ{n.pub_date ? ` · ${formatDate(n.pub_date)}` : ""}</p>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 shrink-0 self-center text-muted-foreground/40 group-hover:text-primary" />
                </Card>
              </Link>
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

export default function DecisionDetailPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <DecisionDetailInner />
    </Suspense>
  );
}
