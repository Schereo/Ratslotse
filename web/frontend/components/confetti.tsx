"use client";

import { useEffect, useState } from "react";

/**
 * Kurzer Konfetti-Regen in Markenfarben — ohne Dependency, rein CSS-animiert
 * (Keyframe `confetti-fall` in globals.css). Bei prefers-reduced-motion wird
 * gar nicht erst gerendert. Entfernt sich nach dem Durchlauf selbst.
 */
const COLORS = ["#0764a6", "#f66623", "#f2b441", "#0d9488", "#3db1f5"];
const PIECES = 36;

export function ConfettiBurst({ onDone }: { onDone?: () => void }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => {
      setVisible(false);
      onDone?.();
    }, 3200);
    return () => clearTimeout(t);
  }, [onDone]);

  if (!visible) return null;
  if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return null;

  return (
    <div className="pointer-events-none fixed inset-0 z-[80] overflow-hidden" aria-hidden>
      {Array.from({ length: PIECES }).map((_, i) => (
        <span
          key={i}
          className="absolute block animate-confetti-fall rounded-[2px]"
          style={{
            left: `${(i * 37 + 11) % 100}%`,
            top: "-3vh",
            width: 6 + (i % 3) * 3,
            height: 10 + (i % 4) * 3,
            backgroundColor: COLORS[i % COLORS.length],
            animationDelay: `${(i % 12) * 0.12}s`,
            animationDuration: `${2.2 + (i % 5) * 0.25}s`,
          }}
        />
      ))}
    </div>
  );
}
