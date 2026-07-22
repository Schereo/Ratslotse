"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Users, Euro, TrendingUp, Target, User } from "lucide-react";
import { PartyAnalysis, FinanceData } from "@/lib/types";
import { Card, Segmented, Spinner, EmptyState } from "@/components/ui";
import { POLICY_FIELD_LABELS, PartyBadge, DecisionLinkCard, formatEuro } from "@/components/decision-ui";
import { useFetch } from "@/lib/use-fetch";
import { ChartExplainer } from "@/components/chart-explainer";
import { AnalysisIntro } from "@/components/analysis-intro";
import { TrendsView } from "@/components/council-trends";
import { GoalsView } from "@/components/council-goals";
import { PersonenView } from "@/components/council-members";

function Block({ title, hint, explain, children }: { title: string; hint?: string; explain?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card className="p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {hint && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{hint}</p>}
      {explain && <ChartExplainer>{explain}</ChartExplainer>}
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
    <>
      {/* Desktop: die volle Heatmap-Tabelle. */}
      <div className="hidden overflow-x-auto sm:block">
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
                <td className="sticky left-0 z-10 whitespace-nowrap bg-card py-1 pr-3"><PartyBadge party={p} /></td>
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
      {/* Mobil (Design 16a②): Top-3-Felder je Fraktion als Balken statt 12-Spalten-Scroll. */}
      <div className="space-y-2.5 sm:hidden">
        {parties.map((p) => <HeatmapMobileRow key={p} party={p} fields={fields} row={matrix[p] ?? {}} />)}
      </div>
    </>
  );
}

function HeatmapMobileRow({ party, fields, row }: { party: string; fields: string[]; row: Record<string, number> }) {
  const [expanded, setExpanded] = useState(false);
  const ranked = fields.map((f) => ({ f, n: row[f] ?? 0 })).filter((x) => x.n > 0).sort((x, y) => y.n - x.n);
  const localMax = Math.max(1, ranked[0]?.n ?? 1);
  const shown = expanded ? ranked : ranked.slice(0, 3);
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <PartyBadge party={party} />
      <div className="mt-2 flex flex-col gap-1.5">
        {shown.map(({ f, n }) => (
          <div key={f} className="flex items-center gap-2">
            <span className="w-[74px] shrink-0 truncate text-xs text-foreground">{POLICY_FIELD_LABELS[f] ?? f}</span>
            <span className="h-[7px] flex-1 overflow-hidden rounded-full bg-muted">
              <span className="block h-full rounded-full bg-primary" style={{ width: `${(n / localMax) * 100}%` }} />
            </span>
            <span className="w-5 shrink-0 text-right text-[11px] tabular-nums text-muted-foreground">{n}</span>
          </div>
        ))}
        {ranked.length === 0 && <p className="text-xs text-muted-foreground">Keine Anträge erfasst.</p>}
      </div>
      {ranked.length > 3 && (
        <button type="button" onClick={() => setExpanded((v) => !v)}
          className="mt-2 text-[11.5px] font-medium text-primary hover:underline">
          {expanded ? "weniger anzeigen" : `alle ${ranked.length} Felder →`}
        </button>
      )}
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
            <div className="w-24 shrink-0 sm:w-32"><PartyBadge party={r.party} /></div>
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

/** Erfolgsquoten auf Basis der eingereichten Antrags-DOKUMENTE (Anlagen der
 *  Vorlagen) — belastbarer als die Protokoll-Erwähnungen, daher bevorzugt. */
function AntragSuccessRates({ a }: { a: PartyAnalysis }) {
  const stats = a.antrag_stats!;
  const rows = stats.parties.filter((r) => r.n >= 5);
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div key={r.party} className="flex items-center gap-3">
          <div className="w-24 shrink-0 sm:w-32"><PartyBadge party={r.party} /></div>
          <div className="flex h-5 flex-1 overflow-hidden rounded bg-muted">
            <div className="bg-green-500/80" style={{ width: `${(r.angenommen / r.n) * 100}%` }} />
            <div className="bg-red-500/80" style={{ width: `${(r.abgelehnt / r.n) * 100}%` }} />
          </div>
          <div className="w-24 shrink-0 text-right text-xs text-muted-foreground">
            {Math.round((r.angenommen / r.n) * 100)}% ang. · {r.n}
          </div>
        </div>
      ))}
      <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs text-muted-foreground">
        <Dot cls="bg-green-500/80" label="angenommen" />
        <Dot cls="bg-red-500/80" label="abgelehnt" />
        <span className="text-muted-foreground/70">
          · Zahl = entschiedene Anträge · nur Antragsteller mit mindestens 5 · aus {stats.n_mit_beschluss} von {stats.n_antraege} Antrags-Dokumenten
        </span>
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

function PartiesView() {
  const { data, loading } = useFetch<PartyAnalysis>("/council/analysis");
  if (loading) return <div className="py-10"><Spinner /></div>;
  if (!data || data.coverage.with_factions === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Analyse möglich" hint="Es sind noch keine Beschlüsse mit benannter antragstellender Person klassifiziert." />;
  }
  return (
    <div className="space-y-4">
      <AnalysisIntro summary={<>Wer bringt welche Anträge ein — aus <strong className="font-semibold text-foreground">{data.coverage.with_factions}</strong> Beschlüssen mit benannter Person.</>}>
        Protokolle nennen namentliche Einzelstimmen nur selten. Diese Analyse zeigt daher,{" "}
        <strong className="font-semibold text-foreground">wer welche Anträge einbringt</strong> und wie sie ausgehen —
        nicht das Stimmverhalten jeder Fraktion bei jeder Abstimmung. Grundlage: {data.coverage.with_factions} von{" "}
        {data.coverage.total} Beschlüssen (ab 2018).
      </AnalysisIntro>
      <Block
        title="Wer bringt welche Themen ein?"
        hint="Anträge je Partei und Themenfeld — dunkler = mehr."
        explain={
          <>
            Jede Zeile ist eine Fraktion, jede Spalte ein Themenfeld; die Zahl zählt die dort eingebrachten
            Anträge — je dunkler die Zelle, desto mehr. Lesebeispiel: Eine dunkle Zelle bei „Verkehr“ heißt,
            diese Fraktion treibt Verkehrsthemen besonders voran. Gezählt wird, <em>wer den Antrag stellt</em> —
            nicht, wer wie abstimmt.
          </>
        }
      >
        <Heatmap a={data} />
      </Block>
      {data.antrag_stats && data.antrag_stats.parties.some((r) => r.n >= 5) ? (
        <Block
          title="Erfolgsquote der Anträge"
          hint="Wie die eingereichten Anträge der Fraktionen ausgehen — aus den Original-Antragsdokumenten."
          explain={
            <>
              Gezählt werden die im Ratsinformationssystem eingereichten Antrags-Dokumente der Fraktionen
              (inkl. Änderungsanträge) und der klare Endstand der zugehörigen Vorlage — bevorzugt der Beschluss
              des Rats selbst: grün angenommen, rot abgelehnt. Vertagte/offene Anträge zählen nicht mit.
              Vorsicht beim Deuten: Eine hohe Quote kann „mehrheitsfähig“ heißen — oder dass eine Fraktion vor
              allem stellt, was sicher durchgeht.
            </>
          }
        >
          <AntragSuccessRates a={data} />
        </Block>
      ) : (
        <Block
          title="Erfolgsquote der Anträge"
          hint="Wie die eingebrachten Anträge je Partei ausgehen."
          explain={
            <>
              Jeder Balken zeigt, wie die Anträge einer Fraktion ausgehen: grün angenommen, rot abgelehnt, gelb
              vertagt. Die Prozentzahl rechts zählt nur entschiedene Anträge. Vorsicht beim Deuten: Eine hohe
              Quote kann „mehrheitsfähig“ heißen — oder dass eine Fraktion vor allem stellt, was sicher durchgeht.
            </>
          }
        >
          <SuccessRates a={data} />
        </Block>
      )}
      <Block
        title="Streitgrad nach Themenfeld"
        hint="Welche Themen den Rat spalten, welche Konsens sind."
        explain={
          <>
            Der Balken misst, wie oft Abstimmungen in diesem Themenfeld <em>nicht</em> einstimmig waren — es
            gab also Gegenstimmen oder Enthaltungen. 0 % wäre reiner Konsens; hohe Werte markieren die
            Reizthemen des Rats.
          </>
        }
      >
        <Contention a={data} />
      </Block>
      <Block title="Häufige Allianzen" hint="Parteien, die Anträge gemeinsam einbringen.">
        <Alliances a={data} />
      </Block>
    </div>
  );
}

function MoneyByField({ data }: { data: FinanceData }) {
  const router = useRouter();
  const rows = data.by_field;
  if (!rows.length) return null;
  const max = Math.max(1, ...rows.map((f) => f.total));
  const label = (f: string) => data.field_labels[f] ?? POLICY_FIELD_LABELS[f] ?? f;
  return (
    <div className="space-y-1.5">
      {rows.map((f) => (
        <button key={f.field} type="button"
          onClick={() => router.push(`/council?tab=decisions&field=${f.field}`)}
          className="group flex w-full items-center gap-3 rounded-md px-1 py-1 text-left transition-colors hover:bg-muted/50">
          <div className="w-28 shrink-0 truncate text-sm text-foreground sm:w-44">{label(f.field)}</div>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-emerald-500/70 transition-colors group-hover:bg-emerald-500" style={{ width: `${(f.total / max) * 100}%` }} />
          </div>
          <div className="w-32 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
            {formatEuro(f.total)} <span className="text-muted-foreground/60">· {f.n}</span>
          </div>
        </button>
      ))}
      <p className="pt-1.5 text-xs leading-relaxed text-muted-foreground/70">
        Summe automatisch erkannter Beträge je Themenfeld (ohne Jahresabschlüsse/Haushaltspläne).
        Zahl = Beschlüsse mit Betrag. Anklicken öffnet die Beschlüsse des Felds.
      </p>
    </div>
  );
}

function FinanceHeadline({ total, count }: { total: number; count: number }) {
  return (
    <div className="rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-transparent p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Erkanntes Finanzvolumen</p>
      <p className="mt-1 font-display text-[2rem] font-extrabold leading-none tracking-tight text-emerald-700 dark:text-emerald-400">≈ {formatEuro(total)}</p>
      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
        über <strong className="font-semibold text-foreground">{count} {count === 1 ? "Beschluss" : "Beschlüsse"}</strong> mit
        Betrag · ohne Jahresabschlüsse/Haushaltspläne (grobe Größenordnung)
      </p>
    </div>
  );
}

function FinanceView() {
  const { data, loading } = useFetch<FinanceData>("/council/finance");
  if (loading) return <div className="py-10"><Spinner /></div>;
  if (!data || (data.decisions.length === 0 && data.by_field.length === 0)) {
    return <EmptyState mascot="sleep" title="Noch keine Finanzdaten" hint="Es wurden noch keine €-Beträge aus Beschlüssen erkannt." />;
  }
  const total = data.by_field.reduce((s, f) => s + f.total, 0);
  const count = data.by_field.reduce((s, f) => s + f.n, 0);
  return (
    <div className="space-y-4">
      <Block
        title="Wofür fließt das Geld?"
        hint="Erkanntes Finanzvolumen je Themenfeld — welche Felder die größten Summen bewegen."
        explain={
          <>
            Summiert die Euro-Beträge, die in den Beschlusstexten automatisch erkannt wurden — das ist{" "}
            <em>nicht der offizielle Haushalt</em>, sondern eine Größenordnung aus den Entscheidungen selbst.
            Jahresabschlüsse und Haushaltspläne sind bewusst ausgenommen, sonst würden sie alles überstrahlen.
            Ein Klick auf eine Zeile öffnet die Beschlüsse dahinter.
          </>
        }
      >
        <div className="space-y-4">
          <FinanceHeadline total={total} count={count} />
          <MoneyByField data={data} />
        </div>
      </Block>
      {data.decisions.length > 0 && (
        <Block title="Größte Finanzbeschlüsse"
          hint="Beschlüsse mit dem höchsten im Text genannten Betrag (ohne Jahresabschlüsse/Haushaltspläne — automatisch erkannt).">
          <div className="space-y-2">
            {data.decisions.map((d) => (
              <DecisionLinkCard key={d.id} id={d.id} title={d.title} committee={d.committee}
                session_date={d.session_date} field={d.policy_field} amount={d.amount_eur} />
            ))}
          </div>
        </Block>
      )}
    </div>
  );
}

type AnalysisSub = "parteien" | "finanzen" | "trends" | "ziele" | "personen";
// Trends zuerst und als Default: Rückblicke + Quartals-Trends sind der
// zugänglichste Einstieg in die Analyse — Parteien/Personen sind die Vertiefung.
const SUB_TABS: [AnalysisSub, string, typeof Users][] = [
  ["trends", "Trends", TrendingUp],
  ["parteien", "Parteien", Users],
  ["personen", "Personen", User],
  ["finanzen", "Finanzen", Euro],
  ["ziele", "Ziele", Target],
];

export function AnalysisTab() {
  const sp = useSearchParams();
  const router = useRouter();
  const raw = sp.get("sub");
  const sub: AnalysisSub = raw === "finanzen" || raw === "parteien" || raw === "ziele" || raw === "personen" ? raw : "trends";
  const setSub = (s: AnalysisSub) => {
    const params = new URLSearchParams(sp.toString());
    params.set("tab", "analysis");
    if (s === "trends") params.delete("sub"); else params.set("sub", s);
    router.replace(`/council?${params.toString()}`, { scroll: false });
  };

  return (
    <div className="mt-4 space-y-4">
      <Segmented
        className="overflow-x-auto sm:w-fit"
        value={sub}
        onChange={setSub}
        options={SUB_TABS.map(([s, lbl, Icon]) => ({ value: s, label: lbl, icon: Icon }))}
      />
      {sub === "parteien" ? <PartiesView /> : sub === "personen" ? <PersonenView />
        : sub === "finanzen" ? <FinanceView /> : sub === "trends" ? <TrendsView /> : <GoalsView />}
    </div>
  );
}
