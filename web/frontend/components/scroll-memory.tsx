"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";

/** Scroll-Gedächtnis je Seite (Tims iOS-Befund 12.08.).
 *
 *  Im App-Router wird beim Navigieren die alte Seite abgebaut — Zustand UND
 *  Scroll-Position sind weg. Auf dem Handy fühlt sich das falsch an: Wer aus
 *  einer weit gescrollten Liste kurz woanders hinschaut, erwartet beim
 *  Zurückkommen dieselbe Stelle, nicht den Listenanfang.
 *
 *  Diese Komponente merkt sich die Position je Route (Pfad + Query) in der
 *  sessionStorage und stellt sie beim Betreten wieder her. Zwei Feinheiten:
 *
 *  - Der Inhalt kommt asynchron. Direkt nach dem Mount ist die Seite oft noch
 *    kurz — deshalb wird die Wiederherstellung wiederholt versucht, solange
 *    die Seite wächst (bis ~2 s), und abgebrochen, sobald jemand selbst
 *    scrollt: Ein Sprung unter den Fingern wäre schlimmer als der Listenanfang.
 *  - Gespeichert wird laufend (gedrosselt) statt beim Verlassen, weil das
 *    Unmount-Ereignis in der App nicht zuverlässig kommt, wenn das Betriebs-
 *    system die WebView einfriert.
 */
export function ScrollMemory() {
  const pathname = usePathname();
  const sp = useSearchParams();
  const scrollKey = `ratslotse:scroll:${pathname}?${sp.toString()}`;

  useEffect(() => {
    // Der Schlüssel gehört ZU DIESEM Effekt (kein Ref!): React rendert die
    // neue Seite, BEVOR es den alten Effekt abbaut — ein geteilter Ref zeigte
    // beim Aufräumen längst auf die neue Route und schrieb die gemerkte
    // Position unter den falschen Schlüssel (erst gemessen, dann behoben).
    const key = scrollKey;
    let abgebrochen = false;
    // NICHT window.scrollY beim Aufräumen lesen: Der Router setzt die Seite
    // beim Navigieren auf 0, bevor der Effekt abgebaut wird — gespeichert
    // würde dann eine Null und die gemerkte Stelle wäre weg (erst gemessen,
    // dann behoben). Also die zuletzt SELBST gescrollte Position mitführen.
    let letzteY = 0;
    const merken = () => {
      try {
        if (letzteY > 0) sessionStorage.setItem(key, String(Math.round(letzteY)));
        else sessionStorage.removeItem(key);
      } catch { /* privater Modus */ }
    };
    let ziel = 0;
    try { ziel = Number(sessionStorage.getItem(key) || 0); } catch { /* s. o. */ }
    const aufraeumen: (() => void)[] = [];

    // NICHT bei touchstart abbrechen: Der Tipp auf die Tab-Leiste erzeugt auf
    // dem iPhone einen Touch, der noch in der neuen Seite ankommt — das
    // Wiederherstellen brach dadurch ab, bevor es begann (Tims Befund 12.08.:
    // „von Fragen zurück auf Sitzungen ist die Liste ganz oben"). Abgebrochen
    // wird erst, wenn jemand WIRKLICH selbst scrollt.
    const eigenerScroll = () => { abgebrochen = true; };
    if (ziel > 0) {
      window.addEventListener("wheel", eigenerScroll, { passive: true, once: true });
      window.addEventListener("touchmove", eigenerScroll, { passive: true, once: true });
      window.addEventListener("keydown", eigenerScroll, { once: true });
      // Bis die nachgeladene Liste steht, liegt das Ziel außerhalb. Auf dem
      // Gerät dauert der API-Aufruf länger als im Browser — zwei Sekunden
      // waren zu knapp, jetzt acht; ein ResizeObserver stößt den Versuch an,
      // sobald die Seite wächst, statt nur zu pollen.
      const start = Date.now();
      let beobachter: ResizeObserver | undefined;
      const fertig = () => { beobachter?.disconnect(); beobachter = undefined; };
      const versuch = () => {
        if (abgebrochen) return fertig();
        const machbar = document.documentElement.scrollHeight - window.innerHeight;
        if (machbar >= ziel - 4) {
          window.scrollTo(0, ziel);
          letzteY = ziel;
          return fertig();
        }
        if (Date.now() - start > 8000) return fertig();
        requestAnimationFrame(versuch);
      };
      requestAnimationFrame(versuch);
      if (typeof ResizeObserver !== "undefined") {
        beobachter = new ResizeObserver(() => versuch());
        beobachter.observe(document.documentElement);
      }
      aufraeumen.push(fertig);
    }

    let timer: number | undefined;
    const beiScroll = () => {
      letzteY = window.scrollY;
      window.clearTimeout(timer);
      timer = window.setTimeout(merken, 150);
    };
    window.addEventListener("scroll", beiScroll, { passive: true });
    document.addEventListener("visibilitychange", merken);
    return () => {
      merken();
      window.clearTimeout(timer);
      window.removeEventListener("scroll", beiScroll);
      window.removeEventListener("wheel", eigenerScroll);
      window.removeEventListener("touchmove", eigenerScroll);
      window.removeEventListener("keydown", eigenerScroll);
      document.removeEventListener("visibilitychange", merken);
      for (const f of aufraeumen) f();
    };
  }, [scrollKey]);

  return null;
}
