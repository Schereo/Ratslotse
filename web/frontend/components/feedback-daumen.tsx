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
import { sendAndForget } from "@/lib/send-and-forget";
import { cn } from "@/lib/utils";

/** Aus welcher Fläche der Daumen kommt — `QaFeedbackBody.source` im Backend.
 *  Ohne das Feld stünden Lottis Erklärungen und die Archiv-Antworten in einem
 *  Topf, und „taugen Lottis Antworten?" wäre nicht mehr zu stellen. */
export type FeedbackQuelle = "ask" | "lotti";

/** Die festen Gründe zum Daumen runter — `QaFeedbackBody.reason_kind`.
 *  Freitext allein ließ sich nicht zählen: „falsch“ und „veraltet“ sind zwei
 *  verschiedene Fehler mit zwei verschiedenen Ursachen. */
const GRUENDE: { id: GrundArt; label: string }[] = [
  { id: "wrong", label: "Falsch" },
  { id: "incomplete", label: "Unvollständig" },
  { id: "outdated", label: "Veraltet" },
  { id: "off_topic", label: "Thema verfehlt" },
];
type GrundArt = "wrong" | "incomplete" | "outdated" | "off_topic";

/** 👎 fragt optional nach dem Grund; gesendet wird fire-and-forget, der Dank
 *  kommt sofort.
 *
 *  **Die Antwort zur Prüfung freigeben (seit 10/2026).** Bis dahin kam mit
 *  einem 👎 nur die Frage und der Anfang der Antwort an — welche Quelle
 *  fehlte oder falsch gelesen wurde, ließ sich nicht mehr klären. Mit
 *  `answerId` (nur angemeldet, nur „Frag den Rat“) bietet das Formular an,
 *  die ganze Antwort samt Quellen mitzuschicken. Das Häkchen ist AUS; ohne es
 *  bleibt alles wie bisher. */
export function FeedbackDaumen({ question, answer, source = "ask", answerId = null }: {
  question: string;
  answer: string;
  source?: FeedbackQuelle;
  answerId?: string | null;
}) {
  const [abgegeben, setAbgegeben] = useState<"up" | "down" | null>(null);
  const [frageGrund, setFrageGrund] = useState(false);
  const [reason, setGrund] = useState("");
  const [art, setArt] = useState<GrundArt | null>(null);
  const [freigeben, setFreigeben] = useState(false);
  const post = (rating: "up" | "down", extra?: { reason?: string; art?: GrundArt | null; freigeben?: boolean }) =>
    sendAndForget(apiUrl("/council/qa-feedback"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        question: question.slice(0, 300),
        answer_excerpt: answer.slice(0, 500) || null,
        rating,
        reason: extra?.reason?.trim() || null,
        reason_kind: extra?.art ?? null,
        answer_id: answerId,
        share_answer: Boolean(extra?.freigeben && answerId),
        source,
      }),
    });
  const senden = (rating: "up" | "down") => {
    // Nochmal auf denselben Daumen: nichts zu melden, nichts zu senden — das
    // spart eine Zeile in der Tabelle und einen Schlag aufs Rate-Limit.
    if (rating === abgegeben) return;
    const korrektur = abgegeben !== null;
    setAbgegeben(rating);
    setFrageGrund(rating === "down");
    // Beim Umschwenken auf „hilfreich" ist der alte Grund hinfällig — und
    // mit ihm die Freigabe (der Server löscht die Kopie ebenso).
    if (rating === "up") { setGrund(""); setArt(null); setFreigeben(false); }
    // Der Daumen zählt sofort — auch wenn der Grund nie kommt.
    post(rating);
    if (rating === "up") toast.success(korrektur ? "Danke — Bewertung geändert." : "Danke für die Rückmeldung!");
  };
  const grundNachreichen = () => {
    setFrageGrund(false);
    // Nur mit echtem Inhalt nachsenden — die Zeile ersetzt beim Auswerten
    // den nackten Daumen (gleiche Frage, jüngerer Zeitstempel).
    if (reason.trim() || art || freigeben) post("down", { reason, art, freigeben });
    toast.success("Danke für die Rückmeldung!");
  };
  return (
    <>
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
    </span>
      {frageGrund && (
        // Eine eigene Zeile unter der Fußzeile: Vier Gründe, ein Feld und ein
        // Häkchen passen nicht neben die Icons, und eingeklemmt brach das
        // Feld auf dem Telefon in eine 40-px-Spalte.
        <form className="flex basis-full flex-col gap-1.5 pt-1"
          data-feedback-grund
          onSubmit={(e) => { e.preventDefault(); grundNachreichen(); }}>
          <div className="flex flex-wrap gap-1" role="group" aria-label="Was war nicht gut?">
            {GRUENDE.map((g) => (
              <button key={g.id} type="button" aria-pressed={art === g.id}
                onClick={() => setArt(art === g.id ? null : g.id)}
                className={cn("rounded-full border px-2 py-0.5 text-[11px] transition-colors",
                  art === g.id ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground")}>
                {g.label}
              </button>
            ))}
          </div>
          <div className="flex min-w-0 items-center gap-1">
            {/* 16px auf Touch: Unter 16px zoomt iOS-Safari beim Fokus in das
                Feld hinein (Tims Befund beim Daumen runter). */}
            <input value={reason} onChange={(e) => setGrund(e.target.value)} autoFocus
              placeholder="Was war falsch? (optional)" maxLength={500}
              className="h-7 w-full min-w-0 max-w-xs rounded-md border border-border bg-card px-2 text-[16px] outline-none placeholder:text-muted-foreground/60 focus:border-primary sm:h-6 sm:text-[11px]" />
            <button type="submit" className="flex-none text-[11px] font-medium text-primary hover:underline">Senden</button>
          </div>
          {answerId && (
            <label className="flex max-w-prose items-start gap-1.5 text-[11px] leading-snug text-muted-foreground">
              <input type="checkbox" checked={freigeben} onChange={(e) => setFreigeben(e.target.checked)}
                className="mt-0.5 h-3.5 w-3.5 flex-none accent-primary" />
              <span>
                <span className="font-medium text-foreground">Antwort mit Quellen zur Prüfung mitschicken.</span>{" "}
                Dann sehen wir die ganze Antwort und ihre Quellen und können den Fehler finden. Ohne Häkchen
                speichern wir nur die Frage und den Anfang der Antwort.
              </span>
            </label>
          )}
        </form>
      )}
    </>
  );
}
