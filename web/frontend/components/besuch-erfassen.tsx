"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";

/** Nur die sichtbare App hält einen Besuch offen. Ein Hintergrund-Tab oder
 * API-Polling darf den nächsten Rückblick nicht verschlucken. */
export function BesuchErfassen({ userId }: { userId: number }) {
  const qc = useQueryClient();
  useEffect(() => {
    let cancelled = false;
    let lastWindow: string | undefined;
    const record = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const visit = await api.post<ApiAntwort<"/today/visit", "post">>("/today/visit", {});
        if (cancelled) return;
        if (lastWindow !== visit.until) {
          lastWindow = visit.until;
          await qc.invalidateQueries({ queryKey: ["today-updates", userId] });
        }
      } catch { /* Der Rückblick bietet seinen eigenen Wiederholen-Knopf. */ }
    };
    void record();
    document.addEventListener("visibilitychange", record);
    const timer = window.setInterval(record, 5 * 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", record);
    };
  }, [userId, qc]);
  return null;
}
