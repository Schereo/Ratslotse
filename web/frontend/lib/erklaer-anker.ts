"use client";

import { usePathname } from "next/navigation";

import { pfad } from "./utils";

/**
 * Ein Baustein sagt Lotti, dass er erklärbar ist — mit einer Zeile.
 *
 * **Warum ein Hook und kein Attribut von Hand.** Der Schlüssel besteht aus
 * Seite und Baustein (`schulden.rate-treppe`), und die Seite kennt der
 * Baustein nicht: Dieselbe Zeitreihe steht auf elf Seiten. Von Hand hieße das
 * elf Aufrufstellen mit je einem Schlüssel, den irgendwann jemand kopiert und
 * nicht anpasst. Der Hook liest den Pfad und setzt ihn davor.
 *
 * ```tsx
 * <div {...useErklaerAnker("rate-treppe", "Rate-Treppe")}>…</div>
 * ```
 *
 * **Was der Anker bewirkt.** Drei Dinge, alle in Lottis Fenster:
 * - **Kontext einer Markierung.** Wer in diesem Element Text markiert und
 *   „Lotti fragen" drückt, schickt den SICHTBAREN Text des Elements mit —
 *   nicht die Seite, nicht die Nachbarn, nur dieses Element
 *   (`components/assistentin/markier-knopf.tsx`). Ohne Anker geht nur die
 *   Markierung: Was nicht ausdrücklich ein Baustein ist, wird nicht geraten.
 * - **Die Landkarte der Seite** für „Wo finde ich …?" (`ankerListe`).
 * - **Der Anschluss-Chip** „<Titel> erklären" unter einer Antwort.
 *
 * Bis 23.09.2026 bekam jedes Element mit Anker im Erklär-Modus zusätzlich
 * ein „?"-Abzeichen; den Modus gibt es nicht mehr (Tim: „keiner versteht,
 * wie das funktioniert").
 */
export function useErklaerAnker(name: string, titel?: string): {
  "data-erklaer": string;
  "data-erklaer-titel"?: string;
} {
  const seite = pfad(usePathname())
    .replace(/^\//, "")
    .replace(/\//g, "-") || "start";
  return {
    "data-erklaer": `${seite}.${name}`,
    ...(titel ? { "data-erklaer-titel": titel } : {}),
  };
}
