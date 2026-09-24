"use client";

import { useEffect, useState } from "react";
import { ULTRA_MEDIA } from "./vollbreit";

/** Ist das Fenster so breit wie `ultra`? Vor dem Mount `false` — die Seite
 *  rendert also zuerst die schmale Form, wie jede Breite unter 2200 px. */
export function useUltra(): boolean {
  const [ultra, setUltra] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(ULTRA_MEDIA);
    const h = () => setUltra(mq.matches);
    h();
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);
  return ultra;
}
