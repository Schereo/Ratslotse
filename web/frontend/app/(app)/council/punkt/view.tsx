"use client";

/* Ein Tagesordnungspunkt auf seiner eigenen Seite (Schalter `punkt-seite`,
   Plan `docs/plan-sitzungsseite-kurs.md`, Schritt 4).

   Für Punkte ohne Protokoll-Beschluss. Hat der Punkt einen, steht oben ein
   Hinweis mit Link zur Beschluss-Seite — der Inhalt bleibt lesbar, niemand
   landet woanders als erwartet (Plan 3.9). */

import { Suspense, useState } from "react";
import { notFound, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Printer } from "lucide-react";
import { DetailSkeleton, formatDate } from "@/components/ui";
import { ReiterLeiste, ReiterTafel, type Reiter } from "@/components/ui/reiter";
import { AbrufFehler } from "@/components/abruf-fehler";
import { BookmarkButton } from "@/components/bookmark-button";
import { ShareButton } from "@/components/share-button";
import { normalizeParty, partyBrand } from "@/components/decision-ui";
import { AufEinenBlick, FragDenRat, Unterlagen, Vorgeschichte, type Punkt } from "@/components/session/item-sections";
import { MeineNotiz } from "@/components/notiz/meine-notiz";
import { ChatBridgeProvider } from "@/components/notiz/chat-bridge";
import { noteDocuments } from "@/lib/doc-ref";
import { istRis } from "@/lib/ris";
import { Argumente, Fraktionen } from "@/components/session/item-arguments";
import { kurzfassung } from "@/components/tagesordnung";
import { KiStern } from "@/components/ki-stern";
import { AusDenUnterlagen } from "@/components/session/aus-den-unterlagen";
import { ImHaushalt } from "@/components/session/im-haushalt";
import { Wahlprogramme } from "@/components/session/wahlprogramme";
import { HaushaltsentwurfBefunde } from "@/components/session/haushaltsentwurf-befunde";
import { AehnlicheBeschluesse, BeteiligungsHinweis, VideoSprung, WoDasIst } from "@/components/session/punkt-umfeld";
import { ErklaerBereich, Erklaert, SeitenBegriffe } from "@/components/session/begriffe";
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
        <h1 className="text-foreground">Diesen Punkt findest du in der Tagesordnung der Sitzung.</h1>
        <Link href={sitzungHref(ksinr, [nr])} className="mt-3 inline-flex min-h-11 items-center gap-1.5 font-medium text-primary hover:underline">
          Zur Sitzung <ArrowRight className="h-4 w-4" aria-hidden /></Link>
      </div>
    );
  }
  return <PunktView p={data} />;
}

/** Die linke Spalte in Reitern (Tims Wunsch 23.11.2026): Notiz und Chat
 *  sollen nebeneinander stehen können — „Meine Notiz" ist deshalb ein Reiter
 *  der Lesespalte, der Chat bleibt rechts daneben. Vorher stand die Notiz
 *  ganz unten in der Seitenspalte, unter Chat, Steckbrief und Karte. */
type Tab = "overview" | "arguments" | "factions" | "history" | "documents" | "note";

/** Nur der Notiz-Reiter wird gemerkt: Wer eine Sitzung Punkt für Punkt
 *  mitschreibt, will mit „Weiter" nicht jedes Mal zurück auf den Überblick.
 *  Die übrigen Reiter sind Ansichten — ein neuer Punkt beginnt vorn. Ohne
 *  Speicher (privates Fenster) eben ohne Gedächtnis. */
const NOTE_TAB_KEY = "ratslotse:punkt-reiter";

function rememberedTab(): Tab | null {
  try { return sessionStorage.getItem(NOTE_TAB_KEY) === "note" ? "note" : null; } catch { return null; }
}

function rememberTab(t: Tab) {
  try {
    if (t === "note") sessionStorage.setItem(NOTE_TAB_KEY, "note");
    else sessionStorage.removeItem(NOTE_TAB_KEY);
  } catch { /* privat */ }
}

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
  const ausDenUnterlagen = useFeature("aus-den-unterlagen");
  const mitAntraegen = useFeature("aenderungsantraege");
  const args = mitArgumenten ? p.arguments ?? null : null;
  const similar = p.surroundings?.similar ?? [];
  const hasOverview = Boolean(kurz) || Boolean(p.budget_context?.blocks.length) || Boolean(p.program_stances?.parties.length)
    || similar.length > 0 || (ausDenUnterlagen && Boolean(p.template_fields || p.dossier))
    || (mitAntraegen && Boolean(p.amendments?.length));
  const tabs: Reiter<Tab>[] = [
    hasOverview ? { id: "overview" as const, label: "Überblick" } : null,
    args?.show_arguments ? { id: "arguments" as const, label: "Argumente", count: args.pro_count + args.contra_count } : null,
    args?.show_factions && args.factions.length ? { id: "factions" as const, label: "Fraktionen", count: args.factions.length } : null,
    p.history.length ? { id: "history" as const, label: "Vorgeschichte", count: p.history.length } : null,
    p.documents.length ? { id: "documents" as const, label: "Unterlagen", count: p.documents.length } : null,
    mitNotizen ? { id: "note" as const, label: "Meine Notiz" } : null,
  ].filter((r): r is NonNullable<typeof r> => r !== null);
  const [chosen, setChosen] = useState<Tab | null>(rememberedTab);
  const current = tabs.find((r) => r.id === chosen)?.id ?? tabs[0]?.id ?? null;
  const choose = (t: Tab) => { setChosen(t); rememberTab(t); };
  const mitReitern = tabs.length > 1;
  const panel = (id: Tab, children: React.ReactNode, className?: string) => {
    if (current !== id) return null;
    return mitReitern
      ? <ReiterTafel id={id} aktiv={current} className={cn("mt-4", className)}>{children}</ReiterTafel>
      : <div className={className}>{children}</div>;
  };
  const seit = p.history.length > 1 ? p.history[0].session_date.slice(0, 4) : null;
  const partei = ci.applicant ? normalizeParty(ci.applicant) : null;
  const brand = partei ? partyBrand(partei) : null;

  return (
    <SeitenBegriffe begriffe={p.terms}>
    {/* Notiz (links) und „Frag den Rat“ (rechts) reden über diese Brücke:
        „Im Chat fragen“ an einem Verweis in der Notiz. */}
    <ChatBridgeProvider>
    <div className="mx-auto max-w-[1240px]">
      <Link href={sitzungHref(p.ksinr, [it.item_number])}
        className="inline-flex min-h-11 items-center gap-2 rounded-lg text-sm text-muted-foreground transition-colors hover:text-foreground">
        <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden /> {p.committee} am {formatDate(p.session_date)}
      </Link>

      {p.decision_id != null && (
        <p className="mt-3 rounded-xl border border-primary/25 bg-primary/[0.06] p-3 text-sm text-foreground">
          Zu diesem Punkt gibt es inzwischen einen Beschluss.{" "}
          <Link href={decisionHref(p.decision_id)} className="font-medium textlink">Zum Beschluss</Link>
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
          {p.surroundings?.video && <p className="mt-3"><VideoSprung video={p.surroundings.video} /></p>}
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
        {/* Im Notiz-Reiter bleibt die Notiz beim Scrollen neben einem langen
            Chat stehen (`sticky`) — das geht nur, wenn ihre Spalte so hoch ist
            wie die Seitenspalte. In den anderen Reitern nicht: Dort risse das
            Strecken eine Lücke über „Zurück/Weiter". */}
        <div className={cn("min-w-0", current === "note" && "breit:flex breit:flex-col breit:self-stretch")}>
          <BeteiligungsHinweis b={p.surroundings?.participation ?? null} />
          <div className={cn(current === "note" && "breit:flex-1")}>
            {mitReitern && current && (
              <ReiterLeiste reiter={tabs} aktiv={current} onChange={choose} label="Zu diesem Punkt" />
            )}

            {panel("overview", (
              <div className="[&>*:first-child]:mt-0">
                {kurz && (
                  <section aria-labelledby="kurz" className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                    {/* Eine Überschrift statt Kicker „Kurzfassung" plus „Das Wichtigste
                        in Kürze" — beides sagte dasselbe (Tim, 12.11.2026). Dass der
                        Text automatisch entstand, sagt der Stern an seinem Ende. */}
                    <h2 id="kurz" className="font-display text-base font-semibold text-foreground">Das Wichtigste in Kürze</h2>
                    <ErklaerBereich className="mt-2">
                      <p className="text-lese text-foreground">
                        <Erklaert text={kurz} />
                        <KiStern className="ml-1" text="Automatische Kurzfassung. Verbindlich sind die Unterlagen im Ratsinfo." />
                      </p>
                    </ErklaerBereich>
                    {ci.important && ci.important_reason && (
                      <ErklaerBereich className="mt-3">
                        <p className="rounded-lg border-l-[3px] border-primary bg-primary/[0.07] px-3 py-2 text-hinweis text-foreground">
                          <strong className="font-semibold text-primary">Warum wichtig:</strong> <Erklaert text={ci.important_reason} />
                        </p>
                      </ErklaerBereich>
                    )}
                  </section>
                )}

                {(ausDenUnterlagen || mitAntraegen) && (
                  <AusDenUnterlagen f={ausDenUnterlagen ? p.template_fields : null}
                    antraege={mitAntraegen ? p.amendments : undefined} dossier={ausDenUnterlagen ? p.dossier : null} />
                )}

                <HaushaltsentwurfBefunde befunde={p.budget_findings} />
                <ImHaushalt kontext={p.budget_context} />
                <Wahlprogramme bezug={p.program_stances} />
                <AehnlicheBeschluesse liste={similar} />
              </div>
            ))}
            {panel("arguments", args && <Argumente args={args} ksinr={p.ksinr} itemNumber={it.item_number} />)}
            {panel("factions", args && <Fraktionen args={args} />)}
            {panel("history", <Vorgeschichte p={p} titel={mitReitern ? null : "Vorgeschichte"} />)}
            {panel("documents", <Unterlagen p={p} titel={mitReitern ? null : "Unterlagen"} />)}
            {panel("note", (
              <MeineNotiz targetKind="agenda_item" targetKey={`${p.ksinr}|${it.item_number}`} rows={14}
              documents={noteDocuments(p.documents, istRis)} />
            ), "breit:sticky breit:top-[calc(env(safe-area-inset-top)+4.75rem)] desk:top-6")}
            {!current && (
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
          <WoDasIst orte={p.surroundings?.places ?? []} />
        </aside>
      </div>
    </div>
    </ChatBridgeProvider>
    </SeitenBegriffe>
  );
}

