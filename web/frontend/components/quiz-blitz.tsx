"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Zap, RotateCcw, Trophy } from "lucide-react";
import type { QuizQuestion, QuizAnswerResult } from "@/lib/types";
import { Card, Button } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { ConfettiBurst } from "@/components/confetti";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const DURATION_MS = 60_000;
/** So lange steht die Tönung „richtig/falsch", bevor die nächste Frage kommt. */
const FEEDBACK_MS = 320;

type Phase = "ready" | "play" | "done";
type Summary = { best: number; today_best: number; new_best: boolean };

/** Blitzrunde (Plan Q6): 60 Sekunden, so viele Fragen wie möglich. Jede
 *  Antwort läuft über `/quiz/answer` (Punkte, Statistik wie immer); nach
 *  einer kurzen Tönung kommt sofort die nächste Frage, ohne Auflösungstext.
 *  Die Combo („3 in Folge") ist reine Anzeige. */
export function QuizBlitz({ onExit }: { onExit: () => void }) {
  const [phase, setPhase] = useState<Phase>("ready");
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<{ i: number; correctIndex: number } | null>(null);
  const [correct, setCorrect] = useState(0);
  const [answered, setAnswered] = useState(0);
  const [combo, setCombo] = useState(0);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const deadline = useRef(0);
  const barRef = useRef<HTMLDivElement>(null);
  const stats = useRef({ correct: 0, answered: 0 });

  const finish = useCallback(async () => {
    setPhase("done");
    try {
      setSummary(await api.post<Summary>("/quiz/blitz/complete", stats.current));
    } catch { /* ohne Bestmarke geht es auch */ }
  }, []);

  async function start() {
    setLoading(true);
    try {
      const r = await api.get<{ questions: QuizQuestion[] }>("/quiz/blitz-round?n=40");
      if (!r.questions.length) return;
      setQuestions(r.questions);
      setIdx(0); setCorrect(0); setAnswered(0); setCombo(0); setPicked(null); setSummary(null);
      stats.current = { correct: 0, answered: 0 };
      deadline.current = Date.now() + DURATION_MS;
      setPhase("play");
    } finally {
      setLoading(false);
    }
  }

  // Die Uhr: eine Leiste, die per transform schrumpft (keine animierte
  // Breite, DESIGNSPRACHE §7), und das Ende der Runde.
  useEffect(() => {
    if (phase !== "play") return;
    let raf = 0;
    const tick = () => {
      const left = Math.max(0, deadline.current - Date.now());
      if (barRef.current) barRef.current.style.transform = `scaleX(${left / DURATION_MS})`;
      if (left <= 0) { void finish(); return; }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [phase, finish]);

  const q = questions[idx];

  async function choose(i: number) {
    if (!q || picked) return;
    let r: QuizAnswerResult | null = null;
    try {
      r = await api.post<QuizAnswerResult>("/quiz/answer", { question_id: q.id, selected_index: i });
    } catch { /* als falsch zählen */ }
    const ok = !!r?.correct;
    stats.current = { correct: stats.current.correct + (ok ? 1 : 0), answered: stats.current.answered + 1 };
    setCorrect(stats.current.correct);
    setAnswered(stats.current.answered);
    setCombo((c) => (ok ? c + 1 : 0));
    setPicked({ i, correctIndex: r?.correct_index ?? -1 });
    window.setTimeout(() => {
      setPicked(null);
      if (Date.now() >= deadline.current) return;
      if (idx + 1 >= questions.length) { void finish(); return; }
      setIdx((x) => x + 1);
    }, FEEDBACK_MS);
  }

  if (phase === "ready") {
    return (
      <Card className="mx-auto max-w-xl p-8 text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-500">
          <Zap className="h-6 w-6" />
        </span>
        <h2 className="mt-4 text-2xl font-bold text-foreground">Blitzrunde</h2>
        <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
          60 Sekunden, so viele Fragen wie möglich. Nach jeder Antwort geht es sofort weiter.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button variant="secondary" onClick={onExit}>Zurück</Button>
          <Button onClick={() => void start()} disabled={loading}><Zap className="!size-4" /> Los geht&apos;s</Button>
        </div>
      </Card>
    );
  }

  if (phase === "done") {
    return (
      <Card className="relative mx-auto max-w-xl overflow-hidden p-8 text-center">
        {summary?.new_best && correct > 0 && <ConfettiBurst />}
        <Mascot pose={summary?.new_best ? "celebrate" : "wave"} regung={summary?.new_best ? "hebt-pokal" : undefined}
          regie="lebhaft" className="mx-auto h-24 w-24" />
        <h2 className="mt-3 text-2xl font-bold text-foreground">{correct} richtig</h2>
        <p className="mt-1 text-sm text-muted-foreground">von {answered} beantworteten Fragen in 60 Sekunden</p>
        {summary && (
          <p className="mx-auto mt-4 inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-3 py-1 text-sm text-foreground">
            <Trophy className="h-4 w-4 text-amber-600" />
            {summary.new_best ? "Neue Bestmarke!" : `Deine Bestmarke: ${summary.best}`}
          </p>
        )}
        <div className="mt-6 flex justify-center gap-2">
          <Button variant="secondary" onClick={onExit}>Zur Auswahl</Button>
          <Button onClick={() => void start()} disabled={loading}><RotateCcw className="!size-4" /> Nochmal</Button>
        </div>
      </Card>
    );
  }

  if (!q) return null;
  const two = q.options.length === 2;
  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-4 flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
          <div ref={barRef} className="h-full w-full origin-left rounded-full bg-amber-500" />
        </div>
        <span className="shrink-0 text-sm font-semibold tabular-nums text-foreground">{correct}</span>
      </div>
      <Card className="p-5">
        <div className="flex h-5 items-center justify-between text-xs">
          <span className="text-muted-foreground">Frage {answered + 1}</span>
          {combo >= 2 && (
            <span key={combo} className="font-semibold text-amber-700 animate-in zoom-in-95 duration-tipp dark:text-amber-500">
              {combo} in Folge
            </span>
          )}
        </div>
        <h2 className="mt-2 text-lg font-semibold leading-snug text-foreground">{q.question}</h2>
        <div className={cn("mt-4 gap-2", two ? "grid grid-cols-2" : "flex flex-col")}>
          {q.options.map((opt, i) => {
            const state = !picked ? "idle"
              : i === picked.correctIndex ? "correct"
                : i === picked.i ? "wrong" : "idle";
            return (
              <button key={`${q.id}-${i}`} type="button" disabled={!!picked} onClick={() => void choose(i)}
                className={cn(
                  "rounded-lg border px-4 py-3 text-sm transition-colors duration-tipp active:scale-[0.98]",
                  two ? "min-h-20 text-center font-semibold" : "text-left",
                  state === "idle" && "border-border hover:border-primary/50 hover:bg-primary/5",
                  state === "correct" && "border-green-600/40 bg-green-500/10",
                  state === "wrong" && "border-red-600/40 bg-red-500/10",
                )}>
                {opt}
              </button>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
