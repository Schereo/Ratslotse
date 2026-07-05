"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { MapPin, Play, ArrowRight, RotateCcw } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { ConfettiBurst } from "@/components/confetti";
import { api } from "@/lib/api";

// Leaflet ist client-only + schwer → erst beim Spielen laden.
const QuizMap = dynamic(() => import("@/components/quiz-map").then((m) => m.QuizMap), {
  ssr: false,
  loading: () => <div className="h-[360px] w-full animate-pulse rounded-xl bg-muted sm:h-[440px]" />,
});

type MapResult = { correct: boolean; points: number };

/** Karten-Quiz: „Wo liegt Stadtteil X?" — pro Frage die Oldenburg-Karte, der
 *  Nutzer klickt den Stadtteil an, danach Auflösung (grün = richtig). */
export function QuizMapPlay({ targets, onExit }: { targets: string[]; onExit: () => void }) {
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [result, setResult] = useState<MapResult | null>(null);
  const [points, setPoints] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [done, setDone] = useState(false);

  const target = targets[idx];

  async function pick(name: string) {
    if (result) return;
    setPicked(name);
    try {
      const r = await api.post<{ correct: boolean; target: string; points: number }>(
        "/quiz/map-answer", { target, clicked: name });
      setResult({ correct: r.correct, points: r.points });
      setPoints((p) => p + r.points);
      if (r.correct) setCorrect((c) => c + 1);
    } catch {
      setResult({ correct: name === target, points: 0 });
    }
  }

  function next() {
    if (idx + 1 >= targets.length) { setDone(true); return; }
    setIdx((i) => i + 1);
    setPicked(null);
    setResult(null);
  }

  if (done) {
    const quote = Math.round((correct / targets.length) * 100);
    return (
      <Card className="relative mx-auto max-w-xl overflow-hidden p-8 text-center">
        {correct > 0 && <ConfettiBurst />}
        <Mascot pose={quote >= 60 ? "celebrate" : "wave"} className="mx-auto h-20 w-20" />
        <h2 className="mt-3 text-2xl font-bold text-foreground">{correct} von {targets.length} gefunden</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {points} {points === 1 ? "Punkt" : "Punkte"} · Trefferquote {quote} %
        </p>
        <p className="mt-4 text-sm text-foreground">
          {quote >= 80 ? "Top — du kennst deine Stadtteile!" : quote >= 50 ? "Gut! Ein paar Ecken noch." : "Weiter erkunden lohnt sich."}
        </p>
        <Button onClick={onExit} className="mt-6"><RotateCcw className="!size-4" /> Zur Auswahl</Button>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-xl">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-primary">
        <MapPin className="h-4 w-4" /> Karten-Quiz
      </p>
      <div className="mb-4 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out-strong"
               style={{ width: `${(idx / targets.length) * 100}%` }} />
        </div>
        <span className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">{idx + 1}/{targets.length}</span>
      </div>

      <Card className="p-4">
        <h2 className="text-lg font-semibold leading-snug text-foreground">
          Wo liegt <span className="text-primary">{target}</span>?
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {result ? "Grün = richtig." : "Tippe den Stadtteil auf der Karte an."}
        </p>

        <QuizMap
          className="mt-3 h-[360px] w-full sm:h-[440px]"
          picked={picked}
          solution={result ? target : null}
          disabled={result !== null}
          onPick={pick}
        />

        {result && (
          <div className="mt-3 rounded-lg border border-border bg-muted/40 p-3">
            <p className="text-sm font-medium text-foreground">
              {result.correct ? `Richtig! +${result.points}` : "Leider daneben."}
            </p>
            {!result.correct && (
              <p className="mt-1 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{target}</span> ist grün markiert
                {picked ? <> — angetippt hattest du <span className="font-medium text-foreground">{picked}</span>.</> : "."}
              </p>
            )}
          </div>
        )}
      </Card>

      <div className="mt-4 flex justify-end">
        <Button onClick={next} disabled={result === null}>
          {idx + 1 >= targets.length ? "Ergebnis" : "Weiter"} <ArrowRight className="!size-4" />
        </Button>
      </div>
    </div>
  );
}

/** Einstieg zum Karten-Quiz auf der Quiz-Startseite. */
export function QuizMapCard({ onStart }: { onStart: () => void }) {
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 border-emerald-500/30 bg-emerald-500/5 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
          <MapPin className="h-5 w-5" />
        </div>
        <div>
          <p className="font-semibold text-foreground">Karten-Quiz</p>
          <p className="text-sm text-muted-foreground">Finde Stadtteile auf der Oldenburg-Karte.</p>
        </div>
      </div>
      <Button className="shrink-0" onClick={onStart}>
        <Play className="!size-4" /> Karten-Quiz starten
      </Button>
    </Card>
  );
}
