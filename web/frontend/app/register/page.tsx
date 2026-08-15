"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useWeiterSuffix, zielNachAnmeldung } from "@/lib/public-routes";
import { useAuth } from "@/lib/auth";
import { Button, Input, PasswordInput } from "@/components/ui";
import { AuthShell } from "@/components/auth-shell";
import { AppleSignInButton } from "@/components/apple-sign-in-button";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const weiter = useWeiterSuffix();
  const [displayName, setDisplayName] = useState("");
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
      await register(email, password, displayName.trim());
      // Von einem geteilten Beschluss aus registriert? Dann dorthin zurück.
      router.replace(zielNachAnmeldung());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registrierung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Leinen los!" pose="celebrate" breit>
        <p className="mt-3 text-sm text-muted-foreground">
          Erstelle dein kostenloses Konto — Lotti lotst dich danach durch die ersten Schritte.
        </p>
        <div className="mt-5">
          {/* RL-1001: Apple steht immer an erster Stelle (nur in der App sichtbar). */}
          <AppleSignInButton label="Mit Apple registrieren" />
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          {/* Zwei Spalten, sobald die Karte breit ist (ab lg): Auf dem iPad quer
              ist Höhe die knappe Größe, Breite die üppige — Name und E-Mail
              nebeneinander sparen eine ganze Feldzeile. Schmal bleibt es
              einspaltig, dort wäre nebeneinander unbedienbar. */}
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              {/* Freiwillig — und zwar überall sonst auch schon: der Server nimmt
                  null, „Mit Apple registrieren" liefert gar keinen Namen, und
                  jede Anzeige kommt ohne aus („Moin!“ statt „Moin, X!“). Nur
                  dieses Feld verlangte ihn und ließ sonst niemanden vorbei. */}
              <label htmlFor="display-name" className="mb-1 block text-sm font-medium text-foreground">
                Anzeigename <span className="font-normal text-muted-foreground">(optional)</span>
              </label>
              {/* Kein autoFocus — dieselbe Lehre wie auf der Anmeldung: Das
                  statische HTML trägt das Attribut, iOS klappt die Tastatur schon
                  beim Parsen auf und scrollt das Feld über sie. Dabei wanderte die
                  ganze Karte nach oben und Lotti über ihrer Kante in die Dynamic
                  Island (Tims Befund 14.08.). Ohne Autofokus bleibt der Screen
                  stehen, wie er gebaut ist. */}
              <Input id="display-name" className="h-11" value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={60} autoComplete="name" placeholder="Dein Vorname genügt" />
            </div>
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium text-foreground">E-Mail</label>
              <Input id="email" type="email" className="h-11" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            </div>
          </div>
          <div>
            {/* Die Längenregel steht neben dem Label statt darunter: dieselbe
                Auskunft, eine Zeile weniger Karte — und sie ist dort zu lesen,
                bevor jemand tippt, nicht erst danach. */}
            <div className="mb-1 flex items-baseline justify-between gap-2">
              <label htmlFor="password" className="block text-sm font-medium text-foreground">Passwort</label>
              <span id="password-hinweis" className="text-xs text-muted-foreground">Mindestens 8 Zeichen</span>
            </div>
            <PasswordInput id="password" aria-describedby="password-hinweis" className="h-11" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {/* RL-1001: Registrieren ist DIE Signal-Handlung dieses Screens. */}
          <Button type="submit" variant="signal" disabled={busy} className="h-11 w-full">
            {busy ? "Erstellen…" : "Konto erstellen"}
          </Button>
          {/* RL-F01: DSGVO-Transparenz direkt an der Handlung (App-Review-relevant). */}
          <p className="text-center text-xs leading-relaxed text-muted-foreground">
            Mit der Registrierung akzeptierst du unsere{" "}
            <Link href="/datenschutz" className="underline hover:text-foreground">Datenschutzerklärung</Link>.
            Danach bestätigst du kurz deine E-Mail-Adresse.
          </p>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          Schon registriert?{" "}
          <Link href={`/login${weiter}`} className="font-medium text-primary hover:underline">
            Anmelden
          </Link>
        </p>
        {/* Hier endete bis 15.08. der Bürgerprojekt-Hinweis mit den
            Pflicht-Links. Beides steht jetzt unter der Karte auf dem
            Hintergrund (siehe AuthShell) — das ist der Platz, der auf dem
            iPad quer gefehlt hat. */}
    </AuthShell>
  );
}
