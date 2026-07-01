"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Trends, FieldRecap } from "@/lib/types";
import { Card, Spinner, EmptyState } from "@/components/ui";
import { POLICY_FIELD_LABELS, formatEuro } from "@/components/decision-ui";
import { decisionHref } from "@/lib/routes";
import { useFetch } from "@/lib/use-fetch";
import { ChartExplainer } from "@/components/chart-explainer";

// Distinct, dark-mode-safe series colours for the top policy fields —
// abgeleitet aus der Markenpalette (Hafenblau, Signal-Orange, Gold der Mütze).
const COLORS = ["#1c86c8", "#f66623", "#0d9488", "#f2b441", "#8b6ce8", "#e4577e"];

function qLabel(q: string) {
  // "2024-Q3" → "Q3 '24"
  const [y, quarter] = q.split("-");
  return `${quarter} '${y.slice(2)}`;
}

// "2024-Q3" → calendar date range for deep-linking into the decisions list.
const Q_START: Record<number, string> = { 1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01" };
const Q_END: Record<number, string> = { 1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31" };
function quarterRange(q: string): { from: string; to: string } {
  const [y, qq] = q.split("-Q");
  const qi = Math.min(4, Math.max(1, parseInt(qq, 10) || 1));
  return { from: `${y}-${Q_START[qi]}`, to: `${y}-${Q_END[qi]}` };
}

function Block({ title, hint, explain, children }: { title: string; hint?: string; explain?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card className="p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {hint && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{hint}</p>}
      {explain && <ChartExplainer>{explain}</ChartExplainer>}
      <div className="mt-4">{children}</div>
    </Card>
  );
}

function StackedDecisions({ d, onQuarter }: { d: Trends; onQuarter: (q: string) => void }) {
  const totals = d.quarters.map((_, qi) => d.fields.reduce((s, f) => s + (d.by_field[f]?.[qi] ?? 0), 0));
  const max = Math.max(1, ...totals);
  const label = (f: string) => d.field_labels[f] ?? POLICY_FIELD_LABELS[f] ?? f;
  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height: 190 }}>
        {d.quarters.map((q, qi) => (
          <button key={q} type="button" onClick={() => onQuarter(q)}
            className="group flex h-full flex-1 flex-col justify-end rounded-sm transition-colors hover:bg-muted/50"
            title={`${qLabel(q)}: ${totals[qi]} Beschlüsse — klicken für die Beschlüsse dieses Quartals`}>
            <div className="flex flex-col-reverse overflow-hidden rounded-sm opacity-90 transition-opacity group-hover:opacity-100"
              style={{ height: `${(totals[qi] / max) * 100}%`, minHeight: totals[qi] > 0 ? 3 : 0 }}>
              {d.fields.map((f, fi) => {
                const v = d.by_field[f]?.[qi] ?? 0;
                return v ? <div key={f} style={{ height: `${(v / totals[qi]) * 100}%`, background: COLORS[fi % COLORS.length] }} /> : null;
              })}
            </div>
          </button>
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
      <p className="mt-2 text-[11px] text-muted-foreground/70">Balken anklicken, um die Beschlüsse eines Quartals zu öffnen.</p>
    </div>
  );
}

function MoneyBars({ d, onQuarter }: { d: Trends; onQuarter: (q: string) => void }) {
  const max = Math.max(1, ...d.money);
  const drivers = d.money_drivers ?? [];
  // The single largest recognised item across the shown quarters — a concrete
  // anchor for "what is this money?".
  let topI = -1;
  drivers.forEach((dr, i) => { if (dr && (topI < 0 || dr.eur > (drivers[topI]?.eur ?? 0))) topI = i; });
  const top = topI >= 0 ? drivers[topI] : null;
  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height: 130 }}>
        {d.quarters.map((q, qi) => {
          const dr = drivers[qi];
          const tip = `${qLabel(q)}: ${formatEuro(d.money[qi])}`
            + (dr ? ` · größter Posten: ${dr.title} (${formatEuro(dr.eur)})` : "");
          return (
            <button key={q} type="button" onClick={() => onQuarter(q)}
              className="group flex h-full flex-1 flex-col justify-end rounded-sm transition-colors hover:bg-muted/50"
              title={tip}>
              <div className="rounded-sm bg-emerald-500/70 transition-colors group-hover:bg-emerald-500"
                style={{ height: `${(d.money[qi] / max) * 100}%`, minHeight: d.money[qi] > 0 ? 2 : 0 }} />
            </button>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-1.5 text-[10px] text-muted-foreground">
        {d.quarters.map((q) => <span key={q} className="flex-1 text-center">{qLabel(q)}</span>)}
      </div>
      {top && (
        <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">
          Größter erkannter Einzelposten:{" "}
          <Link href={decisionHref(top.id)} className="font-medium text-foreground hover:text-primary hover:underline">
            {top.title}
          </Link>{" "}
          <span className="whitespace-nowrap text-muted-foreground/80">— {formatEuro(top.eur)} ({qLabel(d.quarters[topI])})</span>
        </p>
      )}
    </div>
  );
}

function FieldRecaps() {
  const { data } = useFetch<{ recaps: FieldRecap[] }>("/council/field-recaps");
  const recaps = data?.recaps ?? [];
  if (recaps.length === 0) return null;
  return (
    <Block title="Rückblick je Themenfeld" hint="KI-generierte Kurzfassung der jeweils neuesten Beschlüsse je Bereich — was den Rat zuletzt beschäftigt hat.">
      <div className="grid gap-3 sm:grid-cols-2">
        {recaps.map((r) => (
          <div key={r.policy_field} className="flex flex-col rounded-lg border border-border bg-muted/20 p-3.5">
            <h4 className="text-sm font-semibold text-foreground">{r.field_label}</h4>
            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{r.summary}</p>
            <Link
              href={`/council?tab=decisions&field=${r.policy_field}&cat=all${r.period_from ? `&date_from=${r.period_from}` : ""}${r.period_to ? `&date_to=${r.period_to}` : ""}`}
              className="mt-2.5 inline-flex w-fit text-xs text-muted-foreground transition-colors hover:text-primary"
            >
              Basierend auf den {r.n_decisions} neuesten Beschlüssen →
            </Link>
          </div>
        ))}
      </div>
    </Block>
  );
}

export function TrendsView() {
  const { data, loading } = useFetch<Trends>("/council/trends");
  const router = useRouter();

  if (loading) return <div className="py-10"><Spinner /></div>;
  if (!data || data.quarters.length === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Trends" hint="Es sind noch nicht genug datierte, klassifizierte Beschlüsse vorhanden." />;
  }
  const onQuarter = (q: string) => {
    const { from, to } = quarterRange(q);
    router.push(`/council?tab=decisions&date_from=${from}&date_to=${to}`);
  };
  return (
    <div className="space-y-4">
      <FieldRecaps />
      <Block
        title="Beschlüsse je Quartal"
        hint="Wie viel der Rat entscheidet — und in welchen Themenfeldern. Balken anklicken für das Quartal."
        explain={
          <>
            Jede Säule ist ein Quartal, die Farben stapeln die Themenfelder. Hohe Säulen sind
            entscheidungsreiche Monate (oft vor der Sommerpause), die Farbanteile verraten, welche Themen
            gerade dominieren. Ein Klick auf eine Säule öffnet alle Beschlüsse dieses Quartals.
          </>
        }
      >
        <StackedDecisions d={data} onQuarter={onQuarter} />
      </Block>
      <Block
        title="Erkanntes Finanzvolumen je Quartal"
        hint="Summe der im Beschlusstext genannten Beträge (ohne Jahresabschlüsse/Haushaltspläne — grobe Größenordnung)."
        explain={
          <>
            Wie viel Geld die Beschlüsse eines Quartals bewegt haben — summiert aus den im Text erkannten
            Beträgen. Ein einzelnes Großprojekt kann eine Säule dominieren; der „größte Einzelposten“
            darunter ordnet das ein.
          </>
        }
      >
        <MoneyBars d={data} onQuarter={onQuarter} />
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
