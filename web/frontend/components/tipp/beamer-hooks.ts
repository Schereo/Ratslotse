"use client";

// Kleine, reine Hooks für den Beamer (PR 4) — geteilt zwischen podium.tsx und
// scoreboard.tsx, deshalb hier statt in einer der beiden Dateien.

import { useEffect, useRef, useState } from "react";

/** Zählt eine Zahl weich von ihrem letzten Wert zum neuen hoch (Punkte auf
 *  Podium und Rangliste). Bei `prefers-reduced-motion` springt sie direkt —
 *  dieselbe Abwägung wie beim FLIP-Verzicht: der Endzustand ist die Zahl
 *  selbst, keine Animation ist also auch kein Informationsverlust. */
export function useTween(ziel: number, dauerMs = 700): number {
  const [wert, setWert] = useState(ziel);
  const vorherRef = useRef(ziel);

  useEffect(() => {
    const start = vorherRef.current;
    vorherRef.current = ziel;
    if (start === ziel) return;
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setWert(ziel);
      return;
    }
    let frame = 0;
    const begonnen = performance.now();
    const schritt = (jetzt: number) => {
      const anteil = Math.min(1, (jetzt - begonnen) / dauerMs);
      // easeOutCubic — schnell los, weich in die Zielzahl hinein.
      const geglaettet = 1 - (1 - anteil) ** 3;
      setWert(Math.round(start + (ziel - start) * geglaettet));
      if (anteil < 1) frame = requestAnimationFrame(schritt);
    };
    frame = requestAnimationFrame(schritt);
    return () => cancelAnimationFrame(frame);
  }, [ziel, dauerMs]);

  return wert;
}

/** War `wert` in den letzten `ms` Millisekunden GESTIEGEN? Für den kurzen
 *  Leucht-Rahmen einer Zeile, die gerade einen Platz gutgemacht hat — auf
 *  `-rank` angewendet, denn ein kleinerer Rang ist ein besserer. Feuert nie
 *  beim ersten Rendern (sonst leuchtete beim Laden jede Zeile einmal auf). */
export function useFrisch(wert: number, ms = 1600): boolean {
  const [frisch, setFrisch] = useState(false);
  const vorherRef = useRef(wert);
  const erstesRef = useRef(true);

  useEffect(() => {
    if (erstesRef.current) {
      erstesRef.current = false;
      vorherRef.current = wert;
      return;
    }
    const gestiegen = wert > vorherRef.current;
    vorherRef.current = wert;
    if (!gestiegen) return;
    setFrisch(true);
    const t = setTimeout(() => setFrisch(false), ms);
    return () => clearTimeout(t);
  }, [wert, ms]);

  return frisch;
}
