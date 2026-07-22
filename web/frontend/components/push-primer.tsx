"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isNativeApp } from "@/lib/platform";
import { enablePush } from "@/lib/push";
import { Button, Card, toast } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";
import type { Topic, User } from "@/lib/types";

const SNOOZE_KEY = "ratslotse.push-primer.snoozed-until";
const SNOOZE_DAYS = 7;

/** Push-Primer (RL-1102): freundliche Vorab-Karte in der App, BEVOR der
 *  System-Dialog erscheint — wer hier zustimmt, sagt auch im iOS-Dialog fast
 *  immer ja; wer „Später" tippt, wird 7 Tage nicht wieder gefragt (und der
 *  System-Dialog bleibt unverbraucht: iOS zeigt ihn nur einmal).
 *  RL-F02: erst beim ersten RELEVANTEN Moment — es gibt ≥ 1 Thema oder
 *  ≥ 1 Ausschuss-Abo. Eine frische Installation ohne beides sieht nichts. */
export function PushPrimer() {
  const { user, refresh } = useAuth();
  const theme = useMascotTheme();
  const [visible, setVisible] = useState(false);
  const native = isNativeApp();

  const topicsQuery = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<Topic[]>("/topics"),
    enabled: native && !!user,
  });
  const subsQuery = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => api.get<{ subscriptions: string[] }>("/subscriptions"),
    enabled: native && !!user,
  });
  const relevant =
    (topicsQuery.data?.length ?? 0) > 0 || (subsQuery.data?.subscriptions.length ?? 0) > 0;

  useEffect(() => {
    if (!native || !user || !relevant) {
      setVisible(false);
      return;
    }
    const pushOn = user.delivery_channel === "push" || user.delivery_channel === "both";
    if (pushOn) return;
    const until = Number(localStorage.getItem(SNOOZE_KEY) ?? 0);
    if (Date.now() < until) return;
    setVisible(true);
  }, [user, native, relevant]);

  const enable = useMutation({
    mutationFn: async () => {
      const ok = await enablePush();
      if (!ok) throw new ApiError(400, "Bitte Mitteilungen in den iOS-Einstellungen für Ratslotse erlauben.");
      // E-Mail bleibt an — Push kommt dazu (delivery_channel: both).
      const channel = user?.delivery_channel === "push" ? "push" : "both";
      await api.put<User>("/account/delivery", { delivery_channel: channel });
    },
    onSuccess: () => {
      refresh();
      setVisible(false);
      toast.success("Mitteilungen sind an — Lotti meldet sich bei Neuigkeiten.");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Mitteilungen konnten nicht aktiviert werden."),
  });

  const snooze = () => {
    localStorage.setItem(SNOOZE_KEY, String(Date.now() + SNOOZE_DAYS * 86400000));
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <Card className="mt-6 flex items-start gap-3 p-4">
      <Mascot pose="point" theme={theme} decorative className="h-12 w-12 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-foreground">Nichts mehr verpassen?</p>
        <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
          Lotti schickt dir eine Mitteilung, wenn der Rat zu deinen Themen
          entscheidet oder eine abonnierte Tagesordnung erscheint — direkt aufs
          Gerät, keine Werbung.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={() => enable.mutate()} disabled={enable.isPending}>
            {enable.isPending ? "Aktiviere…" : "Mitteilungen aktivieren"}
          </Button>
          <Button size="sm" variant="ghost" onClick={snooze}>Später</Button>
        </div>
      </div>
      <button
        type="button"
        onClick={snooze}
        aria-label="Hinweis schließen"
        className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <X className="h-4 w-4" />
      </button>
    </Card>
  );
}
