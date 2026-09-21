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
 * **Was der Anker bewirkt.** Im Erklär-Modus (`components/assistentin/
 * erklaer-modus.tsx`) bekommt das Element ein „?"-Abzeichen; ein Tipp darauf
 * schickt seinen SICHTBAREN Text an Lotti — nicht die Seite, nicht die
 * Nachbarn, nur dieses Element. Ohne Anker gibt es kein Abzeichen: Was nicht
 * ausdrücklich erklärbar ist, wird nicht geraten.
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
