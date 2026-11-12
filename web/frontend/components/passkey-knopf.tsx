"use client";

/* „Mit Passkey anmelden“ (seit 11/2026, Schalter `passkey-anmeldung`). Steht
   auf Anmeldung und Registrierung VOR E-Mail und Passwort — Tim wollte, dass
   die Seite zu Passkey oder Apple lenkt; die Adresse bleibt trotzdem Pflicht,
   sonst gäbe es keine Benachrichtigungen. Dieselbe Abfrage schließt, wo der
   Browser es kann, auch die Notizen auf (`lib/passkey.ts`). */

import { useEffect, useState } from "react";
import { KeyRound } from "lucide-react";
import { useFeature } from "@/lib/features";
import { passkeyAnmeldungMoeglich } from "@/lib/passkey";
import { PasskeyFehler } from "@/lib/notiz-passkey";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui";

/** Ist der Passkey-Weg hier anzubieten? Erst nach dem Mount gefragt, damit
 *  Server- und Browser-HTML übereinstimmen. */
export function usePasskeyAnmeldung(): boolean {
  const an = useFeature("passkey-anmeldung");
  const [moeglich, setMoeglich] = useState(false);
  useEffect(() => setMoeglich(passkeyAnmeldungMoeglich()), []);
  return an && moeglich;
}

/** Die Meldung zu einem Fehlschlag — oder `null`, wenn niemand eine braucht
 *  (selbst abgebrochen). */
export function passkeyMeldung(err: unknown): string | null {
  if (err instanceof PasskeyFehler) return err.art === "abgebrochen" ? null : err.message;
  if (err instanceof ApiError) return err.message;
  return err instanceof Error ? err.message : "Das hat nicht geklappt.";
}

export function PasskeyKnopf({ label, onClick, busy, variant = "primary" }: {
  label: string; onClick: (e: React.MouseEvent<HTMLButtonElement>) => void; busy: boolean; variant?: "primary" | "signal";
}) {
  return (
    <Button type="button" variant={variant} disabled={busy} onClick={onClick} className="h-11 w-full gap-2">
      <KeyRound className="h-4 w-4" aria-hidden />
      {busy ? "Wartet auf den Passkey …" : label}
    </Button>
  );
}

/** Die Linie zwischen dem empfohlenen Weg und E-Mail/Passwort. */
export function OderTrenner({ text }: { text: string }) {
  return (
    <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground" role="separator">
      <span className="h-px flex-1 bg-border" />
      {text}
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}
