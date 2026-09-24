"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Check, X, ExternalLink, ThumbsUp, ThumbsDown, ArrowRight, RotateCcw, Send, ChevronDown, ChevronUp, Lightbulb, Scale } from "lucide-react";
import { QuizQuestion, QuizAnswerResult } from "@/lib/types";
import { Card, Button, Input } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { ConfettiBurst } from "@/components/confetti";
import { GlossaryText } from "@/components/glossary-text";
import { QuizChart } from "@/components/quiz-chart";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { FrageChips } from "@/components/frage-chips";

// Leaflet ist client-only + schwer → erst laden, wenn eine Karte gebraucht wird.
const LocatorMap = dynamic(() => import("@/components/quiz-locator-map").then((m) => m.LocatorMap), {
  ssr: false,
  loading: () => <div className="h-44 w-full animate-pulse rounded-lg bg-muted" />,
});

export const CATEGORY_LABEL: Record<string, string> = {
  history: "Geschichte",
  places: "Orte & Wahrzeichen",
  people: "Menschen",
  council_politics: "Ratspolitik",
  estimation: "Schätzfrage",
};
/** Die Bauform sagt mehr als die Kategorie: Ein Haushaltsvergleich ist keine
 *  Schätzfrage mit Schieber, ein Antrag keine gewöhnliche Ratspolitik-Frage. */
const FORMAT_LABEL: Record<string, string> = {
  verdict: "Antrag",
  compare: "Vergleich",
  order: "Reihenfolge",
};
const SOURCE_LABEL: Record<string, string> = {
  wikipedia: "Wikipedia",
  city: "Stadt Oldenburg",
  ratsinfo: "Ratsinformationssystem",
};
const DIFF_LABEL: Record<string, string> = { easy: "leicht", medium: "mittel", hard: "schwer" };

const nf = new Intl.NumberFormat("de-DE");
const nf1 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });

/** Betrag einer Vergleichs-Antwort aus dem Diagramm der Auflösung — die
 *  Balken tragen dieselben Beschriftungen wie die beiden Antworten. */
function compareAmount(result: QuizAnswerResult | null, option: string): string | null {
  const item = result?.chart?.items.find((it) => it.label === option);
  if (!item || !result?.chart) return null;
  return result.chart.unit === "Mio. Euro" ? `${nf1.format(item.value)} Mio. €` : `${nf1.format(item.value)} ${result.chart.unit}`;
}
const fmt = (n: number | null | undefined) => (n == null ? "?" : nf.format(Math.round(n)));

// Lottis Reaktionen auf die Auflösung — kurz und aufmunternd, nie belehrend.
// Deterministisch je Frage gewählt (q.id), damit der Spruch beim Re-Render
// (Bewerten, „Mehr dazu") stabil bleibt.
const LOTTI_RIGHT = [
  "Volltreffer — du kennst dich aus!",
  "Genau richtig. Weiter so!",
  "Stark — das sitzt.",
];
const LOTTI_CLOSE = [
  "Fast! Das war richtig knapp.",
  "Nah dran — gutes Gespür!",
];
const LOTTI_WRONG = [
  "Macht nichts — jetzt kennst du die Antwort.",
  "Knifflige Frage. Beim nächsten Mal weißt du es.",
  "Knapp daneben — weiter geht’s.",
];
const lottiSays = (pool: string[], seed: number) => pool[seed % pool.length];

/** Lottis Reaktion auf eine Antwort: jubelt bei richtig, winkt bei „nah dran",
 *  schaut ratlos bei daneben — plus ein kurzer aufmunternder Spruch. Dekorativ
 *  fürs Screenreader (die Verdikt-Zeile sagt alles). Auch im Karten-Quiz. */
export function LottiReaction({ outcome, seed, children }: {
  outcome: "right" | "close" | "wrong";
  seed: number;
  children: React.ReactNode;
}) {
  // Aus dem Regungs-Katalog: Beifall bei richtig, anerkennendes Nicken bei
  // knapp, Kopfschütteln (nie Enttäuschung) bei daneben.
  const regung = outcome === "right" ? "klatscht" : outcome === "close" ? "nickt" : "schuettelt-kopf";
  const pool = outcome === "right" ? LOTTI_RIGHT : outcome === "close" ? LOTTI_CLOSE : LOTTI_WRONG;
  return (
    <div className="flex items-center gap-2.5">
      <Mascot decorative regung={regung} className="h-14 w-14 shrink-0" />
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{children}</p>
        <p className="text-xs text-muted-foreground">{lottiSays(pool, seed)}</p>
      </div>
    </div>
  );
}

/** Spielt eine Runde Fragen durch: eine Frage nach der anderen, sofortiges
 *  Feedback (Lösung, Erklärung, Quelle, Bewertung), am Ende eine Zusammenfassung.
 *  `onComplete` meldet das Endergebnis (z. B. um die Tages-Challenge zu buchen);
 *  `title` beschriftet den Runden-Kontext (Tages-Challenge / Meine Fehler).
 *  `practice` (RL-U14, eigene Fragen): Antworten laufen über `answerPath`,
 *  ohne Punkte, ohne Qualitäts-Bewertung — nur Üben. */
export function QuizPlay({ questions, onExit, onComplete, title, answerPath = "/quiz/answer", practice = false }: {
  questions: QuizQuestion[];
  onExit: () => void;
  onComplete?: (r: { correct: number; total: number; points: number }) => void;
  title?: string;
  answerPath?: string;
  practice?: boolean;
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
  // Reihenfolge-Frage: die angetippten Antworten, Platz 1 zuerst.
  const [orderPicks, setOrderPicks] = useState<number[]>([]);

  const q = questions[idx];
  const isEstimate = q.qtype === "estimate";
  const eMin = q.range_min ?? 0;
  const eMax = q.range_max ?? 100;
  const eStep = Math.max(1, Math.round((eMax - eMin) / 100));
  // Start bewusst NICHT in der Mitte: Die Spannen liegen oft symmetrisch um die
  // richtige Zahl — wer den Slider gar nicht bewegte, lag damit „zufällig"
  // richtig. Deterministisch je Frage bei ~22 % bzw. ~78 % der Spanne.
  const eStart = Math.min(eMax, Math.max(eMin,
    Math.round((eMin + (eMax - eMin) * (q.id % 2 === 0 ? 0.22 : 0.78)) / eStep) * eStep));
  const eCurrent = guess ?? eStart;

  async function choose(i: number) {
    if (chosen !== null) return;
    setChosen(i);
    try {
      const r = await api.post<QuizAnswerResult>(answerPath, { question_id: q.id, selected_index: i });
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
      const r = await api.post<QuizAnswerResult>(answerPath, { question_id: q.id, value });
      setResult(r);
      setPoints((p) => p + r.points);
      if (r.correct) setCorrect((c) => c + 1);
    } catch {
      setResult({ correct: false, correct_index: -1, points: 0, answer_value: null, unit: null, explanation: null, source_type: null, source_ref: null });
    }
  }

  function tapOrder(i: number) {
    if (chosen !== null) return;
    // Nochmal antippen nimmt die Antwort (und alles danach) wieder heraus.
    setOrderPicks((xs) => (xs.includes(i) ? xs.slice(0, xs.indexOf(i)) : [...xs, i]));
  }

  async function submitOrder() {
    if (chosen !== null || orderPicks.length !== q.options.length) return;
    setChosen(0);
    try {
      const r = await api.post<QuizAnswerResult>(answerPath, { question_id: q.id, order: orderPicks });
      setResult(r);
      setPoints((p) => p + r.points);
      if (r.correct) setCorrect((c) => c + 1);
    } catch {
      setResult({ correct: false, correct_index: -1, points: 0, explanation: null, source_type: null, source_ref: null });
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
    setHintShown(false); setComment(""); setCommentSent(false); setOrderPicks([]);
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
    // Lotti feiert mit — bzw. muntert auf: Pose und Botschaft folgen der Quote,
    // aber sie ist IMMER auf deiner Seite (nie enttäuscht). Ab 90 % tanzt sie.
    const pose = quote >= 80 ? "celebrate" : quote >= 50 ? "wave" : "point";
    const cheer =
      quote >= 90 ? "Sensationell — fast fehlerfrei!"
      : quote >= 80 ? "Stark — du kennst dich richtig gut aus!"
      : quote >= 50 ? "Gut gemacht! In der nächsten Runde kannst du noch etwas entdecken."
      : "Keine Sorge — mit jeder Runde kennst du Oldenburg ein bisschen besser.";
    return (
      <Card className="relative mx-auto max-w-xl overflow-hidden p-8 text-center">
        {correct > 0 && <ConfettiBurst />}
        <Mascot pose={pose} regung={quote === 100 ? "hebt-pokal" : quote >= 90 ? "klatscht" : undefined} regie="lebhaft" className={cn("mx-auto h-24 w-24", quote >= 90 && "lotti-dance")} />
        <h2 className="mt-3 text-2xl font-bold text-foreground">
          {correct} von {questions.length} richtig
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {practice ? `Trefferquote ${quote} % — Übung gibt keine Punkte` : `${points} ${points === 1 ? "Punkt" : "Punkte"} · Trefferquote ${quote} %`}
        </p>
        {/* Lottis Zuspruch — als Sprechblase unter ihr. */}
        <p className="mx-auto mt-4 max-w-sm rounded-2xl rounded-tl-sm border border-border bg-muted/40 px-4 py-2.5 text-sm text-foreground">
          {cheer}
        </p>
        <Button onClick={onExit} className="mt-6"><RotateCcw className="!size-4" /> Zur Auswahl</Button>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-xl">
      {title && <p className="mb-2 text-sm font-semibold text-primary">{title}</p>}
      {/* Fortschritt — der Balken zeigt die AKTUELLE Frage (wie das Label
          „3/5"), nicht nur die schon abgeschlossenen. */}
      <div className="mb-4 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out-strong"
               style={{ width: `${((idx + 1) / questions.length) * 100}%` }} />
        </div>
        <span className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
          {idx + 1}/{questions.length}
        </span>
      </div>

      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-md bg-primary/10 px-2 py-0.5 font-medium text-primary">
            {(q.format && FORMAT_LABEL[q.format]) ?? CATEGORY_LABEL[q.category] ?? q.category}
          </span>
          <span className="text-muted-foreground">
            {practice ? `Eigene Frage${q.area_key && q.area_key !== "Stadtweit" ? ` · ${q.area_key}` : ""}` : (DIFF_LABEL[q.difficulty] ?? q.difficulty)}
          </span>
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
        ) : q.qtype === "order" ? (
          /* Reihenfolge: nacheinander antippen = Platz 1, 2, 3, 4. Kein Ziehen —
             auf dem Telefon unzuverlässig und ohne Tastatur nicht bedienbar. */
          <div className="mt-4">
            <div className="flex flex-col gap-2">
              {q.options.map((opt, i) => {
                const rank = orderPicks.indexOf(i);
                const rightRank = result?.correct_order ? result.correct_order.indexOf(i) : -1;
                const state = !result ? "idle" : rank === rightRank ? "correct" : "wrong";
                const amount = result ? compareAmount(result, opt) : null;
                return (
                  <button key={i} type="button" disabled={chosen !== null} onClick={() => tapOrder(i)}
                    aria-label={rank >= 0 ? `${opt}, Platz ${rank + 1}` : opt}
                    className={cn(
                      "flex items-center gap-3 rounded-lg border px-3 py-3 text-left text-sm transition-colors duration-tipp",
                      state === "idle" && (rank >= 0 ? "border-primary/40 bg-primary/5" : "border-border hover:border-primary/50 hover:bg-primary/5"),
                      state === "correct" && "border-green-600/40 bg-green-500/10",
                      state === "wrong" && "border-red-600/40 bg-red-500/10",
                    )}>
                    <span className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold tabular-nums",
                      rank >= 0 ? "bg-primary text-primary-foreground" : "border border-dashed border-border text-muted-foreground")}>
                      {rank >= 0 ? rank + 1 : ""}
                    </span>
                    <span className="flex-1 text-foreground">{opt}</span>
                    {result && (
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        Platz {rightRank + 1}{amount ? ` · ${amount}` : ""}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            {chosen === null && (
              <div className="mt-3 flex items-center justify-between gap-2">
                <button type="button" onClick={() => setOrderPicks([])} disabled={!orderPicks.length}
                  className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-40">Zurücksetzen</button>
                <Button onClick={() => void submitOrder()} disabled={orderPicks.length !== q.options.length}>
                  Reihenfolge prüfen
                </Button>
              </div>
            )}
          </div>
        ) : q.format === "verdict" || q.format === "compare" ? (
          /* Zwei Antworten, zwei große Kacheln: Beim Antrag zählt der eine
             Tipp, beim Vergleich das Nebeneinander — untereinander gestapelt
             läse sich „Feuerwehr oder Stadtbibliothek?" wie eine Liste. */
          <div className="relative mt-5 grid grid-cols-2 gap-3">
            {q.options.map((opt, i) => {
              const isChosen = chosen === i;
              const isCorrect = result && i === result.correct_index;
              const state = result ? (isCorrect ? "correct" : isChosen ? "wrong" : "idle") : "idle";
              const amount = q.format === "compare" ? compareAmount(result, opt) : null;
              const Icon = q.format === "verdict" ? (i === 0 ? Check : X) : null;
              return (
                <button
                  key={i}
                  type="button"
                  disabled={chosen !== null}
                  onClick={() => choose(i)}
                  className={cn(
                    "flex min-h-28 flex-col items-center justify-center gap-2 rounded-xl border px-3 py-4 text-center transition-[transform,background-color,border-color] duration-tipp ease-out-strong active:scale-[0.98]",
                    state === "idle" && "border-border bg-card hover:border-primary/40 hover:bg-primary/5 disabled:opacity-60",
                    state === "correct" && "border-green-600/40 bg-green-500/10",
                    state === "wrong" && "border-red-600/40 bg-red-500/10",
                  )}
                >
                  {Icon && (
                    <span className={cn("flex h-9 w-9 items-center justify-center rounded-full",
                      state === "idle" ? "bg-muted text-muted-foreground"
                        : state === "correct" ? "bg-green-600/15 text-green-700 dark:text-green-400"
                        : "bg-red-600/15 text-red-700 dark:text-red-400")}>
                      <Icon className="h-5 w-5" />
                    </span>
                  )}
                  <span className="text-[15px] font-semibold leading-snug text-foreground">{opt}</span>
                  {amount && (
                    <span className={cn("text-sm font-medium tabular-nums",
                      isCorrect ? "text-green-700 dark:text-green-400" : "text-muted-foreground")}>
                      {amount}
                    </span>
                  )}
                </button>
              );
            })}
            {q.format === "compare" && (
              <span aria-hidden className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                oder
              </span>
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
            <LottiReaction seed={q.id}
              outcome={result.correct ? "right" : result.points > 0 ? "close" : "wrong"}>
              {practice
                ? (result.correct ? "Richtig!" : "Leider daneben.")
                : result.correct
                  ? `Richtig! +${result.points}`
                  : result.points > 0 ? `Nah dran! +${result.points}` : "Leider daneben."}
            </LottiReaction>
            {isEstimate && result.answer_value != null && (
              <p className="mt-1 text-sm text-foreground">
                Richtige Antwort:{" "}
                <span className="font-semibold tabular-nums">{fmt(result.answer_value)} {result.unit}</span>
              </p>
            )}
            {result.explanation && (
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground"><GlossaryText text={result.explanation} /></p>
            )}

            {/* „Beschlüsse dazu": verwandte Ratsbeschlüsse zum Thema — öffnet die
                Beschluss-Suche in neuem Tab, damit die Runde nicht verloren geht. */}
            {result.topic && (
              <a href={`/council?tab=decisions&q=${encodeURIComponent(result.topic)}`}
                 target="_blank" rel="noreferrer"
                 className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/5 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/10">
                <Scale className="h-3.5 w-3.5" /> Beschlüsse dazu <ExternalLink className="h-3 w-3" />
              </a>
            )}

            {/* Diagramm der Auflösung (Haushalts-Fragen): Balken, Donut oder
                Trendlinie — animiert, der gefragte Bereich hervorgehoben. */}
            {result.chart && q.format !== "compare" && q.qtype !== "order" && <QuizChart chart={result.chart} className="mt-3" />}

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

            {/* Vom Spiel zum Inhalt: hch hat am 17.09.2026 zehn Fragen in
                fünf Minuten gespielt — und danach führte kein Weg weiter.
                Die Quizfrage wird zur Frage an Lotti; die Analyse macht daraus
                die eigenständige Suchfrage. Nicht bei eigenen Übungsfragen. */}
            {!practice && (
              <FrageChips className="mt-3" titel="Frag Lotti dazu"
                fragen={[{ label: "Mehr dazu aus den Ratsbeschlüssen",
                           frage: `${q.question.trim().replace(/\?$/u, "")} — was steht dazu in den Ratsbeschlüssen?` }]} />
            )}
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              {result.source_ref && result.source_type ? (
                result.source_ref.startsWith("/") ? (
                  // Eigene Seite (der Beschluss hinter einer Antrags-Frage):
                  // neuer Tab, damit die Runde nicht verloren geht.
                  <Link href={result.source_ref} target="_blank"
                     className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                    Zum Beschluss <ExternalLink className="h-3 w-3" />
                  </Link>
                ) : result.source_ref.startsWith("http") ? (
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
              {/* Qualitäts-Bewertung — hilft schlechte Fragen auszutauschen.
                  Eigene Fragen (practice) bewertet man nicht selbst. */}
              <span className={cn("inline-flex items-center gap-1.5", practice && "hidden")}>
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
                  placeholder="Was ist daran schlecht?"
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
