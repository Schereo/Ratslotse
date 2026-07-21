"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "@/components/ui";
import { appleIdentityToken, appleSignInAvailable } from "@/lib/apple";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

/** Apple-Logo als Inline-Pfad (das offizielle Glyph, HIG-konform in Weiß). */
function AppleLogo() {
  return (
    <svg viewBox="0 0 814 1000" aria-hidden className="h-4 w-4 fill-current">
      <path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76.5 0-103.7 40.8-165.9 40.8s-105.6-57-155.5-127C46.7 790.7 0 663 0 541.8c0-194.4 126.4-297.5 250.8-297.5 66.1 0 121.2 43.4 162.7 43.4 39.5 0 101.1-46 176.3-46 28.5 0 130.9 2.6 198.3 99.2zm-234-181.5c31.1-36.9 53.1-88.1 53.1-139.3 0-7.1-.6-14.3-1.9-20.1-50.6 1.9-110.8 33.7-147.1 75.8-28.5 32.4-55.1 83.6-55.1 135.5 0 7.8 1.3 15.6 1.9 18.1 3.2.6 8.4 1.3 13.6 1.3 45.4 0 102.5-30.4 135.5-71.3z" />
    </svg>
  );
}

/** „Mit Apple fortfahren" (RL-1001/1002): steht auf den Auth-Seiten IMMER an
 *  erster Position — gerendert wird er aber nur in der nativen App (der
 *  Web-Flow bräuchte eine Apple-Service-ID). Nach dem Mount geprüft, damit
 *  SSR/Hydration deckungsgleich bleiben. */
export function AppleSignInButton({ label = "Mit Apple fortfahren" }: { label?: string }) {
  const { loginWithApple } = useAuth();
  const router = useRouter();
  const [available, setAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => setAvailable(appleSignInAvailable()), []);

  if (!available) return null;

  const onClick = async () => {
    setBusy(true);
    try {
      const token = await appleIdentityToken();
      if (!token) return; // abgebrochen — kein Fehler-Toast
      await loginWithApple(token);
      router.replace("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Apple-Anmeldung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={onClick}
        disabled={busy}
        className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-black text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-60 dark:bg-white dark:text-black"
      >
        <AppleLogo /> {busy ? "Anmelden…" : label}
      </button>
      <div className="my-4 flex items-center gap-3" aria-hidden>
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">oder mit E-Mail</span>
        <span className="h-px flex-1 bg-border" />
      </div>
    </>
  );
}
