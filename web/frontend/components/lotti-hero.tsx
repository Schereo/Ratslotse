"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { SeasonalFamily } from "@/components/seasonal-mascot";

/* Das Tor vor der 3D-Szene (Design „Lotti Hero Familie", Schutzschalter 11 + 13).
 *
 * Die Szene selbst zieht three.js nach — rund 600 KB. Diese Datei entscheidet,
 * ob das überhaupt passiert, und lädt sie erst danach nach. Der `dynamic`-Import
 * mit `ssr: false` sorgt dafür, dass three in einem eigenen Bündel landet: Die
 * Startseite kostet unverändert das, was sie vorher kostete, und lädt die Szene
 * erst, wenn dieses Bauteil im Browser wirklich montiert wird.
 *
 * Ohne Szene bleibt die gezeichnete Familie stehen — dieselben Figuren, nur
 * still. Das ist kein Platzhalter, sondern genau das, was hier vorher stand:
 * Wer schmal, sparsam oder mit reduzierter Bewegung unterwegs ist, verliert
 * nichts gegenüber vorher.
 */

const LottiSzene = dynamic(() => import("@/components/lotti-szene"), {
  ssr: false,
  // Bis three geladen ist, steht die gezeichnete Familie da. Kein Ladekringel:
  // Der wäre an dieser Stelle auffälliger als das, was danach kommt.
  loading: () => <StilleFamilie />,
});

function StilleFamilie() {
  return (
    <div className="flex h-full items-center justify-center">
      <SeasonalFamily className="h-20 sm:h-24" />
    </div>
  );
}

export function LottiHero({ className }: { className?: string }) {
  // 13 · Auf schmalen Fenstern wird three.js gar nicht erst geladen — dort zählt
  //      jede Sekunde, und vier Figuren wären ohnehin zu klein zu erkennen.
  // 11 · Wer reduzierte Bewegung eingestellt hat, bekommt sie ebenfalls nicht:
  //      eine ruhige Zeichnung ist billiger als eine Szene, die stillsteht.
  const [zeigen, setZeigen] = useState(false);

  useEffect(() => {
    const breit = window.matchMedia("(min-width: 1024px)");
    const ruhe = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pruefen = () => setZeigen(breit.matches && !ruhe.matches);
    pruefen();
    breit.addEventListener("change", pruefen);
    ruhe.addEventListener("change", pruefen);
    return () => {
      breit.removeEventListener("change", pruefen);
      ruhe.removeEventListener("change", pruefen);
    };
  }, []);

  return (
    <div className={className}>
      {zeigen ? <LottiSzene className="h-full w-full" /> : <StilleFamilie />}
    </div>
  );
}
