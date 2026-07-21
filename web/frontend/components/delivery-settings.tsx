"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { BellRing } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isNativeApp } from "@/lib/platform";
import { enablePush } from "@/lib/push";
import { Button, Card, Switch, toast } from "@/components/ui";
import type { DeliveryChannel, User } from "@/lib/types";

/** Benachrichtigungen-Karte (RL-702, Design 6a): E-Mail und Push als
 *  unabhängige Schalter (intern weiter der eine delivery_channel:
 *  email | push | both) + „Test-Benachrichtigung senden". Mindestens ein
 *  Kanal bleibt an — sonst käme ja nie etwas an. */
export function DeliverySettings() {
  const { user, refresh } = useAuth();
  // Detected after mount to avoid a hydration mismatch between the static export
  // (rendered as web) and the app runtime.
  const [native, setNative] = useState(false);
  useEffect(() => { setNative(isNativeApp()); }, []);

  const mutation = useMutation({
    mutationFn: (channel: DeliveryChannel) =>
      api.put<User>("/account/delivery", { delivery_channel: channel }),
    onSuccess: () => {
      refresh();
      toast.success("Zustellung aktualisiert.");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Konnte nicht gespeichert werden."),
  });

  const testMutation = useMutation({
    mutationFn: () => api.post<{ sent: string[] }>("/account/test-notification", {}),
    onSuccess: (d) =>
      d.sent.length > 0
        ? toast.success(`Test unterwegs: ${d.sent.map((s) => (s === "email" ? "E-Mail" : "Push")).join(" + ")}.`)
        : toast.error("Kein Kanal konnte zustellen — Push braucht die App, E-Mail den Versand-Dienst."),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Test konnte nicht gesendet werden."),
  });

  const current = user?.delivery_channel ?? "email";
  const emailOn = current === "email" || current === "both";
  const pushOn = current === "push" || current === "both";
  // Push nur in der App aktivierbar; ist er (auf einem anderen Gerät) schon an,
  // bleibt der Schalter auch im Web sichtbar/bedienbar.
  const pushAvailable = native || pushOn;

  const apply = (email: boolean, push: boolean) => {
    if (!email && !push) {
      toast.error("Mindestens ein Kanal muss an bleiben.");
      return;
    }
    mutation.mutate(email && push ? "both" : email ? "email" : "push");
  };

  const togglePush = async (next: boolean) => {
    if (next) {
      const ok = await enablePush();
      if (!ok) {
        toast.error("Bitte Mitteilungen für Ratslotse in den Geräte-Einstellungen erlauben.");
        return;
      }
    }
    apply(emailOn, next);
  };

  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Benachrichtigungen</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Für neue Beschlüsse zu deinen Themen und abonnierte Tagesordnungen.
      </p>
      <div className="mt-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">E-Mail</p>
            <p className="truncate text-xs text-muted-foreground">an {user?.email}</p>
          </div>
          <Switch
            checked={emailOn}
            aria-label="E-Mail-Benachrichtigungen"
            disabled={mutation.isPending}
            onCheckedChange={(v) => apply(v, pushOn)}
          />
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">Push</p>
            <p className="text-xs text-muted-foreground">
              {pushAvailable ? "Mitteilung direkt auf dieses Gerät." : "Nur in der App verfügbar."}
            </p>
          </div>
          <Switch
            checked={pushOn}
            aria-label="Push-Benachrichtigungen"
            disabled={!pushAvailable || mutation.isPending}
            onCheckedChange={togglePush}
          />
        </div>
      </div>
      <Button
        variant="secondary"
        size="sm"
        className="mt-5"
        onClick={() => testMutation.mutate()}
        disabled={testMutation.isPending}
      >
        <BellRing /> {testMutation.isPending ? "Sende…" : "Test-Benachrichtigung senden"}
      </Button>
    </Card>
  );
}
