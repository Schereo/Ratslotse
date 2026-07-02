"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isNativeApp } from "@/lib/platform";
import { enablePush } from "@/lib/push";
import { Card, toast } from "@/components/ui";
import type { DeliveryChannel, User } from "@/lib/types";

const OPTIONS: { value: DeliveryChannel; title: string; desc: string }[] = [
  { value: "email", title: "E-Mail", desc: "Benachrichtigung an deine E-Mail-Adresse." },
  { value: "push", title: "Push (App)", desc: "Mitteilung direkt auf dieses Gerät." },
  { value: "both", title: "Beides", desc: "Per E-Mail und Push." },
];

/** Choose where the daily digest is delivered. */
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

  const current = user?.delivery_channel ?? "email";

  // Push only makes sense in the app; still surface it if it's already the active
  // channel (e.g. set on another device) so the selection is visible on the web.
  const options = OPTIONS.filter((o) => o.value !== "push" || native || current === "push");

  const choose = async (channel: DeliveryChannel) => {
    if (channel === current) return;
    if (channel === "push") {
      const ok = await enablePush();
      if (!ok) {
        toast.error("Bitte Mitteilungen für Ratslotse in den Geräte-Einstellungen erlauben.");
        return;
      }
    }
    mutation.mutate(channel);
  };

  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Zustellung</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Wähle, wie du Benachrichtigungen zu deinen Themen bekommst.
      </p>
      <div className="mt-4 space-y-2">
        {options.map((opt) => {
          const pushUnavailable = opt.value === "push" && !native;
          const blocked = pushUnavailable;
          const active = current === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              disabled={blocked || mutation.isPending}
              onClick={() => choose(opt.value)}
              className={[
                "flex w-full items-start gap-3 rounded-lg border p-3 text-left transition",
                active ? "border-primary bg-primary/5" : "border-border hover:bg-muted",
                blocked ? "cursor-not-allowed opacity-50" : "",
              ].join(" ")}
            >
              <span
                className={[
                  "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                  active ? "border-primary" : "border-muted-foreground",
                ].join(" ")}
              >
                {active && <span className="h-2 w-2 rounded-full bg-primary" />}
              </span>
              <span>
                <span className="block text-sm font-medium text-foreground">{opt.title}</span>
                <span className="block text-xs text-muted-foreground">
                  {opt.desc}
                  {pushUnavailable && " — nur in der App verfügbar."}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
