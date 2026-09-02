"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button, toast } from "@/components/ui";
import { cn } from "@/lib/utils";

/**
 * „Diesen Vorgang verfolgen" (Design 28a/W1).
 *
 * Themen und Ausschuss-Abos sind breite Netze. Wer EINE Vorlage durch die
 * Gremien begleiten will — die Schule im eigenen Viertel, das Stadion —, hatte
 * bisher nur die Möglichkeit, regelmäßig selbst nachzusehen. Ein Klick hier
 * genügt; der tägliche Cron meldet jede neue Beratungsstation.
 *
 * Der Zustand kommt als `initial` von der Beschluss-Seite mit (eine Abfrage
 * weniger); danach führt der Knopf ihn selbst weiter.
 */
export function FollowButton({ kvonr, initial, className }: {
  kvonr: number;
  initial: boolean;
  className?: string;
}) {
  const qc = useQueryClient();
  const [following, setFollowing] = useState(initial);
  const [busy, setBusy] = useState(false);

  // Beim Wechsel auf einen anderen Beschluss derselben Seite mitziehen.
  useEffect(() => setFollowing(initial), [initial, kvonr]);

  const toggle = async () => {
    if (busy) return;
    const next = !following;
    setBusy(true);
    setFollowing(next); // optimistisch — bei Fehler unten zurückgedreht
    try {
      if (next) await api.post(`/council/template/${kvonr}/follow`, {});
      else await api.del(`/council/template/${kvonr}/follow`);
      qc.invalidateQueries({ queryKey: ["vorlage-follows"] });
      toast.success(
        next
          ? "Wird verfolgt — du hörst von uns, sobald es weitergeht."
          : "Vorgang wird nicht mehr verfolgt.",
      );
    } catch (e) {
      setFollowing(!next);
      toast.error(e instanceof ApiError ? e.message : "Hat nicht geklappt.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={toggle}
      disabled={busy}
      aria-pressed={following}
      className={cn("mt-3 w-full", className)}
    >
      {busy ? <Loader2 className="animate-spin" /> : following ? <BellOff /> : <Bell />}
      {following ? "Wird verfolgt" : "Diesen Vorgang verfolgen"}
    </Button>
  );
}
