"use client";

import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/lib/auth";
import { OnboardingFlow } from "@/components/onboarding-flow";
import { AufrufZaehler } from "@/components/aufruf-zaehler";
import { OfflinePill } from "@/components/offline-pill";
import { Toaster } from "@/components/ui";
import { fehlerMelderAnhaengen } from "@/lib/fehler-melden";
import { initTheme } from "@/lib/theme";
import { lohntWiederholen } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            // Einmal nachfassen bei Netz/5xx — nie bei 4xx: Ein 403 oder 404
            // bleibt beim zweiten Mal derselbe und kostete nur eine Sekunde
            // mehr Spinner.
            retry: (n, e) => n < 1 && lohntWiederholen(e),
          },
        },
      }),
  );

  useEffect(() => {
    initTheme();
    // Fehler, die keine React-Grenze fängt: ein `throw` außerhalb des
    // Renderns, ein abgelehntes Versprechen ohne `catch`. Sie landeten bisher
    // nur in der Browser-Konsole des Betroffenen — also nirgendwo.
    fehlerMelderAnhaengen();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {children}
        {/* 26a: richtet ein statt nur vorzustellen — ersetzt die drei
            Intro-Karten (RL-1103). Wer die schon gesehen hat, gilt als
            Bestandsnutzer und wird nicht nachträglich durchgeschickt.
            Muss INNERHALB des AuthProviders hängen: Der Flow richtet Abos und
            Themen ein, die es ohne Konto nicht gibt. */}
        <OnboardingFlow />
        {/* Zählt Seitenaufrufe (anonym, ohne Cookie). Muss INNERHALB des
            AuthProviders hängen: Ob jemand angemeldet ist, geht als Ja/Nein
            mit, damit der Server dafür kein Konto auflösen muss. */}
        <AufrufZaehler />
      </AuthProvider>
      {/* RL-1103: Offline-Hinweis. */}
      <OfflinePill />
      <Toaster />
    </QueryClientProvider>
  );
}
