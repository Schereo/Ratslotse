"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/** Ein Bereich, der auf- und zufährt, statt zu erscheinen und zu verschwinden.
 *
 *  Die Höhe kommt aus einem Raster (`grid-template-rows: 0fr ↔ 1fr`, s.
 *  `.aufklapp` in globals.css) — der einzige Weg, eine UNBEKANNTE Höhe ohne
 *  Messung zu animieren. Die Alternativen taugen beide nicht: Ein geschätztes
 *  `max-height` läuft entweder zu früh aus (Inhalt springt am Ende) oder viel
 *  zu lange leer nach, und eine JS-Messung müsste bei jeder Änderung des
 *  Inhalts neu messen — hier lädt die Tagesordnung erst nach dem Aufklappen.
 *
 *  Der Inhalt bleibt beim Zufahren stehen, bis die Bewegung durch ist. Ohne
 *  das gäbe es nichts zu sehen: Die Aufrufstelle hängt ihren Inhalt an
 *  denselben Zustand wie `offen`, er wäre also im selben Bild verschwunden, in
 *  dem das Zufahren beginnt — die Karte fiele in sich zusammen, aber leer.
 *
 *  Und ein Rückfall auf Zeit: `transitionend` kommt NICHT, wenn gar keine
 *  Bewegung läuft — bei `prefers-reduced-motion` (der globale Block legt
 *  Übergänge still) und bei einem Element, das gerade `display: none` ist
 *  (die Handy-Liste der Kandidaten-Rangliste auf breiten Fenstern, gemessen
 *  15.09.2026). Der zugeklappte Inhalt blieb dann im DOM stehen — unsichtbar
 *  hinter `0fr`, aber für Screenreader und Tests da. Nach dem Takt plus
 *  Reserve wird deshalb in jedem Fall abgeräumt.
 *
 *  Und die Reihenfolge beim Auffahren: erst den Inhalt bei `0fr` einhängen,
 *  im NÄCHSTEN Frame auf `1fr` schalten. Vorher stand `data-offen` schon im
 *  selben Bild, in dem der Inhalt noch fehlte — die Bewegung lief ein, zwei
 *  Frames an einem leeren Kasten, und der Inhalt erschien mitten darin:
 *  Gemessen 15.09.2026 (Kandidaten-Rangliste) stand der erste sichtbare Frame
 *  bei 264 von 991 px, gut ein Viertel offen. Tim: „springt ein wenig auf". */
export function Aufklapp({ offen, children, className }: {
  offen: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  const [gemountet, setGemountet] = useState(offen);
  // Die Rasterspur — folgt `offen` mit einem Frame Verzug beim Auffahren,
  // damit der Inhalt schon steht, wenn die Bewegung beginnt.
  const [faehrt, setFaehrt] = useState(offen);
  // Der zuletzt gezeigte Inhalt — was während des Zufahrens stehen bleibt.
  const letzter = useRef<React.ReactNode>(children);
  if (offen) letzter.current = children;

  useEffect(() => {
    if (offen) {
      setGemountet(true);
      const raf = requestAnimationFrame(() => setFaehrt(true));
      return () => cancelAnimationFrame(raf);
    }
    setFaehrt(false);
    // Die 300 ms der Bewegung (s. `.aufklapp` in globals.css) plus Reserve —
    // läuft sie, kommt `transitionend` vorher und der Timer räumt nur nach.
    const id = window.setTimeout(() => setGemountet(false), 450);
    return () => window.clearTimeout(id);
  }, [offen]);

  return (
    <div
      className={cn("aufklapp", className)}
      data-offen={faehrt ? "true" : undefined}
      onTransitionEnd={(e) => {
        // Nur auf die eigene Höhen-Bewegung hören: Im Inhalt laufen weitere
        // Übergänge (Hover-Flächen der TOP-Zeilen), deren Ende hier ankommt.
        if (e.propertyName === "grid-template-rows" && e.target === e.currentTarget && !offen) {
          setGemountet(false);
        }
      }}
    >
      <div className="min-h-0 overflow-hidden">{gemountet ? (offen ? children : letzter.current) : null}</div>
    </div>
  );
}
