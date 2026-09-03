"use client";

import { useCallback, useEffect, useState } from "react";
import { Play } from "lucide-react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Button } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { startGuidedTour, tourGesehen } from "@/components/tour";
import {
  ONBOARDING_DONE_EVENT,
  ONBOARDING_FINISHED_EVENT,
} from "@/components/onboarding-flow";
import { einladungStand, merkeEinladung } from "@/lib/tour-einladung";

/**
 * Lottis Einladung zur Tour — der Moment direkt nach der Einrichtung.
 *
 * Der Assistent (onboarding-flow.tsx) endet mit „Fertig", und dann stand man
 * unvermittelt auf „Heute": Karten, Zahlen, Navigation, alles auf einmal. Die
 * geführte Tour hätte genau das erklärt, aber sie beginnt hinter einem kleinen
 * Knopf in der „Erste Schritte"-Karte, den Erstnutzer*innen erst einmal finden
 * müssen (Tims Befund, 03.09.2026). Jetzt tritt Lotti groß vor die Seite und
 * fragt — Tour starten oder erst mal selbst umschauen. Beides ist ein Tipp.
 *
 * Wann sie erscheint: genau einmal, sobald der Assistent seinen letzten Schritt
 * abgeschlossen hat. Maßgeblich ist die gemerkte Marke (`lib/tour-einladung.ts`),
 * die der Assistent beim Abschluss selbst setzt — das Ereignis daneben ist nur
 * die Abkürzung für den Fall, dass diese Komponente in dem Moment schon steht.
 * Auf das Ereignis allein war Verlass genau nicht: Die Einladung hängt in der
 * App-Hülle, und wer den Assistenten in einem Tab beendet, der noch das Bündel
 * von vor einem Deploy fährt, hatte sie nie gemountet — auf Prod ist die
 * Einladung dadurch komplett ausgefallen (Tims Befund, 03.09.2026).
 *
 * Nie ein zweites Mal, auch nicht, wenn die Tour über die „Erste Schritte"-Karte
 * längst gelaufen ist.
 */

/** Der Assistent verschwindet ohne Ausblendung; ein Wimpernschlag Pause, damit
 *  die Seite dahinter einmal ganz zu sehen war, bevor Lotti davortritt. */
const VERZOEGERUNG_MS = 450;

export function TourEinladung() {
  const [offen, setOffen] = useState(false);

  // Einmal beim Start (Neuladen mit ausstehender Einladung) und dann auf das
  // Abschluss-Ereignis des Assistenten.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const zeigen = () => {
      // Wer die Tour schon kennt, wird nicht eingeladen — die Marke wird dann
      // gleich hier abgeräumt, damit die Abzeichen nicht darauf warten.
      if (tourGesehen()) { merkeEinladung("erledigt"); return; }
      timer = setTimeout(() => setOffen(true), VERZOEGERUNG_MS);
    };
    if (einladungStand() === "offen") zeigen();
    // Der Assistent hat die Marke schon gesetzt; das Ereignis sagt nur, dass
    // es jetzt gleich losgeht, ohne auf das nächste Aufbauen zu warten.
    const onFinished = () => zeigen();
    window.addEventListener(ONBOARDING_FINISHED_EVENT, onFinished);
    return () => {
      window.removeEventListener(ONBOARDING_FINISHED_EVENT, onFinished);
      if (timer) clearTimeout(timer);
    };
  }, []);

  const schliessen = useCallback(() => {
    merkeEinladung("erledigt");
    setOffen(false);
    // Die zurückgehaltenen Abzeichen dürfen jetzt — die Marke steht nicht mehr
    // auf „offen", der Riegel in isOnboardingVisible() ist damit weg.
    window.dispatchEvent(new Event(ONBOARDING_DONE_EVENT));
  }, []);

  const tourStarten = useCallback(() => {
    schliessen();
    startGuidedTour();
  }, [schliessen]);

  if (!offen) return null;

  return (
    <DialogPrimitive.Root open onOpenChange={(o) => { if (!o) schliessen(); }}>
      <DialogPrimitive.Portal>
        {/* Dieselbe Abdunkelung wie die Tour, die gleich folgt — der Übergang
            von der Einladung in die erste Station soll wie ein Zug wirken. */}
        <DialogPrimitive.Overlay className="fixed inset-0 z-[var(--level-dialog)] bg-[hsl(213_60%_5%/0.62)] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-[var(--level-dialog)] w-[calc(100%-2rem)] max-w-[24rem] -translate-x-1/2 -translate-y-1/2 rounded-[20px] border border-border bg-card px-6 pb-6 pt-8 text-center shadow-lifted outline-none ease-out-strong data-[state=open]:animate-in data-[state=open]:duration-200 data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:duration-150 data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
        >
          {/* Lotti groß, mit den zwei auslaufenden Ringen des Auftakts — hier
              in Hafenblau und Signal, weil die Karte hell ist. */}
          <div className="wl-lotti relative mx-auto flex h-32 w-32 items-center justify-center">
            <span aria-hidden className="wl-ring absolute h-[132px] w-[132px] rounded-full border-2 border-primary" />
            <span aria-hidden className="wl-ring wl-ring-2 absolute h-[132px] w-[132px] rounded-full border-2 border-signal" />
            <Mascot pose="wave" decorative className="h-28 w-28" />
          </div>

          <p className="wl-title mt-5 font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-signal">
            Alles eingerichtet
          </p>
          <DialogPrimitive.Title className="wl-title mt-2 font-display text-[24px] font-extrabold leading-[1.12] tracking-tight text-foreground [hyphens:none]">
            Soll ich dich einmal herumführen?
          </DialogPrimitive.Title>
          <p className="wl-r1 mt-2.5 text-[14px] leading-relaxed text-muted-foreground">
            Ich bin Lotti. In einer Minute zeige ich dir, wo du dem Rat Fragen
            stellst, Beschlüsse findest und deine Themen pflegst.
          </p>

          <div className="wl-r2 mt-6 flex flex-col gap-2">
            <Button onClick={tourStarten} className="h-11 w-full text-[15px]" autoFocus>
              <Play className="!size-4" />
              Tour starten
            </Button>
            <Button variant="ghost" onClick={schliessen} className="w-full text-muted-foreground hover:text-foreground">
              Erst mal selbst umschauen
            </Button>
          </div>
          {/* Der Weg zurück, falls jemand ablehnt — genau der, der vorher
              niemandem auffiel. */}
          <p className="wl-r3 mt-4 text-[11.5px] leading-snug text-muted-foreground/80">
            Die Tour findest du später auf der Übersicht unter „Erste Schritte“.
          </p>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
