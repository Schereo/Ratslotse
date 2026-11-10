"use client";

/* Mitlesen während der Sitzung (Schalter `mitlesen`, Plan
   `docs/plan-sitzungsseite-kurs.md` § 4.5, Schritt 5).

   Oben die Tafel mit dem Kurs, die aktive Boje orange umrandet; darunter der
   Punkt, der gerade dran ist, mit den Abschnitten der Punkt-Seite
   untereinander. Im Rat folgt die Seite der Übertragung, in Ausschüssen gibt
   man den Takt selbst vor — was gilt, rechnet `lib/mitlesen.ts`. */

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { notFound, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ExternalLink, List, Radio } from "lucide-react";
import { DetailSkeleton } from "@/components/ui";
import { AbrufFehler } from "@/components/abruf-fehler";
import { Course } from "@/components/session/course";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { FragDenRat, Unterlagen, Vorgeschichte, type Punkt } from "@/components/session/item-sections";
import { ergebnisseJeTop, kurzfassung, sessionUrl } from "@/components/tagesordnung";
import { normalizeParty, partyBrand } from "@/components/decision-ui";
import { useFetch } from "@/lib/use-fetch";
import { istNichtGefunden } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { shortCommittee } from "@/lib/committees";
import { LIVE_REFRESH_MS, isStadtrat, type LiveState } from "@/lib/live";
import { loadStored, mitlesenState, move, saveStored, steps, type Stored } from "@/lib/mitlesen";
import { sessionKicker, splitNumber } from "@/lib/session-page";
import { punktHref, sitzungHref } from "@/lib/routes";
import type { SessionWithCourse } from "@/components/session/session-page";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";
const NICHTOEFFENTLICH = "Nichtöffentlich berät ein Ausschuss, wenn das öffentliche Wohl oder berechtigte Interessen Einzelner es verlangen, zum Beispiel bei Grundstücken, Personal oder Verträgen.";

function speicher(): Storage | null {
  try { return typeof window !== "undefined" ? window.localStorage : null; } catch { return null; }
}

export default function MitlesenPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <MitlesenInner />
    </Suspense>
  );
}

function MitlesenInner() {
  const sp = useSearchParams();
  const ksinr = Number(sp.get("ksinr") || 0);
  const an = useFeature("mitlesen");
  const { data, loading, error, refetch } = useFetch<SessionWithCourse>(ksinr > 0 ? `/council/session/${ksinr}` : null, { quiet: true });
  // Im Rat kommt der Stand der Übertragung alle 20 Sekunden neu.
  const rat = !!data && isStadtrat(data.committee);
  useEffect(() => {
    if (!rat) return;
    const t = window.setInterval(() => refetch(), LIVE_REFRESH_MS);
    return () => window.clearInterval(t);
  }, [rat, refetch]);

  if (ksinr <= 0) notFound();
  if (loading && !data) return <DetailSkeleton />;
  if (!data) {
    if (error && !istNichtGefunden(error)) return <AbrufFehler error={error} onRetry={refetch} was="Diese Sitzung" />;
    notFound();
  }
  if (!an || !data.course) {
    return (
      <div className="mx-auto max-w-2xl py-10 text-center">
        <p className="text-foreground">Mitlesen gibt es für diese Sitzung nicht.</p>
        <Link href={sitzungHref(ksinr)} className="mt-3 inline-flex min-h-11 items-center gap-1.5 font-medium text-primary hover:underline">
          Zur Tagesordnung <ArrowRight className="h-4 w-4" aria-hidden /></Link>
      </div>
    );
  }
  return <Mitlesen data={data} ksinr={ksinr} />;
}

function Mitlesen({ data, ksinr }: { data: SessionWithCourse; ksinr: number }) {
  const course = data.course;
  const alle = useMemo(() => steps(course), [course]);
  const [stored, setStored] = useState<Stored>({ active: null, follow: true });
  useEffect(() => { setStored(loadStored(speicher(), ksinr)); }, [ksinr]);
  const state = mitlesenState(alle, stored, (data as unknown as { live_state?: LiveState }).live_state ?? null);
  const schritt = alle[state.index];
  const titelRef = useRef<HTMLHeadingElement>(null);
  const ersterLauf = useRef(true);
  const leiste = useRef<HTMLDivElement>(null);

  // Die Leiste unten deckte Lottis schwebenden Knopf zu (und er sie). Wie der
  // Composer auf /fragen meldet sie ihre Höhe als `--rl-composer`, solange
  // sie wirklich unten steht; ab `breit` ist sie weg.
  useEffect(() => {
    const el = leiste.current;
    if (!el) return;
    const melden = () => {
      if (getComputedStyle(el).display !== "none") {
        document.documentElement.style.setProperty("--rl-composer", `${el.offsetHeight}px`);
      } else {
        document.documentElement.style.removeProperty("--rl-composer");
      }
    };
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(melden) : null;
    ro?.observe(el);
    window.addEventListener("resize", melden);
    melden();
    return () => {
      ro?.disconnect();
      window.removeEventListener("resize", melden);
      document.documentElement.style.removeProperty("--rl-composer");
    };
  }, []);

  const gehe = useCallback((i: number) => {
    const neu = move(alle, state, i);
    setStored(neu);
    saveStored(speicher(), ksinr, neu);
  }, [alle, state, ksinr]);

  // Beim Wechsel an den Anfang der Karte, Fokus auf ihren Titel — ohne Gleiten
  // bei reduzierter Bewegung. Nicht beim ersten Aufruf: Da steht man oben.
  useEffect(() => {
    if (ersterLauf.current) { ersterLauf.current = false; return; }
    const el = titelRef.current;
    if (!el) return;
    const ruhig = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.closest("article")?.scrollIntoView({ behavior: ruhig ? "auto" : "smooth", block: "start" });
    el.focus({ preventScroll: true });
  }, [state.index]);

  const { outcomeByItem, videoByItem } = useMemo(() => ergebnisseJeTop(data), [data]);
  const provisional = useMemo(
    () => Object.fromEntries(Object.entries(videoByItem).map(([k, v]) => [k, v.outcome as DecisionOutcome])),
    [videoByItem]);
  const results = useMemo(() => ({ outcomeByItem, provisionalByItem: provisional }), [outcomeByItem, provisional]);
  const waehle = useCallback((nr: string) => {
    const i = alle.findIndex((s) => s.key === nr || s.items.includes(nr));
    if (i >= 0) gehe(i);
  }, [alle, gehe]);

  const vorher = state.index > 0 ? alle[state.index - 1] : null;
  const nachher = state.index < alle.length - 1 ? alle[state.index + 1] : null;
  const etappe = course.stages[schritt.stage];
  const punktSeite = useFeature("punkt-seite");

  return (
    <div className="mx-auto max-w-[1240px] pb-24 breit:pb-0">
      <header aria-labelledby="mitlesen-titel" className="hh-tafel mt-3 rounded-[18px] p-4 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className={KICKER}>{sessionKicker(data)}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-3">
              <h1 id="mitlesen-titel" className="font-display text-[28px] font-bold leading-tight text-foreground sm:text-[32px]">
                {shortCommittee(data.committee)}
              </h1>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-sm font-medium text-foreground">
                <span className="h-2 w-2 rounded-full bg-signal" aria-hidden /> Mitlesen
              </span>
            </div>
          </div>
          <Link href={sitzungHref(ksinr)} className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-primary hover:underline">
            <List className="h-4 w-4" aria-hidden /> Ganze Tagesordnung
          </Link>
        </div>

        <div className="mt-5 border-t border-border pt-4">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className={KICKER}>Kurs der Sitzung</h2>
            <p className={KICKER}>
              Etappe {schritt.stage + 1} von {course.stages.length} · {etappe.name} · Boje {state.index + 1} von {alle.length}
            </p>
          </div>
          <Course course={course} results={results} active={schritt.closed ? null : schritt.key} onSelect={waehle} />
        </div>

        <div className="mt-4 hidden flex-wrap items-center gap-3 breit:flex">
          <Steuerung vorher={vorher} nachher={nachher} onZurueck={() => gehe(state.index - 1)} onWeiter={() => gehe(state.index + 1)} />
          <p className="text-hinweis text-muted-foreground">{state.note}</p>
          {state.source === "paused" && state.broadcastIndex >= 0 && (
            <button type="button" onClick={() => gehe(state.broadcastIndex)}
              className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-primary/40 bg-card px-3 text-sm font-medium text-primary hover:bg-accent">
              <Radio className="h-4 w-4" aria-hidden /> Zur Übertragung: {alle[state.broadcastIndex].label}
            </button>
          )}
        </div>
        <p className="mt-3 text-hinweis text-muted-foreground breit:hidden">{state.note}</p>
      </header>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] items-start gap-6 breit:grid-cols-[minmax(0,1fr)_360px]">
        <JetztDran key={schritt.key} ksinr={ksinr} schritt={schritt} course={course} titelRef={titelRef}
          punktSeite={punktSeite}
          fuss={<Steuerung vorher={vorher} nachher={nachher} onZurueck={() => gehe(state.index - 1)} onWeiter={() => gehe(state.index + 1)} />} />
        <aside className="flex flex-col gap-4" aria-label="Neben der Sitzung">
          {!schritt.closed && <FragDenRatKurz ksinr={ksinr} nr={schritt.key} />}
          <AlsNaechstes alle={alle} ab={state.index + 1} onWaehle={gehe} />
          <a href={sessionUrl(ksinr)} target="_blank" rel="noreferrer"
            className="block rounded-xl border border-dashed border-border p-3 hover:bg-accent">
            <span className="flex items-center justify-between gap-2 text-quelle font-medium text-foreground">Sitzung im Ratsinfo <ExternalLink className="h-4 w-4 text-muted-foreground" aria-hidden /></span>
            <span className="text-meta text-muted-foreground">Tagesordnung, Vorlagen und Anlagen</span>
          </a>
        </aside>
      </div>

      {/* Handy: Zurück und Weiter kleben am unteren Rand — die kleinen Punkte
          im Kurs sind dort nicht antippbar. */}
      <div ref={leiste} className="fixed inset-x-0 bottom-[var(--rl-unten,0px)] z-[var(--ebene-schwebend)] border-t border-border bg-card/95 p-3 backdrop-blur breit:hidden">
        <Steuerung vorher={vorher} nachher={nachher} onZurueck={() => gehe(state.index - 1)} onWeiter={() => gehe(state.index + 1)} />
      </div>
    </div>
  );
}

function Steuerung({ vorher, nachher, onZurueck, onWeiter }: {
  vorher: { label: string; title: string } | null; nachher: { label: string; title: string } | null;
  onZurueck: () => void; onWeiter: () => void;
}) {
  return (
    <div className="flex w-full items-stretch gap-2 breit:w-auto">
      {vorher && (
        <button type="button" onClick={onZurueck} aria-label={`Zurück zu ${vorher.label} · ${vorher.title}`}
          className="inline-flex h-[52px] w-[52px] flex-none items-center justify-center rounded-xl border border-border bg-card text-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <ArrowLeft className="h-5 w-5" aria-hidden />
        </button>
      )}
      {nachher && (
        <button type="button" onClick={onWeiter}
          className="inline-flex min-h-[52px] min-w-0 flex-1 items-center justify-between gap-3 rounded-xl bg-primary px-4 text-left text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring breit:w-[360px] breit:flex-none">
          <span className="min-w-0">
            <span className="block text-xs opacity-90">Weiter</span>
            <span className="block truncate font-semibold">{nachher.label} · {nachher.title}</span>
          </span>
          <ArrowRight className="h-5 w-5 flex-none" aria-hidden />
        </button>
      )}
    </div>
  );
}

function JetztDran({ ksinr, schritt, course, titelRef, fuss, punktSeite }: {
  ksinr: number; schritt: ReturnType<typeof steps>[number]; course: SessionWithCourse["course"];
  titelRef: React.RefObject<HTMLHeadingElement>; fuss: React.ReactNode; punktSeite: boolean;
}) {
  const nr = schritt.closed || schritt.items.length > 1 ? null : schritt.key;
  const { data: p } = useFetch<Punkt>(nr ? `/council/session/${ksinr}/item?nr=${encodeURIComponent(nr)}` : null, { quiet: true });
  const item = nr ? course.items[nr] : null;
  const etappe = course.stages[schritt.stage];
  const { prefix, rest } = splitNumber(schritt.label);
  const partei = item?.applicant ? normalizeParty(item.applicant) : null;
  const brand = partei ? partyBrand(partei) : null;
  return (
    <article className="min-w-0 scroll-mt-24 rounded-2xl border border-primary/40 bg-card shadow-sm">
      <div className="p-5 sm:p-6">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className={cn(KICKER, "inline-flex items-center gap-1.5 text-foreground")}>
            <span className="h-2 w-2 rounded-full bg-signal" aria-hidden /> Jetzt dran
          </span>
          <span className="text-sm text-muted-foreground">Etappe {schritt.stage + 1} von {course.stages.length} · {etappe.name}</span>
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="font-display text-[40px] font-bold leading-none tabular-nums" aria-hidden>
            {prefix && <span className="text-muted-foreground">{prefix} </span>}<span className="text-foreground">{rest}</span>
          </p>
          {item?.type_label && <span className="rounded-md border border-border px-2 py-0.5 text-xs font-medium text-foreground">{item.type_label}</span>}
          {item?.important && <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-foreground">Wichtig</span>}
          {p?.item.template_number && <span className={KICKER}>Vorlage {p.item.template_number}</span>}
        </div>
        <h2 id="jetzt-titel" ref={titelRef} tabIndex={-1} className="mt-3 font-display text-2xl font-bold leading-tight text-foreground outline-none [overflow-wrap:anywhere]" lang="de">
          {schritt.closed ? "Nichtöffentlicher Teil" : schritt.title}
        </h2>
        {item?.applicant && (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-muted-foreground">
            {brand && <span className="h-2 w-2 rounded-full" style={{ backgroundColor: brand.bg }} aria-hidden />}
            <span className="font-semibold text-foreground">{item.applicant}</span>
          </p>
        )}
        {item?.important && item.important_reason && (
          <p className="mt-2 text-hinweis text-foreground"><strong className="font-semibold">Wichtig:</strong> {item.important_reason}</p>
        )}
        {p && kurzfassung(p.item) && <p className="mt-3 text-lese text-foreground">{kurzfassung(p.item)}</p>}
        {schritt.items.length > 1 && (
          <ul className="mt-3 space-y-1 text-sm text-foreground">
            {schritt.items.map((n) => (
              <li key={n}><span className="mr-2 font-mono text-muted-foreground">{n}</span>{course.items[n]?.short_title}</li>
            ))}
          </ul>
        )}
        {schritt.closed && (
          <>
            <p className="mt-3 text-hinweis text-foreground">
              {schritt.label} · Das Ratsinfo sperrt hier auch die Überschriften. Mehr als die Zahl der Punkte ist nicht öffentlich.
            </p>
            <LottiErklaert className="mt-3" title="Lotti erklärt's einfach" text={NICHTOEFFENTLICH} />
          </>
        )}
      </div>
      {p && p.history.length > 0 && <div className="border-t border-border p-5 sm:p-6"><Vorgeschichte p={p} titel="Vorgeschichte" bare /></div>}
      {p && p.documents.length > 0 && <div className="border-t border-border p-5 sm:p-6"><Unterlagen p={p} titel="Unterlagen" bare /></div>}
      {nr && punktSeite && (
        <p className="border-t border-border px-5 py-3 sm:px-6">
          <Link href={punktHref(ksinr, nr)} className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary hover:underline">
            Eigene Seite zu diesem Punkt <ArrowRight className="h-4 w-4" aria-hidden /></Link>
        </p>
      )}
      <div className="hidden justify-end border-t border-border bg-muted/30 p-4 breit:flex">{fuss}</div>
    </article>
  );
}

function FragDenRatKurz({ ksinr, nr }: { ksinr: number; nr: string }) {
  const { data: p } = useFetch<Punkt>(`/council/session/${ksinr}/item?nr=${encodeURIComponent(nr)}`, { quiet: true });
  if (!p) return null;
  return <FragDenRat p={p} />;
}

function AlsNaechstes({ alle, ab, onWaehle }: {
  alle: ReturnType<typeof steps>; ab: number; onWaehle: (i: number) => void;
}) {
  const naechste = alle.slice(ab, ab + 3);
  if (!naechste.length) return null;
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm" aria-labelledby="als-naechstes">
      <h2 id="als-naechstes" className={KICKER}>Als Nächstes</h2>
      <ul className="mt-2 divide-y divide-border/60">
        {naechste.map((s, i) => (
          <li key={s.label}>
            <button type="button" onClick={() => onWaehle(ab + i)}
              className="flex min-h-11 w-full items-center gap-3 py-2 text-left hover:bg-accent/50">
              <span className="w-14 flex-none font-display text-lg font-bold text-foreground">{s.label}</span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{s.title}</span>
              <ArrowRight className="h-4 w-4 flex-none text-muted-foreground" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
