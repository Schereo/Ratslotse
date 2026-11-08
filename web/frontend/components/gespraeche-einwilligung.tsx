"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ShieldAlert } from "lucide-react";

import { Aufklapp } from "@/components/aufklapp";
import { EuFlagge } from "@/components/eu-flagge";
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
 *
 * **Kurz, weil sie sonst niemand liest** (Tim 08.11.2026). Bis dahin standen
 * zwölf Zeilen Fließtext vor der ersten Frage. Sichtbar bleibt, was man vor
 * der Wahl wissen MUSS — wohin die Frage geht und was man nicht eingeben
 * sollte —, als zwei Zeilen mit Zeichen. Was die Wahl im Einzelnen bedeutet,
 * steht unter „Mehr dazu“.
 */
export function GespraecheEinwilligung({ onEntschieden, kompakt = false, className }: {
  /** Wird mit der getroffenen Wahl gerufen, sobald der Server sie hat. */
  onEntschieden: (merken: boolean) => void;
  /** Lottis Fenster ist 384 px breit — dort stehen die Knöpfe untereinander. */
  kompakt?: boolean;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [mehr, setMehr] = useState(false);

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
          <p className="mt-0.5 text-hinweis text-muted-foreground">
            Dann findest du sie auf allen Geräten wieder.
          </p>
          {/* V-01: Der Verarbeitungshinweis gehört VOR die Wahl — ein Neuling
              sah ihn sonst nie vor seiner ersten Frage. Diese Karte
              unterbricht ohnehin genau einmal. */}
          <ul className="mt-2.5 space-y-1.5 text-hinweis text-foreground/90">
            <li className="flex gap-2">
              <EuFlagge className="mt-[0.3rem] h-[11px] w-4" />
              <span>Die KI läuft ausschließlich in Rechenzentren in der EU.</span>
            </li>
            <li className="flex gap-2">
              <ShieldAlert className="mt-[0.2rem] h-4 w-4 shrink-0 text-signal" aria-hidden />
              <span>Bitte keine persönlichen oder sensiblen Daten eingeben.</span>
            </li>
          </ul>
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
          <button
            type="button"
            aria-expanded={mehr}
            onClick={() => setMehr((m) => !m)}
            className="mt-2.5 inline-flex min-h-8 items-center gap-1 text-hinweis font-medium text-primary hover:underline"
          >
            Mehr dazu
            <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", mehr && "rotate-180")} aria-hidden />
          </button>
          <Aufklapp offen={mehr}>
            <div className="space-y-1.5 pt-1.5 text-hinweis text-muted-foreground">
              <p>
                Frage und passende Ratsauszüge gehen über den Vermittler OpenRouter (USA) an
                KI-Modelle bei Microsoft Azure in der EU, die nichts speichern und nicht damit
                trainieren. Mit einer Auswahl erlaubst du diese Übermittlung — ohne sie kann die KI
                keine Antwort erzeugen.
              </p>
              <p>
                Gemerkte Gespräche stehen oben unter „Gespräche&#8220;. Ohne Merken wird ein Gespräch
                gelöscht, sobald du es schließt — auch das, was du Lotti im Fenster fragst.
              </p>
              <p>
                Deine Wahl kannst du jederzeit unter{" "}
                <Link href="/account" className="text-primary hover:underline">Konto</Link> ändern.
                Mehr in der{" "}
                <Link href="/datenschutz" className="text-primary hover:underline">Datenschutzerklärung</Link>.
              </p>
            </div>
          </Aufklapp>
        </div>
      </div>
    </div>
  );
}
