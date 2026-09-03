"use client";

import { useLayoutEffect, useRef } from "react";

type Stand = { x: number; y: number; breite: number; hoehe: number; rahmen: string };

/** Wo die Markierung zuletzt stand — je Leiste eine Zeile, außerhalb von React.
 *
 *  Der Grund ist der Knackpunkt der ganzen Bewegung: Bei jeder Navigation baut
 *  Next die Leiste NEU auf (die Punkte hängen an `?tab=`, und
 *  `useSearchParams` schickt den Baum durch seine Suspense-Grenze). Das
 *  Marker-Element ist danach ein anderer Knoten, der nichts von seinem
 *  Vorgänger weiß — er erschiene an der neuen Stelle einfach, und genau das
 *  ist das Problem, das die gleitende Markierung lösen soll. Der Merkstand
 *  überlebt den Wiederaufbau: Der neue Knoten setzt sich erst stumm dorthin,
 *  wo der alte stand, und fährt von dort los.
 *
 *  Er hängt am Rahmenmaß der Leiste. Ist die Leiste inzwischen anders groß
 *  (Fenster gedreht, Seitenleiste gegen Tab-Leiste getauscht), sagt die
 *  gemerkte Stelle nichts mehr über dieselbe Fläche — dann wird ohne Weg
 *  gesetzt, statt quer über eine neue Geometrie zu fahren.
 *
 *  Wer keinen Namen übergibt, bekommt keinen Merkstand — und braucht ihn auch
 *  nicht: Ein Segment-Umschalter mitten auf einer Seite überlebt seine eigenen
 *  Wechsel, das Element bleibt dasselbe und die Transition läuft von allein.
 *  Ein Name je Instanz wäre dort sogar schädlich, weil die Tabelle mit jedem
 *  Seitenaufruf um einen toten Eintrag wüchse. */
const MERKSTAND = new Map<string, Stand>();

/** Die gleitende Aktiv-Markierung — EINE Fläche, die von Ziel zu Ziel fährt.
 *
 *  Vorher hatte jeder Navigationspunkt seine eigene Pille: Beim Wechsel ging
 *  die eine aus und die andere an. Zwei Zustände, kein Weg — man sah, wo man
 *  IST, aber nie, wo man HERKAM. Jetzt liegt eine einzige Fläche hinter den
 *  Zielen und fährt zum neuen; das Auge nimmt die Strecke mit und weiß danach,
 *  wie die Punkte zueinander stehen.
 *
 *  Der Hook misst das Ziel mit `data-aktiv="true"` und schreibt Größe und
 *  Versatz direkt auf das Marker-Element — an React vorbei, weil ein
 *  State-Update je Messung bei jedem Resize einen Render auslöste, ohne dass
 *  sich am Baum etwas ändert.
 *
 *  Drei Dinge, die hier schon schiefgingen und deshalb so stehen:
 *  • **Der allererste Aufschlag darf nicht gleiten.** Sonst flöge die
 *    Markierung beim Laden aus der Ecke herein und behauptete einen Weg, den
 *    niemand gegangen ist. Gefahren wird nur, wenn es einen Vorgängerstand
 *    gibt — im Element selbst oder im Merkstand.
 *  • **Ohne JS bleibt die Pille am Punkt.** Die Fläche des aktiven Punktes
 *    wird erst durchsichtig, wenn der Container `data-marker="an"` trägt (CSS
 *    in globals.css) — bis zur Hydration und bei abgeschaltetem JS markiert
 *    also weiterhin die alte Pille, statt gar nichts.
 *  • **Nicht messen, solange nichts da ist.** Vor dem Layout (und in einer
 *    ausgeblendeten Leiste — die Tab-Leiste ist am Desktop `display:none`)
 *    sind alle Rechtecke 0 breit; eine solche Messung zöge den Marker auf
 *    einen Punkt zusammen. */
export function useGleitMarker(schluessel: string, merkname?: string) {
  const gruppeRef = useRef<HTMLDivElement | null>(null);
  const markerRef = useRef<HTMLSpanElement | null>(null);

  useLayoutEffect(() => {
    const gruppe = gruppeRef.current;
    const marker = markerRef.current;
    if (!gruppe || !marker) return;

    const setzen = (st: Stand) => {
      marker.style.width = `${st.breite}px`;
      marker.style.height = `${st.hoehe}px`;
      marker.style.transform = `translate(${st.x}px, ${st.y}px)`;
    };

    /** Misst, wo die Fläche stehen müsste — `null`, wenn es (noch) nichts zu
     *  markieren gibt: kein aktives Ziel, oder eine Leiste, die gar nicht
     *  angezeigt wird (die Tab-Leiste ist am Desktop `display:none`, dort sind
     *  alle Rechtecke 0 breit und eine Messung zöge den Marker auf einen
     *  Punkt zusammen). */
    const messen = (): Stand | null => {
      const ziel = gruppe.querySelector<HTMLElement>('[data-aktiv="true"]');
      if (!ziel) return null;
      const g = gruppe.getBoundingClientRect();
      const z = ziel.getBoundingClientRect();
      if (z.width === 0 || z.height === 0) return null;
      return {
        x: z.left - g.left,
        y: z.top - g.top,
        breite: z.width,
        hoehe: z.height,
        rahmen: `${Math.round(g.width)}x${Math.round(g.height)}`,
      };
    };

    const anwenden = (bewegen: boolean) => {
      const st = messen();
      if (!st) {
        marker.dataset.sichtbar = "false";
        return;
      }
      marker.dataset.gleitet = bewegen ? "true" : "false";
      setzen(st);
      marker.dataset.sichtbar = "true";
      gruppe.dataset.marker = "an";
      if (merkname) MERKSTAND.set(merkname, st);
    };

    // Zwei Wege führen zu einer Bewegung, und sie schließen einander aus:
    //  • Der Knoten steht noch (ein Segment-Umschalter, den man anklickt) —
    //    dann liegt der Ausgangspunkt schon im Element, es genügt, die
    //    Transition einzuschalten.
    //  • Der Knoten ist neu (die Navigation hat die Leiste neu gebaut) — dann
    //    muss der Ausgangspunkt erst aus dem Merkstand gesetzt werden.
    // Bleibt der dritte Fall: weder noch, also der allererste Auftritt. Der
    // springt, denn es gibt nichts, wovon er losfahren könnte.
    const schonDa = marker.dataset.sichtbar === "true";
    const gemerkt = merkname ? MERKSTAND.get(merkname) : undefined;
    const jetzt = messen();
    if (!schonDa && gemerkt && jetzt && gemerkt.rahmen === jetzt.rahmen) {
      // Erst stumm dorthin, wo die Markierung vor dem Wiederaufbau stand …
      marker.dataset.gleitet = "false";
      setzen(gemerkt);
      marker.dataset.sichtbar = "true";
      gruppe.dataset.marker = "an";
      // … dann ein Reflow erzwingen, damit der Browser diesen Zwischenstand
      // wirklich als Ausgangspunkt nimmt. Ohne ihn fasst er beide Zuweisungen
      // zu einer zusammen und es gibt nichts zu animieren. (`requestAnimation-
      // Frame` täte es auch, überlebt aber den doppelten Effekt-Lauf des
      // Entwicklungsmodus nicht — dessen Aufräumroutine sagt es wieder ab.)
      void marker.offsetWidth;
      anwenden(true);
    } else {
      anwenden(schonDa);
    }

    // Breite der Leiste, Schriftwechsel, die Admin-Zeile, die nach dem Laden
    // der Rolle dazukommt: Der Marker hängt an gemessenen Pixeln und muss
    // jeder Größenänderung folgen — ohne Weg, denn hier bewegt sich nicht das
    // Ziel, sondern der Rahmen darum.
    const ro = new ResizeObserver(() => anwenden(false));
    ro.observe(gruppe);
    return () => ro.disconnect();
  }, [merkname, schluessel]);

  return { gruppeRef, markerRef };
}

/** Die Fläche selbst.
 *
 *  `radius` passt sie an die Form ihres Ziels an (eckige Pille in der
 *  Seitenleiste, runde in der Tab-Leiste), `farbe` an dessen Fläche. Beides
 *  läuft über CSS-Variablen und nicht über Klassen: Eine Tailwind-Klasse wie
 *  `bg-card` und die Grundregel `.gleit-marker` haben dieselbe Spezifität, es
 *  entschiede also die Reihenfolge im gebauten Stylesheet — und die steht
 *  nirgends geschrieben. `className` bleibt für alles, was die Grundregel gar
 *  nicht anfasst (Schatten). */
export function GleitMarker({ markerRef, radius, farbe, kurve, className }: {
  markerRef: React.RefObject<HTMLSpanElement>;
  radius: string;
  farbe?: string;
  /** Abweichende Kurve — z. B. `var(--ease-back-out)`, damit die Fläche am
   *  Ziel kurz einrastet statt nur anzukommen. Nur für kurze Wege zwischen
   *  kleinen Zielen; über etwa 40 px wirkt Überschwingen wie Wackelpudding. */
  kurve?: string;
  className?: string;
}) {
  return (
    <span
      ref={markerRef}
      aria-hidden
      className={["gleit-marker", className].filter(Boolean).join(" ")}
      style={{
        "--gleit-radius": radius,
        ...(farbe ? { "--gleit-farbe": farbe } : {}),
        ...(kurve ? { "--gleit-kurve": kurve } : {}),
      } as React.CSSProperties}
    />
  );
}
