"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button, Input, PasswordInput } from "@/components/ui";
import { AuthShell } from "@/components/auth-shell";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Das Passwort muss mindestens 8 Zeichen lang sein.");
      return;
    }
    setBusy(true);
    try {
      await register(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registrierung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Leinen los!" pose="celebrate">
        <p className="mt-3 text-sm text-muted-foreground">
          Erstelle dein kostenloses Konto — Lotti lotst dich danach durch die ersten Schritte.
        </p>
        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-medium text-foreground">E-Mail</label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="email" />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-foreground">Passwort</label>
            <PasswordInput id="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
            <p className="mt-1 text-xs text-muted-foreground">Mindestens 8 Zeichen.</p>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Erstellen…" : "Konto erstellen"}
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Schon registriert?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Anmelden
          </Link>
        </p>
    </AuthShell>
  );
}
