"use client";

import { useEffect } from "react";
import { Mascot } from "@/components/mascot";
import { Button } from "@/components/ui";

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
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Mascot pose="confused" className="h-28 w-28" />
      <h1 className="mt-4 text-xl font-semibold text-foreground">Etwas ist schiefgelaufen</h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        Da ist Lotti kurz vom Kurs abgekommen. Versuch es erneut — die Navigation
        und deine Daten sind davon nicht betroffen.
      </p>
      <Button className="mt-5" onClick={reset}>
        Erneut versuchen
      </Button>
    </div>
  );
}
