"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { PartyAnalysis } from "@/lib/types";
import { Card, ChartSkeleton, EmptyState } from "@/components/ui";
import { POLICY_FIELD_LABELS, PartyBadge } from "@/components/decision-ui";
import { useFetch } from "@/lib/use-fetch";
import { ChartExplainer } from "@/components/chart-explainer";
import { AnalysisIntro } from "@/components/analysis-intro";
import { FrageChips } from "@/components/frage-chips";
import { TrendsView } from "@/components/council-trends";
import { GoalsView } from "@/components/council-goals";
import { PlansView } from "@/components/council-plans";
import { useFeature } from "@/lib/features";
import { PersonenView } from "@/components/council-members";
import { AnalyseReiter, ANALYSE_FRAGEN, analysisSub } from "@/components/analyse-reiter";

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
            <span className="w-[116px] shrink-0 truncate text-xs text-foreground" title={POLICY_FIELD_LABELS[f] ?? f}>{POLICY_FIELD_LABELS[f] ?? f}</span>
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
        const dec = r.accepted + r.rejected + r.postponed || 1;
        return (
          <div key={r.party} className="flex items-center gap-3">
            <div className="w-24 shrink-0 sm:w-32"><PartyBadge party={r.party} /></div>
            <div className="flex h-5 flex-1 overflow-hidden rounded bg-muted">
              <div className="bg-green-500/80" style={{ width: `${(r.accepted / dec) * 100}%` }} />
              <div className="bg-red-500/80" style={{ width: `${(r.rejected / dec) * 100}%` }} />
              <div className="bg-amber-500/80" style={{ width: `${(r.postponed / dec) * 100}%` }} />
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
            <div className="bg-green-500/80" style={{ width: `${(r.accepted / r.n) * 100}%` }} />
            <div className="bg-red-500/80" style={{ width: `${(r.rejected / r.n) * 100}%` }} />
          </div>
          <div className="w-24 shrink-0 text-right text-xs text-muted-foreground">
            {Math.round((r.accepted / r.n) * 100)}% ang. · {r.n}
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
  if (loading) return <div className="py-4"><ChartSkeleton bars={8} /></div>;
  if (!data || data.coverage.with_factions === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Analyse möglich" hint="Für diese Auswertung gibt es noch nicht genügend Beschlüsse, bei denen Antragstellende genannt sind." />;
  }
  return (
    <div className="space-y-4">
      <AnalysisIntro summary={<>Diese Auswertung zeigt anhand von <strong className="font-semibold text-foreground">{data.coverage.with_factions}</strong> Beschlüssen, wer welche Anträge einbringt.</>}>
        Protokolle nennen namentliche Einzelstimmen nur selten. Diese Analyse zeigt daher,{" "}
        <strong className="font-semibold text-foreground">wer welche Anträge einbringt</strong> und wie darüber entschieden wird —
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
          hint="Wie über die eingereichten Anträge der Fraktionen entschieden wurde."
          explain={
            <>
              Gezählt werden die im Ratsinformationssystem eingereichten Anträge der Fraktionen,
              einschließlich Änderungsanträgen. Maßgeblich ist die endgültige Entscheidung zur Vorlage,
              möglichst die des Rats selbst: grün angenommen, rot abgelehnt. Vertagte oder offene Anträge zählen nicht mit.
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
        title="Uneinigkeit nach Themenfeld"
        hint="Bei welchen Themen der Rat häufig nicht einstimmig entscheidet."
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
      <Block title="Gemeinsame Anträge" hint="Parteien, die häufig zusammen Anträge einbringen.">
        <Alliances a={data} />
      </Block>
    </div>
  );
}

// Reiterleiste, Unterreiter und ihre Fragen stehen seit 11/2026 in
// components/analyse-reiter.tsx — die Ideen-Seite braucht nur die Leiste und
// zog vorher mit ihr den ganzen Analyse-Code mit.

export function AnalysisTab() {
  const sp = useSearchParams();
  const router = useRouter();
  // „Pläne der Stadt“ ersetzt hinter dem Schalter die Ziel-Seite (docs/plan-ziele-plaene.md).
  const plaene = useFeature("plaene");
  const sub = analysisSub(sp.get("sub"));
  // Den Reiter „Finanzen“ gibt es seit 11/2026 nicht mehr: Er summierte die
  // Euro-Beträge aus Beschlusstexten, der Haushalt zeigt die echten Zahlen
  // (Tims Entscheidung 09.11.2026). Alte Links landen dort statt bei Trends.
  const alterFinanzLink = sp.get("sub") === "finanzen";
  useEffect(() => {
    if (alterFinanzLink) router.replace("/haushalt");
  }, [alterFinanzLink, router]);

  return (
    <div className="mt-4 space-y-4">
      <AnalyseReiter aktiv={sub} />
      {/* Die Auswertungen sind das, was Neue nach dem Wahlabend als Erstes
          anklicken (BartVZ, Neele — Auswertung 17.09.2026), und dort endete
          es. Zwei Fragen je Reiter, die die Zahlen darunter zur Sprache bringen. */}
      <FrageChips fragen={ANALYSE_FRAGEN[sub]} />
      {sub === "parties" ? <PartiesView /> : sub === "personen" ? <PersonenView />
        : sub === "trends" ? <TrendsView /> : plaene ? <PlansView /> : <GoalsView />}
    </div>
  );
}
