"use client";

/* Bausteine eines Tagesordnungspunkts — auf seiner eigenen Seite
   (`app/(app)/council/punkt/`) und beim Mitlesen
   (`app/(app)/council/sitzung/mitlesen/`) dieselben (Plan Sitzungsseite,
   Schritte 4 und 5). */

import Link from "next/link";
import { ArrowRight, ChevronDown, ExternalLink } from "lucide-react";
import { formatDate } from "@/components/ui";
import { OUTCOME_DOT_CLS, OUTCOME_WORD, normalizeParty, partyBrand, voteLabel } from "@/components/decision-ui";
import { FragDenRatChat } from "@/components/frag-den-rat-chat";
import { useVorschlagsfragen } from "@/lib/vorschlagsfragen";
import { KiStern } from "@/components/ki-stern";
import { shortCommittee } from "@/lib/committees";
import { decisionHref, sitzungHref } from "@/lib/routes";
import type { ApiAntwort } from "@/lib/vertrag";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ART_WORT, ohneDatum, teileListe } from "@/lib/unterlagen";

export type Punkt = ApiAntwort<"/council/session/{ksinr}/item">;

const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";

export function Vorgeschichte({ p, titel, bare }: { p: Punkt; titel: string | null; bare?: boolean }) {
  return (
    <section className={bare ? undefined : "rounded-2xl border border-border bg-card p-5 shadow-sm"}>
      {titel && <h2 className="mb-3 font-display text-base font-semibold text-foreground">{titel}</h2>}
      <ol className="relative space-y-5 border-l-2 border-primary/25 pl-5">
        {p.history.map((s, i) => {
          const o = s.outcome as DecisionOutcome | null;
          return (
            <li key={`${s.ksinr}-${i}`} className="relative">
              <span aria-hidden className={cn("absolute -left-[27px] top-1 h-3 w-3 rounded-full",
                s.current ? "bg-primary" : "border-2 border-primary/50 bg-card")} />
              <p className={cn("text-sm text-muted-foreground", s.current && "text-primary")}>
                <span className={cn("font-semibold tabular-nums", s.current ? "text-primary" : "text-foreground")}>{formatDate(s.session_date)}</span>
                {" · "}{s.committee}{s.current ? " · diese Sitzung" : ""}
              </p>
              {o && (
                <p className="mt-1 flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  <span className={cn("h-2 w-2 rounded-full", OUTCOME_DOT_CLS[o])} aria-hidden />
                  {OUTCOME_WORD[o]}{s.vote ? <span className="font-normal text-muted-foreground"> · {voteLabel(s.vote)}</span> : null}
                </p>
              )}
              {s.text && <p className="mt-1 text-sm text-foreground">{s.text}</p>}
              {s.decision_id != null && (
                <Link href={decisionHref(s.decision_id)} className="mt-1 inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                  Zum Beschluss <ArrowRight className="h-4 w-4" aria-hidden /></Link>
              )}
              {!s.current && s.decision_id == null && (
                <Link href={sitzungHref(s.ksinr, [s.item_number])} className="mt-1 inline-flex min-h-11 items-center gap-1.5 text-sm text-primary hover:underline">
                  {s.item_number} in dieser Sitzung <ArrowRight className="h-4 w-4" aria-hidden /></Link>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

type Unterlage = Punkt["documents"][number];

function UnterlageZeile({ d }: { d: Unterlage }) {
  const art = ART_WORT[d.doc_type ?? (d.kind === "template" ? "template" : d.kind === "protocol" ? "protocol" : "other")];
  const partei = d.applicants?.[0] ? normalizeParty(d.applicants[0]) : null;
  const brand = partei ? partyBrand(partei) : null;
  const merkmale = [
    d.pages ? `${d.pages} ${d.pages === 1 ? "Seite" : "Seiten"}` : null,
    d.is_scan ? "Scan ohne Textebene" : null,
    d.after_session ? "kam nach dieser Sitzung dazu" : null,
    d.date ? formatDate(d.date) : null,
  ].filter(Boolean);
  return (
    <li>
      <a href={d.url} target="_blank" rel="noreferrer"
        className="flex h-full items-start gap-3 rounded-xl border border-dashed border-border p-3 hover:bg-accent">
        {d.list_no != null && (
          <span className="mt-0.5 inline-flex h-5 min-w-5 flex-none items-center justify-center rounded-md bg-muted px-1 font-mono text-[11px] font-medium text-muted-foreground">
            {d.list_no}
          </span>
        )}
        <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="rounded-md border border-border bg-card px-1.5 py-0.5 text-[11px] font-medium text-foreground">{art}</span>
            {d.applicants && d.applicants.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-meta font-semibold text-foreground">
                {brand && <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: brand.bg }} />}
                {d.applicants.join(", ")}
              </span>
            )}
          </span>
          <span className="mt-1 block text-quelle font-medium text-foreground">{ohneDatum(d.label)}</span>
          {merkmale.length > 0 && <span className="text-meta text-muted-foreground">{merkmale.join(" · ")}</span>}
        </span>
        <ExternalLink className="mt-1 h-4 w-4 flex-none text-muted-foreground" aria-hidden />
      </a>
    </li>
  );
}

/** Die Gegenlese-Liste (Plan Vorlagen aufbereiten, § 6.1): je Dokument
 *  einmal, mit Nummer, Art, Antragsteller und Seiten — Lesestoff offen,
 *  Belegmaterial eingeklappt, Protokolle früherer Stationen zuletzt. */
export function Unterlagen({ p, titel, bare }: { p: Punkt; titel: string | null; bare?: boolean }) {
  const { lesestoff, beleg, protokolle } = teileListe(p.documents);
  return (
    <section className={bare ? undefined : "rounded-2xl border border-border bg-card p-5 shadow-sm"}>
      {titel && <h2 className="mb-3 font-display text-base font-semibold text-foreground">{titel}</h2>}
      {lesestoff.length > 0 && (
        <ul className="grid gap-2">{lesestoff.map((d) => <UnterlageZeile key={d.url} d={d} />)}</ul>
      )}
      {beleg.length > 0 && (
        <details className="group mt-3" open={lesestoff.length === 0}>
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 text-sm font-medium text-foreground">
            <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
            Weitere Unterlagen <span className="text-muted-foreground">{beleg.length}</span>
          </summary>
          <ul className="mt-2 grid gap-2">{beleg.map((d) => <UnterlageZeile key={d.url} d={d} />)}</ul>
        </details>
      )}
      {protokolle.length > 0 && (
        <ul className="mt-3 grid gap-2">{protokolle.map((d) => <UnterlageZeile key={d.url} d={d} />)}</ul>
      )}
    </section>
  );
}

/** „Frag den Rat · zu diesem Punkt": Die Antwort entsteht hier, mit dem Punkt
 *  als Gegenstand (`ksinr` + `top` → `screen.refs`, Plan 3.10) — seit
 *  11.11.2026 direkt auf der Seite (`FragDenRatChat`). Ohne Konto führt eine
 *  Frage wie jeder Frage-Chip zur Anmeldung und danach zur Fragen-Seite. */
export function FragDenRat({ p }: { p: Punkt }) {
  const nr = p.item.item_number;
  const hat = (k: string) => p.documents.some((d) => d.kind === k);
  // Die festen Fragen sind nur noch der Rückfall: Passende zu genau diesem
  // Punkt kommen vom Modell (lib/vorschlagsfragen.ts).
  const rueckfall = [
    "Worum geht es dabei in einfachen Worten?",
    p.history.length > 1 ? "Was wurde dazu früher beschlossen?" : null,
    p.course_item.type === "motion" ? "Was sagt die Verwaltung zu diesem Antrag?" : null,
    hat("template") ? "Was kostet das?" : null,
  ].filter((x): x is string => !!x);
  const vorschlaege = useVorschlagsfragen(
    `/council/page-questions?ksinr=${p.ksinr}&nr=${encodeURIComponent(nr)}`, rueckfall);
  const ziel = (q: string) =>
    `/fragen?q=${encodeURIComponent(q)}&chip=1&ksinr=${p.ksinr}&top=${encodeURIComponent(nr)}`;
  const an = p.documents.length;
  return (
    <section aria-labelledby="frag-den-rat" className="rounded-2xl border border-border bg-card shadow-sm">
      <div className="border-b border-border p-4">
        <h2 id="frag-den-rat" className="font-display text-base font-semibold text-foreground">
          Frag den Rat
          <KiStern className="ml-1" text="Automatische Antwort aus den Unterlagen zu diesem Punkt. Kann unvollständig sein — Quellen prüfen." />
        </h2>
        <p className="text-sm text-muted-foreground">zu diesem Punkt · {nr}</p>
      </div>
      {an > 0 && (
        <p className="border-b border-border bg-primary/[0.06] px-4 py-2.5 text-sm text-foreground">
          <span className={cn(KICKER, "mr-1")}>An Bord · {an} {an === 1 ? "Unterlage" : "Unterlagen"}</span>
          Die Frage kennt diesen Punkt — du musst nichts erklären.
        </p>
      )}
      <FragDenRatChat seite={{ route: "/council/punkt", refs: { ksinr: p.ksinr, item_number: nr } }}
        vorschlaege={vorschlaege} fallbackHref={ziel} platzhalter="Deine Frage zu diesem Punkt …" />
    </section>
  );
}

export function AufEinenBlick({ p }: { p: Punkt }) {
  const ci = p.course_item;
  const kommend = p.session_date >= new Date().toISOString().slice(0, 10);
  const zeilen: [string, string][] = [];
  zeilen.push(["Stand", `${ci.type_label ?? "Punkt"} · ${shortCommittee(p.committee)} · ${formatDate(p.session_date)} · ${p.item.item_number}`]);
  if (p.item.template_number) zeilen.push(["Vorlage", p.item.template_number]);
  if (ci.applicant) zeilen.push(["Antrag von", ci.applicant]);
  const weiter = ci.next_on_agenda
    ? `Steht am ${formatDate(ci.next_on_agenda.session_date)} wieder auf der Tagesordnung (${ci.next_on_agenda.item_number}).`
    : kommend ? "Ergebnisse stehen hier, sobald das Protokoll der Sitzung vorliegt." : null;
  if (weiter) zeilen.push(["Wie es weitergeht", weiter]);
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm" aria-labelledby="auf-einen-blick">
      <h2 id="auf-einen-blick" className="font-display text-base font-semibold text-foreground">Auf einen Blick</h2>
      <dl className="mt-2 divide-y divide-border/60">
        {zeilen.map(([k, v]) => (
          <div key={k} className="py-2.5">
            <dt className={KICKER}>{k}</dt>
            <dd className="mt-0.5 text-sm text-foreground [overflow-wrap:anywhere]">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}


