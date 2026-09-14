"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  aendereSuche, istSucheinstieg, letzteSuche, merkeSuche, merkeSuchPosition,
  suchAdresse, suchPosition,
} from "./suchkontext";

export function useSuchparameter() {
  const sp = useSearchParams();
  const [adresse, setAdresse] = useState(() => suchAdresse(sp.toString()));
  const [bereit, setBereit] = useState(false);
  const aktuell = useRef<string | null>(null);

  useEffect(() => {
    const eingang = sp.toString();
    if (eingang === aktuell.current) return;
    const href = istSucheinstieg(eingang)
      ? letzteSuche() ?? suchAdresse(eingang)
      : suchAdresse(eingang);
    aktuell.current = href.split("?")[1];
    setAdresse(href);
    setBereit(true);
    merkeSuche(href);
    if (eingang !== aktuell.current) {
      // Next integriert die native History in useSearchParams. Filterwechsel
      // brauchen keinen Server-Roundtrip und keinen zusätzlichen Zurück-Schritt.
      window.history.replaceState(null, "", href + window.location.hash);
    }
  }, [sp]);

  const setzen = useCallback((werte: Record<string, string>) => {
    const href = aendereSuche(aktuell.current ?? "", werte);
    aktuell.current = href.split("?")[1];
    setAdresse(href);
    merkeSuche(href);
    window.history.replaceState(null, "", href);
  }, []);

  const parameter = useMemo(() => new URLSearchParams(adresse.split("?")[1]), [adresse]);
  return { parameter, adresse, bereit, setzen };
}

/** Die Position gehört zur konkreten Liste, nicht global zum letzten
 *  Beschluss. So vermischen sich zwei Suchläufe mit verschiedenen Filtern
 *  oder Seiten nicht. Gespeichert wird beim Öffnen, bevor Next scrollt. */
export function merkeSuchtreffer(adresse: string, link: HTMLAnchorElement): void {
  merkeSuchPosition({
    href: adresse,
    treffer: link.id,
    oben: link.getBoundingClientRect().top,
    detail: link.pathname + link.search,
  });
}

export function useSuchposition(adresse: string, laedt: boolean) {
  const wiederhergestellt = useRef<string | null>(null);
  useEffect(() => {
    if (laedt || wiederhergestellt.current === adresse) return;
    const position = suchPosition(adresse);
    const anker = /^#beschluss-\d+$/.test(window.location.hash) ? window.location.hash.slice(1) : null;
    const ziel = document.getElementById(anker ?? position?.treffer ?? "");
    if (!ziel) { wiederhergestellt.current = adresse; return; }
    const frame = requestAnimationFrame(() => {
      wiederhergestellt.current = adresse;
      ziel.focus({ preventScroll: true });
      if (position && (!anker || anker === position.treffer)) {
        const oben = Math.min(position.oben, window.innerHeight - 100);
        window.scrollTo({ top: window.scrollY + ziel.getBoundingClientRect().top - oben, behavior: "instant" });
      } else {
        ziel.scrollIntoView({ block: "center", behavior: "instant" });
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [adresse, laedt]);
}
