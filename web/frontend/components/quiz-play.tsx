"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { Check, X, ExternalLink, ThumbsUp, ThumbsDown, ArrowRight, RotateCcw, Send, ChevronDown, ChevronUp, Lightbulb } from "lucide-react";
import { QuizQuestion, QuizAnswerResult } from "@/lib/types";
import { Card, Button, Input } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { ConfettiBurst } from "@/components/confetti";
import { GlossaryText } from "@/components/glossary-text";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

// Leaflet ist client-only + schwer → erst laden, wenn eine Karte gebraucht wird.
const LocatorMap = dynamic(() => import("@/components/quiz-locator-map").then((m) => m.LocatorMap), {
  ssr: false,
  loading: () => <div className="h-44 w-full animate-pulse rounded-lg bg-muted" />,
});

export const CATEGORY_LABEL: Record<string, string> = {
  geschichte: "Geschichte",
  orte: "Orte & Wahrzeichen",
  menschen: "Menschen",
  ratspolitik: "Ratspolitik",
  schaetzen: "Schätzfrage",
};
const SOURCE_LABEL: Record<string, string> = {
  wikipedia: "Wikipedia",
  stadt: "Stadt Oldenburg",
  ratsinfo: "Ratsinformationssystem",
};
const DIFF_LABEL: Record<string, string> = { leicht: "leicht", mittel: "mittel", schwer: "schwer" };

const nf = new Intl.NumberFormat("de-DE");
const fmt = (n: number | null | undefined) => (n == null ? "?" : nf.format(Math.round(n)));

/** Spielt eine Runde Fragen durch: eine Frage nach der anderen, sofortiges
 *  Feedback (Lösung, Erklärung, Quelle, Bewertung), am Ende eine Zusammenfassung.
 *  `onComplete` meldet das Endergebnis (z. B. um die Tages-Challenge zu buchen);
 *  `title` beschriftet den Runden-Kontext (Tages-Challenge / Meine Fehler). */
export function QuizPlay({ questions, onExit, onComplete, title }: {
  questions: QuizQuestion[];
  onExit: () => void;
  onComplete?: (r: { correct: number; total: number; points: number }) => void;
  title?: string;
}) {
  const [idx, setIdx] = useState(0);
  const [chosen, setChosen] = useState<number | null>(null);
  const [result, setResult] = useState<QuizAnswerResult | null>(null);
  const [rated, setRated] = useState<"gut" | "schlecht" | null>(null);
  const [comment, setComment] = useState("");
  const [commentSent, setCommentSent] = useState(false);
  const [points, setPoints] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [done, setDone] = useState(false);
  const [guess, setGuess] = useState<number | null>(null);
  const [showMore, setShowMore] = useState(false);
  const [hintShown, setHintShown] = useState(false);

  const q = questions[idx];
  const isEstimate = q.qtype === "estimate";
  const eMin = q.range_min ?? 0;
  const eMax = q.range_max ?? 100;
  const eStep = Math.max(1, Math.round((eMax - eMin) / 100));
  const eCurrent = guess ?? Math.round((eMin + eMax) / 2);

  async function choose(i: number) {
    if (chosen !== null) return;
    setChosen(i);
    try {
      const r = await api.post<QuizAnswerResult>("/quiz/answer", { question_id: q.id, selected_index: i });
      setResult(r);
      setPoints((p) => p + r.points);
      if (r.correct) setCorrect((c) => c + 1);
    } catch {
      setResult({ correct: false, correct_index: -1, points: 0, explanation: null, source_type: null, source_ref: null });
    }
  }

  async function submitEstimate(value: number) {
    if (chosen !== null) return;
    setChosen(value);
    try {
      const r = await api.post<QuizAnswerResult>("/quiz/answer", { question_id: q.id, value });
      setResult(r);
      setPoints((p) => p + r.points);
      if (r.correct) setCorrect((c) => c + 1);
    } catch {
      setResult({ correct: false, correct_index: -1, points: 0, answer_value: null, unit: null, explanation: null, source_type: null, source_ref: null });
    }
  }

  function next() {
    if (idx + 1 >= questions.length) {
      setDone(true);
      onComplete?.({ correct, total: questions.length, points });
      return;
    }
    setIdx((i) => i + 1);
    setChosen(null); setResult(null); setRated(null); setGuess(null); setShowMore(false);
    setHintShown(false); setComment(""); setCommentSent(false);
  }

  function rate(verdict: "gut" | "schlecht") {
    setRated(verdict);
    // Bewertung sofort speichern; bei „schlecht" darf optional noch ein Grund folgen.
    void api.post("/quiz/rate", { question_id: q.id, verdict }).catch(() => {});
  }

  function sendComment() {
    const text = comment.trim();
    setCommentSent(true);
    if (!text) return; // leer = übersprungen, die „schlecht"-Wertung steht schon
    // Upsert: dieselbe Wertung, jetzt mit Begründung.
    void api.post("/quiz/rate", { question_id: q.id, verdict: "schlecht", comment: text.slice(0, 500) }).catch(() => {});
  }

  if (done) {
    const quote = Math.round((correct / questions.length) * 100);
    return (
      <Card className="relative mx-auto max-w-xl overflow-hidden p-8 text-center">
        {correct > 0 && <ConfettiBurst />}
        <Mascot pose={quote >= 60 ? "celebrate" : "wave"} className="mx-auto h-20 w-20" />
        <h2 className="mt-3 text-2xl font-bold text-foreground">
          {correct} von {questions.length} richtig
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {points} {points === 1 ? "Punkt" : "Punkte"} · Trefferquote {quote} %
        </p>
        <p className="mt-4 text-sm text-foreground">
          {quote >= 80 ? "Stark — du kennst dich aus!" : quote >= 50 ? "Gut gemacht. Da geht noch mehr!" : "Weiter üben lohnt sich — du wirst besser."}
        </p>
        <Button onClick={onExit} className="mt-6"><RotateCcw className="!size-4" /> Zur Auswahl</Button>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-xl">
      {title && <p className="mb-2 text-sm font-semibold text-primary">{title}</p>}
      {/* Fortschritt */}
      <div className="mb-4 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out-strong"
               style={{ width: `${(idx / questions.length) * 100}%` }} />
        </div>
        <span className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
          {idx + 1}/{questions.length}
        </span>
      </div>

      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-md bg-primary/10 px-2 py-0.5 font-medium text-primary">
            {CATEGORY_LABEL[q.category] ?? q.category}
          </span>
          <span className="text-muted-foreground">{DIFF_LABEL[q.difficulty] ?? q.difficulty}</span>
        </div>
        <h2 className="mt-3 text-lg font-semibold leading-snug text-foreground">{q.question}</h2>

        {/* Optionaler Tipp — hilft bei schweren Fragen, ohne die Lösung zu
            verraten. Nur vor dem Auflösen anbietbar. */}
        {q.hint && chosen === null && (
          hintShown ? (
            <p className="mt-3 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-foreground">
              <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              <span>{q.hint}</span>
            </p>
          ) : (
            <button type="button" onClick={() => setHintShown(true)}
              className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-amber-600 hover:underline dark:text-amber-500">
              <Lightbulb className="h-4 w-4" /> Tipp anzeigen
            </button>
          )
        )}

        {isEstimate ? (
          <div className="mt-6">
            <div className="mb-3 text-center text-3xl font-bold tabular-nums text-foreground">
              {fmt(eCurrent)}{" "}
              {q.unit && <span className="text-lg font-medium text-muted-foreground">{q.unit}</span>}
            </div>
            <input
              type="range" min={eMin} max={eMax} step={eStep} value={eCurrent}
              disabled={chosen !== null}
              onChange={(e) => setGuess(Number(e.target.value))}
              aria-label="Schätzwert"
              className="w-full accent-primary disabled:opacity-60"
            />
            <div className="mt-1 flex justify-between text-xs tabular-nums text-muted-foreground">
              <span>{fmt(eMin)}</span>
              <span>{fmt(eMax)}</span>
            </div>
            {chosen === null && (
              <Button className="mt-4 w-full" onClick={() => submitEstimate(eCurrent)}>
                Schätzung abgeben
              </Button>
            )}
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-2">
            {q.options.map((opt, i) => {
              const isChosen = chosen === i;
              const isCorrect = result && i === result.correct_index;
              const state = result
                ? isCorrect ? "correct" : isChosen ? "wrong" : "idle"
                : "idle";
              return (
                <button
                  key={i}
                  type="button"
                  disabled={chosen !== null}
                  onClick={() => choose(i)}
                  className={cn(
                    "flex items-center justify-between gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-colors",
                    state === "idle" && "border-border hover:border-primary/50 hover:bg-primary/5 disabled:opacity-60",
                    state === "correct" && "border-green-500 bg-green-500/10 text-foreground",
                    state === "wrong" && "border-red-500 bg-red-500/10 text-foreground",
                  )}
                >
                  <span>{opt}</span>
                  {state === "correct" && <Check className="h-4 w-4 shrink-0 text-green-600" />}
                  {state === "wrong" && <X className="h-4 w-4 shrink-0 text-red-600" />}
                </button>
              );
            })}
          </div>
        )}

        {result && (
          <div className="mt-4 rounded-lg border border-border bg-muted/40 p-3">
            <p className="text-sm font-medium text-foreground">
              {result.correct
                ? `Richtig! +${result.points}`
                : result.points > 0 ? `Nah dran! +${result.points}` : "Leider daneben."}
            </p>
            {isEstimate && result.answer_value != null && (
              <p className="mt-1 text-sm text-foreground">
                Richtige Antwort:{" "}
                <span className="font-semibold tabular-nums">{fmt(result.answer_value)} {result.unit}</span>
              </p>
            )}
            {result.explanation && (
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground"><GlossaryText text={result.explanation} /></p>
            )}

            {/* „Mehr dazu": ausführliche Erklärung, Foto (mit Bildnachweis) und
                eine kleine Karte — nur wenn zur Frage vorhanden, aufklappbar. */}
            {(result.detail || result.image || result.map) && (
              <div className="mt-2">
                <button type="button" onClick={() => setShowMore((v) => !v)}
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                  {showMore ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  {showMore ? "Weniger" : "Mehr dazu"}
                </button>
                {showMore && (
                  <div className="mt-2 space-y-3">
                    {result.detail && (
                      <p className="text-sm leading-relaxed text-foreground"><GlossaryText text={result.detail} /></p>
                    )}
                    {result.image && (
                      <figure className="overflow-hidden rounded-lg border border-border">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={result.image.url} alt={result.map?.label || "Foto zur Frage"}
                             className="max-h-64 w-full object-cover" />
                        <figcaption className="px-2 py-1 text-[11px] leading-snug text-muted-foreground">
                          Foto: {result.image.author || "unbekannt"}
                          {result.image.license && (
                            <> · {result.image.license_url ? (
                              <a href={result.image.license_url} target="_blank" rel="noreferrer" className="hover:underline">{result.image.license}</a>
                            ) : result.image.license}</>
                          )}
                          {" · "}
                          {result.image.source_url ? (
                            <a href={result.image.source_url} target="_blank" rel="noreferrer" className="hover:underline">Wikimedia Commons</a>
                          ) : "Wikimedia Commons"}
                        </figcaption>
                      </figure>
                    )}
                    {result.map && (
                      <LocatorMap lat={result.map.lat} lon={result.map.lon} label={result.map.label}
                                  geojson={result.map.geojson} className="h-44 w-full" />
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              {result.source_ref && result.source_type ? (
                result.source_ref.startsWith("http") ? (
                  <a href={result.source_ref} target="_blank" rel="noreferrer"
                     className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                    Quelle: {SOURCE_LABEL[result.source_type] ?? result.source_type}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    Quelle: {SOURCE_LABEL[result.source_type] ?? result.source_type}
                  </span>
                )
              ) : <span />}
              {/* Qualitäts-Bewertung — hilft schlechte Fragen auszutauschen */}
              <span className="inline-flex items-center gap-1.5">
                {rated ? (
                  <span className="text-xs text-muted-foreground">Danke fürs Feedback</span>
                ) : (
                  <>
                    <span className="text-xs text-muted-foreground">Gute Frage?</span>
                    <button type="button" aria-label="Gute Frage" onClick={() => rate("gut")}
                      className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-green-600">
                      <ThumbsUp className="h-4 w-4" />
                    </button>
                    <button type="button" aria-label="Schlechte Frage melden" onClick={() => rate("schlecht")}
                      className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-red-600">
                      <ThumbsDown className="h-4 w-4" />
                    </button>
                  </>
                )}
              </span>
            </div>
            {/* Nach 👎 optional (nicht Pflicht) ein Grund — hilft, schlechte
                Fragen gezielt zu ersetzen. Die Wertung selbst ist schon gebucht. */}
            {rated === "schlecht" && !commentSent && (
              <div className="mt-2 flex items-center gap-2">
                <Input
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") sendComment(); }}
                  maxLength={500}
                  placeholder="Optional: Was ist an der Frage schlecht?"
                  className="h-8 text-sm"
                />
                <Button variant="secondary" size="sm" className="shrink-0" onClick={sendComment}>
                  <Send className="!size-3.5" /> Senden
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>

      <div className="mt-4 flex justify-end">
        <Button onClick={next} disabled={chosen === null}>
          {idx + 1 >= questions.length ? "Ergebnis" : "Weiter"} <ArrowRight className="!size-4" />
        </Button>
      </div>
    </div>
  );
}
