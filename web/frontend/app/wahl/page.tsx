"use client";

// /wahl — die kurze, sagbare Adresse („ratslotse.de/wahl"). Sie zeigt immer
// auf die Wahl im Fokus: von zwei Tagen vor dem Wahlschluss bis drei Tage
// danach auf diese, sonst auf die nächste anstehende.
//
// Warum eine Weiterleitung im Browser und keine im Server: Welche Wahl gemeint
// ist, entscheidet das Backend (`elections.focus`) und kann sich täglich
// ändern. Eine Regel in `next.config.mjs` wäre zur Bauzeit festgelegt — also
// genau die Konstante, die dieser ganze Umbau loswerden wollte.

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAppConfig } from "@/lib/features";

export default function WahlSeite() {
  const router = useRouter();
  const { data, isError } = useAppConfig();
  const ziel = data?.election?.path;

  useEffect(() => {
    if (ziel) router.replace(ziel);
    else if (isError) router.replace("/wahlen");
  }, [ziel, isError, router]);

  return (
    <main className="mx-auto flex min-h-[60dvh] max-w-md items-center justify-center px-4 text-center">
      <p className="text-[14px] text-muted-foreground">Einen Moment — wir schauen, welche Wahl gerade dran ist.</p>
    </main>
  );
}
