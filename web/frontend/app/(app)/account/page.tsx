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
import { Button, Card, ConfirmDialog, Label, PageHeader, PasswordInput, toast } from "@/components/ui";
import { DeliverySettings } from "@/components/delivery-settings";
import { BadgesCard } from "@/components/badges";
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

      <div className="mt-6 grid max-w-4xl items-start gap-6 lg:grid-cols-2">
        <DeliverySettings />

        {/* RL-U12 (11a): zwischen Benachrichtigungen und Passwort. */}
        <BadgesCard />

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

        <Card className="border-destructive/30 p-6 lg:col-span-2">
          <h2 className="font-semibold text-destructive">Konto löschen</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Löscht dein Konto und alle zugehörigen Daten (Themen, Treffer, Abos) unwiderruflich.
            {hasPassword
              ? " Zur Bestätigung brauchst du dein aktuelles Passwort."
              : " Zur Bestätigung meldest du dich einmal frisch mit Apple an."}
          </p>
          {hasPassword ? (
            <div className="mt-4 max-w-xs space-y-1.5">
              <Label htmlFor="delete-password">Aktuelles Passwort</Label>
              <PasswordInput
                id="delete-password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
          ) : !nativeApple ? (
            <p className="mt-3 text-sm text-muted-foreground">
              Die Apple-Bestätigung funktioniert nur in der App — oder richte dir oben
              zuerst ein Passwort ein.
            </p>
          ) : null}
          <Button
            variant="danger"
            className="mt-4"
            onClick={() => setDeleteOpen(true)}
            disabled={(hasPassword ? !deletePassword : !nativeApple) || deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Lösche…" : hasPassword ? "Konto löschen" : "Mit Apple bestätigen & löschen"}
          </Button>
        </Card>
      </div>

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
