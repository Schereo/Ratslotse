"use client";

import { useEffect } from "react";
import { Mascot } from "@/components/mascot";
import { Button } from "@/components/ui";
import { meldeFehler } from "@/lib/fehler-melden";
import { chunkFehlerHeilen, istChunkFehler } from "@/lib/chunk-fehler";

/**
 * Error-Boundary INNERHALB der App-Shell: Wirft eine Seite (z. B. wegen eines
 * kaputten Datensatzes), bleiben Sidebar/Topbar/Bottom-Nav stehen und nur der
 * Inhaltsbereich zeigt den Fehler. Ohne diese Datei fiele der Fehler bis zur
 * Root-Boundary durch und risse die komplette Navigation mit.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
    // Nach einem Deploy fehlen die Programmteile der alten Seite: einmal neu
    // laden statt einer Fehlerseite, aus der „Erneut versuchen" nicht hinausführt.
    if (chunkFehlerHeilen(error)) return;
    // Und melden: React fängt den Fehler hier ab, `window.onerror` sieht ihn
    // nie. Bis 10/2026 blieben Abstürze innerhalb der App-Hülle deshalb
    // ungemeldet — nur die Wurzel-Fehlerseite meldete.
    meldeFehler(error.digest ? Object.assign(error, {
      message: `${error.message} [digest ${error.digest}]`,
    }) : error);
  }, [error]);
  const chunk = istChunkFehler(error);

  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Mascot regung="ist-traurig" className="h-28 w-28" />
      <h1 className="mt-4 text-xl font-semibold text-foreground">Etwas ist schiefgelaufen</h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        Da ist Lotti kurz vom Kurs abgekommen. Versuch es erneut — die Navigation
        und deine Daten sind davon nicht betroffen.
      </p>
      {/* Ein fehlender Programmteil kommt nur durch echtes Neuladen zurück. */}
      <Button className="mt-5" onClick={chunk ? () => window.location.reload() : reset}>
        {chunk ? "Seite neu laden" : "Erneut versuchen"}
      </Button>
    </div>
  );
}
