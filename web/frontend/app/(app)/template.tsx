"use client";

/** RL-1104: sanfter Seiten-Einstieg bei jeder Navigation im eingeloggten
 *  Bereich. Ein template.tsx re-mountet pro Navigation — die CSS-Klasse
 *  (nur transform/opacity) läuft daher genau einmal je Seitenwechsel und
 *  ruht komplett bei prefers-reduced-motion.
 *
 *  Nach dem Ende fliegt die Klasse RUNTER: animation-fill-mode `both` hält
 *  den letzten Frame fest, und Chrome rechnet auch `transform: none` dort
 *  als Identitäts-Matrix — das Element bliebe damit für immer Containing
 *  Block und würde jedes position:fixed der Seite kapern (der Chat-Composer
 *  hing so an der Seite statt am Viewport, Tims TestFlight-Befund 11.08.).
 *  Bei reduzierter Bewegung feuert kein animationend — dort definiert die
 *  Klasse aber auch keine Animation, es gibt nichts zu entfernen. */
export default function AppTemplate({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="animate-fade-up"
      onAnimationEnd={(e) => {
        if (e.animationName === "fade-up" && e.target === e.currentTarget) {
          e.currentTarget.classList.remove("animate-fade-up");
        }
      }}
    >
      {children}
    </div>
  );
}
