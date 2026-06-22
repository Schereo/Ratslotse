"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, ExternalLink, ChevronDown, Landmark } from "lucide-react";
import { api, qs, ApiError } from "@/lib/api";
import { useDebounce } from "@/lib/use-debounce";
import { CouncilSession, SessionDetail, AgendaItem } from "@/lib/types";
import {
  Badge, Card, CardListSkeleton, EmptyState, Input, PageHeader, Select, Spinner, formatDate, toast,
} from "@/components/ui";
import { cn } from "@/lib/utils";

type Scope = "all" | "upcoming" | "recent";

const sessionUrl = (ksinr: number) => `https://buergerinfo.oldenburg.de/si0057.php?__ksinr=${ksinr}`;

function itemMatches(it: AgendaItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return it.title.toLowerCase().includes(q) || (it.vorlage_nr?.toLowerCase().includes(q) ?? false);
}

/** Render text with the first case-insensitive match of `query` highlighted. */
function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  if (!q) return <>{text}</>;
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

function AgendaRow({ it, query }: { it: AgendaItem; query: string }) {
  const hit = itemMatches(it, query);
  return (
    <li
      className={cn(
        "flex flex-wrap items-start gap-x-3 gap-y-1 rounded-md px-2 py-2",
        hit && "bg-amber-50 dark:bg-amber-950/40",
      )}
    >
      <span className="shrink-0 text-xs font-medium text-muted-foreground">{it.item_number}</span>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-foreground"><Highlight text={it.title} query={query} /></p>
        {it.vorlage_nr && (
          <p className="text-xs text-muted-foreground">Vorlage <Highlight text={it.vorlage_nr} query={query} /></p>
        )}
      </div>
      {!it.is_public && <Badge color="amber">nichtöffentlich</Badge>}
    </li>
  );
}

export default function CouncilPage() {
  const [q, setQ] = useState("");
  const [committee, setCommittee] = useState("");
  const [scope, setScope] = useState<Scope>("upcoming");
  const [committees, setCommittees] = useState<string[]>([]);
  const [sessions, setSessions] = useState<CouncilSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [agenda, setAgenda] = useState<Record<number, AgendaItem[]>>({});
  const [agendaLoading, setAgendaLoading] = useState<Record<number, boolean>>({});

  const debouncedQ = useDebounce(q, 350);

  useEffect(() => {
    api.get<{ committees: string[] }>("/council/committees").then((d) => setCommittees(d.committees)).catch(() => {});
  }, []);

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

  // Instant search on debounced query / filter / scope change (and on mount).
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, scope]);

  const toggle = async (s: CouncilSession) => {
    const willExpand = !expanded[s.ksinr];
    setExpanded((prev) => ({ ...prev, [s.ksinr]: willExpand }));
    if (willExpand && !agenda[s.ksinr]) {
      setAgendaLoading((prev) => ({ ...prev, [s.ksinr]: true }));
      try {
        const d = await api.get<SessionDetail>(`/council/session/${s.ksinr}`);
        setAgenda((prev) => ({ ...prev, [s.ksinr]: d.agenda_items }));
      } catch {
        toast.error("Tagesordnung konnte nicht geladen werden.");
        setExpanded((prev) => ({ ...prev, [s.ksinr]: false }));
      } finally {
        setAgendaLoading((prev) => ({ ...prev, [s.ksinr]: false }));
      }
    }
  };

  const query = q.trim();

  return (
    <div>
      <PageHeader
        title="Ratsinformationssystem"
        description="Sitzungen und Tagesordnungen des Oldenburger Stadtrats."
      />

      <Card className="mt-6 p-4">
        <div className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="In Tagesordnungen suchen (z. B. Bebauungsplan)…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
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
                    scope === s && !q && !committee
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
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
          hasSearched ? (
            <EmptyState
              icon={Landmark}
              title="Keine Sitzungen gefunden"
              hint="Versuche andere Suchbegriffe oder passe die Filter an."
            />
          ) : (
            <EmptyState icon={Landmark} title="Noch keine Sitzungen vorhanden" />
          )
        ) : (
          <div className="space-y-3">
            <p className="text-sm font-medium text-muted-foreground">
              {sessions.length} {sessions.length === 1 ? "Sitzung" : "Sitzungen"}
            </p>
            {sessions.map((s) => {
              const isExpanded = !!expanded[s.ksinr];
              const matched = s.matched_items ?? [];
              const showSection = !!query || isExpanded;
              return (
                <Card key={s.ksinr} className="overflow-hidden p-0">
                  <button
                    type="button"
                    onClick={() => toggle(s)}
                    className="group flex w-full items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-muted/40"
                  >
                    <div className="min-w-0">
                      <h3 className="font-semibold text-foreground">{s.committee}</h3>
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        {formatDate(s.session_date)} · {s.session_time} Uhr · {s.location}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge color="blue">{s.n_items} {s.n_items === 1 ? "TOP" : "TOPs"}</Badge>
                      <ChevronDown
                        className={cn(
                          "h-5 w-5 text-muted-foreground/50 transition-transform",
                          isExpanded && "rotate-180 text-primary",
                        )}
                      />
                    </div>
                  </button>

                  {showSection && (
                    <div className="border-t border-border px-4 pb-4 pt-3">
                      {isExpanded ? (
                        agendaLoading[s.ksinr] ? (
                          <div className="py-2"><Spinner /></div>
                        ) : (
                          <ul className="space-y-0.5">
                            {(agenda[s.ksinr] ?? []).map((it, i) => (
                              <AgendaRow key={i} it={it} query={query} />
                            ))}
                          </ul>
                        )
                      ) : query ? (
                        matched.length > 0 ? (
                          <>
                            <p className="mb-1 px-2 text-xs font-medium text-muted-foreground">
                              {matched.length} {matched.length === 1 ? "Treffer" : "Treffer"} in der Tagesordnung
                            </p>
                            <ul className="space-y-0.5">
                              {matched.map((it, i) => <AgendaRow key={i} it={it} query={query} />)}
                            </ul>
                          </>
                        ) : (
                          <p className="px-2 text-sm text-muted-foreground">
                            Kein Tagesordnungspunkt enthält „{query}" — Treffer im Ausschussnamen.
                          </p>
                        )
                      ) : null}

                      <div className="mt-3 flex items-center gap-4 px-2">
                        <button
                          type="button"
                          onClick={() => toggle(s)}
                          className="text-sm font-medium text-primary hover:underline"
                        >
                          {isExpanded ? "Weniger anzeigen" : `Alle ${s.n_items} TOPs anzeigen`}
                        </button>
                        <a
                          href={sessionUrl(s.ksinr)}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
                        >
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
