"use client";

// Der Schlangenpfad — eine geschlungene Route, die Stationen einer Liste
// verbindet und sich beim Scrollen nachzeichnet.
//
// ENTSTANDEN FÜR DIE HAUSHALTSDEBATTE (abschnitt-streit.tsx, Tims Wunsch vom
// 21.08.2026: „geschlungen von rechts nach links, und die Personen tauchen
// erst beim Scrollen mit Animation auf") und auf Tims Wunsch vom 22.08. als
// eigener Baustein herausgelöst.
//
// DER VERTRAG, in drei Markierungen:
//
//  * **`data-punkt`** an einem Element je Station: sein Mittelpunkt ist ein
//    Anker der Route. Die Kurve wird an den ECHTEN Positionen gemessen, nicht
//    an einer angenommenen Geometrie — ändert sich das Layout (Aufklappen,
//    Fensterbreite), zeichnet der ResizeObserver neu. Stehen alle Punkte
//    übereinander, ergibt dieselbe Rechnung von allein eine gerade Linie.
//  * **`data-auftritt`** an Elementen, die beim ersten Sichtkontakt
//    erscheinen sollen: Der Baustein setzt dort `data-reveal="aus"` und beim
//    ersten Schnitt mit dem Sichtfenster einmalig `data-reveal="an"`. Die
//    Übergänge selbst gehören dem Aufrufer (Tailwind-Klassen wie
//    `motion-safe:data-[reveal=aus]:opacity-0`) — der Baustein sagt WANN,
//    die Station sagt WIE sie auftritt.
//  * **Die Inhalte müssen OPAK sein**, wo die Route nicht durchscheinen
//    soll. Das ist die Statik dieses Bausteins: Die Kurve läuft frei und
//    mit vollem Schwung HINTER den Stationen durch (sie liegt im selben
//    Stapel VOR ihnen im DOM). Ein erster Entwurf versuchte, transparenten
//    Text mit dem Pfad zu umfahren — kantig, halbbreit, und bei anderen
//    Fensterbreiten lief er doch durch den Text.
//
// WAS DER BAUSTEIN ZEICHNET: eine blasse Vorzeichnung der ganzen Route
// (`text-border`, mit Pfeilspitze am Ende — der Weg führt irgendwohin) und
// darüber einen kräftigeren Stift (`text-primary`), der genau so weit
// gezeichnet ist, wie die Liste gescrollt wurde. Der Stift folgt mit einer
// halben Sekunde weichem Nachlauf, statt hart an der Scroll-Position zu
// kleben, und schreibt per direktem DOM (rAF-gedrosselt): Ein setState je
// Scroll-Ereignis renderte alle Stationen neu.
//
// `prefers-reduced-motion` schaltet alles Bewegte ab: Route fertig
// gezeichnet, Stationen sichtbar. Ohne JavaScript bleibt schlicht alles
// stehen und sichtbar — kein Observer läuft, kein `data-reveal` wird gesetzt.

import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function Schlangenpfad({ children, className }: {
  children: React.ReactNode;
  className?: string;
}) {
  const inhalt = useRef<HTMLDivElement>(null);
  const stift = useRef<SVGPathElement>(null);
  const [pfad, setPfad] = useState<{ d: string; w: number; h: number } | null>(null);
  // Eine id je Instanz: Zwei Schlangenpfade auf einer Seite dürfen sich die
  // Pfeilspitzen-Definition nicht teilen.
  const pfeilId = useId();

  // Die Kurve aus den echten Punkt-Positionen.
  useEffect(() => {
    const el = inhalt.current;
    if (!el) return;
    const messen = () => {
      const basis = el.getBoundingClientRect();
      const punkte = [...el.querySelectorAll<HTMLElement>("[data-punkt]")].map((p) => {
        const r = p.getBoundingClientRect();
        return { x: r.left - basis.left + r.width / 2, y: r.top - basis.top + r.height / 2 };
      });
      if (punkte.length < 2) { setPfad(null); return; }
      // EIN weicher Bogen je Übergang, kein Eckwerk: Die Steuerpunkte liegen
      // senkrecht unter bzw. über den Ankern — die Kurve verlässt einen Punkt
      // nach unten, schwingt über die Breite und kommt von oben beim
      // nächsten an.
      let d = `M ${punkte[0].x.toFixed(1)} ${punkte[0].y.toFixed(1)}`;
      for (let i = 1; i < punkte.length; i++) {
        const a = punkte[i - 1], b = punkte[i];
        const zug = Math.max(36, (b.y - a.y) * 0.55);
        d += ` C ${a.x.toFixed(1)} ${(a.y + zug).toFixed(1)}, ${b.x.toFixed(1)} ${(b.y - zug).toFixed(1)}, ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
      }
      setPfad({ d, w: basis.width, h: basis.height });
    };
    messen();
    const ro = new ResizeObserver(messen);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Der wandernde Stift — direktes DOM, s. Kopfkommentar.
  useEffect(() => {
    const el = stift.current;
    if (!el || !pfad) return;
    const laenge = el.getTotalLength();
    // Erst OHNE Übergang auf den Startzustand — sonst „malt" sich die ganze
    // Route beim ersten Rendern einmal quer durchs Bild.
    el.style.transition = "none";
    el.style.strokeDasharray = `${laenge}`;
    el.style.strokeDashoffset = `${laenge}`;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.style.strokeDashoffset = "0";
      return;
    }
    void el.getBoundingClientRect();
    el.style.transition = "stroke-dashoffset 0.55s cubic-bezier(0.22, 0.61, 0.36, 1)";
    let angemeldet = 0;
    const zeichnen = () => {
      angemeldet = 0;
      const basis = inhalt.current;
      if (!basis) return;
      const r = basis.getBoundingClientRect();
      // Gezeichnet ist, was über der Lese-Linie (85 % der Fensterhöhe) liegt.
      const anteil = Math.min(1, Math.max(0, (window.innerHeight * 0.85 - r.top) / r.height));
      el.style.strokeDashoffset = `${laenge * (1 - anteil)}`;
    };
    const aufScroll = () => {
      if (!angemeldet) angemeldet = requestAnimationFrame(zeichnen);
    };
    zeichnen();
    window.addEventListener("scroll", aufScroll, { passive: true });
    window.addEventListener("resize", aufScroll);
    return () => {
      if (angemeldet) cancelAnimationFrame(angemeldet);
      window.removeEventListener("scroll", aufScroll);
      window.removeEventListener("resize", aufScroll);
    };
  }, [pfad]);

  // Der Auftritt der Stationen.
  useEffect(() => {
    const el = inhalt.current;
    if (!el) return;
    const stationen = [...el.querySelectorAll<HTMLElement>("[data-auftritt]")];
    if (!stationen.length) return;
    const io = new IntersectionObserver((eintraege) => {
      for (const e of eintraege) {
        if (!e.isIntersecting) continue;
        (e.target as HTMLElement).dataset.reveal = "an";
        io.unobserve(e.target);
      }
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.1 });
    for (const s of stationen) {
      s.dataset.reveal = "aus";
      io.observe(s);
    }
    return () => io.disconnect();
  }, []);

  return (
    <div ref={inhalt} className={cn("relative", className)}>
      {pfad && (
        <svg
          aria-hidden
          className="pointer-events-none absolute inset-0 text-border"
          width={pfad.w} height={pfad.h}
          viewBox={`0 0 ${pfad.w} ${pfad.h}`}
          fill="none"
        >
          <defs>
            {/* Der Chevron zeigt im Marker-Raum nach +x; `orient="auto"`
                dreht ihn in die Laufrichtung — am Ende also auf die letzte
                Station zu. */}
            <marker id={pfeilId} viewBox="0 0 8 8" refX="6" refY="4"
              markerWidth="8" markerHeight="8" orient="auto">
              <path d="M 2 1 L 6 4 L 2 7" stroke="currentColor" strokeWidth="1.5"
                fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </marker>
          </defs>
          <path d={pfad.d} stroke="currentColor" strokeWidth="1.5"
            markerEnd={`url(#${pfeilId})`} />
          {/* Der Stift etwas kräftiger als die blasse Vorzeichnung — er ist
              die Route, die man schon gegangen ist. */}
          <path ref={stift} d={pfad.d} className="text-primary/45" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" />
        </svg>
      )}
      {children}
    </div>
  );
}
