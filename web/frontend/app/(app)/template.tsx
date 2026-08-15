"use client";

/** RL-1104: sanfter Seiten-Einstieg bei jeder Navigation im eingeloggten
 *  Bereich. Ein template.tsx re-mountet pro Navigation — die CSS-Klasse läuft
 *  daher genau einmal je Seitenwechsel und ruht komplett bei
 *  prefers-reduced-motion.
 *
 *  Die Animation blendet nur ein, sie hebt nicht mehr an: Ein laufendes
 *  transform macht das Element zum Containing Block für jedes position:fixed
 *  darin — der Chat-Composer saß die ersten 0,34 s jeder Navigation 164 px zu
 *  hoch, verdeckte die unterste Beispielfrage und sprang am Animationsende an
 *  den Bildschirmrand (Tims Befund 15.08.). Der Dauerzustand war schon
 *  entschärft (fill-mode hält `transform: none` fest, was Chrome trotzdem als
 *  Matrix rechnet — deshalb fliegt die Klasse unten nach dem Lauf runter),
 *  das Fenster WÄHREND des Laufs blieb. Siehe app/globals.css.
 *
 *  Das Abräumen bleibt trotzdem: Ohne es hielte `opacity: 1` einen
 *  Stacking-Context fest, den hier niemand braucht. Bei reduzierter Bewegung
 *  feuert kein animationend — dort definiert die Klasse aber auch keine
 *  Animation, es gibt nichts zu entfernen. */
export default function AppTemplate({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="animate-page-in"
      onAnimationEnd={(e) => {
        if (e.animationName === "page-in" && e.target === e.currentTarget) {
          e.currentTarget.classList.remove("animate-page-in");
        }
      }}
    >
      {children}
    </div>
  );
}
