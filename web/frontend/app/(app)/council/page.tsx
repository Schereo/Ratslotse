"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, ExternalLink } from "lucide-react";
import { api, qs, ApiError } from "@/lib/api";
import { CouncilSession, SessionDetail } from "@/lib/types";
import {
  Badge, Button, Card, EmptyState, Input, Select, Spinner, formatDate,
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
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [detail, setDetail] = useState<SessionDetail | null>(null);

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

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  const openDetail = async (s: CouncilSession) => {
    try {
      setDetail(await api.get<SessionDetail>(`/council/session/${s.ksinr}`));
    } catch {
      toast.error("Sitzung konnte nicht geladen werden.");
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-foreground">Ratsinformationssystem</h1>
      <p className="mt-1 text-sm text-muted-foreground">Sitzungen und Tagesordnungen des Oldenburger Stadtrats.</p>

      <Card className="mt-6 p-4">
        <form onSubmit={(e) => { e.preventDefault(); load(); }} className="space-y-3">
          <Input placeholder="In Tagesordnungen suchen (z. B. Bebauungsplan)…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select value={committee} onChange={(e) => setCommittee(e.target.value)}>
              <option value="">Alle Ausschüsse</option>
              {committees.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <div className="flex gap-1 rounded-md border border-input bg-card p-1">
              {(["upcoming", "recent", "all"] as Scope[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => { setScope(s); setQ(""); setCommittee(""); }}
                  className={cn(
                    "flex-1 rounded-sm px-2 py-1.5 text-sm font-medium transition-colors",
                    scope === s && !q && !committee ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent",
                  )}
                >
                  {s === "upcoming" ? "Kommend" : s === "recent" ? "Vergangen" : "Alle"}
                </button>
              ))}
            </div>
          </div>
          <Button type="submit" className="w-full sm:w-auto">
            <Search className="h-4 w-4" /> Suchen
          </Button>
        </form>
      </Card>

      <div className="mt-6">
        {loading ? (
          <Spinner />
        ) : sessions.length === 0 ? (
          hasSearched
            ? <EmptyState title="Keine Sitzungen gefunden" hint="Versuche andere Suchbegriffe oder Filter." />
            : <EmptyState title="Noch keine Sitzungen vorhanden" hint="Klicke auf 'Suchen', um Sitzungen zu laden." />
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">{sessions.length} Sitzungen</p>
            {sessions.map((s) => (
              <button
                key={s.ksinr}
                type="button"
                className="w-full text-left"
                onClick={() => openDetail(s)}
                onKeyDown={(e) => e.key === "Enter" && openDetail(s)}
              >
                <Card className="p-4 transition-shadow hover:shadow-md">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-foreground">{s.committee}</h3>
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        {formatDate(s.session_date)} · {s.session_time} Uhr · {s.location}
                      </p>
                    </div>
                    <Badge color="blue">{s.n_items} TOP</Badge>
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
                <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Tagesordnung</h3>
                <ul className="mt-2 divide-y divide-border">
                  {detail.agenda_items.map((it, i) => (
                    <li key={i} className="flex flex-wrap items-start gap-x-3 gap-y-1 py-2">
                      <span className="shrink-0 font-mono text-xs text-muted-foreground">{it.item_number}</span>
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
