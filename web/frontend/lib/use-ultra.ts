"use client";

import { useEffect, useState } from "react";
import { ULTRA_MEDIA, WEIT_MEDIA } from "./vollbreit";

function useMedia(query: string): boolean {
  const [treffer, setTreffer] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const h = () => setTreffer(mq.matches);
    h();
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, [query]);
  return treffer;
}

/** Ist das Fenster so breit wie `ultra`? Vor dem Mount `false` — die Seite
 *  rendert also zuerst die schmale Form, wie jede Breite unter 2200 px. */
export function useUltra(): boolean {
  return useMedia(ULTRA_MEDIA);
}

/** Dasselbe für `weit` (1680 px). */
export function useWeit(): boolean {
  return useMedia(WEIT_MEDIA);
}

/** Telefonbreite (unter `sm`, 640 px). Der Spieler „Neu bei Ratslotse"
 *  nimmt dort die hochkante Fassung der Clips (`media_narrow`). */
export function useTelefonBreite(): boolean {
  return useMedia("(max-width: 639.98px)");
}
