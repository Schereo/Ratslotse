"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Button, Card, PasswordInput, toast } from "@/components/ui";
import { BrandMark } from "@/components/brand";

function ResetForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Die Passwörter stimmen nicht überein.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: password });
      toast.success("Passwort gesetzt. Bitte melde dich an.");
      router.replace("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Zurücksetzen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <p className="mt-4 text-sm text-muted-foreground">
        Der Link ist unvollständig oder fehlt. Fordere unter{" "}
        <Link href="/forgot-password" className="text-primary hover:underline">Passwort vergessen</Link> einen neuen an.
      </p>
    );
  }

  return (
    <form onSubmit={onSubmit} className="mt-6 space-y-4">
      <div>
        <label htmlFor="new-password" className="mb-1 block text-sm font-medium text-foreground">Neues Passwort</label>
        <PasswordInput id="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoFocus autoComplete="new-password" />
      </div>
      <div>
        <label htmlFor="confirm-password" className="mb-1 block text-sm font-medium text-foreground">Passwort bestätigen</label>
        <PasswordInput id="confirm-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={busy} className="w-full">{busy ? "Speichern…" : "Passwort setzen"}</Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm p-8">
        <div className="flex items-center gap-3">
          <BrandMark />
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Neues Passwort</h1>
        </div>
        <Suspense fallback={<p className="mt-6 text-sm text-muted-foreground">Lädt…</p>}>
          <ResetForm />
        </Suspense>
      </Card>
    </div>
  );
}
