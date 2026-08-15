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
  const [titel, setTitel] = useState<string | null>(null);
  useEffect(() => {
    const auf = (e: Event) => {
      const d = (e as CustomEvent).detail ?? {};
      setSichtbar(!!d.sichtbar);
      setTitel(typeof d.titel === "string" && d.titel.trim() ? d.titel.trim() : null);
    };
    window.addEventListener("rl:gespraeche-status", auf);
    return () => window.removeEventListener("rl:gespraeche-status", auf);
  }, []);
  if (!sichtbar) return null;
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent("rl:gespraeche-oeffnen"))}
      aria-label="Meine Gespräche öffnen"
      title={titel ? `Gespräch: ${titel}` : "Meine Gespräche"}
      className="inline-flex h-9 max-w-[52vw] items-center justify-center rounded-[10px] border border-border bg-card px-2 text-muted-foreground shadow-sm transition-colors active:bg-muted sm:gap-1.5 sm:px-2.5 md:hidden"
    >
      <History className="h-4 w-4 shrink-0" aria-hidden />
      {/* V-03: Wo Platz ist, sagt der Knopf nicht nur WAS er ist, sondern in
          welchem Gespräch man gerade steckt — nach Tagen ist das die
          Orientierung, die sonst fehlt. Ohne aktives Gespräch: altes Label. */}
      <span className="hidden truncate text-xs font-medium sm:inline">
        {titel ?? "Gespräche"}
      </span>
    </button>
  );
}

/** Fragen als eigene Seite (Split 12.08., Tims Go): das Headliner-Feature
 *  landet direkt im Gespräch — kein Modus-Umschalter, der Platz kostet und
 *  Aufmerksamkeit stiehlt. `?q=` befüllt den Composer vor, `?share=` öffnet
 *  einen geteilten Antwort-Snapshot (beides wertet das Ratsgespräch aus).
 *  Das data-tour-Ziel „ki-frage-tab" wohnte vorher am Umschalter und wanderte
 *  beim Split auf diesen Wrapper — womit der Tour-Spotlight die ganze Seite
 *  umfasste und nichts mehr hervorhob. Die Tour erklärt Fragen jetzt am
 *  Navigationspunkt und mit einer eigenen Beispiel-Station (components/tour.tsx),
 *  hier braucht es keinen Anker mehr. */
function FragenInner() {
  return (
    <div>
      <PageHeader
        title="Fragen"
        /* Kurz halten (Tims Befund 12.08.): Auf dem Handy lief der Satz über
           drei Zeilen und schob den Empty State nach unten — worauf die
           Antwort fußt, sagt der Empty State selbst. */
        description="In normaler Sprache fragen — Antwort mit Quellen."
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
