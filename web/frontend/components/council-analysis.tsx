"use client";

import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { PartyAnalysis } from "@/lib/types";
import { Card, Spinner, EmptyState, toast } from "@/components/ui";
import { POLICY_FIELD_LABELS } from "@/components/decision-ui";

function Block({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <Card className="p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {hint && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{hint}</p>}
      <div className="mt-3.5">{children}</div>
    </Card>
  );
}

function Dot({ cls, label }: { cls: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2 w-2 rounded-sm ${cls}`} /> {label}
    </span>
  );
}

function Heatmap({ a }: { a: PartyAnalysis }) {
  const { parties, fields, matrix } = a.topic_matrix;
  const max = Math.max(1, ...parties.flatMap((p) => fields.map((f) => matrix[p]?.[f] ?? 0)));
  return (
    <div className="overflow-x-auto">
      <table className="border-collapse text-xs">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-card p-2" />
            {fields.map((f) => (
              <th key={f} className="whitespace-nowrap px-2 py-1.5 text-center font-medium text-muted-foreground">
                {POLICY_FIELD_LABELS[f] ?? f}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {parties.map((p) => (
            <tr key={p}>
              <td className="sticky left-0 z-10 whitespace-nowrap bg-card py-1 pr-3 font-medium text-foreground">{p}</td>
              {fields.map((f) => {
                const c = matrix[p]?.[f] ?? 0;
                const op = c ? 0.1 + 0.9 * (c / max) : 0;
                return (
                  <td key={f} className="p-0.5">
                    <div
                      className="min-w-[34px] rounded py-1.5 text-center tabular-nums"
                      style={{
                        backgroundColor: c ? `hsl(var(--primary) / ${op})` : "transparent",
                        color: op > 0.55 ? "hsl(var(--primary-foreground))" : undefined,
                      }}
                    >
                      {c || ""}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SuccessRates({ a }: { a: PartyAnalysis }) {
  return (
    <div className="space-y-2.5">
      {a.success_rates.map((r) => {
        const dec = r.angenommen + r.abgelehnt + r.vertagt || 1;
        return (
          <div key={r.party} className="flex items-center gap-3">
            <div className="w-24 shrink-0 truncate text-sm font-medium text-foreground sm:w-32">{r.party}</div>
            <div className="flex h-5 flex-1 overflow-hidden rounded bg-muted">
              <div className="bg-green-500/80" style={{ width: `${(r.angenommen / dec) * 100}%` }} />
              <div className="bg-red-500/80" style={{ width: `${(r.abgelehnt / dec) * 100}%` }} />
              <div className="bg-amber-500/80" style={{ width: `${(r.vertagt / dec) * 100}%` }} />
            </div>
            <div className="w-24 shrink-0 text-right text-xs text-muted-foreground">
              {r.rate != null ? `${Math.round(r.rate * 100)}% ang.` : "—"} · {r.motions}
            </div>
          </div>
        );
      })}
      <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs text-muted-foreground">
        <Dot cls="bg-green-500/80" label="angenommen" />
        <Dot cls="bg-red-500/80" label="abgelehnt" />
        <Dot cls="bg-amber-500/80" label="vertagt" />
        <span className="text-muted-foreground/70">· Quote = angenommen / entschieden · Zahl = Anträge</span>
      </div>
    </div>
  );
}

function Contention({ a }: { a: PartyAnalysis }) {
  return (
    <div className="space-y-2">
      {a.contention.map((r) => (
        <div key={r.field} className="flex items-center gap-3">
          <div className="w-28 shrink-0 truncate text-sm text-foreground sm:w-40">{a.field_labels[r.field] ?? r.field}</div>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${r.contested_rate * 100}%` }} />
          </div>
          <div className="w-28 shrink-0 text-right text-xs text-muted-foreground">
            {Math.round(r.contested_rate * 100)}% strittig
          </div>
        </div>
      ))}
      <p className="pt-1 text-xs text-muted-foreground/70">Anteil der Abstimmungen mit Gegenstimmen oder Enthaltungen (nicht einstimmig).</p>
    </div>
  );
}

function Alliances({ a }: { a: PartyAnalysis }) {
  if (!a.alliances.length) return <p className="text-sm text-muted-foreground">Keine gemeinsamen Anträge erkannt.</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {a.alliances.map((al, i) => (
        <div key={i} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5">
          <span className="text-sm font-medium text-foreground">{al.a} + {al.b}</span>
          <span className="text-xs text-muted-foreground">{al.count}×</span>
        </div>
      ))}
    </div>
  );
}

export function AnalysisTab() {
  const [data, setData] = useState<PartyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<PartyAnalysis>("/council/analysis")
      .then(setData)
      .catch((e) => { if (e instanceof ApiError) toast.error(e.message); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="py-10"><Spinner /></div>;
  if (!data || data.coverage.with_factions === 0) {
    return <EmptyState icon={BarChart3} title="Noch keine Analyse möglich" hint="Es sind noch keine Beschlüsse mit benanntem Antragsteller klassifiziert." />;
  }

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-lg border border-border bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
        Auswertung der <span className="font-medium text-foreground">{data.coverage.with_factions}</span> Beschlüsse
        mit benanntem Antragsteller (von {data.coverage.total}). Protokolle nennen selten namentliche Einzelstimmen —
        diese Analyse zeigt daher, <span className="font-medium text-foreground">wer welche Anträge einbringt</span> und
        wie sie ausgehen, nicht das Stimmverhalten jeder Fraktion bei jeder Abstimmung.
      </div>
      <Block title="Wer bringt welche Themen ein?" hint="Anträge je Partei und Themenfeld — dunkler = mehr.">
        <Heatmap a={data} />
      </Block>
      <Block title="Erfolgsquote der Anträge" hint="Wie die eingebrachten Anträge je Partei ausgehen.">
        <SuccessRates a={data} />
      </Block>
      <Block title="Streitgrad nach Themenfeld" hint="Welche Themen den Rat spalten, welche Konsens sind.">
        <Contention a={data} />
      </Block>
      <Block title="Häufige Allianzen" hint="Parteien, die Anträge gemeinsam einbringen.">
        <Alliances a={data} />
      </Block>
    </div>
  );
}
