"use client";

import { useState } from "react";

import { Mascot } from "@/components/mascot";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * „Soll ich mir deine Gespräche merken?" — die eine Einwilligung.
 *
 * **Warum eine Komponente und nicht zwei Karten.** Der Text stand bis 09/2026
 * fest im Ratsgespräch. Mit Lottis Fenster gibt es eine zweite Fläche, die
 * dieselbe Frage stellt — und sie stellt sie nicht *auch*, sondern
 * **dieselbe**: Es ist ein Schalter am Konto (`web_users.saves_conversations`)
 * und eine Tabelle. Zwei Karten wären zwei Texte, die auseinanderlaufen, und
 * zwei Stellen, an denen der Datenschutz-Satz gepflegt werden müsste.
 *
 * **Drei Zustände, und der mittlere ist der wichtige.** `null` heißt „noch nie
 * gefragt" — nur dann erscheint die Karte. `1` und `0` sind Entscheidungen und
 * werden respektiert, auch von der jeweils anderen Fläche.
 */
export function GespraecheEinwilligung({ onEntschieden, kompakt = false, className }: {
  /** Wird mit der getroffenen Wahl gerufen, sobald der Server sie hat. */
  onEntschieden: (merken: boolean) => void;
  /** Lottis Fenster ist 384 px breit — dort stehen die Knöpfe untereinander. */
  kompakt?: boolean;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);

  const waehlen = async (merken: boolean) => {
    if (busy) return;
    setBusy(true);
    try {
      await api.post("/council/conversations/setting", { an: merken });
      onEntschieden(merken);
    } catch {
      // Ohne Antwort des Servers bleibt die Karte stehen — eine Einwilligung,
      // die nur im Browser gilt, wäre keine.
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={cn("rounded-xl border border-primary/20 bg-primary/[0.04] p-3.5", className)}>
      <div className={cn("flex gap-3", kompakt ? "flex-col items-start" : "flex-col items-start sm:flex-row")}>
        <Mascot pose="wave" decorative className="h-10 w-10 shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">
            Soll ich mir deine Gespräche merken?
          </p>
          <p className="mt-1 text-hinweis text-muted-foreground">
            Wenn du magst, speichere ich deine Verläufe in deinem Konto — du findest
            sie dann auf allen Geräten oben unter „Gespräche&#8220;. Wenn nicht, wird das
            Gespräch gelöscht, sobald du es schließt. Das gilt auch für das, was du
            mich hier im Fenster fragst.
          </p>
          <div className={cn("mt-3 flex gap-2", kompakt ? "flex-col" : "flex-wrap")}>
            <button
              type="button"
              disabled={busy}
              onClick={() => void waehlen(true)}
              className="min-h-11 rounded-full bg-primary px-3.5 py-2 text-hinweis font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
            >
              KI nutzen &amp; merken
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void waehlen(false)}
              className="min-h-11 rounded-full border border-border px-3.5 py-2 text-hinweis font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-60"
            >
              KI nutzen, nicht merken
            </button>
          </div>
          {/* V-01: Der Datenschutz-Hinweis zog aus dem Composer in die
              Einstellungen (gegen den Dauer-Lärm) — ein Neuling sah ihn damit
              nie vor seiner ersten Frage. Diese Karte unterbricht ohnehin genau
              einmal; hier gehört der Satz hin. */}
          <p className="mt-3 text-hinweis text-muted-foreground">
            Frage und passende Ratsauszüge werden über OpenRouter extern verarbeitet;
            eine Drittlandverarbeitung ist möglich. Mit einer Auswahl erlaubst du
            diese Übermittlung. Ohne sie kann die KI keine Antwort erzeugen.
            Bitte keine personenbezogenen oder sensiblen Daten eingeben. Ob der Verlauf
            zusätzlich im Konto gespeichert wird, entscheidest du mit den beiden Optionen.
          </p>
        </div>
      </div>
    </div>
  );
}
