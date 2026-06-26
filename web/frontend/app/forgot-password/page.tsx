"use client";

import { useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Button, Card, Input } from "@/components/ui";
import { BrandMark } from "@/components/brand";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Etwas ist schiefgelaufen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm p-8">
        <div className="flex items-center gap-3">
          <BrandMark />
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Passwort vergessen</h1>
        </div>
        {sent ? (
          <>
            <p className="mt-3 text-sm text-muted-foreground">
              Falls ein Konto mit dieser Adresse existiert, haben wir dir eine E-Mail mit einem Link zum
              Zurücksetzen geschickt. Der Link ist 1 Stunde gültig.
            </p>
            <p className="mt-6 text-center text-sm">
              <Link href="/login" className="font-medium text-primary hover:underline">Zurück zur Anmeldung</Link>
            </p>
          </>
        ) : (
          <>
            <p className="mt-3 text-sm text-muted-foreground">
              Gib deine E-Mail-Adresse ein — wir schicken dir einen Link zum Zurücksetzen deines Passworts.
            </p>
            <form onSubmit={onSubmit} className="mt-6 space-y-4">
              <div>
                <label htmlFor="email" className="mb-1 block text-sm font-medium text-foreground">E-Mail</label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="email" />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" disabled={busy} className="w-full">
                {busy ? "Senden…" : "Link senden"}
              </Button>
            </form>
            <p className="mt-6 text-center text-sm text-muted-foreground">
              <Link href="/login" className="hover:text-foreground hover:underline">Zurück zur Anmeldung</Link>
            </p>
          </>
        )}
      </Card>
    </div>
  );
}
