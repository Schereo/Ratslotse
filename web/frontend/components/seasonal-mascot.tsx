"use client";

import * as React from "react";
import { useEffect, useState } from "react";
import { MascotFamily } from "@/components/mascot";
import { getMascotTheme, type MascotTheme } from "@/lib/mascot-theme";

/**
 * Bestimmt Lottis Outfit nach dem aktuellen Datum — aber erst nach dem Mount,
 * damit das statisch exportierte HTML (Build-Datum) keine falsche Jahreszeit
 * einbrennt und keine Hydration-Warnung entsteht. Vor dem Mount: neutral.
 *
 * Die Sprite-Lotti (<Mascot/>) kleidet sich selbst: Sie wählt ihren
 * Bündel-Ordner nach Jahreszeit (components/lotti.tsx) — ein früheres
 * `SeasonalMascot` braucht es deshalb nicht mehr. Dieser Hook versorgt nur
 * noch die gezeichnete Familie und die Küken.
 */
export function useMascotTheme(): MascotTheme | null {
  const [theme, setTheme] = useState<MascotTheme | null>(null);
  useEffect(() => {
    setTheme(getMascotTheme());
    // Über Mitternacht hinweg aktuell halten (lange Sessions/Kiosk-Displays).
    const id = setInterval(() => setTheme(getMascotTheme()), 60 * 60 * 1000);
    return () => clearInterval(id);
  }, []);
  return theme;
}

/** Die ganze Familie, automatisch der Jahreszeit entsprechend gekleidet. */
export function SeasonalFamily(props: Omit<React.ComponentProps<typeof MascotFamily>, "theme">) {
  const theme = useMascotTheme();
  return <MascotFamily {...props} theme={theme} />;
}
