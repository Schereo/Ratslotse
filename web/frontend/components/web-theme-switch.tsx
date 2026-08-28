"use client";

// Der Lotti-Theme-Schalter, nur im Web: In der nativen App läuft die Wahl über
// Konto → „Erscheinungsbild" (Entscheidung 22.07.), dort wäre ein zweiter
// Regler Doppelsteuerung. Mount-Gate, weil SSR die Plattform nicht kennt.
//
// Gedacht für Köpfe OHNE eingeloggte App-Hülle (Landing, /kommunalwahl):
// Dort gibt es kein Konto, also auch keinen anderen Weg zum Umschalten —
// deshalb erscheint er hier auf allen Bildschirmgrößen, nicht nur Desktop.

import { useEffect, useState } from "react";
import { LottiThemeSwitch } from "@/components/theme-switch";
import { isNativeApp } from "@/lib/platform";

export function WebThemeSwitch({ className }: { className?: string }) {
  const [show, setShow] = useState(false);
  useEffect(() => setShow(!isNativeApp()), []);
  if (!show) return null;
  return <LottiThemeSwitch className={className} />;
}
