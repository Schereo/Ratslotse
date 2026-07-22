"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button, Input, PasswordInput } from "@/components/ui";
import { AuthShell } from "@/components/auth-shell";
import { AppleSignInButton } from "@/components/apple-sign-in-button";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Moin!" pose="wave">
        <p className="mt-3 text-sm text-muted-foreground">Willkommen zurück — melde dich an, um fortzufahren.</p>
        <div className="mt-6">
          {/* RL-1001: Apple steht immer an erster Stelle (nur in der App sichtbar). */}
          <AppleSignInButton label="Mit Apple anmelden" />
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-medium text-foreground">E-Mail</label>
            <Input id="email" type="email" className="h-11" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="email" />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-foreground">Passwort</label>
            <PasswordInput id="password" className="h-11" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={busy} className="h-11 w-full">
            {busy ? "Anmelden…" : "Anmelden"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm">
          <Link href="/forgot-password" className="text-muted-foreground hover:text-foreground hover:underline">
            Passwort vergessen?
          </Link>
        </p>
        <p className="mt-3 text-center text-sm text-muted-foreground">
          Noch kein Konto?{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">
            Registrieren
          </Link>
        </p>
        {/* RL-F08: Docs-Link gestrichen — bleibt über Landing + Footer erreichbar. */}
        <p className="mt-4 border-t border-border pt-4 text-center text-xs text-muted-foreground">
          <Link href="/impressum" className="hover:text-foreground hover:underline">Impressum</Link>
          {" · "}
          <Link href="/datenschutz" className="hover:text-foreground hover:underline">Datenschutz</Link>
        </p>
    </AuthShell>
  );
}
