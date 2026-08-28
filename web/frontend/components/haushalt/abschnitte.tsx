"use client";

// Abschnitts-Navigation für zusammengelegte Haushalts-Seiten.
//
// WARUM ES DAS GIBT (Tim, 21.08.2026): „Jetzt haben wir ja so viele
// Unterseiten. […] Man weiß gar nicht, wo man anfangen soll. […] Man wird
// erschlagen vor Inhalten."
//
// Der Bereich war auf neunzehn Schritte gewachsen, und mehrere davon waren
// entlang unserer Einlese-Geschichte geschnitten statt entlang der Frage, die
// jemand hat: „Was wird gebaut?" stand auf zwei Seiten (geplant / gebaut),
// „Ist das die ganze Stadt?" auf vieren. Wer zusammenlegt, bekommt aber lange
// Seiten — und eine lange Seite ohne Übersicht ist nur eine andere Art, jemanden
// zu erschlagen.
//
// Deshalb dieser Baustein: Er sagt am Kopf, aus welchen Abschnitten die Seite
// besteht, und führt hin. Drei Entscheidungen stecken darin:
//
//  * **Klebt oben, aber nur der Streifen.** Wer im dritten Abschnitt liest,
//    soll ohne Scrollen zurück in den ersten kommen. Der Streifen ist deshalb
//    `sticky`; die Seite darüber scrollt weg. Unterhalb von `desk` klebt
//    außerdem der App-Header (layout.tsx, 61 px + Sicherheitszone) — der
//    Streifen dockt dort unter ihm an, denn bei `top-0` schöbe er sich beim
//    Scrollen vollständig hinter den Header (z-40 schlägt z-10) und wäre
//    mobil unsichtbar. Dieselben 61 px stehen in zahlen-tabelle.tsx
//    (KLEBE_AB); wer Header oder Streifen umbaut, zieht beide Stellen nach.
//  * **Der laufende Abschnitt ist markiert**, gemessen per
//    `IntersectionObserver` und nicht am Scroll-Wert: Letzteres rechnet bei
//    jedem Pixel und liegt bei Abschnitten sehr verschiedener Höhe daneben.
//  * **Kein Zustand in der URL.** Ein `#anker` in der Adresse wäre ein zweiter
//    Wahrheitsträger neben der Scrollposition, und beide driften (dieselbe
//    Falle wie beim Fragen/Suche-Split, wo ein `router.replace` den Alt-Link
//    überschrieb). Die Anker existieren trotzdem als `id` — ein Link von außen
//    springt also, er bleibt nur nicht stehen.

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export type Abschnitt = {
  /** Die `id` des `<section>`-Elements, auf das gesprungen wird. */
  id: string;
  /** Was im Streifen steht — kurz, es müssen mehrere nebeneinander passen. */
  titel: string;
};

/** Scroll-Versatz für die Ziel-`<section>`s des Streifens: der Klebe-Stapel
 *  des jeweiligen Geräts plus Luft. Unterhalb `desk` kleben App-Header
 *  (61 px + Sicherheitszone) und Streifen (49 px) übereinander, ab `desk`
 *  nur der Streifen. Gehört an jede Section, deren `id` in `marken` steht —
 *  sonst springt ein `#anker`-Link von außen unter den Stapel. */
export const ANKER_KLASSE =
  "scroll-mt-[calc(env(safe-area-inset-top)+129px)] desk:scroll-mt-20";

/** Unterkante des klebenden Streifens, in px vom oberen Fensterrand:
 *  `getComputedStyle().top` löst die calc()-Formel (samt Sicherheitszone und
 *  `desk:`-Weiche) auf, dazu die eigene Höhe. Gemessen statt als Konstante,
 *  damit Klick-Versatz und Beobachter auf jedem Gerät zur echten Kante
 *  passen. */
function klebeUnterkante(streifen: HTMLElement | null): number {
  if (!streifen) return 49;
  const oben = parseFloat(getComputedStyle(streifen).top);
  return (Number.isFinite(oben) ? oben : 0) + streifen.offsetHeight;
}

export function Abschnitte({ marken, className }: {
  marken: Abschnitt[];
  className?: string;
}) {
  const [aktiv, setAktiv] = useState<string | null>(marken[0]?.id ?? null);
  const streifen = useRef<HTMLElement>(null);

  useEffect(() => {
    const ziele = marken
      .map((m) => document.getElementById(m.id))
      .filter((el): el is HTMLElement => !!el);
    if (!ziele.length) return;

    // `rootMargin` oben negativ: Ein Abschnitt gilt als der laufende, sobald
    // seine Oberkante unter den klebenden Streifen gewandert ist — nicht schon,
    // wenn er unten ins Bild ragt. Die Kante wird gemessen, weil `rootMargin`
    // kein env()/calc() versteht und der Streifen je Gerät verschieden hoch
    // klebt; nach Größenwechsel oder Rotation wird neu gemessen.
    let beobachter: IntersectionObserver | null = null;
    const beobachten = () => {
      beobachter?.disconnect();
      beobachter = new IntersectionObserver(
        (eintraege) => {
          const sichtbar = eintraege
            .filter((e) => e.isIntersecting)
            .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
          if (sichtbar.length) setAktiv(sichtbar[0].target.id);
        },
        {
          rootMargin: `-${Math.round(klebeUnterkante(streifen.current) + 23)}px 0px -55% 0px`,
          threshold: 0,
        },
      );
      ziele.forEach((z) => beobachter?.observe(z));
    };
    beobachten();

    let ruhe: number | undefined;
    const beiGroessenwechsel = () => {
      window.clearTimeout(ruhe);
      ruhe = window.setTimeout(beobachten, 150);
    };
    window.addEventListener("resize", beiGroessenwechsel);
    return () => {
      window.removeEventListener("resize", beiGroessenwechsel);
      window.clearTimeout(ruhe);
      beobachter?.disconnect();
    };
  }, [marken]);

  if (marken.length < 2) return null;

  return (
    <nav
      ref={streifen}
      aria-label="Abschnitte dieser Seite"
      className={cn(
        "sticky top-[calc(env(safe-area-inset-top)+61px)] z-10 -mx-4 border-b border-border/70 bg-background/85 px-4 py-2 backdrop-blur desk:top-0",
        className,
      )}
    >
      {/* Waagerecht scrollbar statt umbrechend: Vier Abschnittsnamen brechen
          auf 375 px sonst in zwei Zeilen, und ein zweizeiliger Klebestreifen
          nimmt ein Sechstel des Bildschirms. */}
      <ul className="scrollbar-none flex gap-1.5 overflow-x-auto">
        {marken.map((m) => (
          <li key={m.id} className="flex-none">
            <a
              href={`#${m.id}`}
              aria-current={aktiv === m.id ? "true" : undefined}
              onClick={(e) => {
                // Eigener Sprung statt Browser-Voreinstellung: Der klebende
                // Streifen deckt sonst die Überschrift des Ziels zu.
                const ziel = document.getElementById(m.id);
                if (!ziel) return;
                e.preventDefault();
                const oben =
                  ziel.getBoundingClientRect().top +
                  window.scrollY -
                  (klebeUnterkante(streifen.current) + 19);
                window.scrollTo({ top: oben, behavior: "smooth" });
                setAktiv(m.id);
              }}
              className={cn(
                "inline-flex min-h-[32px] items-center rounded-full border px-3 text-[12.5px] font-semibold transition-colors",
                aktiv === m.id
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {m.titel}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
