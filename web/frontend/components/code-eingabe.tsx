"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Button, Input, toast } from "@/components/ui";

/** Den sechsstelligen Code aus der Bestätigungsmail eintippen.
 *
 *  Für den Fall, dass die Mail auf einem anderen Gerät liegt als die Sitzung
 *  (registriert am Laptop, Mail am Handy): Der Link greift nur dort, wo man
 *  angemeldet ist — den Code tippt man einfach hier ein. Gilt für die
 *  Erstbestätigung wie für einen Adresswechsel (`POST /auth/verify-code`). */
export function CodeEingabe({ onBestaetigt, className = "" }: {
  onBestaetigt: () => Promise<void> | void;
  className?: string;
}) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const absenden = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/verify-code", { code });
      setCode("");
      await onBestaetigt();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Bestätigung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={absenden} className={`flex max-w-[16rem] gap-2 ${className}`}>
      <Input
        aria-label="Code aus der E-Mail"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={7}
        placeholder="123 456"
        className="text-center tracking-[0.2em]"
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />
      <Button type="submit" disabled={busy || code.replace(/\D/g, "").length !== 6}>
        {busy ? "Prüfe…" : "Bestätigen"}
      </Button>
    </form>
  );
}
