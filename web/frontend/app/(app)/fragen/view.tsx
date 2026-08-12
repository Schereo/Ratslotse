"use client";

import { Suspense, useEffect, useState } from "react";
import { History } from "lucide-react";
import { PageHeader } from "@/components/ui";
import { QaTab } from "@/components/council-qa";

/** History-Knopf oben rechts im Seitenkopf (Tims TestFlight-Feedback 11.08.):
 *  öffnet das mobile Gespräche-Sheet. Sichtbarkeit und Tap laufen über
 *  Fenster-Events, weil der Gesprächs-State im Ratsgespräch lebt — der Knopf
 *  erscheint nur, wenn es dort etwas zu zeigen gibt. Nur mobil; Desktop hat
 *  seine Knöpfe im Bühnen-Kopf. (Hierher umgezogen aus der Council-Seite,
 *  als Fragen mit dem Split eine eigene Seite wurde.) */
function GespraecheHeaderButton() {
  const [sichtbar, setSichtbar] = useState(false);
  useEffect(() => {
    const auf = (e: Event) => setSichtbar(!!(e as CustomEvent).detail?.sichtbar);
    window.addEventListener("rl:gespraeche-status", auf);
    return () => window.removeEventListener("rl:gespraeche-status", auf);
  }, []);
  if (!sichtbar) return null;
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent("rl:gespraeche-oeffnen"))}
      aria-label="Meine Gespräche öffnen"
      title="Meine Gespräche"
      className="inline-flex h-9 w-9 items-center justify-center rounded-[10px] border border-border bg-card text-muted-foreground shadow-sm transition-colors active:bg-muted sm:w-auto sm:gap-1.5 sm:px-2.5 md:hidden"
    >
      <History className="h-4 w-4" aria-hidden />
      {/* Tims Nachschlag: Wo Platz ist, sagt der Knopf, was er ist. */}
      <span className="hidden text-xs font-medium sm:inline">Gespräche</span>
    </button>
  );
}

/** Fragen als eigene Seite (Split 12.08., Tims Go): das Headliner-Feature
 *  landet direkt im Gespräch — kein Modus-Umschalter, der Platz kostet und
 *  Aufmerksamkeit stiehlt. `?q=` befüllt den Composer vor, `?share=` öffnet
 *  einen geteilten Antwort-Snapshot (beides wertet das Ratsgespräch aus).
 *  Das data-tour-Ziel „ki-frage-tab" wohnte vorher am Umschalter. */
function FragenInner() {
  return (
    <div data-tour="ki-frage-tab">
      <PageHeader
        title="Fragen"
        description="Stell dem Rat eine Frage in normaler Sprache — beantwortet aus Beschlüssen, Wortbeiträgen und Vorlagen."
        action={<GespraecheHeaderButton />}
      />
      <QaTab />
    </div>
  );
}

export default function FragenPage() {
  return (
    <Suspense>
      <FragenInner />
    </Suspense>
  );
}
