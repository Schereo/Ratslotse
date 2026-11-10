"use client";

/* Ein Tagesordnungspunkt auf seiner eigenen Seite (Schalter `punkt-seite`,
   Plan `docs/plan-sitzungsseite-kurs.md`, Schritt 4).

   Für Punkte ohne Protokoll-Beschluss. Hat der Punkt einen, steht oben ein
   Hinweis mit Link zur Beschluss-Seite — der Inhalt bleibt lesbar, niemand
   landet woanders als erwartet (Plan 3.9). */

import { Suspense, useState } from "react";
import { notFound, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ExternalLink, Printer, Sparkles } from "lucide-react";
import { DetailSkeleton, formatDate } from "@/components/ui";
import { AbrufFehler } from "@/components/abruf-fehler";
import { BookmarkButton } from "@/components/bookmark-button";
import { ShareButton } from "@/components/share-button";
import { OUTCOME_DOT_CLS, OUTCOME_WORD, normalizeParty, partyBrand, voteLabel } from "@/components/decision-ui";
import { kurzfassung } from "@/components/tagesordnung";
import { NwzReadHint } from "@/components/nwz-link";
import { chipMerken } from "@/lib/chip-frage";
import { useFetch } from "@/lib/use-fetch";
import { istNichtGefunden } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { shortCommittee } from "@/lib/committees";
import { dayWord } from "@/lib/session-page";
import { decisionHref, punktHref, sitzungHref } from "@/lib/routes";
import type { ApiAntwort } from "@/lib/vertrag";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

type Punkt = ApiAntwort<"/council/session/{ksinr}/item">;

const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";

export default function PunktPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <PunktInner />
    </Suspense>
  );
}

function PunktInner() {
  const sp = useSearchParams();
  const ksinr = Number(sp.get("ksinr") || 0);
  const nr = (sp.get("top") || "").trim();
  const an = useFeature("punkt-seite");
  const { data, loading, error, refetch } = useFetch<Punkt>(
    ksinr > 0 && nr ? `/council/session/${ksinr}/item?nr=${encodeURIComponent(nr)}` : null, { quiet: true });

  if (ksinr <= 0 || !nr) notFound();
  if (loading) return <DetailSkeleton />;
  if (!data) {
    if (error && !istNichtGefunden(error)) return <AbrufFehler error={error} onRetry={refetch} was="Dieser Tagesordnungspunkt" />;
    notFound();
  }
  // Ohne Schalter gibt es die Seite nicht — wer einen Link hat, landet beim
  // Punkt in der Sitzung (dort, wo er heute schon steht).
  if (!an) {
    return (
      <div className="mx-auto max-w-2xl py-10 text-center">
        <p className="text-foreground">Diesen Punkt findest du in der Tagesordnung der Sitzung.</p>
        <Link href={sitzungHref(ksinr, [nr])} className="mt-3 inline-flex min-h-11 items-center gap-1.5 font-medium text-primary hover:underline">
          Zur Sitzung <ArrowRight className="h-4 w-4" aria-hidden /></Link>
      </div>
    );
  }
  return <PunktView p={data} />;
}

type Reiter = "history" | "documents";

function PunktView({ p }: { p: Punkt }) {
  const it = p.item;
  const ci = p.course_item;
  const titel = ci.short_title;
  const kurz = kurzfassung(it);
  const jetzt = new Date();
  const heute = jetzt.toISOString().slice(0, 10);
  const kommend = p.session_date >= heute;
  const wann = kommend ? `${dayWord(p.session_date, jetzt)} im ${p.committee}`
    : `${formatDate(p.session_date)} im ${p.committee}`;
  const kicker = [it.item_number, ci.type_label, it.template_number ? `Vorlage ${it.template_number}` : null, wann]
    .filter(Boolean).join(" · ");
  const reiter: { key: Reiter; label: string; n: number }[] = [
    { key: "history" as const, label: "Vorgeschichte", n: p.history.length },
    { key: "documents" as const, label: "Unterlagen", n: p.documents.length },
  ].filter((r) => r.n > 0);
  const [aktiv, setAktiv] = useState<Reiter | null>(null);
  const zeige = aktiv ?? reiter[0]?.key ?? null;
  const seit = p.history.length > 1 ? p.history[0].session_date.slice(0, 4) : null;
  const partei = ci.applicant ? normalizeParty(ci.applicant) : null;
  const brand = partei ? partyBrand(partei) : null;

  return (
    <div className="mx-auto max-w-[1240px]">
      <Link href={sitzungHref(p.ksinr, [it.item_number])}
        className="inline-flex min-h-11 items-center gap-2 rounded-lg text-sm text-muted-foreground transition-colors hover:text-foreground">
        <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden /> {p.committee} am {formatDate(p.session_date)}
      </Link>

      {p.decision_id != null && (
        <p className="mt-3 rounded-xl border border-primary/25 bg-primary/[0.06] p-3 text-sm text-foreground">
          Zu diesem Punkt gibt es inzwischen einen Beschluss.{" "}
          <Link href={decisionHref(p.decision_id)} className="font-medium text-primary hover:underline">Zum Beschluss</Link>
        </p>
      )}

      <header className="mt-4 flex flex-wrap items-start justify-between gap-4 [overflow-wrap:anywhere]">
        <div className="min-w-0">
          <p className={KICKER}>{kicker}</p>
          <h1 className="mt-1.5 font-display text-[28px] font-bold leading-tight tracking-tight text-foreground sm:text-[32px]" lang="de">
            {titel}
          </h1>
          <p className="mt-2 flex flex-wrap gap-1.5">
            {seit && (
              <span className="rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">
                Im Rat seit {seit} · {p.history.length} Sitzungen
              </span>
            )}
            {ci.postponed > 0 && (
              <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                {ci.postponed === 1 ? "Schon einmal vertagt" : `${ci.postponed}-mal vertagt`}
              </span>
            )}
          </p>
          {ci.applicant && (
            <p className="mt-2 flex items-center gap-1.5 text-sm text-muted-foreground">
              {brand && <span className="h-2 w-2 rounded-full" style={{ backgroundColor: brand.bg }} aria-hidden />}
              Antrag von <span className="font-semibold text-foreground">{ci.applicant}</span>
            </p>
          )}
        </div>
        <div role="group" aria-label="Aktionen zum Punkt" className="flex gap-1">
          <BookmarkButton target={{ kind: "agenda_item", ksinr: p.ksinr, item_number: it.item_number }} compact />
          <button type="button" onClick={() => window.print()} aria-label="Drucken" title="Drucken"
            className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Printer className="h-4 w-4" aria-hidden />
          </button>
          <ShareButton path={punktHref(p.ksinr, it.item_number)} iconOnly title={`${it.item_number} · ${titel}`} />
        </div>
      </header>

      <div className="mt-6 grid items-start gap-6 breit:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0">
          {kurz && (
            <section aria-labelledby="kurz" className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <p className={cn(KICKER, "flex items-center gap-1.5")}><Sparkles className="h-3.5 w-3.5 text-signal" aria-hidden /> Kurzfassung</p>
              <h2 id="kurz" className="mt-1 font-display text-base font-semibold text-foreground">Das Wichtigste in Kürze</h2>
              <p className="mt-2 text-lese text-foreground">{kurz}</p>
              {ci.important && ci.important_reason && (
                <p className="mt-2 text-hinweis text-foreground"><strong className="font-semibold">Wichtig:</strong> {ci.important_reason}</p>
              )}
              <p className="mt-3 text-hinweis text-muted-foreground">Automatische Kurzfassung. Verbindlich sind die Unterlagen im Ratsinfo.</p>
            </section>
          )}

          {reiter.length > 1 && (
            <div role="tablist" aria-label="Zu diesem Punkt" className="mt-6 grid gap-1 rounded-xl bg-muted p-1" style={{ gridTemplateColumns: `repeat(${reiter.length}, minmax(0,1fr))` }}>
              {reiter.map((r) => (
                <button key={r.key} role="tab" type="button" aria-selected={zeige === r.key} onClick={() => setAktiv(r.key)}
                  className={cn("min-h-11 rounded-lg px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    zeige === r.key ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>
                  {r.label} <span className="ml-1 text-xs text-muted-foreground">{r.n}</span>
                </button>
              ))}
            </div>
          )}

          <div className="mt-4" role={reiter.length > 1 ? "tabpanel" : undefined}>
            {zeige === "history" && <Vorgeschichte p={p} titel={reiter.length > 1 ? null : "Vorgeschichte"} />}
            {zeige === "documents" && <Unterlagen p={p} titel={reiter.length > 1 ? null : "Unterlagen"} />}
            {!zeige && (
              <p className="rounded-xl border border-dashed border-border p-4 text-hinweis text-muted-foreground">
                Zu diesem Punkt liegen noch keine früheren Stationen und keine Unterlagen vor.
              </p>
            )}
          </div>

          <div className="mt-6"><NwzReadHint title={titel} /></div>

          <nav aria-label="Weitere Punkte der Sitzung" className="mt-8 flex flex-wrap gap-3 border-t border-border pt-4">
            {p.previous && (
              <Link href={punktHref(p.ksinr, p.previous.item_number)}
                className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-sm hover:bg-accent">
                <ArrowLeft className="h-4 w-4" aria-hidden />
                <span><span className="block text-xs text-muted-foreground">Zurück</span>{p.previous.item_number} · {p.previous.short_title}</span>
              </Link>
            )}
            {p.next && (
              <Link href={punktHref(p.ksinr, p.next.item_number)}
                className="ml-auto inline-flex min-h-11 items-center gap-2 rounded-xl border border-primary bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90">
                <span><span className="block text-xs opacity-90">Weiter</span>{p.next.item_number} · {p.next.short_title}</span>
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            )}
          </nav>
        </div>

        <aside className="flex flex-col gap-4" aria-label="Zu diesem Punkt">
          <FragDenRat p={p} />
          <AufEinenBlick p={p} />
        </aside>
      </div>
    </div>
  );
}

function Vorgeschichte({ p, titel }: { p: Punkt; titel: string | null }) {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      {titel && <h2 className="mb-3 font-display text-base font-semibold text-foreground">{titel}</h2>}
      <ol className="relative space-y-5 border-l-2 border-primary/25 pl-5">
        {p.history.map((s, i) => {
          const o = s.outcome as DecisionOutcome | null;
          return (
            <li key={`${s.ksinr}-${i}`} className="relative">
              <span aria-hidden className={cn("absolute -left-[27px] top-1 h-3 w-3 rounded-full",
                s.current ? "bg-primary" : "border-2 border-primary/50 bg-card")} />
              <p className={cn(KICKER, s.current && "text-primary")}>
                {formatDate(s.session_date)} · {s.committee}{s.current ? " · diese Sitzung" : ""}
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

function Unterlagen({ p, titel }: { p: Punkt; titel: string | null }) {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
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
function FragDenRat({ p }: { p: Punkt }) {
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

function AufEinenBlick({ p }: { p: Punkt }) {
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


