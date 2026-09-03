"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { XCircle } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { setToken } from "@/lib/token";
import type { User } from "@/lib/types";
import { Button, Spinner } from "@/components/ui";
import { AuthShell } from "@/components/auth-shell";
import { useAuth } from "@/lib/auth";
import { SETUP_QUERY_KEY, holeSetupStand } from "@/lib/onboarding-setup";

type State = "missing" | "verifying" | "ok" | "error";

function VerifyInner() {
  const token = useSearchParams().get("token") ?? "";
  const { refresh } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [state, setState] = useState<State>(token ? "verifying" : "missing");
  const [error, setError] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true; // verify exactly once, even under StrictMode double-mount
    (async () => {
      try {
        const u = await api.post<User>("/auth/verify-email", { token });
        // Native app via deep link: the backend hands back a bearer token so the
        // user lands logged-in. On the web access_token is null → no-op.
        if (u.access_token) await setToken(u.access_token);
        try { await refresh(); } catch { /* not logged in — fine */ }
        // Den Stand des Assistenten schon HIER holen, nicht erst im Dashboard:
        // Sonst stünde nach dem Sprung erst „Heute" und der Assistent legte
        // sich eine Antwort später darüber. Fehlschlag ist egal — dann fragt
        // der Assistent selbst nach (er tut es ohnehin).
        try {
          await queryClient.prefetchQuery({ queryKey: SETUP_QUERY_KEY, queryFn: holeSetupStand, retry: false });
        } catch { /* nicht angemeldet o. Ä. — der Assistent fragt selbst */ }
        setState("ok");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Bestätigung fehlgeschlagen.");
        setState("error");
      }
    })();
  }, [token, refresh, queryClient]);

  // Nach dem Bestätigen nicht stehenbleiben: In der App kommt man über einen
  // Deep-Link aus dem Mail-Programm hierher. Wer danach die App wechselt und
  // später zurückkommt, landete sonst wieder auf dieser Seite — mitten im
  // Einrichten und ohne erkennbaren Grund.
  //
  // Ohne Verzögerung und ohne eigene Erfolgskarte: Bis 09/2026 stand hier 1,4 s
  // lang ein helles „E-Mail bestätigt" mit Weiter-Knopf, bevor der dunkle
  // Assistent kam — ein dritter Screen zwischen Mail und Einrichtung, der
  // nichts trug. Wer aus der Mail zurückkommt, springt jetzt direkt ins
  // Einrichten; bis dahin läuft der Lade-Zustand dieser Seite weiter.
  useEffect(() => {
    if (state !== "ok") return;
    router.replace("/dashboard");
  }, [state, router]);

  if (state === "missing") {
    return (
      <p className="mt-6 text-sm text-muted-foreground">
        Der Bestätigungslink ist unvollständig. Bitte öffne den Link aus der E-Mail erneut
        oder fordere im eingeloggten Zustand einen neuen an.
      </p>
    );
  }
  // „ok" zeigt dasselbe Bild wie „verifying": Der Sprung ins Einrichten ist
  // schon unterwegs, ein zweiter Zustand wäre nur ein Aufblitzen.
  if (state === "verifying" || state === "ok") {
    return (
      <div className="mt-6 flex items-center gap-3 text-sm text-muted-foreground">
        <Spinner /> {state === "ok" ? "Es geht los…" : "E-Mail wird bestätigt…"}
      </div>
    );
  }
  return (
    <div className="mt-6 space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium text-destructive">
        <XCircle className="h-5 w-5" /> {error}
      </div>
      <p className="text-sm text-muted-foreground">
        Melde dich an und fordere im Hinweis einen neuen Bestätigungslink an.
      </p>
      <Link href="/login"><Button variant="secondary" className="w-full">Zur Anmeldung</Button></Link>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <AuthShell title="E-Mail bestätigen" pose="search">
      <Suspense fallback={<p className="mt-6 text-sm text-muted-foreground">Lädt…</p>}>
        <VerifyInner />
      </Suspense>
    </AuthShell>
  );
}
