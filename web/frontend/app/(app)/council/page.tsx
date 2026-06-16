"use client";

import { useEffect, useState, useCallback } from "react";
import { api, qs } from "@/lib/api";
import { CouncilSession, SessionDetail } from "@/lib/types";
import { Badge, Button, Card, EmptyState, Input, Spinner, formatDate } from "@/components/ui";

type Scope = "all" | "upcoming" | "recent";

export default function CouncilPage() {
  const [q, setQ] = useState("");
  const [committee, setCommittee] = useState("");
  const [scope, setScope] = useState<Scope>("upcoming");
  const [committees, setCommittees] = useState<string[]>([]);
  const [sessions, setSessions] = useState<CouncilSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<SessionDetail | null>(null);

  useEffect(() => {
    api.get<{ committees: string[] }>("/council/committees").then((d) => setCommittees(d.committees)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const effectiveScope = q || committee ? "all" : scope;
      const data = await api.get<{ sessions: CouncilSession[] }>(
        `/council/sessions${qs({ q, committee, scope: effectiveScope, limit: 100 })}`,
      );
      setSessions(data.sessions);
    } finally {
      setLoading(false);
    }
  }, [q, committee, scope]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  const openDetail = async (s: CouncilSession) => {
    const d = await api.get<SessionDetail>(`/council/session/${s.ksinr}`);
    setDetail(d);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Ratsinformationssystem</h1>
      <p className="mt-1 text-sm text-slate-500">Sitzungen und Tagesordnungen des Oldenburger Stadtrats.</p>

      <Card className="mt-6 p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
          className="space-y-3"
        >
          <Input placeholder="In Tagesordnungen suchen (z. B. Bebauungsplan)…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              value={committee}
              onChange={(e) => setCommittee(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="">Alle Ausschüsse</option>
              {committees.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <div className="flex gap-1 rounded-lg border border-slate-300 bg-white p-1">
              {(["upcoming", "recent", "all"] as Scope[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setScope(s);
                    setQ("");
                    setCommittee("");
                  }}
                  className={`flex-1 rounded-md px-2 py-1 text-sm font-medium ${
                    scope === s && !q && !committee ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {s === "upcoming" ? "Kommend" : s === "recent" ? "Vergangen" : "Alle"}
                </button>
              ))}
            </div>
          </div>
          <Button type="submit">Suchen</Button>
        </form>
      </Card>

      <div className="mt-6">
        {loading ? (
          <Spinner />
        ) : sessions.length === 0 ? (
          <EmptyState title="Keine Sitzungen gefunden" />
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-slate-500">{sessions.length} Sitzungen</p>
            {sessions.map((s) => (
              <Card key={s.ksinr} className="cursor-pointer p-4 transition-shadow hover:shadow-md" >
                <div onClick={() => openDetail(s)} className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-900">{s.committee}</h3>
                    <p className="mt-0.5 text-sm text-slate-500">
                      {formatDate(s.session_date)} · {s.session_time} Uhr · {s.location}
                    </p>
                  </div>
                  <Badge color="blue">{s.n_items} TOP</Badge>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {detail && <SessionModal detail={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

function SessionModal({ detail, onClose }: { detail: SessionDetail; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <Card className="my-8 w-full max-w-2xl p-6">
        <div onClick={(e) => e.stopPropagation()}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-slate-900">{detail.committee}</h2>
              <p className="mt-1 text-sm text-slate-500">
                {formatDate(detail.session_date)} · {detail.session_time} Uhr · {detail.location}
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={onClose}>
              ✕
            </Button>
          </div>

          <h3 className="mt-5 text-sm font-semibold uppercase tracking-wide text-slate-400">Tagesordnung</h3>
          <ul className="mt-2 divide-y divide-slate-100">
            {detail.agenda_items.map((it, i) => (
              <li key={i} className="flex gap-3 py-2">
                <span className="shrink-0 font-mono text-xs text-slate-400">{it.item_number}</span>
                <div>
                  <p className="text-sm text-slate-700">{it.title}</p>
                  {it.vorlage_nr && <p className="text-xs text-slate-400">Vorlage {it.vorlage_nr}</p>}
                </div>
                {!it.is_public && <Badge color="amber">nichtöffentlich</Badge>}
              </li>
            ))}
          </ul>

          <a href={detail.url} target="_blank" rel="noreferrer" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
            Zur Sitzungsseite im Ratsinfo →
          </a>
        </div>
      </Card>
    </div>
  );
}
