"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, ArrowRight, Check, Play } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DecisionOutcome, Topic } from "@/lib/types";
import { shortCommittee } from "@/lib/committees";
import { Button, Card } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";
import { SitzungspauseBanner } from "@/components/sitzungspause-banner";
import { LiveBanner } from "@/components/live-banner";
import { FundstueckCard } from "@/components/fundstueck-card";
import { isLiveNow } from "@/lib/live";
import { PushPrimer } from "@/components/push-primer";
import { formatEuro, OutcomeDot } from "@/components/decision-ui";
import { decisionHref } from "@/lib/routes";
import { startGuidedTour } from "@/components/tour";
import { ConfettiBurst } from "@/components/confetti";
import { useOnboarding, type StepId } from "@/components/onboarding";
import { useCountUp } from "@/lib/use-countup";

const FRAGEN_HREF = "/council?tab=decisions&mode=fragen";

// ksinr null = terminiert, Tagesordnung noch nicht veröffentlicht.
type UpcomingSession = {
  ksinr: number | null; committee: string; session_date: string; session_time: string; n_items: number;
  // RL-902: TOPs, die zu eigenen Themen passen.
  my_topic_items?: { item_number: string; topic_name: string }[];
};
type TopicHit = { topic_name: string; id: number; title: string; committee: string; session_date: string };
type DieseWoche =
  | { found: false }
  | { found: true; decision_id: number; title: string; outcome: DecisionOutcome;
      committee: string; session_date: string; interest_reason: string };
type ZahlDerWoche =
  | { kind: "betrag"; amount_eur: number; decision_id: number; title: string; session_date: string; window_days: number }
  | { kind: "anzahl"; count: number; window_days: number };

const fmtDay = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" });

function relTime(iso: string): string {
  const days = Math.round((Date.now() - new Date(iso + "T12:00:00").getTime()) / 86400000);
  if (days <= 0) return "heute";
  if (days === 1) return "gestern";
  if (days < 7) return `vor ${days} Tagen`;
  if (days < 30) {
    const weeks = Math.round(days / 7);
    return weeks === 1 ? "vor 1 Woche" : `vor ${weeks} Wochen`;
  }
  return new Date(iso + "T12:00:00").toLocaleDateString("de-DE", { day: "numeric", month: "short" });
}

/** „Heute"-Briefing (RL-401, Design 2a/4a): Kopf mit Lotti + Signal-CTA,
 *  Pause-Banner, dann drei Karten — Nächste Sitzungen · Neu zu deinen Themen ·
 *  Zahl der Woche. Jeder Bereich hat einen definierten Leerzustand. */
export default function DashboardPage() {
  const theme = useMascotTheme();
  const { user } = useAuth();

  // Datumszeile erst nach dem Mount (vermeidet SSR/Client-Hydration-Drift).
  const [today, setToday] = useState("");
  useEffect(() => {
    setToday(new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" }));
  }, []);

  const topicsQuery = useQuery({ queryKey: ["topics"], queryFn: () => api.get<Topic[]>("/topics") });
  const topicCount = topicsQuery.data?.length ?? 0;

  const sessionsQuery = useQuery({
    queryKey: ["upcoming-sessions"],
    queryFn: () => api.get<{ sessions: UpcomingSession[] }>("/council/sessions?scope=upcoming&limit=3"),
  });
  const hitsQuery = useQuery({
    queryKey: ["topic-latest-hits"],
    queryFn: () => api.get<{ hits: TopicHit[] }>("/topics/latest-hits?limit=2"),
  });
  const zahlQuery = useQuery({
    queryKey: ["zahl-der-woche"],
    queryFn: () => api.get<ZahlDerWoche>("/council/zahl-der-woche"),
  });
  // RL-U15 (13a-A): Ersatz für den Treffer-Leerzustand — nur laden, wenn er
  // gebraucht würde (Themen vorhanden, aber keine Treffer).
  const hits = hitsQuery.data?.hits ?? [];
  const wocheQuery = useQuery({
    queryKey: ["diese-woche"],
    queryFn: () => api.get<DieseWoche>("/council/diese-woche"),
    enabled: !hitsQuery.isLoading && hits.length === 0 && topicCount > 0,
    staleTime: 60 * 60 * 1000,
  });
  const woche = wocheQuery.data?.found ? wocheQuery.data : null;

  const sessions = sessionsQuery.data?.sessions ?? [];
  const zahl = zahlQuery.data;

  return (
    <div>
      {/* Kopf: Begrüßung + DIE Signal-Handlung des Screens („Frag den Rat"). */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-4">
          <Mascot pose="wave" theme={theme} bob className="h-[72px] w-[72px] shrink-0 sm:h-[88px] sm:w-[88px]" />
          <div className="min-w-0">
            <h1 className="truncate font-display text-2xl font-bold tracking-tight text-foreground sm:text-[30px] sm:leading-9">
              {/* Persönliche Ansprache, sobald ein Anzeigename da ist. */}
              Moin{user?.display_name ? `, ${user.display_name}` : ""}!
            </h1>
            {/* min-h hält die Zeile, bis das Datum clientseitig da ist. */}
            <p className="min-h-5 text-sm text-muted-foreground">{today}</p>
          </div>
        </div>
        <Button variant="signal" asChild className="w-full shrink-0 sm:w-auto" data-tour="frag-den-rat">
          <Link href={FRAGEN_HREF}>
            <Sparkles /> Frag den Rat
          </Link>
        </Button>
      </div>

      {/* RL-U10: Live und Pause teilen sich den Slot — sie schließen sich
          zeitlich aus (in der Sitzungspause tagt niemand). */}
      <SitzungspauseBanner className="mt-6" />
      <LiveBanner />

      {/* RL-1102: nur in der App, solange Push aus ist (7-Tage-Snooze). */}
      <PushPrimer />

      <FirstStepsBar hasTopic={topicCount > 0} />

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[1.2fr_1.2fr_0.9fr]">
        {/* Nächste Sitzungen */}
        <Card className="flex flex-col p-5">
          <h2 className="font-display text-base font-bold text-foreground">Nächste Sitzungen</h2>
          <div className="mt-3 flex-1 space-y-1">
            {sessions.slice(0, 3).map((s) => (
              <Link
                key={s.ksinr ?? `${s.committee}|${s.session_date}`}
                // RL-F06: direkt zur jeweiligen Sitzung (Terminplan-Zeilen ohne
                // ksinr landen weiter auf der Liste).
                href={s.ksinr ? `/council?tab=sessions&ksinr=${s.ksinr}` : "/council?tab=sessions"}
                className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-accent"
              >
                <span className="w-[104px] shrink-0 whitespace-nowrap text-sm font-medium tabular-nums text-foreground">
                  {fmtDay(s.session_date)}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm text-foreground" title={s.committee}>{shortCommittee(s.committee)}</span>
                {isLiveNow(s) ? (
                  /* RL-U10: laufende Sitzung — LIVE schlägt alle anderen Chips. */
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] font-bold text-red-600 dark:text-red-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-red-500" aria-hidden /> LIVE
                  </span>
                ) : (s.my_topic_items?.length ?? 0) > 0 ? (
                  /* RL-902: persönlicher Treffer schlägt den generischen TOPs-Chip. */
                  <span className="shrink-0 rounded-full bg-signal/10 px-2 py-0.5 text-[11px] font-semibold text-signal">
                    {new Set(s.my_topic_items!.map((m) => m.item_number)).size} zu deinen Themen
                  </span>
                ) : s.n_items > 0 && (
                  <span className="shrink-0 rounded-full bg-signal/10 px-2 py-0.5 text-[11px] font-semibold text-signal">
                    {s.n_items} TOPs
                  </span>
                )}
              </Link>
            ))}
            {!sessionsQuery.isLoading && sessions.length === 0 && (
              <p className="px-2 py-2 text-sm leading-relaxed text-muted-foreground">
                Derzeit sind keine kommenden Sitzungen veröffentlicht — Details siehe Hinweis oben.
              </p>
            )}
          </div>
          <Link
            href="/council?tab=sessions"
            className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            Alle Sitzungen <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </Card>

        {/* Neu zu deinen Themen */}
        <Card className="flex flex-col p-5">
          <h2 className="font-display text-base font-bold text-foreground">
            {woche && hits.length === 0 ? "Diese Woche im Rat" : "Neu zu deinen Themen"}
          </h2>
          <div className="mt-3 flex-1 space-y-2">
            {hits.map((h) => (
              <Link key={h.id} href={decisionHref(h.id)} className="block rounded-lg px-2 py-2 transition-colors hover:bg-accent">
                <span className="inline-flex rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
                  {h.topic_name}
                </span>
                <p className="mt-1 line-clamp-2 text-sm font-medium text-foreground">{h.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {shortCommittee(h.committee)} · {relTime(h.session_date)}
                </p>
              </Link>
            ))}
            {!hitsQuery.isLoading && hits.length === 0 && topicCount > 0 && (
              woche ? (
                /* RL-U15 (13a-A): der interessanteste Beschluss der Woche statt
                   des leeren Texts — „Warum spannend" ist wörtlich der
                   interest_reason der Bewertungs-Pipeline. */
                <Link href={decisionHref(woche.decision_id)} className="block rounded-lg px-2 py-2 transition-colors hover:bg-accent">
                  <span className="flex items-center gap-2 text-xs text-muted-foreground">
                    <OutcomeDot outcome={woche.outcome} /> {shortCommittee(woche.committee)}
                  </span>
                  <p className="mt-1 line-clamp-2 text-sm font-medium text-foreground">{woche.title}</p>
                  {woche.interest_reason && (
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      <span className="font-semibold text-signal">Warum spannend:</span> {woche.interest_reason}
                    </p>
                  )}
                  <span className="mt-1.5 inline-flex items-center gap-1 text-sm font-medium text-primary">
                    Zum Beschluss <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </Link>
              ) : (
                <p className="px-2 py-2 text-sm leading-relaxed text-muted-foreground">
                  Noch keine Treffer — sobald der Rat zu deinen Themen entscheidet, steht es hier.
                </p>
              )
            )}
            {!topicsQuery.isLoading && topicCount === 0 && (
              /* Leerzustand 4a: gestrichelte Lotti-Karte „Erstes Thema anlegen". */
              <div className="flex flex-col items-center gap-2 rounded-xl border-2 border-dashed border-border px-4 py-5 text-center">
                <Mascot pose="point" theme={theme} decorative className="h-12 w-12" />
                <p className="text-sm text-muted-foreground">
                  Lege dein erstes Thema an und werde benachrichtigt, sobald der Rat dazu entscheidet.
                </p>
                <Button size="sm" asChild>
                  <Link href="/topics">Erstes Thema anlegen</Link>
                </Button>
              </div>
            )}
          </div>
          {topicCount > 0 && (
            <Link href="/topics" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
              Meine Themen <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          )}
        </Card>

        {/* Zahl der Woche (RL-905) */}
        <Card className="flex flex-col border-signal/30 bg-signal/5 p-5">
          <h2 className="font-display text-base font-bold text-foreground">Zahl der Woche</h2>
          {zahl?.kind === "betrag" && (
            <>
              <p className="mt-3 font-display text-[40px] font-extrabold leading-none tracking-tight text-signal">
                <CountUpEuro amount={zahl.amount_eur} /></p>
              <p className="mt-2 line-clamp-3 flex-1 text-sm leading-relaxed text-muted-foreground">
                beschlossen für: {zahl.title}
              </p>
              <Link
                href={decisionHref(zahl.decision_id)}
                className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
              >
                Zum Beschluss <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </>
          )}
          {zahl?.kind === "anzahl" && (
            <>
              <p className="mt-3 font-display text-[40px] font-extrabold leading-none tracking-tight text-signal">
                <CountUpNumber value={zahl.count} />
              </p>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                {zahl.count === 1 ? "Beschluss" : "Beschlüsse"} in den letzten 7 Tagen — in der Sitzungspause
                sammelt sich hier wenig an.
              </p>
            </>
          )}
          {!zahl && <div className="mt-3 h-10 animate-pulse rounded-lg bg-signal/10" />}
        </Card>
      </div>

      {/* RL-U11: Fundstück des Tages — nach dem Grid; ohne kuratierten Fund
          entfällt die Karte ersatzlos. */}
      <FundstueckCard />
    </div>
  );
}

/** RL-1104: Zahl der Woche zählt hoch — Betrag über den Roh-Euro-Wert
 *  (formatEuro formatiert jeden Zwischenstand), Anzahl direkt. */
function CountUpEuro({ amount }: { amount: number }) {
  const n = useCountUp(Math.round(amount), true, 1100);
  return <>{formatEuro(n)}</>;
}

function CountUpNumber({ value }: { value: number }) {
  const n = useCountUp(value, true, 900);
  return <>{n}</>;
}

/** „Erste Schritte" als EINZEILIGE Leiste (RL-401): Lotti 40 px, Fortschritt,
 *  „Weitermachen" zum nächsten offenen Schritt. Konfetti-Logik wie zuvor;
 *  nach Abschluss (auf irgendeinem Gerät) verschwindet die Leiste. */
function FirstStepsBar({ hasTopic }: { hasTopic: boolean }) {
  const { ready, state, setCelebrated } = useOnboarding();
  const visited = state.steps;

  const steps: { id: StepId; title: string; href: string; done?: boolean }[] = [
    { id: "frag", title: "Stell dem Rat eine Frage", href: FRAGEN_HREF },
    { id: "beschluesse", title: "Beschlüsse durchstöbern", href: "/council" },
    { id: "analyse", title: "Die Analyse erkunden", href: "/council?tab=analysis" },
    { id: "karten", title: "Die Stadtkarte entdecken", href: "/council?tab=themen" },
    { id: "thema", title: "Erstes Thema anlegen", href: "/topics", done: hasTopic },
  ];
  const doneCount = steps.filter((s) => s.done || visited.includes(s.id)).length;
  const allDone = doneCount === steps.length;
  const next = steps.find((s) => !(s.done || visited.includes(s.id)));

  const [celebrate, setCelebrate] = useState(false);
  const [justFinished, setJustFinished] = useState(false);
  useEffect(() => {
    if (!ready || !allDone || state.celebrated || justFinished) return;
    setJustFinished(true);
    setCelebrate(true);
    setCelebrated();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, allDone, state.celebrated, justFinished]);

  if (!ready) return null;
  if (state.celebrated && !justFinished) return null;

  return (
    <Card className="relative mt-6 flex flex-wrap items-center gap-3 overflow-hidden px-4 py-3" data-tour="erste-schritte">
      {celebrate && <ConfettiBurst onDone={() => setCelebrate(false)} />}
      <Mascot pose={allDone ? "celebrate" : "wave"} decorative className="h-10 w-10 shrink-0" />
      <div className="min-w-0 flex-1 basis-48">
        <p className="text-sm font-medium text-foreground">
          {allDone ? "Kurs gehalten — alles erkundet!" : "Erste Schritte mit Lotti"}
        </p>
        <div className="mt-1 flex items-center gap-2">
          <div className="h-1.5 w-full max-w-56 overflow-hidden rounded-full bg-primary/15">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out-strong"
              style={{ width: `${(doneCount / steps.length) * 100}%` }}
            />
          </div>
          <span className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
            {doneCount}/{steps.length}
          </span>
        </div>
      </div>
      {allDone ? (
        <span className="inline-flex items-center gap-1 text-sm font-medium text-green-600 dark:text-green-400">
          <Check className="h-4 w-4" /> Geschafft
        </span>
      ) : (
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="ghost" size="sm" onClick={startGuidedTour} className="h-8 px-2.5 text-xs">
            <Play className="!size-3" /> Tour
          </Button>
          {next && (
            <Button variant="secondary" size="sm" asChild className="h-8 text-xs">
              <Link href={next.href}>
                Weitermachen <ArrowRight className="!size-3.5" />
              </Link>
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
