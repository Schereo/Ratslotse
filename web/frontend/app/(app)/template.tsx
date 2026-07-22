/** RL-1104: sanfter Seiten-Einstieg bei jeder Navigation im eingeloggten
 *  Bereich. Ein template.tsx re-mountet pro Navigation — die CSS-Klasse
 *  (nur transform/opacity) läuft daher genau einmal je Seitenwechsel und
 *  ruht komplett bei prefers-reduced-motion. */
export default function AppTemplate({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-up">{children}</div>;
}
