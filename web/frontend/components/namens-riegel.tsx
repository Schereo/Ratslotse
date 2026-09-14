"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Input } from "@/components/ui";

/** Der Nachtrag für Apple-Anmeldungen: „Wie sollen wir dich nennen?"
 *
 *  Seit 09/2026 ist der Anzeigename bei der Registrierung Pflicht — nur läuft
 *  „Mit Apple anmelden" an diesem Formular vorbei. Apple liefert den Namen
 *  **nur bei der allerersten Autorisierung**, und auch dann nur, wenn man ihn
 *  nicht verbirgt; ein Pflichtfeld im Registrierungsformular erreicht diese
 *  Konten also nie. Deshalb fragt der Riegel unmittelbar nach der Anmeldung
 *  nach, und zwar genau dann, wenn das Konto danach ohne Namen dasteht.
 *
 *  **Nur frische Konten.** Am 10.09.2026 gemessen: Alle drei Apple-Konten auf
 *  Prod tragen einen Namen. „Apple-Konto ohne Namen" heißt heute also „gerade
 *  eben entstanden (oder beim letzten Versuch abgebrochen)" — der Alt-Bestand
 *  wird nicht behelligt, das war Tims Entscheidung. Genau deshalb hängt der
 *  Riegel an dieser Bedingung und nicht an einem „ist neu"-Merker: Wer die
 *  Seite hier schließt, wird beim nächsten Anlauf wieder gefragt.
 *
 *  Nicht wegklickbar: kein Scrim-Klick, kein X. Er hat genau einen Ausgang. */
export function NamensRiegel({ onFertig }: { onFertig: () => void }) {
  const { refresh } = useAuth();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const speichern = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Bitte trage deinen Namen ein.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.post("/account/display-name", { display_name: name.trim() });
      await refresh();
      onFertig();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="namens-riegel-title"
      className="fixed inset-0 z-[var(--level-dialog)] flex items-center justify-center px-4"
    >
      {/* .scrim statt einer eigenen Farbe (s. app/globals.css). Als <div>, nicht
          als Knopf: Hier gibt es nichts zum Wegklicken. */}
      <div className="scrim absolute inset-0" />
      <div className="relative w-full max-w-md rounded-[22px] bg-card p-6 shadow-[0_24px_60px_-20px_rgba(2,32,71,0.45)]">
        <h2 id="namens-riegel-title" className="text-lg font-semibold text-foreground">
          Wie sollen wir dich nennen?
        </h2>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Apple gibt uns deinen Namen nicht mit. Er steht in der Anrede auf „Heute“
          und in deinen E-Mails — dein Vorname genügt.
        </p>
        <form onSubmit={speichern} className="mt-4 space-y-3">
          <Input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={60}
            required
            autoComplete="name"
            placeholder="Dein Vorname genügt"
            aria-label="Anzeigename"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" variant="signal" disabled={busy} className="h-11 w-full">
            {busy ? "Speichern…" : "Weiter"}
          </Button>
        </form>
      </div>
    </div>
  );
}
