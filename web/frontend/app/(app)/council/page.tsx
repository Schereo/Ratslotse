"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, ExternalLink, ChevronRight, Landmark } from "lucide-react";
import { api, qs, ApiError } from "@/lib/api";
import { useDebounce } from "@/lib/use-debounce";
import { CouncilSession, SessionDetail } from "@/lib/types";
import {
  Badge, Card, CardListSkeleton, EmptyState, Input, PageHeader, Select, formatDate,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, toast,
} from "@/components/ui";
import { cn } from "@/lib/utils";

type Scope = "all" | "upcoming" | "recent";

export default function CouncilPage() {
  const [q, setQ] = useState("");
  const [committee, setCommittee] = useState("");
  const [scope, setScope] = useState<Scope>("upcoming");
  const [committees, setCommittees] = useState<string[]>([]);
  const [sessions, setSessions] = useState<CouncilSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);
  const [detail, setDetail] = useState<SessionDetail | null>(null);

  const debouncedQ = useDebounce(q, 350);

  useEffect(() => {
    api.get<{ committees: string[] }>("/council/committees").then((d) => setCommittees(d.committees)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setHasSearched(true);
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

  const openDetail = async (s: CouncilSession) => {
    try {
      setDetail(await api.get<SessionDetail>(`/council/session/${s.ksinr}`));
    } catch {
      toast.error("Sitzung konnte nicht geladen werden.");
    }
  };

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
            <p className="text-sm font-medium text-muted-foreground">{sessions.length} {sessions.length === 1 ? "Sitzung" : "Sitzungen"}</p>
            {sessions.map((s) => (
              <button
                key={s.ksinr}
                type="button"
                className="block w-full text-left"
                onClick={() => openDetail(s)}
              >
                <Card className="card-interactive group p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-foreground">{s.committee}</h3>
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        {formatDate(s.session_date)} · {s.session_time} Uhr · {s.location}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge color="blue">{s.n_items} TOP</Badge>
                      <ChevronRight className="h-5 w-5 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                    </div>
                  </div>
                </Card>
              </button>
            ))}
          </div>
        )}
      </div>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent>
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle>{detail.committee}</DialogTitle>
                <DialogDescription>
                  {formatDate(detail.session_date)} · {detail.session_time} Uhr · {detail.location}
                </DialogDescription>
              </DialogHeader>
              <div>
                <h3 className="text-sm font-semibold text-muted-foreground">Tagesordnung</h3>
                <ul className="mt-2 divide-y divide-border">
                  {detail.agenda_items.map((it, i) => (
                    <li key={i} className="flex flex-wrap items-start gap-x-3 gap-y-1 py-2">
                      <span className="shrink-0 text-xs font-medium text-muted-foreground">{it.item_number}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-foreground">{it.title}</p>
                        {it.vorlage_nr && <p className="text-xs text-muted-foreground">Vorlage {it.vorlage_nr}</p>}
                      </div>
                      {!it.is_public && <Badge color="amber">nichtöffentlich</Badge>}
                    </li>
                  ))}
                </ul>
                <a href={detail.url} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                  Zur Sitzungsseite im Ratsinfo <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
