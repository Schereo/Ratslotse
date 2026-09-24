"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { Crosshair, ArrowRight, RotateCcw } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { ConfettiBurst } from "@/components/confetti";
import { LottiReaction } from "@/components/quiz-play";
import { api } from "@/lib/api";

const PinMap = dynamic(() => import("@/components/quiz-pin-map").then((m) => m.PinMap), {
  ssr: false,
  loading: () => <div className="h-[clamp(340px,55dvh,720px)] w-full animate-pulse rounded-xl bg-muted" />,
});

export type PinQuestion = { slug: string; name: string; kind_label: string };
type PinResult = { distance_m: number; distance_label: string; points: number; name: string; geojson: object };

/** „Wo liegt das?" (Plan Q7): ein Ort, ein Pin, dann die Entfernung zur
 *  echten Lage. Wie das Karten-Quiz eine Frage je Bildschirm. */
export function QuizPinPlay({ questions, onExit }: { questions: PinQuestion[]; onExit: () => void }) {
  const [idx, setIdx] = useState(0);
  const [pin, setPin] = useState<{ lat: number; lon: number } | null>(null);
  const [result, setResult] = useState<PinResult | null>(null);
  const [points, setPoints] = useState(0);
  const [hits, setHits] = useState(0);
  const [done, setDone] = useState(false);
  const [sending, setSending] = useState(false);
  const q = questions[idx];

  async function submit() {
    if (!pin || result || sending) return;
    setSending(true);
    try {
      const r = await api.post<PinResult>("/quiz/pin-answer", { slug: q.slug, ...pin });
      setResult(r);
      setPoints((p) => p + r.points);
      if (r.points >= 2) setHits((h) => h + 1);
    } finally {
      setSending(false);
    }
  }

  function next() {
    if (idx + 1 >= questions.length) { setDone(true); return; }
    setIdx((i) => i + 1); setPin(null); setResult(null);
  }

  if (done) {
    const max = questions.length * 3;
    const good = points >= max * 0.6;
    return (
      <Card className="relative mx-auto max-w-xl overflow-hidden p-8 text-center">
        {good && <ConfettiBurst />}
        <Mascot pose={good ? "celebrate" : "wave"} regie="lebhaft" className="mx-auto h-24 w-24" />
        <h2 className="mt-3 text-2xl font-bold text-foreground">{points} von {max} Punkten</h2>
        <p className="mt-1 text-sm text-muted-foreground">{hits} von {questions.length} Orten gut getroffen</p>
        <Button onClick={onExit} className="mt-6"><RotateCcw className="!size-4" /> Zur Auswahl</Button>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-primary">
        <Crosshair className="h-4 w-4" /> Wo liegt das?
      </p>
      <div className="mb-4 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out-strong"
               style={{ width: `${((idx + 1) / questions.length) * 100}%` }} />
        </div>
        <span className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">{idx + 1}/{questions.length}</span>
      </div>
      <Card className="p-4">
        <p className="text-xs font-medium text-muted-foreground">{q.kind_label}</p>
        <h2 className="text-lg font-semibold leading-snug text-foreground">
          Wo liegt <span className="text-primary">{q.name}</span>?
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {result ? "Grün ist die echte Lage, orange dein Pin." : pin ? "Pin versetzen: einfach woanders tippen." : "Tippe auf die Karte, wo du den Ort vermutest."}
        </p>
        <PinMap key={q.slug} className="mt-3 h-[clamp(340px,55dvh,720px)] w-full" pin={pin}
          solution={result?.geojson ?? null} onPin={setPin} />
        {result ? (
          <div className="mt-3 rounded-lg border border-border bg-muted/40 p-3">
            <LottiReaction seed={idx} outcome={result.points >= 2 ? "right" : result.points === 1 ? "close" : "wrong"}>
              {result.points > 0 ? `${result.distance_label} — +${result.points}` : `${result.distance_label}`}
            </LottiReaction>
          </div>
        ) : null}
      </Card>
      <div className="mt-4 flex justify-end">
        {result ? (
          <Button onClick={next}>{idx + 1 >= questions.length ? "Ergebnis" : "Weiter"} <ArrowRight className="!size-4" /></Button>
        ) : (
          <Button onClick={() => void submit()} disabled={!pin || sending}><Crosshair className="!size-4" /> Hier ist es</Button>
        )}
      </div>
    </div>
  );
}
