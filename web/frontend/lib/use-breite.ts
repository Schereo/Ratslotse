"use client";

// Die Breite eines Diagramm-Containers messen — einmal statt viermal.
//
// Vier Diagramme des Haushalts-Bereichs trugen dieselbe Messung wörtlich im
// Bauch (`gebaut-balken`, `schulden-kurve`, `ist-kurve` byte-gleich,
// `fiscal-equalization-daempfer` bis auf die Mindestbreite). Sie erklärten sich
// dabei gegenseitig in Kommentaren — „dieselbe Messfalle wie in
// schulden-kurve.tsx", „siehe Zeitreihe" —, was der beste Beleg dafür ist,
// dass es eine Sache war und keine vier.
//
// DIE ZWEI FALLEN, DIE HIER EINGEBAUT SIND
//
// 1. `getBoundingClientRect().width`, NICHT `clientWidth`. Letzteres rundet
//    auf ganze Pixel; bei 486,4 px echter Breite käme 486 heraus, und die
//    viewBox stünde damit auf einem Skalierungsfaktor von 1,0008. Das SVG
//    staucht dann die Achsenschrift mit — sichtbar, und zwar auf genau den
//    Fensterbreiten, auf denen niemand testet.
// 2. Der Epsilon-Vergleich (`> 0.5`). Ohne ihn setzt jeder
//    ResizeObserver-Tick den State neu, auch wenn sich nichts geändert hat,
//    und das Diagramm rendert bei jedem Scroll-Ruck durch.
//
// NICHT hierher gehören zwei weitere Messungen des Bereichs:
// `flussbild.tsx` misst mit `clientWidth` und ohne Epsilon — das ist ein
// anderes Verhalten, kein anderer Aufruf, und es zu ändern wäre eine
// Korrektur und kein Umbau. `zeitreihe.tsx` misst ZWEI Elemente mit einem
// Beobachter, weil es daraus eine Layout-Entscheidung ableitet (ein- oder
// zweispaltig) und nicht nur eine viewBox. Beide bleiben, wo sie sind.

import { useEffect, useRef, useState } from "react";

/** Die gemessene Breite des zurückgegebenen Containers.
 *
 *  `standard` gilt bis zur ersten Messung — also im Server-Rendering und im
 *  ersten Frame. `mindest` ist die Untergrenze, unter der ein Diagramm nicht
 *  mehr lesbar wäre; darunter scrollt der Container lieber waagerecht, als
 *  die Beschriftung übereinanderzuschieben. */
export function useBreite(standard = 640, mindest = 280) {
  const box = useRef<HTMLDivElement>(null);
  const [breite, setBreite] = useState(standard);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const pruefe = () => {
      const w = Math.max(el.getBoundingClientRect().width, mindest);
      setBreite((alt) => (Math.abs(w - alt) > 0.5 ? w : alt));
    };
    pruefe();
    const ro = new ResizeObserver(pruefe);
    ro.observe(el);
    return () => ro.disconnect();
  }, [mindest]);
  return { box, breite };
}
