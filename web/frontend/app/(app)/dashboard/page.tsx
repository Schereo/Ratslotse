"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, ArrowRight, Check, Play } from "lucide-react";
import { api } from "@/lib/api";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { useAuth } from "@/lib/auth";
import { Topic } from "@/lib/types";
import { useHeute } from "@/lib/use-heute";
import { Button, Card } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { SitzungspauseBanner } from "@/components/sitzungspause-banner";
import { LiveBanner } from "@/components/live-banner";
import { FundstueckCard } from "@/components/fundstueck-card";
import { NeueTrefferKarte } from "@/components/neue-treffer-karte";
import { HeuteWidget } from "@/components/heute-widget";
import { RecentDecisions } from "@/components/recent-decisions";
import { WocheImRat, type Wochenvorschau } from "@/components/woche-im-rat";
import { HinweisSlot } from "@/components/note-slot";
import { PushPrimer } from "@/components/push-primer";
import { WahlabendHinweis } from "@/components/wahlabend-hinweis";
import { ReleaseNewsCard } from "@/components/release-news-card";
import { formatEuro } from "@/components/decision-ui";
import { fragenHref, decisionHref, viertelHref } from "@/lib/routes";
import { useFeature } from "@/lib/features";
import { MapPinned } from "lucide-react";
import { startGuidedTour } from "@/components/tour";
import { ConfettiBurst } from "@/components/confetti";
import { useOnboarding, type StepId } from "@/components/onboarding";
import { useCountUp } from "@/lib/use-countup";
import { STAFFEL, staffelStil } from "@/components/staffel";
import { cn } from "@/lib/utils";

const FRAGEN_HREF = fragenHref();

// Aus dem API-Vertrag statt von Hand — `kind` unterscheidet die Fälle.
type ZahlDerWoche = ApiAntwort<"/council/zahl-der-woche">;

/** ISO-Datum von vor n Tagen — Ziel des „Diese N ansehen"-Links (Design 28a/S5).
 *  Dasselbe Fenster, das der Endpoint gezählt hat, damit die Suche wirklich
 *  dieselben Beschlüsse zeigt wie die Zahl auf der Karte. */
const lastWeekIso = (days: number) =>
  new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);


/** Heute: persönliche Neuigkeiten zuerst, daneben die Woche und ihre Zahl. */
export default function DashboardPage() {
  const { user } = useAuth();
  const heute = useHeute();

  // Datumszeile erst nach dem Mount (vermeidet SSR/Client-Hydration-Drift).
  const [today, setToday] = useState("");
  useEffect(() => {
    setToday(new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" }));
  }, []);

  const topicsQuery = useQuery({ queryKey: ["topics"], queryFn: () => api.get<Topic[]>("/topics") });

  const zahlQuery = useQuery({
    queryKey: ["zahl-der-woche"],
    queryFn: () => vertrag.get("/council/zahl-der-woche"),
  });
  // Design 14: Die Wochen-Karte steht jetzt IMMER — sie ersetzt „Nächste
  // Sitzungen" und ist damit die vollständige Sicht auf die Woche, nicht mehr
  // ein Ersatz für einen Leerzustand.
  const vorschauQuery = useQuery({
    queryKey: ["wochenvorschau"],
    queryFn: () => api.get<Wochenvorschau>("/council/week-preview"),
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
      {/* Kopf: Begrüßung + DIE Signal-Handlung des Screens („Frag den Rat").
          Die vier Blöcke des Briefings laufen versetzt ein (s.
          components/staffel.tsx) — man liest die Seite in der Reihenfolge,
          in der sie gemeint ist, statt vor einem fertigen Block zu stehen. */}
      <div className={cn("flex flex-wrap items-center justify-between gap-4", STAFFEL)} style={staffelStil(0)}>
        <div className="flex min-w-0 items-center gap-4">
          <Mascot pose="wave" className="h-[72px] w-[72px] shrink-0 sm:h-[88px] sm:w-[88px]" />
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
        className={cn("mt-6", STAFFEL)}
        style={staffelStil(1)}
        hinweise={[
          // Am Wahlabend das Dringendste — der Schalter `wahlabend` entscheidet.
          { key: "wahlabend", label: "Wahlabend", node: <WahlabendHinweis /> },
          { key: "live", label: "Sitzung läuft", node: <LiveBanner /> },
          { key: "pause", label: "Sitzungspause", node: <SitzungspauseBanner /> },
          { key: "erste-schritte", label: "Erste Schritte", node: <FirstStepsBar /> },
          // „Neu bei Ratslotse": nach allem, was gerade passiert (Sitzung,
          // Wahlabend), aber vor der Push-Frage — sie kommt wieder, ein
          // Release nicht.
          { key: "neuigkeiten", label: "Neu bei Ratslotse", node: <ReleaseNewsCard /> },
          { key: "push", label: "Mitteilungen", node: <PushPrimer /> },
        ]}
      />

      {/* Eigenständige Widgets: mobil zuerst die persönlichen Neuigkeiten,
          dann die Woche. Zwei unabhängige Spalten vermeiden Leerraum zwischen
          den unterschiedlich hohen Karten; die Containerbreite entscheidet. */}
      <div className={cn("@container/raster mt-6", STAFFEL)} style={staffelStil(2)}>
        <div className="grid grid-cols-1 items-start gap-4 @3xl/raster:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <NeueTrefferKarte />
          <div className="min-w-0 space-y-4">
            {vorschau && <WocheImRat vorschau={vorschau} heuteIso={heuteIso} />}

          {/* Zahl der Woche (RL-905) — eine Zahl und ein Satz, braucht am
              wenigsten Breite. */}
          <HeuteWidget id="zahl-der-woche" title="Zahl der Woche" className="border-signal/30 bg-signal/5">
            {zahl?.kind === "amount" && (
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
            {zahl?.kind === "count" && (
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
          </HeuteWidget>
          </div>
        </div>
      </div>

      {/* „Mein Viertel" (Feature-Schalter): eine Zeile je gewähltem Stadtteil
          mit der Zahl seiner Vorhaben — der Weg zur Tafel. Ohne gewählten
          Stadtteil führt die Karte zur Auswahl. */}
      <MeinViertelKarte topics={topicsQuery.data} />

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

/** „Mein Viertel" auf der Startseite: je gewähltem Stadtteil (ein Stadtteil
 *  IST ein Thema, s. Einrichtungs-Assistent) die Zahl seiner Vorhaben mit dem
 *  Sprung zur Tafel. Hängt am Feature-Schalter `mein-viertel`; ohne ihn
 *  rendert die Karte nichts. */
function MeinViertelKarte({ topics }: { topics: Topic[] | undefined }) {
  const an = useFeature("mein-viertel");
  const uebersicht = useQuery({
    queryKey: ["viertel-uebersicht"],
    queryFn: () => api.get<ApiAntwort<"/districts/projects">>("/districts/projects"),
    enabled: an,
    staleTime: 10 * 60_000,
  });
  if (!an) return null;
  const orte = uebersicht.data?.districts ?? [];
  const meine = orte.filter((o) => (topics ?? []).some((t) => t.name.toLowerCase() === o.name.toLowerCase()));
  return (
    <Card className={cn("mt-6 p-5", STAFFEL)} style={staffelStil(4)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-base font-bold text-foreground">Mein Viertel</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {meine.length > 0
              ? "Was sich in deinem Stadtteil in den nächsten Jahren ändert."
              : "Was sich in deinem Stadtteil in den nächsten Jahren ändert — wähle ihn auf der Karte."}
          </p>
        </div>
        <span className="rounded-xl bg-primary/10 p-2 text-primary"><MapPinned className="h-5 w-5" /></span>
      </div>
      {meine.length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {meine.map((o) => (
            <li key={o.place_id}>
              <Link href={viertelHref(o.place_id)} className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent">
                {o.name}
                <span className="rounded-full bg-primary/10 px-1.5 text-xs tabular-nums text-primary">{o.count}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <Link href={viertelHref()} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
          Stadtteil wählen <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      )}
    </Card>
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
    { id: "karten", title: "Die Stadtkarte entdecken", href: "/karte" },
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
          {allDone ? "Geschafft — du hast alles erkundet!" : "Erste Schritte mit Lotti"}
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
