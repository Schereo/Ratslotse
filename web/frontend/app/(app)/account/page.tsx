"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { appleIdentityToken, appleSignInAvailable } from "@/lib/apple";
import { isNativeApp } from "@/lib/platform";
import { applyTheme, getTheme, isDarkNow, THEME_EVENT, type Theme } from "@/lib/theme";
import { Button, Card, ConfirmDialog, Input, Label, PageHeader, PasswordInput, toast } from "@/components/ui";
import { DeliverySettings } from "@/components/delivery-settings";
import { BadgesCard } from "@/components/badges";
import { GespraecheCard } from "@/components/gespraeche-settings";
import { cn } from "@/lib/utils";

/**
 * RL-U09 (Design 9a): „Erscheinungsbild" mit Vorschau-Kacheln im
 * iOS-Settings-Stil — Auswahl = Primär-Ring + Häkchen. „Automatisch"
 * (folgt dem System) gibt es nur in der App; im Web ist der Schalter
 * binär, ein gespeicherter System-Modus zeigt den aktuellen Ist-Zustand.
 */
function AppearanceCard() {
  const [ready, setReady] = useState(false);
  const [native, setNative] = useState(false);
  const [theme, setTheme] = useState<Theme>("light");
  useEffect(() => {
    const isNative = isNativeApp();
    setNative(isNative);
    // Auswahl synchron halten, wenn ein anderer Regler (Sidebar-Schalter,
    // ⌘K-Palette) das Theme wechselt — beide sind gleichzeitig sichtbar.
    const sync = () => {
      const stored = getTheme();
      setTheme(!isNative && stored === "system" ? (isDarkNow() ? "dark" : "light") : stored);
    };
    sync();
    setReady(true);
    window.addEventListener(THEME_EVENT, sync);
    return () => window.removeEventListener(THEME_EVENT, sync);
  }, []);
  const choose = (t: Theme) => {
    setTheme(t);
    applyTheme(t);
  };
  const options: { value: Theme; label: string; preview: React.ReactNode }[] = [
    { value: "light", label: "Hell", preview: <TilePreview mode="light" /> },
    { value: "dark", label: "Dunkel", preview: <TilePreview mode="dark" /> },
    ...(native ? [{ value: "system" as Theme, label: "Automatisch", preview: <TilePreview mode="split" /> }] : []),
  ];
  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Erscheinungsbild</h2>
      {ready && (
        <>
          <div className={cn("mt-4 grid gap-2.5", native ? "grid-cols-3" : "grid-cols-2")} role="radiogroup" aria-label="Erscheinungsbild">
            {options.map((o) => (
              <button
                key={o.value}
                type="button"
                role="radio"
                aria-checked={theme === o.value}
                onClick={() => choose(o.value)}
                className={cn(
                  "rounded-xl border border-border p-1.5 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  theme === o.value && "ring-2 ring-primary",
                )}
              >
                {o.preview}
                <span className="mt-1.5 flex items-center justify-center gap-1 text-xs font-medium text-foreground">
                  {theme === o.value && <Check className="h-3.5 w-3.5 text-primary" />}
                  {o.label}
                </span>
              </button>
            ))}
          </div>
          {native && (
            <p className="mt-3 text-xs text-muted-foreground">
              „Automatisch" folgt der iOS-Einstellung deines Geräts.
            </p>
          )}
        </>
      )}
    </Card>
  );
}

/** Mini-Vorschau einer Kachel: helle/dunkle Fläche mit angedeuteten Zeilen. */
function TilePreview({ mode }: { mode: "light" | "dark" | "split" }) {
  const bg =
    mode === "light" ? "bg-white" : mode === "dark" ? "bg-[#0d1826]" : "bg-[linear-gradient(105deg,#ffffff_50%,#0d1826_50%)]";
  return (
    <span className={cn("block h-14 overflow-hidden rounded-lg border border-border", bg)} aria-hidden>
      <span className="mx-2 mt-2 block h-1.5 w-8 rounded-full bg-[#9db2c4]/70" />
      <span className="mx-2 mt-1.5 block h-1 w-12 rounded-full bg-[#9db2c4]/45" />
      <span className="mx-2 mt-1 block h-1 w-10 rounded-full bg-[#9db2c4]/45" />
    </span>
  );
}

export default function AccountPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  // Apple-only-Konten (RL-1002): Löschung per Apple-Re-Auth statt Passwort.
  const hasPassword = user?.has_password !== false;
  const [nativeApple, setNativeApple] = useState(false);
  useEffect(() => setNativeApple(appleSignInAvailable()), []);

  const deleteMutation = useMutation({
    // Löschung verlangt eine frische Bestätigung — eine offene Session allein
    // (fremder Zugriff aufs Gerät) darf das Konto nicht zerstören können.
    mutationFn: async () => {
      if (hasPassword) return api.del("/account", { current_password: deletePassword });
      const token = await appleIdentityToken();
      if (!token) throw new ApiError(400, "Apple-Bestätigung abgebrochen.");
      return api.del("/account", { apple_identity_token: token });
    },
    onSuccess: async () => {
      toast.success("Dein Konto wurde gelöscht.");
      await logout();
      router.replace("/");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Konto konnte nicht gelöscht werden."),
  });

  const changeMutation = useMutation({
    mutationFn: () =>
      api.post("/account/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    onSuccess: () => {
      toast.success("Passwort erfolgreich geändert.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Passwort konnte nicht geändert werden."),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirm) {
      toast.error("Die Passwörter stimmen nicht überein.");
      return;
    }
    changeMutation.mutate();
  };

  return (
    <div>
      <PageHeader title="Mein Konto" description={user?.email} />
      {user?.apple_linked && (
        /* RL-1002: sichtbarer Hinweis, dass dieses Konto mit Apple verknüpft ist. */
        <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-foreground">
           Mit Apple verknüpft
        </span>
      )}

      {/* Karten-Raster (Tims iPad-Befund 16.08.: „Die Karten nutzen nicht die
          ganze Breite und stacken auch nicht so schön wie im Dashboard").
          Beides hatte je eine eigene Ursache:

          1. `max-w-4xl` deckelte das Raster bei 896 px. Auf dem iPad quer
             stehen 1116 px Inhalt zur Verfügung, am Desktop 1136 — 220 bzw.
             240 px blieben ungenutzt. Die Breite gibt jetzt die Hülle vor
             (max-w-7xl in app/(app)/layout.tsx), wie auf allen anderen Seiten.

          2. `lg:grid-cols-2` maß das FENSTER, das Raster liegt aber neben der
             Seitenleiste — dieselbe Falle, die auf dem Dashboard schon
             dokumentiert ist. Deshalb hier dieselbe Antwort: eine
             Container-Query auf der Breite des Rasters. Die Schwelle (768 px)
             ist die des Dashboards; darunter ist eine Spalte breiter als zwei
             enge.

          3. Und der eigentliche Befund: In einem Raster aus sieben Karten
             füllt die Auto-Platzierung ZEILEN, und eine Zeile ist so hoch wie
             ihre höchste Karte. Neben der sehr langen Benachrichtigungen-Karte
             stand deshalb die kurze Abzeichen-Karte und darunter ein halber
             Bildschirm Nichts (gemessen 459 × 494 px), während links noch zu
             scrollen war. Statt eines Rasters aus Einzelkarten sind es jetzt
             ZWEI SPALTEN, die je für sich stapeln — die kurzen Karten füllen
             den Platz neben der langen auf. Auf dem iPad quer sind das
             1116 statt 896 px Breite, 1580 statt 2118 px Höhe und eine größte
             Lücke von 565 × 88 statt 459 × 494 px (im Browser nachgemessen).

          Die Aufteilung ist inhaltlich, nicht nach Höhe gewürfelt: links, was
          Ratslotse von sich aus tut (melden, speichern), rechts, was dich und
          dein Gerät betrifft (Sammlung, Name, Aussehen, Anmeldung). Mobil
          stapelt alles in genau dieser Reihenfolge — die Abzeichen bleiben
          zwischen Benachrichtigungen und Passwort (RL-U12, 11a). */}
      <div className="@container/konto mt-6">
        <div className="grid items-start gap-6 @3xl/konto:grid-cols-2">
          <div className="flex flex-col gap-6">
            <DeliverySettings />

            {/* Design 6a②: „Gespräche speichern" — beidseitig änderbar zur
                Erstnutzungs-Frage im Ratsgespräch. */}
            <GespraecheCard />
          </div>

          <div className="flex flex-col gap-6">
            <BadgesCard />

            <DisplayNameCard />

            <AppearanceCard />

            {hasPassword ? (
              <Card className="p-6">
                <h2 className="font-semibold text-foreground">Passwort ändern</h2>
                <form onSubmit={handleSubmit} className="mt-4 space-y-4">
                  <div>
                    <Label htmlFor="current-password">Aktuelles Passwort</Label>
                    <PasswordInput
                      id="current-password"
                      className="mt-1"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      required
                      autoComplete="current-password"
                    />
                  </div>
                  <div>
                    <Label htmlFor="new-password">Neues Passwort</Label>
                    <PasswordInput
                      id="new-password"
                      className="mt-1"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      required
                      minLength={8}
                      autoComplete="new-password"
                    />
                  </div>
                  <div>
                    <Label htmlFor="confirm-password">Neues Passwort bestätigen</Label>
                    <PasswordInput
                      id="confirm-password"
                      className="mt-1"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      required
                      autoComplete="new-password"
                    />
                  </div>
                  <Button type="submit" disabled={changeMutation.isPending} className="w-full">
                    {changeMutation.isPending ? "Speichern…" : "Passwort ändern"}
                  </Button>
                </form>
              </Card>
            ) : (
              /* Apple-only (RL-1002): keine Passwort-Karte — stattdessen der Weg,
                 eines nachzurüsten (Reset-Link an die Konto-Adresse). */
              <Card className="p-6">
                <h2 className="font-semibold text-foreground">Anmeldung</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Du meldest dich mit Apple an — ein Passwort hat dieses Konto nicht.
                  Falls du zusätzlich eines möchtest, kannst du dir einen Link zum
                  Setzen an deine E-Mail-Adresse schicken lassen.
                </p>
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-4"
                  onClick={async () => {
                    try {
                      await api.post("/auth/forgot-password", { email: user?.email });
                      toast.success("Link zum Passwort-Setzen ist unterwegs — schau in dein Postfach.");
                    } catch (err) {
                      toast.error(err instanceof ApiError ? err.message : "Konnte den Link nicht senden.");
                    }
                  }}
                >
                  Passwort per E-Mail einrichten
                </Button>
              </Card>
            )}
          </div>

          {/* Die Gefahrenzone steht quer unter beiden Spalten — sie gehört zu
              keiner von beiden und soll auch nicht zwischen zwei harmlose
              Karten geraten. Ihr Inhalt legt sich bei Platz nebeneinander
              (Erklärung links, Bestätigung rechts), statt eine Karte über die
              volle Breite mit einem kurzen Feld am linken Rand zu füllen. */}
          <Card className="border-destructive/30 p-6 @3xl/konto:col-span-2">
            <div className="@3xl/konto:flex @3xl/konto:items-end @3xl/konto:justify-between @3xl/konto:gap-8">
              <div className="@3xl/konto:max-w-xl">
                <h2 className="font-semibold text-destructive">Konto löschen</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Löscht dein Konto und alle zugehörigen Daten (Themen, Treffer, Abos) unwiderruflich.
                  {hasPassword
                    ? " Zur Bestätigung brauchst du dein aktuelles Passwort."
                    : " Zur Bestätigung meldest du dich einmal frisch mit Apple an."}
                </p>
              </div>
              <div className="mt-4 flex flex-wrap items-end gap-3 @3xl/konto:mt-0 @3xl/konto:shrink-0 @3xl/konto:justify-end">
                {hasPassword ? (
                  <div className="w-full max-w-xs space-y-1.5 @3xl/konto:w-64">
                    <Label htmlFor="delete-password">Aktuelles Passwort</Label>
                    <PasswordInput
                      id="delete-password"
                      value={deletePassword}
                      onChange={(e) => setDeletePassword(e.target.value)}
                      autoComplete="current-password"
                    />
                  </div>
                ) : !nativeApple ? (
                  <p className="text-sm text-muted-foreground @3xl/konto:max-w-xs">
                    Die Apple-Bestätigung funktioniert nur in der App — oder richte dir oben
                    zuerst ein Passwort ein.
                  </p>
                ) : null}
                <Button
                  variant="danger"
                  onClick={() => setDeleteOpen(true)}
                  disabled={(hasPassword ? !deletePassword : !nativeApple) || deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? "Lösche…" : hasPassword ? "Konto löschen" : "Mit Apple bestätigen & löschen"}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Pflicht-Links für Handy-Web und App (der Seiten-Fuß ist mobil aus):
          über den Konto-Tab jederzeit in zwei Tipps erreichbar. Darüber die
          Abgrenzung zur Stadt — in der App ist der Konto-Tab die einzige Stelle,
          an der ein Fuß überhaupt steht (App-Store-Guideline 5.2). */}
      <p className="mt-8 text-balance text-center text-xs leading-relaxed text-muted-foreground desk:hidden">
        Ratslotse ist ein privates Bürgerprojekt und kein Angebot der Stadt Oldenburg.
      </p>
      <p className="mt-2 text-center text-xs text-muted-foreground desk:hidden">
        <a href="/impressum" className="hover:text-foreground">Impressum</a>
        {" · "}
        <a href="/datenschutz" className="hover:text-foreground">Datenschutz</a>
        {" · "}
        <a href="/changelog" className="hover:text-foreground">Changelog</a>
        {" · "}
        <a href="/barrierefreiheit" className="hover:text-foreground">Barrierefreiheit</a>
        {" · "}
        <a href="/docs" className="hover:text-foreground">Technik-Doku</a>
      </p>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Konto endgültig löschen?"
        description="Diese Aktion kann nicht rückgängig gemacht werden. Dein Konto und alle zugehörigen Daten (Themen, Treffer, Abos) werden dauerhaft gelöscht."
        confirmLabel="Endgültig löschen"
        variant="danger"
        onConfirm={() => deleteMutation.mutate()}
      />
    </div>
  );
}

/** Anzeigename setzen/ändern — auch für Apple-Konten und Alt-Bestand, die
 *  bei der Registrierung keinen angeben konnten. Speist die persönliche
 *  Ansprache auf der Übersicht und in Benachrichtigungs-Mails. */
function DisplayNameCard() {
  const { user, refresh } = useAuth();
  const [name, setName] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (user && !ready) {
      setName(user.display_name ?? "");
      setReady(true);
    }
  }, [user, ready]);
  const save = useMutation({
    mutationFn: () => api.post("/account/display-name", { display_name: name.trim() || null }),
    onSuccess: async () => {
      await refresh();
      toast.success("Anzeigename gespeichert.");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen."),
  });
  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Anzeigename</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        So sprechen wir dich auf der Übersicht und in E-Mails an.
      </p>
      <form
        onSubmit={(e: React.FormEvent) => {
          e.preventDefault();
          save.mutate();
        }}
        className="mt-4 flex gap-2"
      >
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={60}
          autoComplete="name"
          placeholder="z. B. Tim"
          aria-label="Anzeigename"
        />
        <Button type="submit" variant="secondary" disabled={save.isPending}>
          {save.isPending ? "Speichern…" : "Speichern"}
        </Button>
      </form>
    </Card>
  );
}
