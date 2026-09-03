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
 *  dem das Zufahren beginnt — die Karte fiele in sich zusammen, aber leer. */
export function Aufklapp({ offen, children, className }: {
  offen: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  const [gemountet, setGemountet] = useState(offen);
  // Der zuletzt gezeigte Inhalt — was während des Zufahrens stehen bleibt.
  const letzter = useRef<React.ReactNode>(children);
  if (offen) letzter.current = children;

  useEffect(() => { if (offen) setGemountet(true); }, [offen]);

  return (
    <div
      className={cn("aufklapp", className)}
      data-offen={offen ? "true" : undefined}
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
