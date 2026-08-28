"use client";

// Lesestand des Haushalts-Wegweisers — lokal gespeichert, kein Konto nötig
// (H3-08: „Fortschritt lokal gespeichert").
//
// WAS GEZÄHLT WIRD: besuchte Unterseiten des Bereichs, als Pfad
// („/haushalt/pruefung"). Aufgezeichnet wird beim BESUCH der Seite
// (`<FortschrittMerker>` im Haushalts-Layout), nicht beim Klick im
// Wegweiser — wer über die KI-Frage oder einen geteilten Link ankommt,
// zählt genauso.
//
// WAS ES BEDEUTET: „gelesen" heißt hier „aufgerufen". Mehr behaupten wir
// nicht — es gibt keine Scrolltiefe-Messung und keine Quiz-Abfrage, und der
// Wegweiser schreibt deshalb „erledigt" nur an Etappen, deren Seiten alle
// aufgerufen wurden.
//
// WARUM localStorage UND ein eigenes Event: `storage` feuert nur in ANDEREN
// Tabs. Damit der Wegweiser im selben Tab mitzieht (Seite besuchen → zurück
// zur Übersicht), sendet `merkeBesucht` zusätzlich ein Fenster-Event, auf das
// `useFortschritt` hört. Der Hook liefert bis zur Hydration ein leeres Set —
// Server und erster Client-Render sind damit deterministisch gleich.

import { useEffect, useState } from "react";

const SCHLUESSEL = "haushalt.besucht";
const EVENT = "haushalt-fortschritt";

function lies(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const roh = window.localStorage.getItem(SCHLUESSEL);
    const liste = roh ? (JSON.parse(roh) as unknown) : [];
    return new Set(Array.isArray(liste) ? liste.filter((x) => typeof x === "string") : []);
  } catch {
    // Voller Speicher, Safari-Privatmodus, kaputtes JSON: Der Wegweiser
    // funktioniert dann ohne Gedächtnis, statt die Seite zu reißen.
    return new Set();
  }
}

/** Einen Seitenbesuch festhalten. Idempotent — mehrfaches Aufrufen derselben
 *  Seite schreibt nur beim ersten Mal. */
export function merkeBesucht(pfad: string): void {
  if (typeof window === "undefined") return;
  const besucht = lies();
  if (besucht.has(pfad)) return;
  besucht.add(pfad);
  try {
    window.localStorage.setItem(SCHLUESSEL, JSON.stringify([...besucht]));
  } catch {
    return; // s. o. — kein Gedächtnis ist kein Fehler
  }
  window.dispatchEvent(new Event(EVENT));
}

/** Die besuchten Pfade als Set — leer bis zur Hydration, danach live. */
export function useFortschritt(): Set<string> {
  const [besucht, setBesucht] = useState<Set<string>>(new Set());
  useEffect(() => {
    const aktualisiere = () => setBesucht(lies());
    aktualisiere();
    window.addEventListener(EVENT, aktualisiere);
    window.addEventListener("storage", aktualisiere);
    return () => {
      window.removeEventListener(EVENT, aktualisiere);
      window.removeEventListener("storage", aktualisiere);
    };
  }, []);
  return besucht;
}
