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
 *  als Fragen mit dem Split eine eigene Seite wurde.)
 *
 *  Die Grenze ist `desk`, nicht `md`: Der Bühnen-Kopf, der diesen Knopf
 *  ablöst, hängt selbst an `desk` — mit `md:hidden` klaffte dazwischen ein
 *  Loch, in dem KEINE der beiden Varianten stand. Genau dort liegt das iPad
 *  (Tims Befund 15.08.: „irgendwie fehlt der gesprächsverlauf button?"), und
 *  ein Handy quer (844 px) fiel schon vorher stillschweigend hinein. */
function GespraecheHeaderButton() {
  const [sichtbar, setSichtbar] = useState(false);
  const [titel, setTitel] = useState<string | null>(null);
  const [anzahl, setAnzahl] = useState(0);
  useEffect(() => {
    const auf = (e: Event) => {
      const d = (e as CustomEvent).detail ?? {};
      setSichtbar(!!d.sichtbar);
      setTitel(typeof d.titel === "string" && d.titel.trim() ? d.titel.trim() : null);
      setAnzahl(typeof d.anzahl === "number" ? d.anzahl : 0);
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
      className="inline-flex h-10 max-w-[56vw] items-center gap-1.5 rounded-full border border-border bg-card px-3.5 text-foreground shadow-sm transition-colors active:bg-muted desk:hidden"
    >
      <History className="h-[15px] w-[15px] shrink-0 text-primary" aria-hidden />
      {/* Design 15: Der Knopf trägt sein Wort IMMER — das namenlose Uhr-Icon
          war der Grund, warum niemand den Verlauf fand. V-03 bleibt: Im
          aktiven Gespräch steht dessen Titel drin, sonst „Gespräche". */}
      <span className="truncate text-[13.5px] font-semibold">
        {titel ?? "Gespräche"}
      </span>
      {anzahl > 0 && (
        <span className="inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 px-1.5 text-[11.5px] font-bold text-primary">
          {anzahl}
        </span>
      )}
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
      {/* Design 15 (WEG): kein Untertitel mehr — dieselbe Botschaft steht
          einmal, unter „Frag den Rat" im Empty State. Der Kopf gehört dem
          Titel und dem benannten Gespräche-Knopf. */}
      <PageHeader
        title="Fragen"
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
