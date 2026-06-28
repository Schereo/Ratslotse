"use client";

import { useEffect } from "react";
import { Card, Button } from "@/components/ui";
import { BrandMark } from "@/components/brand";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Surface to the browser console; server-side errors are already logged.
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm p-8 text-center">
        <div className="flex items-center justify-center gap-3">
          <BrandMark />
          <span className="text-2xl font-bold tracking-tight text-foreground">Fehler</span>
        </div>
        <h1 className="mt-4 text-lg font-semibold text-foreground">Etwas ist schiefgelaufen</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Bitte versuche es erneut. Falls das Problem bleibt, lade die Seite neu.
        </p>
        <Button onClick={reset} className="mt-6 w-full">Erneut versuchen</Button>
      </Card>
    </div>
  );
}
