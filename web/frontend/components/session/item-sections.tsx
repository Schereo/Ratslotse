"use client";

/* Bausteine eines Tagesordnungspunkts — auf seiner eigenen Seite
   (`app/(app)/council/punkt/`) und beim Mitlesen
   (`app/(app)/council/sitzung/mitlesen/`) dieselben (Plan Sitzungsseite,
   Schritte 4 und 5). */

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { formatDate } from "@/components/ui";
import { OUTCOME_DOT_CLS, OUTCOME_WORD, voteLabel } from "@/components/decision-ui";
import { chipMerken } from "@/lib/chip-frage";
import { shortCommittee } from "@/lib/committees";
import { decisionHref, sitzungHref } from "@/lib/routes";
import type { ApiAntwort } from "@/lib/vertrag";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

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

const ART: Record<string, string> = { template: "Vorlage", attachment: "Anlage", protocol: "Protokoll" };

export function Unterlagen({ p, titel, bare }: { p: Punkt; titel: string | null; bare?: boolean }) {
  return (
    <section className={bare ? undefined : "rounded-2xl border border-border bg-card p-5 shadow-sm"}>
      {titel && <h2 className="mb-3 font-display text-base font-semibold text-foreground">{titel}</h2>}
      <ul className="grid gap-2 @container sm:grid-cols-2">
        {p.documents.map((d, i) => (
          <li key={i}>
            <a href={d.url} target="_blank" rel="noreferrer"
              className="flex h-full items-start justify-between gap-2 rounded-xl border border-dashed border-border p-3 hover:bg-accent">
              <span className="min-w-0 [overflow-wrap:anywhere]">
                <span className="block text-quelle font-medium text-foreground">{d.label}</span>
                <span className="text-meta text-muted-foreground">{ART[d.kind] ?? "Unterlage"}{d.date ? ` · ${formatDate(d.date)}` : ""} · Ratsinfo</span>
              </span>
              <ExternalLink className="mt-1 h-4 w-4 flex-none text-muted-foreground" aria-hidden />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** „Frag den Rat · zu diesem Punkt": Die Frage geht an das Ratsgespräch, mit
 *  dem Punkt als Gegenstand (`ksinr` + `top` → `screen.refs`, Plan 3.10).
 *  Ohne Konto führt der Link wie jeder Frage-Chip zur Anmeldung und danach
 *  zurück zur Frage. */
export function FragDenRat({ p }: { p: Punkt }) {
  const [frage, setFrage] = useState("");
  const nr = p.item.item_number;
  const hat = (k: string) => p.documents.some((d) => d.kind === k);
  const vorschlaege = [
    "Worum geht es dabei in einfachen Worten?",
    p.history.length > 1 ? "Was wurde dazu früher beschlossen?" : null,
    p.course_item.type === "motion" ? "Was sagt die Verwaltung zu diesem Antrag?" : null,
    hat("template") ? "Was kostet das?" : null,
  ].filter((x): x is string => !!x).slice(0, 4);
  const ziel = (q: string) =>
    `/fragen?q=${encodeURIComponent(q)}&chip=1&ksinr=${p.ksinr}&top=${encodeURIComponent(nr)}`;
  const an = p.documents.length;
  return (
    <section aria-labelledby="frag-den-rat" className="rounded-2xl border border-border bg-card shadow-sm">
      <div className="border-b border-border p-4">
        <h2 id="frag-den-rat" className="font-display text-base font-semibold text-foreground">Frag den Rat</h2>
        <p className="text-sm text-muted-foreground">zu diesem Punkt · {nr}</p>
      </div>
      {an > 0 && (
        <p className="border-b border-border bg-primary/[0.06] px-4 py-2.5 text-sm text-foreground">
          <span className={cn(KICKER, "mr-1")}>An Bord · {an} {an === 1 ? "Unterlage" : "Unterlagen"}</span>
          Die Frage kennt diesen Punkt — du musst nichts erklären.
        </p>
      )}
      <ul className="space-y-2 p-4">
        {vorschlaege.map((q) => (
          <li key={q}>
            <Link href={ziel(q)} prefetch={false} onClick={() => chipMerken(q)}
              className="flex min-h-11 items-center justify-between gap-2 rounded-xl border border-primary/30 bg-primary/[0.04] px-3 py-2 text-sm text-foreground hover:bg-primary/[0.08]">
              {q} <ArrowRight className="h-4 w-4 flex-none text-primary" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
      <form className="flex gap-2 px-4 pb-4" onSubmit={(e) => {
        e.preventDefault();
        const q = frage.trim();
        if (q.length < 4) return;
        chipMerken(q);
        window.location.assign(ziel(q));
      }}>
        <label className="sr-only" htmlFor="punkt-frage">Deine Frage zu diesem Punkt</label>
        <input id="punkt-frage" value={frage} onChange={(e) => setFrage(e.target.value)} placeholder="Deine Frage zu diesem Punkt …"
          className="min-h-11 min-w-0 flex-1 rounded-xl border border-input bg-background px-3 text-sm" />
        <button type="submit" aria-label="Frage stellen"
          className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground hover:bg-primary/90">
          <ArrowRight className="h-4 w-4" aria-hidden />
        </button>
      </form>
      <p className="border-t border-border px-4 py-3 text-hinweis text-muted-foreground">
        Automatische Antwort aus den Unterlagen zu diesem Punkt. Kann unvollständig sein — Quellen prüfen.
      </p>
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


