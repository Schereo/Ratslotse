"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { isNativeApp } from "@/lib/platform";
import { Chick } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";

const THRESHOLD = 70; // px Zug, ab dem losgelassen aktualisiert wird
const MAX_PULL = 110;

/** Pull-to-Refresh (RL-1104, nur App): Am Seitenanfang nach unten ziehen —
 *  ein Küken taucht auf, ab der Schwelle lädt die Seite ihre Daten neu
 *  (React-Query-Invalidierung, kein harter Reload). Nur transform/opacity;
 *  der native Gummiband-Effekt der WebView bleibt unangetastet. */
export function PullToRefresh() {
  const qc = useQueryClient();
  const theme = useMascotTheme();
  const [pull, setPull] = useState(0);
  const [busy, setBusy] = useState(false);
  const startY = useRef<number | null>(null);
  const pullRef = useRef(0);
  const busyRef = useRef(false);

  useEffect(() => {
    if (!isNativeApp()) return;

    const setPullBoth = (v: number) => {
      pullRef.current = v;
      setPull(v);
    };

    const onStart = (e: TouchEvent) => {
      startY.current = window.scrollY <= 0 && !busyRef.current ? e.touches[0].clientY : null;
    };
    const onMove = (e: TouchEvent) => {
      if (startY.current == null) return;
      const dy = e.touches[0].clientY - startY.current;
      // Widerstand: der Indikator folgt gebremst, wie man es vom System kennt.
      setPullBoth(dy > 0 ? Math.min(dy * 0.45, MAX_PULL) : 0);
    };
    const onEnd = async () => {
      if (startY.current == null) return;
      startY.current = null;
      const reached = pullRef.current >= THRESHOLD;
      setPullBoth(0);
      if (!reached) return;
      busyRef.current = true;
      setBusy(true);
      const started = Date.now();
      await qc.invalidateQueries().catch(() => {});
      // Mindest-Sichtzeit, damit das Küken nicht nur aufblitzt.
      const rest = Math.max(0, 700 - (Date.now() - started));
      setTimeout(() => {
        busyRef.current = false;
        setBusy(false);
      }, rest);
    };

    document.addEventListener("touchstart", onStart, { passive: true });
    document.addEventListener("touchmove", onMove, { passive: true });
    document.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      document.removeEventListener("touchstart", onStart);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onEnd);
    };
  }, [qc]);

  const visible = busy || pull > 4;
  const offset = busy ? THRESHOLD * 0.75 : pull;

  return (
    <div
      aria-hidden={!busy}
      role="status"
      className="pointer-events-none fixed inset-x-0 top-[env(safe-area-inset-top)] z-50 flex justify-center"
      style={{
        transform: `translateY(${visible ? offset - 46 : -56}px)`,
        opacity: visible ? Math.min(1, offset / THRESHOLD) : 0,
        transition: startY.current == null ? "transform 0.25s ease-out, opacity 0.2s ease-out" : "none",
      }}
    >
      <span className="flex items-center gap-2 rounded-full border border-border bg-card/95 px-3 py-1.5 shadow-sm backdrop-blur">
        <Chick tone="orange" theme={theme} decorative className={busy ? "h-6 w-6 animate-bounce" : "h-6 w-6"} />
        <span className="text-xs font-medium text-muted-foreground">
          {busy ? "Aktualisiere…" : pull >= THRESHOLD ? "Loslassen zum Aktualisieren" : "Ziehen zum Aktualisieren"}
        </span>
      </span>
    </div>
  );
}
