"use client";

import { useEffect, useState } from "react";
import { Chick } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";
import { cn } from "@/lib/utils";

/**
 * Ein Küken, das ab und zu unten am Bildschirmrand hereinschaut, kurz hüpft und
 * wieder abtaucht — rein dekorativ (aria-hidden, klickt nicht). Erscheint alle
 * ~50–100 s abwechselnd links/rechts. Bei prefers-reduced-motion bleibt es via
 * CSS unsichtbar (kein Hereinfahren).
 */
export function PeekingChick() {
  const theme = useMascotTheme();
  const [visible, setVisible] = useState(false);
  // Solange Lottis Fenster offen ist, bleibt das Küken weg: Zwei Möwen in
  // derselben Ecke sind eine zu viel, und die eine davon erklärt gerade etwas.
  const [lottiOffen, setLottiOffen] = useState(false);
  useEffect(() => {
    const auf = (e: Event) => setLottiOffen(!!(e as CustomEvent).detail?.offen);
    window.addEventListener("ratslotse:lotti-offen", auf);
    return () => window.removeEventListener("ratslotse:lotti-offen", auf);
  }, []);
  const [side, setSide] = useState<"left" | "right">("right");
  const [tone, setTone] = useState<"orange" | "gold">("orange");

  useEffect(() => {
    let show: ReturnType<typeof setTimeout>;
    let hide: ReturnType<typeof setTimeout>;
    const loop = () => {
      show = setTimeout(() => {
        setSide(Math.random() < 0.5 ? "left" : "right");
        setTone(Math.random() < 0.5 ? "orange" : "gold");
        setVisible(true);
        hide = setTimeout(() => {
          setVisible(false);
          loop();
        }, 5400);
      }, 50000 + Math.random() * 50000);
    };
    loop();
    return () => { clearTimeout(show); clearTimeout(hide); };
  }, []);

  if (!visible || lottiOffen) return null;
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none fixed bottom-0 z-30 print-hidden",
        // Rechts weiter innen als früher (war right-3/sm:right-8): Dort
        // schwebt der Lotti-Knopf, und ein Küken halb dahinter sieht aus
        // wie ein Darstellungsfehler.
        side === "right" ? "right-24 sm:right-28" : "left-3 sm:left-8",
      )}
    >
      <div className="animate-peek">
        <Chick tone={tone} theme={theme} decorative className="h-16 w-16 drop-shadow-lg sm:h-20 sm:w-20" />
      </div>
    </div>
  );
}
