"use client";

/* Ein Tagesordnungspunkt auf seiner eigenen Seite (Schalter `punkt-seite`,
   Plan `docs/plan-sitzungsseite-kurs.md`, Schritt 4).

   Für Punkte ohne Protokoll-Beschluss. Hat der Punkt einen, steht oben ein
   Hinweis mit Link zur Beschluss-Seite — der Inhalt bleibt lesbar, niemand
   landet woanders als erwartet (Plan 3.9). */

import { Suspense, useState, type CSSProperties } from "react";
import { notFound, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Printer, Sparkles } from "lucide-react";
import { DetailSkeleton, formatDate } from "@/components/ui";
import { AbrufFehler } from "@/components/abruf-fehler";
import { BookmarkButton } from "@/components/bookmark-button";
import { ShareButton } from "@/components/share-button";
import { normalizeParty, partyBrand } from "@/components/decision-ui";
import { AufEinenBlick, FragDenRat, Unterlagen, Vorgeschichte, type Punkt } from "@/components/session/item-sections";
import { MeineNotiz } from "@/components/notiz/meine-notiz";
import { Argumente, Fraktionen } from "@/components/session/item-arguments";
import { kurzfassung } from "@/components/tagesordnung";
import { useFetch } from "@/lib/use-fetch";
import { istNichtGefunden } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { shortCommittee } from "@/lib/committees";
import { dayWord } from "@/lib/session-page";
import { decisionHref, punktHref, sitzungHref } from "@/lib/routes";
import { cn } from "@/lib/utils";

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

type Reiter = "arguments" | "factions" | "history" | "documents";

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
  const mitNotizen = useFeature("notizen");
  const mitArgumenten = useFeature("punkt-argumente");
  const args = mitArgumenten ? p.arguments ?? null : null;
  const reiter: { key: Reiter; label: string; n: number }[] = [
    { key: "arguments" as const, label: "Argumente", n: args?.show_arguments ? args.pro_count + args.contra_count : 0 },
    { key: "factions" as const, label: "Fraktionen", n: args?.show_factions ? args.factions.length : 0 },
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
        <div role="group" aria-label="Aktionen zum Punkt" className="flex items-center gap-1">
          <BookmarkButton target={{ kind: "agenda_item", ksinr: p.ksinr, item_number: it.item_number }} compact className="h-11 w-11" />
          <button type="button" onClick={() => window.print()} aria-label="Drucken" title="Drucken"
            className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Printer className="h-4 w-4" aria-hidden />
          </button>
          <ShareButton path={punktHref(p.ksinr, it.item_number)} iconOnly title={`${it.item_number} · ${titel}`} className="h-11 w-11 justify-center rounded-lg hover:bg-accent" />
        </div>
      </header>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] items-start gap-6 [overflow-wrap:anywhere] breit:grid-cols-[minmax(0,1fr)_360px]">
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
            <div role="tablist" aria-label="Zu diesem Punkt"
              className={cn("mt-6 grid gap-1 rounded-xl bg-muted p-1", reiter.length > 2 ? "grid-cols-2 sm:grid-cols-[repeat(var(--n),minmax(0,1fr))]" : "grid-cols-2")}
              style={{ "--n": reiter.length } as CSSProperties}>
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
            {zeige === "arguments" && args && <Argumente args={args} ksinr={p.ksinr} itemNumber={it.item_number} />}
            {zeige === "factions" && args && <Fraktionen args={args} />}
            {zeige === "history" && <Vorgeschichte p={p} titel={reiter.length > 1 ? null : "Vorgeschichte"} />}
            {zeige === "documents" && <Unterlagen p={p} titel={reiter.length > 1 ? null : "Unterlagen"} />}
            {!zeige && (
              <p className="rounded-xl border border-dashed border-border p-4 text-hinweis text-muted-foreground">
                Zu diesem Punkt liegen noch keine früheren Stationen und keine Unterlagen vor.
              </p>
            )}
          </div>


          <nav aria-label="Weitere Punkte der Sitzung" className="mt-8 flex flex-wrap gap-3 border-t border-border pt-4">
            {p.previous && (
              <Link href={punktHref(p.ksinr, p.previous.item_number)}
                className="inline-flex min-h-11 min-w-0 max-w-full items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-sm hover:bg-accent">
                <ArrowLeft className="h-4 w-4 flex-none" aria-hidden />
                <span className="min-w-0"><span className="block text-xs text-muted-foreground">Zurück</span>{p.previous.item_number} · {p.previous.short_title}</span>
              </Link>
            )}
            {p.next && (
              <Link href={punktHref(p.ksinr, p.next.item_number)}
                className="ml-auto inline-flex min-h-11 min-w-0 max-w-full items-center gap-2 rounded-xl border border-primary bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90">
                <span className="min-w-0"><span className="block text-xs opacity-90">Weiter</span>{p.next.item_number} · {p.next.short_title}</span>
                <ArrowRight className="h-4 w-4 flex-none" aria-hidden />
              </Link>
            )}
          </nav>
        </div>

        <aside className="flex flex-col gap-4" aria-label="Zu diesem Punkt">
          <FragDenRat p={p} />
          <AufEinenBlick p={p} />
          {mitNotizen && <MeineNotiz targetKind="agenda_item" targetKey={`${p.ksinr}|${it.item_number}`} />}
        </aside>
      </div>
    </div>
  );
}

