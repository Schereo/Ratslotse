"use client";

// Hält fest, welche Haushalts-Unterseite gerade besucht wird — die Datenseite
// des Wegweiser-Lesestands (lib/haushalt-fortschritt.ts).
//
// Sitzt im Haushalts-LAYOUT, nicht in den Seiten: Neunzehn einzelne Aufrufe
// wären neunzehn Gelegenheiten, einen zu vergessen — dieselbe Begründung wie
// beim Umgebungs-Gate direkt daneben. Gezählt wird jede Unterseite
// (/haushalt/…), nicht die Übersicht selbst: Sie ist der Wegweiser, kein
// Schritt. Die beiden Steckbriefe (/haushalt/bereich, /haushalt/steuer)
// werden mitgeschrieben, tauchen im Wegweiser aber nicht auf — er fragt nur
// nach seinen eigenen Zielen.

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { merkeBesucht } from "@/lib/haushalt-fortschritt";
import { pfad } from "@/lib/utils";

export function FortschrittMerker() {
  const p = pfad(usePathname());
  useEffect(() => {
    if (/^\/haushalt\/[a-z-]+$/.test(p)) merkeBesucht(p);
  }, [p]);
  return null;
}
