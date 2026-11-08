"use client";

import { useEffect, useState } from "react";

import { auswahlText } from "@/lib/markieren";
import { tastaturHoehe } from "@/lib/tastatur";

// Die zwei Hooks, die Knopf UND Fenster brauchen. Sie standen bis 11/2026 in
// panel.tsx — und weil index.tsx sie von dort holte, hing das ganze Fenster
// (samt Antwort-Bausteinen, Glossar und Diagrammen, gut 50 KB gzip) an jeder
// Seite der App, auch wo es nie jemand öffnet. Jetzt lädt index.tsx das
// Fenster erst bei Bedarf nach (next/dynamic).

/**
 * Wie hoch die Bildschirmtastatur gerade steht.
 *
 * Nötig, weil das Fenster `position: fixed` ist: Auf iOS schrumpft der
 * Layout-Viewport nicht, wenn die Tastatur aufgeht — die Eingabezeile läge
 * dahinter, und der Browser kann ein fixiertes Fenster nicht hereinscrollen.
 * Die Rechnung selbst steht in `lib/tastatur.ts` und ist dort geprüft.
 */
export function useTastatur(): number {
  const [hoehe, setHoehe] = useState(0);
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const messen = () => setHoehe(tastaturHoehe(vv, window.innerHeight));
    messen();
    vv.addEventListener("resize", messen);
    vv.addEventListener("scroll", messen);
    return () => {
      vv.removeEventListener("resize", messen);
      vv.removeEventListener("scroll", messen);
    };
  }, []);
  return hoehe;
}

/** Der markierte Text der Seite — als Hook, damit Knopf und Fenster dieselbe
 *  Quelle haben. Läuft über `selectionchange` mit kurzer Ruhepause: Während
 *  man mit der Maus zieht, feuert das Ereignis bei jedem Pixel. */
export function useMarkierung(): string {
  const [text, setText] = useState("");
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const onChange = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const fenster = document.querySelector("[data-lotti-fenster]");
        setText(auswahlText(document.getSelection(), fenster, document.activeElement));
      }, 250);
    };
    document.addEventListener("selectionchange", onChange);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("selectionchange", onChange);
    };
  }, []);
  return text;
}
