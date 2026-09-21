"use client";

/**
 * Daumen hoch/runter zu einer KI-Antwort (5a/I-03) — der einzige
 * Qualitätsmesser außerhalb der Eval-Gold-Fälle.
 *
 * **Warum eine eigene Datei.** Die Komponente stand bis 09/2026 als private
 * Funktion in `council-qa.tsx`. Lottis Fenster braucht denselben Daumen
 * (B6 der zweiten Durchsicht) — und ein zweiter Nachbau hieße: zwei
 * Zustandsmaschinen für dieselbe Sache, zwei Stellen für die Grund-Nachfrage,
 * zwei Gelegenheiten, den Endpunkt-Body auseinanderlaufen zu lassen. Sie
 * kennt deshalb keinen `Turn` mehr, sondern nur Frage, Antwort und die
 * Fläche, aus der der Daumen kommt.
 *
 * Design: DESIGNSPRACHE.md „Turn-Fußzeile" — stille Icon-Aktionen, 15 px
 * Trefferfläche, keine gerahmten Buttons.
 */

import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";

import { toast } from "@/components/ui";
import { apiUrl, authHeaders } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Aus welcher Fläche der Daumen kommt — `QaFeedbackBody.source` im Backend.
 *  Ohne das Feld stünden Lottis Erklärungen und die Archiv-Antworten in einem
 *  Topf, und „taugen Lottis Antworten?" wäre nicht mehr zu stellen. */
export type FeedbackQuelle = "ask" | "lotti";

/** 👎 fragt optional nach dem Grund; gesendet wird fire-and-forget, der Dank
 *  kommt sofort. */
export function FeedbackDaumen({ question, answer, source = "ask" }: {
  question: string;
  answer: string;
  source?: FeedbackQuelle;
}) {
  const [abgegeben, setAbgegeben] = useState<"up" | "down" | null>(null);
  const [frageGrund, setFrageGrund] = useState(false);
  const [reason, setGrund] = useState("");
  const post = (rating: "up" | "down", grundText?: string) =>
    void fetch(apiUrl("/council/qa-feedback"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        question: question.slice(0, 300),
        answer_excerpt: answer.slice(0, 500) || null,
        rating,
        reason: grundText?.trim() || null,
        source,
      }),
    }).catch(() => {});
  const senden = (rating: "up" | "down") => {
    // Nochmal auf denselben Daumen: nichts zu melden, nichts zu senden — das
    // spart eine Zeile in der Tabelle und einen Schlag aufs Rate-Limit.
    if (rating === abgegeben) return;
    const korrektur = abgegeben !== null;
    setAbgegeben(rating);
    setFrageGrund(rating === "down");
    // Beim Umschwenken auf „hilfreich" ist der alte Grund hinfällig.
    if (rating === "up") setGrund("");
    // Der Daumen zählt sofort — auch wenn der Grund nie kommt.
    post(rating);
    if (rating === "up") toast.success(korrektur ? "Danke — Bewertung geändert." : "Danke für die Rückmeldung!");
  };
  const grundNachreichen = () => {
    setFrageGrund(false);
    // Nur mit echtem Text nachsenden — die Grund-Zeile ersetzt beim Auswerten
    // den nackten Daumen (gleiche Frage, jüngerer Zeitstempel).
    if (reason.trim()) post("down", reason);
    toast.success("Danke für die Rückmeldung!");
  };
  return (
    <span className="flex items-center gap-0.5">
      {/* Beide Daumen bleiben anklickbar: Wer sich vertippt oder es sich
          anders überlegt, muss die Bewertung ändern können (Tims Befund).
          Der nicht gewählte Daumen tritt nur zurück, statt zu erstarren. */}
      <button type="button" aria-label="Antwort war hilfreich" title="Hilfreich"
        data-feedback-daumen="up"
        aria-pressed={abgegeben === "up"}
        onClick={() => senden("up")}
        className={cn("rounded-md p-1 transition-colors",
          abgegeben === "up" ? "text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
          abgegeben === "down" && "opacity-40 hover:opacity-100")}>
        <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
      </button>
      <button type="button" aria-label="Antwort war nicht hilfreich" title="Nicht hilfreich"
        data-feedback-daumen="down"
        aria-pressed={abgegeben === "down"}
        onClick={() => senden("down")}
        className={cn("rounded-md p-1 transition-colors",
          abgegeben === "down" ? "text-signal" : "text-muted-foreground hover:bg-muted hover:text-foreground",
          abgegeben === "up" && "opacity-40 hover:opacity-100")}>
        <ThumbsDown className="h-3.5 w-3.5" aria-hidden />
      </button>
      {frageGrund && (
        <form className="ml-1 flex min-w-0 items-center gap-1"
          onSubmit={(e) => { e.preventDefault(); grundNachreichen(); }}>
          {/* 16px auf Touch: Unter 16px zoomt iOS-Safari beim Fokus in das
              Feld hinein (Tims Befund beim Daumen runter). */}
          <input value={reason} onChange={(e) => setGrund(e.target.value)} autoFocus
            placeholder="Was war falsch? (optional)" maxLength={500}
            className="h-7 w-44 min-w-0 rounded-md border border-border bg-card px-2 text-[16px] outline-none placeholder:text-muted-foreground/60 focus:border-primary sm:h-6 sm:w-40 sm:text-[11px]" />
          <button type="submit" className="text-[11px] font-medium text-primary hover:underline">Senden</button>
        </form>
      )}
    </span>
  );
}
