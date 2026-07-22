"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

/** Offline-Hinweis (RL-1103): dezente Pille am unteren Rand, sobald die
 *  Verbindung weg ist — zusammen mit dem persistierten Query-Cache liest man
 *  in der App gespeicherte Inhalte weiter, statt auf Fehler zu laufen.
 *  Bewusst auch im Web aktiv (kostet nichts, hilft im Zug genauso). */
export function OfflinePill() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    setOffline(!navigator.onLine);
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      className="pointer-events-none fixed inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-50 flex justify-center lg:bottom-6"
    >
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/95 px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur">
        <WifiOff className="h-3.5 w-3.5" /> Offline — du siehst gespeicherte Inhalte
      </span>
    </div>
  );
}
