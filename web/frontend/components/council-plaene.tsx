"use client";

// <PlaeneView> — „Pläne der Stadt“ in der Analyse (Schalter `plaene`,
// docs/plan-ziele-plaene.md § 3.1). Ersetzt hinter dem Schalter die Ziel-Seite.
//
// Gebaut wird alles im Backend (council/plan_pages.py): Gruppen, Sortierung,
// Kicker, „letzter Bericht“ und der Satz, wenn der Bestand schweigt. Hier
// wird nur gezeichnet.
//
// Was die Seite NICHT zeigt, steht in § 3.4: keine Note, keine Quote über
// Pläne, kein Fortschrittsbalken, kein Rot.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Card, ChartSkeleton, EmptyState } from "@/components/ui";
import { AnalysisIntro } from "@/components/analysis-intro";
import { useFetch } from "@/lib/use-fetch";
import { planHref } from "@/lib/routes";
import { cn } from "@/lib/utils";
import { datum, statusTon, type PlanKarte, type PlanUebersicht } from "@/lib/plaene";

export function Kicker({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={cn("font-mono text-[10.5px] uppercase leading-snug tracking-[0.08em] text-muted-foreground", className)}>
      {children}
    </p>
  );
}

export function StatusAbzeichen({ karte }: { karte: Pick<PlanKarte, "status" | "status_label" | "successor"> }) {
  const ton = statusTon(karte.status);
  if (ton === "none") return null;
  const text = karte.status === "superseded" && karte.successor
    ? `abgelöst durch ${karte.successor.title}` : karte.status_label;
  return (
    <span className={cn("inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium",
      ton === "primary" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}>
      {text}
    </span>
  );
}

function LetzterBericht({ karte }: { karte: PlanKarte }) {
  const r = karte.latest_report;
  return (
    <div className="mt-3 border-t border-border/70 pt-2.5">
      {r ? (
        <>
          <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
            {r.oral ? "Letzter Bericht · mündlich" : "Letzter Bericht"}
          </p>
          <p className="mt-0.5 break-words text-[13.5px] leading-snug text-foreground">{r.title}</p>
          <p className="mt-0.5 text-meta text-muted-foreground">
            {[r.committee, datum(r.date)].filter(Boolean).join(" · ")}
          </p>
        </>
      ) : null}
      {karte.report_note && (
        <p className={cn("text-hinweis text-muted-foreground", r && "mt-1.5")}>{karte.report_note}</p>
      )}
    </div>
  );
}

function PlanKarteView({ karte }: { karte: PlanKarte }) {
  return (
    <Link href={planHref(karte.key)} prefetch={false}
      className="group block h-full rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <Card className="flex h-full flex-col p-4 transition-colors group-hover:border-primary/40">
        <Kicker>{karte.kicker}</Kicker>
        <div className="mt-1.5 flex items-start gap-2">
          <h3 className="min-w-0 flex-1 break-words text-quelle font-semibold leading-snug text-foreground">
            {karte.title}
          </h3>
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
        </div>
        {karte.office && <p className="mt-0.5 text-meta text-muted-foreground">{karte.office}</p>}
        <div className="mt-2"><StatusAbzeichen karte={karte} /></div>
        <div className="mt-auto">
          <LetzterBericht karte={karte} />
        </div>
      </Card>
    </Link>
  );
}

export function PlaeneView() {
  const { data, loading } = useFetch<PlanUebersicht>("/council/plans");
  if (loading) return <div className="py-4"><ChartSkeleton bars={6} /></div>;
  if (!data || data.count === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Pläne" hint="Das Register der Pläne ist leer." />;
  }
  return (
    <div className="space-y-6">
      <AnalysisIntro summary={<>{data.count} Pläne der Stadt: was der Rat beschlossen hat und was die Verwaltung ihm <strong className="font-semibold text-foreground">seitdem berichtet</strong> hat.</>}>
        Welche Pläne hier stehen, legt ein von Hand gepflegtes Register fest: Pläne mit Maßnahmen und
        Ratsbeschluss, Rahmenpläne und Strategien, Pflicht- und Fachpläne. Die Berichte findet Ratslotse
        über die Titel der Tagesordnungspunkte im Ratsinformationssystem. Nichtöffentliche Sitzungen,
        Mitteilungen ohne Vorlage und Berichte außerhalb des Ratsinformationssystems sieht Ratslotse nicht —
        „kein Bericht“ heißt deshalb „keinen gefunden“. Ratslotse vergibt keine Noten und rechnet keine
        Quoten über Pläne hinweg.
      </AnalysisIntro>
      {data.groups.filter((g) => g.plans.length > 0).map((g) => (
        <section key={g.key} aria-labelledby={`plaene-${g.key}`} className="@container">
          <div className="mb-2.5 flex items-baseline justify-between gap-3">
            <h2 id={`plaene-${g.key}`} className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              {g.label}
            </h2>
            <p className="font-mono text-meta text-muted-foreground">{g.plans.length}</p>
          </div>
          <ul className="grid gap-3 @3xl:grid-cols-2 @6xl:grid-cols-3">
            {g.plans.map((k) => <li key={k.key}><PlanKarteView karte={k} /></li>)}
          </ul>
        </section>
      ))}
      {data.references.length > 0 && (
        <section aria-labelledby="plaene-verweise">
          <h2 id="plaene-verweise" className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
            Auch im Register · Steuerungskonzepte und Pläne Dritter
          </h2>
          <ul className="mt-2 divide-y divide-border rounded-xl border border-border bg-card">
            {data.references.map((k) => (
              <li key={k.key}>
                <Link href={planHref(k.key)} prefetch={false}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50">
                  <span className="min-w-0 flex-1">
                    <span className="block break-words text-[14px] font-medium text-foreground">{k.title}</span>
                    <span className="block text-meta text-muted-foreground">{k.kicker}</span>
                  </span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
