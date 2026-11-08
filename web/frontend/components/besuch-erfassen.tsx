"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";

type Rueckblick = ApiAntwort<"/today/updates">;

/** Nur die sichtbare App hält einen Besuch offen. Ein Hintergrund-Tab oder
 * API-Polling darf den nächsten Rückblick nicht verschlucken.
 *
 * Auf „Heute" zeichnet der Rückblick den Besuch selbst auf
 * (`POST /today/visit/updates`, s. seit-besuch-widget.tsx). Läuft seine
 * Abfrage gerade, wäre ein zweiter POST doppelt — er entfällt dann. Damit das
 * schon beim Seitenaufruf greift, wartet der erste Aufruf einen Takt: Effekte
 * laufen Geschwister für Geschwister, und dieser hier steht in der Hülle VOR
 * dem Seiteninhalt. Ohne den Takt käme sein POST immer zuerst, bevor der
 * Rückblick überhaupt angefragt hat.
 */
export function BesuchErfassen({ userId }: { userId: number }) {
  const qc = useQueryClient();
  useEffect(() => {
    const key = ["today-updates", userId];
    let cancelled = false;
    let lastWindow: string | undefined;
    const record = async () => {
      if (document.visibilityState !== "visible") return;
      if (qc.isFetching({ queryKey: key, exact: true }) > 0) return;
      try {
        const visit = await api.post<ApiAntwort<"/today/visit", "post">>("/today/visit", {});
        if (cancelled) return;
        if (lastWindow !== visit.until) {
          lastWindow = visit.until;
          // Zeigt der Rückblick schon diesen Besuch (er hat ihn ja selbst
          // aufgezeichnet), gibt es nichts nachzuladen.
          if (qc.getQueryData<Rueckblick>(key)?.until !== visit.until) {
            await qc.invalidateQueries({ queryKey: key });
          }
        }
      } catch { /* Der Rückblick bietet seinen eigenen Wiederholen-Knopf. */ }
    };
    const first = window.setTimeout(record, 0);
    document.addEventListener("visibilitychange", record);
    const timer = window.setInterval(record, 5 * 60_000);
    return () => {
      cancelled = true;
      clearTimeout(first);
      clearInterval(timer);
      document.removeEventListener("visibilitychange", record);
    };
  }, [userId, qc]);
  return null;
}
