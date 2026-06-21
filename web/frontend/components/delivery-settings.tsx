"use client";

import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, toast } from "@/components/ui";
import type { DeliveryChannel, User } from "@/lib/types";

const OPTIONS: { value: DeliveryChannel; title: string; desc: string }[] = [
  { value: "email", title: "E-Mail", desc: "Digest an deine E-Mail-Adresse." },
  { value: "telegram", title: "Telegram", desc: "Digest in deinen Bot-Chat (Konto muss verbunden sein)." },
  { value: "both", title: "Beides", desc: "Digest per E-Mail und Telegram." },
];

/** Choose where the daily digest is delivered. */
export function DeliverySettings() {
  const { user, refresh } = useAuth();

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
  const linked = !!user?.linked;

  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Zustellung</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Wähle, wie du deinen täglichen Digest bekommst.
      </p>
      <div className="mt-4 space-y-2">
        {OPTIONS.map((opt) => {
          const needsTelegram = opt.value !== "email" && !linked;
          const active = current === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              disabled={needsTelegram || mutation.isPending}
              onClick={() => !active && mutation.mutate(opt.value)}
              className={[
                "flex w-full items-start gap-3 rounded-lg border p-3 text-left transition",
                active ? "border-primary bg-primary/5" : "border-border hover:bg-muted",
                needsTelegram ? "cursor-not-allowed opacity-50" : "",
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
                  {needsTelegram && " — zuerst Telegram verbinden."}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
