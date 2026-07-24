"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { setToken } from "@/lib/token";
import type { User } from "@/lib/types";
import { Button, Spinner } from "@/components/ui";
import { AuthShell } from "@/components/auth-shell";
import { useAuth } from "@/lib/auth";

type State = "missing" | "verifying" | "ok" | "error";

function VerifyInner() {
  const token = useSearchParams().get("token") ?? "";
  const { refresh } = useAuth();
  const router = useRouter();
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
        setState("ok");
        try { await refresh(); } catch { /* not logged in — fine */ }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Bestätigung fehlgeschlagen.");
        setState("error");
      }
    })();
  }, [token, refresh]);

  // Nach dem Bestätigen nicht stehenbleiben: In der App kommt man über einen
  // Deep-Link aus dem Mail-Programm hierher. Wer danach die App wechselt und
  // später zurückkommt, landete sonst wieder auf dieser Seite — mitten im
  // Einrichten und ohne erkennbaren Grund. Kurz bestätigen, dann weiter.
  useEffect(() => {
    if (state !== "ok") return;
    const t = setTimeout(() => router.replace("/dashboard"), 1400);
    return () => clearTimeout(t);
  }, [state, router]);

  if (state === "missing") {
    return (
      <p className="mt-6 text-sm text-muted-foreground">
        Der Bestätigungslink ist unvollständig. Bitte öffne den Link aus der E-Mail erneut
        oder fordere im eingeloggten Zustand einen neuen an.
      </p>
    );
  }
  if (state === "verifying") {
    return (
      <div className="mt-6 flex items-center gap-3 text-sm text-muted-foreground">
        <Spinner /> E-Mail wird bestätigt…
      </div>
    );
  }
  if (state === "ok") {
    return (
      <div className="mt-6 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <CheckCircle2 className="h-5 w-5 text-emerald-600" /> E-Mail bestätigt.
        </div>
        <p className="text-sm text-muted-foreground">
          Danke! Dein Konto ist jetzt aktiv — es geht gleich weiter.
        </p>
        <Link href="/dashboard"><Button className="w-full">Weiter zum Dashboard</Button></Link>
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
