"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, ExternalLink, ChevronDown, Landmark, Scale, Users, FileText } from "lucide-react";
import { api, qs, ApiError } from "@/lib/api";
import { useDebounce } from "@/lib/use-debounce";
import {
  CouncilSession, SessionDetail, AgendaItem, CouncilDecision, DecisionOutcome,
} from "@/lib/types";
import {
  Badge, Card, CardListSkeleton, EmptyState, Input, PageHeader, Select, Spinner, formatDate, toast,
} from "@/components/ui";
import { cn } from "@/lib/utils";

type Scope = "all" | "upcoming" | "recent";
type Tab = "sessions" | "decisions";

const sessionUrl = (ksinr: number) => `https://buergerinfo.oldenburg.de/si0057.php?__ksinr=${ksinr}`;

function itemMatches(it: AgendaItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return it.title.toLowerCase().includes(q) || (it.vorlage_nr?.toLowerCase().includes(q) ?? false);
}

function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  if (!q || !text) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded bg-amber-200 px-0.5 text-foreground dark:bg-amber-700/60">
        {text.slice(idx, idx + q.length)}
      </mark>
      {text.slice(idx + q.length)}
    </>
  );
}

const OUTCOME_META: Record<DecisionOutcome, { label: string; cls: string }> = {
  angenommen: { label: "Angenommen", cls: "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300" },
  abgelehnt: { label: "Abgelehnt", cls: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" },
  vertagt: { label: "Vertagt", cls: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300" },
  zur_kenntnis: { label: "Zur Kenntnis", cls: "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300" },
  kein_beschluss: { label: "Kein Beschluss", cls: "bg-muted text-muted-foreground" },
};

function OutcomeBadge({ outcome }: { outcome: DecisionOutcome | null }) {
  if (!outcome) return null;
  const m = OUTCOME_META[outcome] ?? OUTCOME_META.kein_beschluss;
  return (
    <span className={cn("shrink-0 whitespace-nowrap rounded-md px-2.5 py-0.5 text-xs font-medium", m.cls)}>
      {m.label}
    </span>
  );
}

function VoteLine({ d }: { d: CouncilDecision }) {
  const parts: string[] = [];
  if (d.vote) parts.push(d.vote);
  if (d.gegenstimmen) parts.push(`${d.gegenstimmen} Gegenstimmen`);
  if (d.enthaltungen) parts.push(`${d.enthaltungen} Enthaltungen`);
  if (parts.length === 0 && d.factions.length === 0) return null;
  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-2">
      {parts.length > 0 && (
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Scale className="h-3.5 w-3.5" /> {parts.join(" · ")}
        </span>
      )}
      {d.factions.map((f) => (
        <span key={f} className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{f}</span>
      ))}
    </div>
  );
}

function DecisionCard({ d, query }: { d: CouncilDecision; query: string }) {
  const isSub = d.kind === "subvote";
  return (
    <Card className={cn("p-4", isSub && "border-l-2 border-l-border bg-muted/30")}>
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs text-muted-foreground">
          {isSub ? `Teilabstimmung · TOP ${d.parent_item}` : `${d.committee} · ${formatDate(d.session_date)}`}
        </span>
        <OutcomeBadge outcome={d.outcome} />
      </div>
      <div className="mt-1.5 font-medium text-foreground">
        {!isSub && d.item_number && <span className="text-muted-foreground">TOP {d.item_number} · </span>}
        <Highlight text={d.title ?? ""} query={query} />
      </div>
      {d.beschluss && (
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          <Highlight text={d.beschluss} query={query} />
        </p>
      )}
      <VoteLine d={d} />
      {!isSub && (
        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs">
          {!query && <span className="text-muted-foreground">{d.committee} · {formatDate(d.session_date)}</span>}
          {d.protocol_url && (
            <a href={d.protocol_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
              <FileText className="h-3.5 w-3.5" /> Protokoll
            </a>
          )}
          <a href={sessionUrl(d.ksinr)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-muted-foreground hover:text-primary">
            <ExternalLink className="h-3.5 w-3.5" /> Zur Sitzung
          </a>
        </div>
      )}
    </Card>
  );
}

const OUTCOME_FILTERS: { value: string; label: string }[] = [
  { value: "", label: "Alle" },
  { value: "angenommen", label: "Angenommen" },
  { value: "abgelehnt", label: "Abgelehnt" },
  { value: "vertagt", label: "Vertagt" },
];

function DecisionsTab({ committees }: { committees: string[] }) {
  const [q, setQ] = useState("");
  const [committee, setCommittee] = useState("");
  const [outcome, setOutcome] = useState("");
  const [decisions, setDecisions] = useState<CouncilDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const debouncedQ = useDebounce(q, 350);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ decisions: CouncilDecision[] }>(
        `/council/decisions${qs({ q, committee, outcome, limit: 150 })}`,
      );
      setDecisions(data.decisions);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, [q, committee, outcome]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, outcome]);

  const query = q.trim();

  return (
    <div>
      <Card className="mt-4 p-4">
        <div className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder="Beschlüsse durchsuchen (z. B. Haushalt, Radwege)…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select value={committee} onChange={(e) => setCommittee(e.target.value)}>
              <option value="">Alle Ausschüsse</option>
              {committees.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <div className="flex gap-1 overflow-x-auto rounded-md bg-muted p-1">
              {OUTCOME_FILTERS.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setOutcome(o.value)}
                  className={cn(
                    "flex-1 whitespace-nowrap rounded-sm px-2 py-1.5 text-sm font-medium transition-colors",
                    outcome === o.value ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div className="mt-6">
        {loading ? (
          <CardListSkeleton rows={5} />
        ) : decisions.length === 0 ? (
          <EmptyState icon={Scale} title="Keine Beschlüsse gefunden" hint="Andere Suche/Filter — oder das Protokoll ist noch nicht veröffentlicht." />
        ) : (
          <div className="space-y-2.5">
            <p className="text-sm font-medium text-muted-foreground">
              {decisions.length} {decisions.length === 1 ? "Beschluss" : "Beschlüsse"}
            </p>
            {decisions.map((d) => <DecisionCard key={d.id} d={d} query={query} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function AgendaRow({ it, query, outcome }: { it: AgendaItem; query: string; outcome?: DecisionOutcome | null }) {
  const hit = itemMatches(it, query);
  return (
    <li className={cn("flex flex-wrap items-start gap-x-3 gap-y-1 rounded-md px-2 py-2", hit && "bg-amber-50 dark:bg-amber-950/40")}>
      <span className="shrink-0 text-xs font-medium text-muted-foreground">{it.item_number}</span>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-foreground"><Highlight text={it.title} query={query} /></p>
        {it.vorlage_nr && <p className="text-xs text-muted-foreground">Vorlage <Highlight text={it.vorlage_nr} query={query} /></p>}
      </div>
      {outcome ? <OutcomeBadge outcome={outcome} /> : !it.is_public ? <Badge color="amber">nichtöffentlich</Badge> : null}
    </li>
  );
}

function AttendanceSection({ detail }: { detail: SessionDetail }) {
  const att = detail.attendance ?? [];
  if (att.length === 0) return null;
  const byParty: Record<string, number> = {};
  for (const a of att) {
    if (a.role === "verwaltung" || a.role === "protokoll" || a.role === "gast") continue;
    const p = a.party || "—";
    byParty[p] = (byParty[p] ?? 0) + 1;
  }
  return (
    <div className="mt-4 border-t border-border pt-3">
      <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <Users className="h-4 w-4" /> Anwesenheit ({att.length})
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {Object.entries(byParty).sort((a, b) => b[1] - a[1]).map(([p, n]) => (
          <span key={p} className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{p} {n}</span>
        ))}
      </div>
    </div>
  );
}

function SessionsTab({ committees }: { committees: string[] }) {
  const [q, setQ] = useState("");
  const [committee, setCommittee] = useState("");
  const [scope, setScope] = useState<Scope>("upcoming");
  const [sessions, setSessions] = useState<CouncilSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [detail, setDetail] = useState<Record<number, SessionDetail>>({});
  const [detailLoading, setDetailLoading] = useState<Record<number, boolean>>({});
  const debouncedQ = useDebounce(q, 350);

  const load = useCallback(async () => {
    setLoading(true);
    setHasSearched(true);
    setExpanded({});
    try {
      const effectiveScope = q || committee ? "all" : scope;
      const data = await api.get<{ sessions: CouncilSession[] }>(
        `/council/sessions${qs({ q, committee, scope: effectiveScope, limit: 100 })}`,
      );
      setSessions(data.sessions);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, [q, committee, scope]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, scope]);

  const toggle = async (s: CouncilSession) => {
    const willExpand = !expanded[s.ksinr];
    setExpanded((prev) => ({ ...prev, [s.ksinr]: willExpand }));
    if (willExpand && !detail[s.ksinr]) {
      setDetailLoading((prev) => ({ ...prev, [s.ksinr]: true }));
      try {
        const d = await api.get<SessionDetail>(`/council/session/${s.ksinr}`);
        setDetail((prev) => ({ ...prev, [s.ksinr]: d }));
      } catch {
        toast.error("Sitzung konnte nicht geladen werden.");
        setExpanded((prev) => ({ ...prev, [s.ksinr]: false }));
      } finally {
        setDetailLoading((prev) => ({ ...prev, [s.ksinr]: false }));
      }
    }
  };

  const query = q.trim();

  return (
    <div>
      <Card className="mt-4 p-4">
        <div className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder="In Tagesordnungen suchen (z. B. Bebauungsplan)…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select value={committee} onChange={(e) => setCommittee(e.target.value)}>
              <option value="">Alle Ausschüsse</option>
              {committees.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <div className="flex gap-1 rounded-md bg-muted p-1">
              {(["upcoming", "recent", "all"] as Scope[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => { setScope(s); setQ(""); setCommittee(""); }}
                  className={cn(
                    "flex-1 rounded-sm px-2 py-1.5 text-sm font-medium transition-colors",
                    scope === s && !q && !committee ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {s === "upcoming" ? "Kommend" : s === "recent" ? "Vergangen" : "Alle"}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div className="mt-6">
        {loading ? (
          <CardListSkeleton rows={5} />
        ) : sessions.length === 0 ? (
          <EmptyState icon={Landmark} title={hasSearched ? "Keine Sitzungen gefunden" : "Noch keine Sitzungen vorhanden"} hint={hasSearched ? "Versuche andere Suchbegriffe oder Filter." : undefined} />
        ) : (
          <div className="space-y-3">
            <p className="text-sm font-medium text-muted-foreground">{sessions.length} {sessions.length === 1 ? "Sitzung" : "Sitzungen"}</p>
            {sessions.map((s) => {
              const isExpanded = !!expanded[s.ksinr];
              const matched = s.matched_items ?? [];
              const d = detail[s.ksinr];
              const outcomeByItem: Record<string, DecisionOutcome | null> = {};
              for (const dec of d?.decisions ?? []) {
                if (dec.kind === "decision" && dec.item_number) outcomeByItem[dec.item_number] = dec.outcome;
              }
              return (
                <Card key={s.ksinr} className="overflow-hidden p-0">
                  <button type="button" onClick={() => toggle(s)} className="group flex w-full items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-muted/40">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-foreground">{s.committee}</h3>
                      <p className="mt-0.5 text-sm text-muted-foreground">{formatDate(s.session_date)} · {s.session_time} Uhr · {s.location}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge color="blue">{s.n_items} {s.n_items === 1 ? "TOP" : "TOPs"}</Badge>
                      <ChevronDown className={cn("h-5 w-5 text-muted-foreground/50 transition-transform", isExpanded && "rotate-180 text-primary")} />
                    </div>
                  </button>

                  {(query || isExpanded) && (
                    <div className="border-t border-border px-4 pb-4 pt-3">
                      {isExpanded ? (
                        detailLoading[s.ksinr] ? (
                          <div className="py-2"><Spinner /></div>
                        ) : (
                          <>
                            <ul className="space-y-0.5">
                              {(d?.agenda_items ?? []).map((it, i) => (
                                <AgendaRow key={i} it={it} query={query} outcome={outcomeByItem[it.item_number]} />
                              ))}
                            </ul>
                            {d && <AttendanceSection detail={d} />}
                          </>
                        )
                      ) : query ? (
                        matched.length > 0 ? (
                          <>
                            <p className="mb-1 px-2 text-xs font-medium text-muted-foreground">{matched.length} Treffer in der Tagesordnung</p>
                            <ul className="space-y-0.5">{matched.map((it, i) => <AgendaRow key={i} it={it} query={query} />)}</ul>
                          </>
                        ) : (
                          <p className="px-2 text-sm text-muted-foreground">Kein Tagesordnungspunkt enthält „{query}" — Treffer im Ausschussnamen.</p>
                        )
                      ) : null}

                      <div className="mt-3 flex items-center gap-4 px-2">
                        <button type="button" onClick={() => toggle(s)} className="text-sm font-medium text-primary hover:underline">
                          {isExpanded ? "Weniger anzeigen" : `Alle ${s.n_items} TOPs anzeigen`}
                        </button>
                        <a href={sessionUrl(s.ksinr)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary">
                          Ratsinfo <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function CouncilPage() {
  const [tab, setTab] = useState<Tab>("sessions");
  const [committees, setCommittees] = useState<string[]>([]);

  useEffect(() => {
    api.get<{ committees: string[] }>("/council/committees").then((d) => setCommittees(d.committees)).catch(() => {});
  }, []);

  return (
    <div>
      <PageHeader title="Ratsinformationssystem" description="Sitzungen, Tagesordnungen und Beschlüsse des Oldenburger Stadtrats." />

      <div className="mt-6 inline-flex gap-1 rounded-md bg-muted p-1">
        {([["sessions", "Sitzungen & Tagesordnungen"], ["decisions", "Beschlüsse"]] as [Tab, string][]).map(([t, label]) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "rounded-sm px-3 py-1.5 text-sm font-medium transition-colors",
              tab === t ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "sessions" ? <SessionsTab committees={committees} /> : <DecisionsTab committees={committees} />}
    </div>
  );
}
