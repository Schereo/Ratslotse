"use client";

import { useCallback, useEffect, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Der Erklär-Modus: Jeder erklärbare Baustein bekommt ein „?"-Abzeichen.
 *
 * **Warum Abzeichen und kein Zeiger-Modus.** Ein Modus, in dem man „auf etwas
 * klickt", braucht Hover, um zu zeigen, was klickbar ist — und das Handy hat
 * keins. Dazu kommt Tims Regel „Zeigerhand nur mit Ziel": Eine Zeigerhand über
 * der halben Seite verspricht etwas, das dort nicht ist. Abzeichen sind
 * tippbar, mit Tabulator erreichbar und sagen von selbst, **was** erklärbar
 * ist, statt es raten zu lassen.
 *
 * **Was hier NICHT passiert.** Kein Fallback auf „die nächste Karte", wenn ein
 * Bereich keinen Anker hat. Was nicht ausdrücklich erklärbar ist, bekommt kein
 * Abzeichen — ein geratener Ausschnitt wäre schlechter als keiner, weil er
 * aussieht, als wüsste Lotti, worauf man gezeigt hat.
 */

type Marke = { key: string; x: number; y: number; el: HTMLElement; titel: string };

function gleich(a: Marke[], b: Marke[]): boolean {
  return a.length === b.length
    && a.every((m, i) => m.key === b[i].key && m.x === b[i].x && m.y === b[i].y);
}

export function ErklaerModus({ aktiv, onWaehlen, onBeenden }: {
  aktiv: boolean;
  onWaehlen: (el: HTMLElement) => void;
  onBeenden: () => void;
}) {
  const [marken, setMarken] = useState<Marke[]>([]);

  const messen = useCallback(() => {
    const aus: Marke[] = [];
    for (const el of document.querySelectorAll<HTMLElement>("[data-erklaer]")) {
      const r = el.getBoundingClientRect();
      // Nur, was wirklich zu sehen ist: Ein Abzeichen auf einem zugeklappten
      // oder weggescrollten Baustein zeigt auf nichts.
      if (r.width < 40 || r.height < 24) continue;
      if (r.bottom < 0 || r.top > window.innerHeight) continue;
      aus.push({
        key: el.getAttribute("data-erklaer") ?? "",
        titel: el.getAttribute("data-erklaer-titel") ?? "",
        // Oben rechts am Element, leicht eingerückt.
        x: Math.min(r.right - 18, window.innerWidth - 22),
        y: Math.max(r.top + 18, 22),
        el,
      });
    }
    // Nur setzen, wenn sich wirklich etwas geändert hat: Der Beobachter unten
    // feuert auch für die Abzeichen selbst, und ein neues Array bei jedem Lauf
    // wäre eine Endlosschleife aus Messen und Zeichnen.
    setMarken((alt) => (gleich(alt, aus) ? alt : aus));
  }, []);

  useEffect(() => {
    if (!aktiv) {
      setMarken([]);
      return;
    }
    messen();
    // Neu messen bei Scroll und Größenwechsel — im nächsten Frame, sonst
    // rechnet man bei jedem Pixel und die Seite ruckelt.
    let frame = 0;
    const planen = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(messen);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onBeenden(); };
    // Und bei jeder DOM-Änderung. **Das ist kein Feinschliff:** Die
    // Haushalts-Seiten holen ihre Daten nach, die Bausteine erscheinen also
    // SPÄTER als der Modus. Ohne diesen Beobachter maß der erste Lauf eine
    // halb leere Seite und zeigte kein einziges Abzeichen — gemessen im
    // Browsertest am 21.09.2026, und zwar genau so, wie es jemandem passiert,
    // der den Modus gleich nach dem Seitenwechsel startet.
    const beobachter = new MutationObserver(planen);
    beobachter.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("scroll", planen, { passive: true });
    window.addEventListener("resize", planen);
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(frame);
      beobachter.disconnect();
      window.removeEventListener("scroll", planen);
      window.removeEventListener("resize", planen);
      window.removeEventListener("keydown", onKey);
    };
  }, [aktiv, messen, onBeenden]);

  if (!aktiv) return null;

  return (
    <>
      {marken.map((m) => (
        <button
          key={m.key}
          type="button"
          data-erklaer-marke
          onClick={() => onWaehlen(m.el)}
          aria-label={m.titel ? `Erklären: ${m.titel}` : "Diesen Baustein erklären"}
          style={{ left: m.x, top: m.y }}
          className={cn(
            "fixed z-40 flex h-7 w-7 items-center justify-center rounded-full",
            "border border-primary/30 bg-card text-[13px] font-bold text-primary shadow-lifted",
            "animate-in fade-in-0 zoom-in-95 duration-fluss",
            "hover:bg-primary hover:text-primary-foreground",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        >
          ?
        </button>
      ))}
      {marken.length === 0 && (
        <p
          role="status"
          className="fixed inset-x-4 bottom-28 z-40 mx-auto max-w-sm rounded-xl border border-border bg-card px-3 py-2 text-center text-hinweis text-muted-foreground shadow-lifted"
        >
          Auf dieser Seite kann ich gerade nichts einzeln erklären — frag mich
          einfach im Fenster.
        </p>
      )}
    </>
  );
}
