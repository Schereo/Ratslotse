import type { Metadata } from "next";
import { Suspense } from "react";
import View from "./view";
import { PROBLEM_ANGEBOT } from "@/lib/probleme";
import { buergerportalVorschauAktiv } from "@/lib/probleme-server";

export const metadata: Metadata = {
  title: PROBLEM_ANGEBOT.name,
  description: "Kommunale Probleme in Oldenburg auf einer unabhängigen, von Ratslotse moderierten Karte entdecken.",
  openGraph: {
    title: `${PROBLEM_ANGEBOT.name} — Ratslotse`,
    description: "Private Beobachtungen, öffentlich gebündelt: kommunale Probleme in Oldenburg auf einer Karte.",
  },
};

export default function Page() {
  // Vercel stellt bei Branch-Deployments VERCEL_ENV=preview bereit. Dort
  // funktionieren die neue FastAPI-Route und ihre leere Preview-Datenbank noch
  // nicht zwangsläufig gemeinsam mit dem Frontend. Frei erfundene, klar
  // markierte Daten machen die UI trotzdem prüfbar; Produktion nutzt immer API.
  return (
    <Suspense fallback={null}>
      <View vorschau={buergerportalVorschauAktiv()} />
    </Suspense>
  );
}
