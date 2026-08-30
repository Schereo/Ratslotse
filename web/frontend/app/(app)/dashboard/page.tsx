"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, ArrowRight, Check, Play } from "lucide-react";
import { api } from "@/lib/api";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { useAuth } from "@/lib/auth";
import { DecisionOutcome, Topic } from "@/lib/types";
import { shortCommittee } from "@/lib/committees";
import { useHeute } from "@/lib/use-heute";
import { Button, Card } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";
import { SitzungspauseBanner } from "@/components/sitzungspause-banner";
import { LiveBanner } from "@/components/live-banner";
import { FundstueckCard } from "@/components/fundstueck-card";
import { RecentDecisions } from "@/components/recent-decisions";
import { WocheImRat, type Wochenvorschau } from "@/components/woche-im-rat";
import { HinweisSlot } from "@/components/hinweis-slot";
import { PushPrimer } from "@/components/push-primer";
import { formatEuro, OutcomeDot } from "@/components/decision-ui";
import { fragenHref, decisionHref } from "@/lib/routes";
import { startGuidedTour } from "@/components/tour";
import { ConfettiBurst } from "@/components/confetti";
import { useOnboarding, type StepId } from "@/components/onboarding";
import { useCountUp } from "@/lib/use-countup";

const FRAGEN_HREF = fragenHref();

type TopicHit = { topic_name: string; id: number; title: string; committee: string; session_date: string };
// Aus dem API-Vertrag statt von Hand — beide sind dort echte Unions, `found`
// bzw. `kind` unterscheiden die Fälle.
//
// Einzige Abweichung: `outcome` steht im Vertrag als `string`, nicht als Union.
// Die Spalte wird vom LLM befüllt; eine Verengung im Backend hieße, dass ein
// unerwarteter Wert die Antwort mit 500 abbricht statt nur ein Etikett
// unbeschriftet zu lassen. Die Oberfläche darf enger sehen als der Vertrag.
type DieseWocheRoh = ApiAntwort<"/council/diese-woche">;
type DieseWoche =
  | Extract<DieseWocheRoh, { found: false }>
  | (Omit<Extract<DieseWocheRoh, { found: true }>, "outcome"> & { outcome: DecisionOutcome | null });
type ZahlDerWoche = ApiAntwort<"/council/zahl-der-woche">;

/** ISO-Datum von vor n Tagen — Ziel des „Diese N ansehen"-Links (Design 28a/S5).
 *  Dasselbe Fenster, das der Endpoint gezählt hat, damit die Suche wirklich
 *  dieselben Beschlüsse zeigt wie die Zahl auf der Karte. */
const lastWeekIso = (days: number) =>
  new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);

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
 *  Pause-Banner, dann die Wochen-Karte (Design 14) und darunter zwei kurze —
 *  Neu zu deinen Themen · Zahl der Woche. Jeder Bereich hat einen definierten
 *  Leerzustand. */
export default function DashboardPage() {
  const theme = useMascotTheme();
  const { user } = useAuth();
  const heute = useHeute();

  // Datumszeile erst nach dem Mount (vermeidet SSR/Client-Hydration-Drift).
  const [today, setToday] = useState("");
  useEffect(() => {
    setToday(new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" }));
  }, []);

  const topicsQuery = useQuery({ queryKey: ["topics"], queryFn: () => api.get<Topic[]>("/topics") });
  const topicCount = topicsQuery.data?.length ?? 0;

  const hitsQuery = useQuery({
    queryKey: ["topic-latest-hits"],
    queryFn: () => api.get<{ hits: TopicHit[] }>("/topics/latest-hits?limit=2"),
  });
  const zahlQuery = useQuery({
    queryKey: ["zahl-der-woche"],
    queryFn: () => vertrag.get("/council/zahl-der-woche"),
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
  // Design 14: Die Wochen-Karte steht jetzt IMMER — sie ersetzt „Nächste
  // Sitzungen" und ist damit die vollständige Sicht auf die Woche, nicht mehr
  // ein Ersatz für einen Leerzustand.
  const vorschauQuery = useQuery({
    queryKey: ["wochenvorschau"],
    queryFn: () => api.get<Wochenvorschau>("/council/wochenvorschau"),
    staleTime: 60 * 60 * 1000,
  });
  const vorschau = vorschauQuery.data?.found ? vorschauQuery.data : null;

  // Lokales ISO-Datum für den „HEUTE"-Chip der Wochen-Karte. Bewusst nicht
  // über toISOString(): Das rechnet in UTC und machte aus 00:30 Uhr deutscher
  // Zeit den Vortag. Vor dem Mount ist es leer — dann zeigt die Karte Daten
  // statt „heute", genau wie useHeute() es vorsieht.
  const heuteIso = heute
    ? `${heute.getFullYear()}-${String(heute.getMonth() + 1).padStart(2, "0")}-${String(heute.getDate()).padStart(2, "0")}`
    : "";

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

      {/* Design 28a/R4: ein Platz für Hinweise statt bis zu vier gestapelter
          Banner. Die Reihenfolge ist die Priorität — Live schlägt Pause (die
          beiden schließen sich ohnehin aus), erst danach kommt Kür.
          RL-1102: der Push-Primer erscheint nur in der App, solange Push aus
          ist (7-Tage-Snooze) — er steht hier zuletzt, weil er sich am ehesten
          vertagen lässt. */}
      <HinweisSlot
        className="mt-6"
        hinweise={[
          { key: "live", label: "Sitzung läuft", node: <LiveBanner /> },
          { key: "pause", label: "Sitzungspause", node: <SitzungspauseBanner /> },
          { key: "erste-schritte", label: "Erste Schritte", node: <FirstStepsBar /> },
          { key: "push", label: "Mitteilungen", node: <PushPrimer /> },
        ]}
      />

      {/* Karten-Raster (Tims Befund 12.08.: drei Spalten kamen zu früh).

          Die Stufen zählen die Breite des RASTERS, nicht die des Fensters —
          dazwischen liegt die Seitenleiste. Bei 1280 px Fenster bleiben dem
          Raster nur 976 px (im Browser nachgemessen), und die Fenster-Stufe
          `xl:` schaltete trotzdem auf drei Spalten: 334 / 392 / 218 px. Die
          dritte Spalte war damit schmaler als ein Telefon. Auf dem Telefon
          selbst gibt es die Leiste gar nicht — dieselbe Fensterbreite meint
          also zwei verschiedene Platzangebote, und nur eine Container-Query
          kann beide auseinanderhalten.

          Die Schwellen richten sich danach, was die TEXTREICHSTE Karte zum
          Lesen braucht — die Wochen-Ausgabe —, nicht danach, was gerade noch
          hineinpasst:

            < 768 px   eine Spalte    (Telefon)
            ≥ 768 px   zwei Spalten   (iPad hoch/quer, kleine Laptops)
                       die Ausgabe nimmt die erste Zeile ganz ein, die beiden
                       kurzen Karten teilen sich die zweite
            ≥ 1152 px  drei Spalten   — erst hier trägt die dritte Spalte
                       mehr als eine Zahl und drei Wörter

          minmax(0, …fr) statt nacktem fr: Sonst gewinnt die Mindestbreite des
          Inhalts gegen die Gewichtung — die Sitzungs-Liste mit ihren langen
          Gremiennamen drückte sich auf 420 px, während die Ausgabe mit 334 px
          auskommen musste (im Browser nachgemessen).

          items-start: Jede Karte trägt ihre eigene Höhe. Vorher streckte das
          Raster „Nächste Sitzungen" und „Zahl der Woche" auf die Höhe der
          Ausgabe — mit einem Feld Leerraum darunter, das nichts sagt. */}
      {/* Design 14: „Die Woche im Rat" steht über dem Raster und nimmt die
          volle Breite. Sie ersetzt zwei Karten (Nächste Sitzungen + Diese
          Woche im Rat) und braucht den Platz für ihre Tages-Rail — je breiter
          sie ist, desto mehr trägt sie (Ort, Kurzbegründung, dritter Punkt).
          Darunter bleibt das Raster für die beiden kurzen Karten. */}
      {vorschau && (
        <div className="mt-6">
          <WocheImRat vorschau={vorschau} heuteIso={heuteIso} />
        </div>
      )}

      {/* Nur noch zwei kurze Karten: „Neu zu deinen Themen" (Rückblick) und
          „Zahl der Woche". Zwei Spalten reichen — die dritte war für die
          Sitzungs-Liste da, die jetzt in der Wochen-Karte steckt. */}
      <div className="@container/raster mt-4">
        <div className="grid grid-cols-1 items-start gap-4 @3xl/raster:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          {/* Neu zu deinen Themen — der Rückblick auf entschiedene Beschlüsse.
              Die Vorschau auf die Woche ist seit Design 14 eine eigene Karte
              über dem Raster; diese hier trägt nur noch die Treffer. */}
          <Card className="flex flex-col p-5">
            <h2 className="font-display text-base font-bold text-foreground">Neu zu deinen Themen</h2>
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

          {/* Zahl der Woche (RL-905) — eine Zahl und ein Satz, braucht am
              wenigsten Breite. */}
          <Card className="flex flex-col border-signal/30 bg-signal/5 p-5 @3xl/raster:order-3 @6xl/raster:order-none">
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
                {/* Design 28a/S5: Die auffälligste Zahl des Screens war in dieser
                    Variante der einzige Inhalt ohne Ziel. Die Suche kennt
                    date_from längst — es fehlte nur der Link dorthin. */}
                {zahl.count > 0 && (
                  <Link
                    href={`/council?tab=decisions&date_from=${lastWeekIso(zahl.window_days)}`}
                    className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    Diese {zahl.count} ansehen <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                )}
              </>
            )}
            {!zahl && <div className="mt-3 h-10 animate-pulse rounded-lg bg-signal/10" />}
          </Card>
        </div>
      </div>

      {/* Design 28a/S5: „Zuletzt angesehen" lag fertig im Repo, wurde aber von
          keiner Seite gerendert. Bei leerer Historie rendert die Komponente
          ohnehin nichts — sie kostet also keinen Platz, bis es etwas zu zeigen
          gibt, und schließt den zweiten Sackgassen-Punkt des Dashboards. */}
      <RecentDecisions className="mt-6" />

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
function FirstStepsBar() {
  const { ready, state, setCelebrated } = useOnboarding();
  const visited = state.steps;

  const steps: { id: StepId; title: string; href: string; done?: boolean }[] = [
    { id: "frag", title: "Stell dem Rat eine Frage", href: FRAGEN_HREF },
    { id: "beschluesse", title: "Beschlüsse durchstöbern", href: "/council" },
    { id: "analyse", title: "Die Analyse erkunden", href: "/council?tab=analysis" },
    { id: "karten", title: "Die Stadtkarte entdecken", href: "/council?tab=themen" },
    // „Erstes Thema anlegen" stand hier früher als fünfter Punkt. Er war der
    // einzige, den die Tour nicht abhaken konnte (er verlangt ein echtes
    // Thema) — die Leiste blieb deshalb nach jeder Tour unvollständig stehen.
    // Themen anzulegen bewirbt jetzt allein die Tour-Station „Deine Themen".
  ];
  const doneCount = steps.filter((s) => s.done || visited.includes(s.id)).length;
  const allDone = doneCount === steps.length;

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
    <Card className="relative flex flex-wrap items-center gap-3 overflow-hidden px-4 py-3" data-tour="erste-schritte">
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
          {/* Ein Knopf statt zweier: „Tour" und „Weitermachen" führten an
              verschiedene Orte — der auffälligere sprang nur stumm auf die
              nächste Seite, ohne dass Lotti auftauchte. Jetzt startet er
              immer die geführte Tour. Und beim allerersten Mal heißt er
              „Starten": „Weitermachen" behauptet einen Fortschritt, den es
              noch nicht gibt. */}
          <Button variant="secondary" size="sm" onClick={startGuidedTour} className="h-8 text-xs">
            <Play className="!size-3" />
            {visited.length === 0 ? "Tour starten" : "Weitermachen"}
            <ArrowRight className="!size-3.5" />
          </Button>
        </div>
      )}
    </Card>
  );
}
