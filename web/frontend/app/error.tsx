"use client";

import { useEffect } from "react";
import { Card, Button } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { meldeFehler } from "@/lib/fehler-melden";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Surface to the browser console; server-side errors are already logged.
    console.error(error);
    // Und melden. Bis 09/2026 endete der Fehler hier — sichtbar nur in der
    // Konsole des Betroffenen, und der schreibt uns nicht.
    //
    // `digest` ist Nexts Hash eines SERVERSEITIGEN Fehlers: Er steht auch im
    // Server-Log und ist der einzige Faden zwischen beiden Seiten. Er trägt
    // nichts Persönliches, nur eine Prüfsumme.
    meldeFehler(error.digest ? Object.assign(error, {
      message: `${error.message} [digest ${error.digest}]`,
    }) : error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-waves px-4">
      <Card className="w-full max-w-sm p-8 text-center">
        <Mascot regung="ist-traurig" className="mx-auto h-24 w-24" />
        <h1 className="mt-4 text-lg font-semibold text-foreground">Etwas ist schiefgelaufen</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Da ist Lotti kurz vom Kurs abgekommen. Bitte versuche es erneut — falls das Problem bleibt, lade die Seite neu.
        </p>
        <Button onClick={reset} className="mt-6 w-full">Erneut versuchen</Button>
      </Card>
    </div>
  );
}
