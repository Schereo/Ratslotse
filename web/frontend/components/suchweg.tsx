"use client";

/**
 * Der Suchweg der KI-Frage: jeder Schritt mit seinem Ergebnis (seit 11/2026).
 *
 * Texte und Ergebnisse baut der Server (`council/search_trail.py`), hier wird
 * nur angezeigt. Beim Warten steht die Liste offen in der Ladekarte; sobald
 * die Antwort schreibt, klappt sie zu einer Zeile über der Antwort zusammen —
 * wer wissen will, wie die Antwort zustande kam, klappt sie wieder auf.
 *
 * Zeichen wie überall beim Fortschritt (DESIGNSPRACHE.md): Häkchen grün für
 * Erledigtes, Spinner (12 px, primary) für den laufenden Schritt. Kommende
 * Schritte gibt es nicht — welche Kanäle eine Frage braucht, weiß erst der
 * Server unterwegs.
 */
import { useState } from "react";
import { Check, ChevronDown, Loader2 } from "lucide-react";

import type { SuchwegEintrag } from "@/lib/qa-schritte";
import { cn } from "@/lib/utils";

export function SuchwegListe({ eintraege, laeuft }: {
  eintraege: SuchwegEintrag[];
  /** Der letzte Eintrag läuft noch. */
  laeuft: boolean;
}) {
  return (
    <ol className="flex min-w-0 flex-col gap-1.5">
      {eintraege.map((e, i) => {
        const aktiv = laeuft && i === eintraege.length - 1;
        return (
          <li key={i} className="min-w-0">
            <span className={cn("flex items-start gap-2 text-xs",
              aktiv ? "font-semibold text-foreground" : "text-muted-foreground")}>
              {aktiv
                ? <Loader2 className="mt-0.5 h-3 w-3 shrink-0 animate-spin text-primary" aria-hidden />
                : <Check className="mt-0.5 h-3 w-3 shrink-0 text-green-600" aria-hidden />}
              <span className="min-w-0">{e.text}{aktiv ? " …" : ""}</span>
            </span>
            {e.detail && (
              <span className="ml-5 mt-0.5 line-clamp-3 break-words text-xs text-muted-foreground">
                {e.detail}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Die zugeklappte Zeile über der Antwort. */
export function SuchwegKlappe({ eintraege, laeuft }: {
  eintraege: SuchwegEintrag[]; laeuft: boolean;
}) {
  const [offen, setOffen] = useState(false);
  if (!eintraege.length) return null;
  return (
    <div className="min-w-0">
      <button type="button" onClick={() => setOffen((o) => !o)} aria-expanded={offen}
        className="inline-flex items-center gap-1 rounded text-xs text-muted-foreground transition-colors hover:text-foreground">
        Suchweg · {eintraege.length} {eintraege.length === 1 ? "Schritt" : "Schritte"}
        <ChevronDown className={cn("h-3 w-3 transition-transform", offen && "rotate-180")} aria-hidden />
      </button>
      {offen && (
        <div className="mt-2 rounded-xl border border-border bg-card/60 px-3.5 py-3">
          <SuchwegListe eintraege={eintraege} laeuft={laeuft} />
        </div>
      )}
    </div>
  );
}
