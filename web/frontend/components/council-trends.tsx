"use client";

import { useRouter } from "next/navigation";
import { TrendingUp } from "lucide-react";
import { Trends } from "@/lib/types";
import { Card, Spinner, EmptyState } from "@/components/ui";
import { POLICY_FIELD_LABELS, formatEuro } from "@/components/decision-ui";
import { useFetch } from "@/lib/use-fetch";

// Distinct, dark-mode-safe series colours for the top policy fields.
const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4"];

function qLabel(q: string) {
  // "2024-Q3" → "Q3 '24"
  const [y, quarter] = q.split("-");
  return `${quarter} '${y.slice(2)}`;
}

function Block({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <Card className="p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {hint && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{hint}</p>}
      <div className="mt-4">{children}</div>
    </Card>
  );
}

function StackedDecisions({ d }: { d: Trends }) {
  const totals = d.quarters.map((_, qi) => d.fields.reduce((s, f) => s + (d.by_field[f]?.[qi] ?? 0), 0));
  const max = Math.max(1, ...totals);
  const label = (f: string) => d.field_labels[f] ?? POLICY_FIELD_LABELS[f] ?? f;
  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height: 190 }}>
        {d.quarters.map((q, qi) => (
          <div key={q} className="flex flex-1 flex-col-reverse overflow-hidden rounded-sm"
            style={{ height: `${(totals[qi] / max) * 100}%`, minHeight: totals[qi] > 0 ? 3 : 0 }}
            title={`${qLabel(q)}: ${totals[qi]} Beschlüsse`}>
            {d.fields.map((f, fi) => {
              const v = d.by_field[f]?.[qi] ?? 0;
              return v ? <div key={f} style={{ height: `${(v / totals[qi]) * 100}%`, background: COLORS[fi % COLORS.length] }} /> : null;
            })}
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex gap-1.5 text-[10px] text-muted-foreground">
        {d.quarters.map((q) => <span key={q} className="flex-1 text-center">{qLabel(q)}</span>)}
      </div>
      <div className="mt-3.5 flex flex-wrap gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
        {d.fields.map((f, fi) => (
          <span key={f} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: COLORS[fi % COLORS.length] }} />
            {label(f)}
          </span>
        ))}
      </div>
    </div>
  );
}

function MoneyBars({ d }: { d: Trends }) {
  const max = Math.max(1, ...d.money);
  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height: 130 }}>
        {d.quarters.map((q, qi) => (
          <div key={q} className="flex-1 rounded-sm bg-emerald-500/70"
            style={{ height: `${(d.money[qi] / max) * 100}%`, minHeight: d.money[qi] > 0 ? 2 : 0 }}
            title={`${qLabel(q)}: ${formatEuro(d.money[qi])}`} />
        ))}
      </div>
      <div className="mt-1.5 flex gap-1.5 text-[10px] text-muted-foreground">
        {d.quarters.map((q) => <span key={q} className="flex-1 text-center">{qLabel(q)}</span>)}
      </div>
    </div>
  );
}

export function TrendsTab() {
  const { data, loading } = useFetch<Trends>("/council/trends");
  const router = useRouter();

  if (loading) return <div className="py-10"><Spinner /></div>;
  if (!data || data.quarters.length === 0) {
    return <EmptyState icon={TrendingUp} title="Noch keine Trends" hint="Es sind noch nicht genug datierte, klassifizierte Beschlüsse vorhanden." />;
  }
  return (
    <div className="mt-4 space-y-4">
      <Block title="Beschlüsse je Quartal" hint="Wie viel der Rat entscheidet — und in welchen Themenfeldern.">
        <StackedDecisions d={data} />
      </Block>
      <Block title="Erkanntes Finanzvolumen je Quartal" hint="Summe der im Beschlusstext genannten Beträge (automatisch erkannt, grobe Größenordnung).">
        <MoneyBars d={data} />
      </Block>
      {data.emerging.length > 0 && (
        <Block title="Aktuell aufkommende Themen" hint="Häufigste Schlagworte der letzten zwei Quartale.">
          <div className="flex flex-wrap gap-2">
            {data.emerging.map((e) => (
              <button key={e.tag} onClick={() => router.push(`/council?tab=decisions&q=${encodeURIComponent(e.tag)}`)}
                className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs text-foreground transition-colors hover:bg-muted">
                {e.tag}<span className="text-muted-foreground">{e.n}</span>
              </button>
            ))}
          </div>
        </Block>
      )}
    </div>
  );
}
