"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Pfade, deren Route in dieser Sitzung schon einmal vorgeladen wurde. */
const prefetched = new Set<string>();

/**
 * Eine Vorladung je Ziel-ROUTE statt je Karte.
 *
 * Next 14 lädt jeden sichtbaren `<Link>` einzeln vor, und der Schlüssel
 * enthält die Suchparameter: 27 Themen-Kacheln auf `/council/thema?slug=…`
 * waren 27 dynamisch gerenderte RSC-Pakete (gemessen 11/2026), obwohl Route
 * und JavaScript dieselben sind — die Zielseiten laden ihre Daten ohnehin
 * selbst über `/api`. Listen-Karten tragen deshalb `prefetch={false}`, und die
 * Liste ruft hier EINMAL mit ihrem ersten Ziel an: Das holt den Code der Route
 * in den Browser, der erste Klick wartet dann nur noch auf das kleine
 * RSC-Paket.
 *
 * Gemerkt wird der Pfad ohne Suchparameter, für die ganze Sitzung — das
 * JavaScript einer Route bleibt geladen, auch wenn Nexts Vorlade-Cache längst
 * abgelaufen ist. Zeigt das Ziel auf die Route, auf der man gerade steht
 * (Nachbar-Orte, ähnliche Beschlüsse), ist ihr Code schon da: kein Abruf.
 *
 * Darf in jeder Karte einer Liste stehen — nur die erste löst etwas aus.
 */
export function usePrefetchRoute(href: string | null | undefined) {
  const router = useRouter();
  useEffect(() => {
    if (!href) return;
    const path = href.split(/[?#]/)[0];
    if (prefetched.has(path)) return;
    prefetched.add(path);
    if (path === window.location.pathname) return;
    router.prefetch(href);
  }, [router, href]);
}
