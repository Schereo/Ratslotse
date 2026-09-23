"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";

import { Mascot } from "@/components/mascot";
import { apiUrl, authHeaders } from "@/lib/api";
import {
  darfAnstupsen, leseStand, merkeStand, nachAnzeige, nachJa, nachNein,
} from "@/lib/anstupser";
import { useFeature } from "@/lib/features";
import { cn, pfad } from "@/lib/utils";

/**
 * Lotti klopft an: „Hast du eine Frage zu dem, was du siehst?"
 *
 * **Tims Auftrag vom 21.09.2026**, und das Wort, an dem alles hängt, ist
 * *selten*. Die Grenzen dafür stehen in `lib/anstupser.ts` — hier steht nur,
 * wie gemessen wird (Lesezeit, Interaktion) und wie die Blase aussieht.
 *
 * **Was sie nicht tut:** Sie öffnet das Fenster nicht. Sie ist ein Angebot
 * mit zwei Knöpfen; erst ein „Ja" öffnet. Sie stiehlt keinen Fokus, macht
 * keinen Ton, und am geschlossenen Knopf hängt kein Zähler.
 *
 * **Eigener Schalter** (`lotti-anstupser`): Auf Prod lässt sich das Anklopfen
 * abstellen, ohne Lotti selbst abzuschalten.
 */

/** Wie lange die Blase steht, wenn niemand reagiert. Danach ist sie weg —
 *  und das zählt NICHT als Ablehnung: Wer nicht hinsieht, hat nicht Nein
 *  gesagt. */
const SICHTBAR_MS = 15_000;

/** Ab so viel Scrollen verschwindet sie: Die Person liest weiter, sie
 *  antwortet nicht. */
const SCROLL_WEG_PX = 300;

const SITZUNG_SEITEN = "ratslotse:lotti-seiten";
const SITZUNG_OFFEN = "ratslotse:lotti-war-offen";
const HEUTE_BENUTZT = "ratslotse:lotti-heute";

function zaehleSeite(): number {
  try {
    const n = Number(sessionStorage.getItem(SITZUNG_SEITEN) ?? 0) + 1;
    sessionStorage.setItem(SITZUNG_SEITEN, String(n));
    return n;
  } catch {
    // Ohne Sitzungsspeicher gilt „erste Seite" — und die ist ohnehin tabu.
    return 1;
  }
}

function jaNein(schluessel: string): boolean {
  try { return !!sessionStorage.getItem(schluessel); } catch { return false; }
}

function heuteBenutzt(): boolean {
  try {
    return localStorage.getItem(HEUTE_BENUTZT) === new Date().toISOString().slice(0, 10);
  } catch { return false; }
}

/** Lotti wurde benutzt — merken, damit heute nicht mehr angeklopft wird. */
export function merkeBenutzung(): void {
  try {
    localStorage.setItem(HEUTE_BENUTZT, new Date().toISOString().slice(0, 10));
    sessionStorage.setItem(SITZUNG_OFFEN, "1");
  } catch { /* egal */ }
}

function melde(kind: string): void {
  // Fire and forget: Ein Zähler darf nichts kosten, auch keine Fehlermeldung.
  void fetch(apiUrl("/council/assistant/event"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ kind }),
    keepalive: true,
  }).catch(() => { /* egal */ });
}

export function Anstupser({ erlaubt, onJa }: {
  /** Darf auf DIESER Seite angeklopft werden? (`PageKnowledge.nudge`) */
  erlaubt: boolean;
  onJa: () => void;
}) {
  const an = useFeature("lotti-anstupser");
  const pathname = pfad(usePathname());
  const [sichtbar, setSichtbar] = useState(false);
  const seiteRef = useRef({ seit: Date.now(), sichtbarMs: 0, letzteAktion: Date.now(),
                            scrollBeiAnzeige: 0, nummer: 1 });

  // Je Seitenaufruf von vorn: Lesezeit, letzte Aktion, Zähler.
  useEffect(() => {
    seiteRef.current = {
      seit: Date.now(), sichtbarMs: 0, letzteAktion: Date.now(),
      scrollBeiAnzeige: 0, nummer: zaehleSeite(),
    };
    setSichtbar(false);
  }, [pathname]);

  useEffect(() => {
    if (!an || !erlaubt) return;
    const s = seiteRef.current;
    let letzterTick = Date.now();

    const aktion = () => { s.letzteAktion = Date.now(); };
    window.addEventListener("scroll", aktion, { passive: true });
    window.addEventListener("pointerdown", aktion);
    window.addEventListener("keydown", aktion);

    const tick = window.setInterval(() => {
      const jetzt = Date.now();
      // NUR sichtbare Zeit zählt: Ein Tab im Hintergrund liest nicht.
      if (document.visibilityState === "visible") s.sichtbarMs += jetzt - letzterTick;
      letzterTick = jetzt;
      if (sichtbar) return;
      const stand = leseStand();
      const auswahl = window.getSelection();
      const darf = darfAnstupsen(stand, {
        seiteErlaubt: erlaubt,
        lesezeitMs: s.sichtbarMs,
        seitInteraktionMs: jetzt - s.letzteAktion,
        seitenInSitzung: s.nummer,
        fensterWarOffen: jaNein(SITZUNG_OFFEN),
        heuteBenutzt: heuteBenutzt(),
        beschaeftigt: !!document.activeElement?.closest("input, textarea, [contenteditable='true']")
          || !!(auswahl && !auswahl.isCollapsed),
      }, jetzt);
      if (!darf) return;
      merkeStand(nachAnzeige(stand, jetzt));
      s.scrollBeiAnzeige = window.scrollY;
      setSichtbar(true);
      melde("nudge_shown");
    }, 5_000);

    return () => {
      window.clearInterval(tick);
      window.removeEventListener("scroll", aktion);
      window.removeEventListener("pointerdown", aktion);
      window.removeEventListener("keydown", aktion);
    };
  }, [an, erlaubt, pathname, sichtbar]);

  // Von selbst wieder weg: nach einer Weile oder beim Weiterlesen. Beides
  // zählt NICHT als Ablehnung — wer nicht hinsieht, hat nicht Nein gesagt.
  useEffect(() => {
    if (!sichtbar) return;
    const weg = () => setSichtbar(false);
    const id = window.setTimeout(weg, SICHTBAR_MS);
    const beimScrollen = () => {
      if (Math.abs(window.scrollY - seiteRef.current.scrollBeiAnzeige) > SCROLL_WEG_PX) weg();
    };
    window.addEventListener("scroll", beimScrollen, { passive: true });
    return () => {
      window.clearTimeout(id);
      window.removeEventListener("scroll", beimScrollen);
    };
  }, [sichtbar]);

  if (!an || !sichtbar) return null;

  return (
    <div
      role="status"
      data-lotti-anstupser
      className={cn(
        "fixed right-4 z-50 w-[min(16rem,calc(100vw-2rem))] rounded-2xl border border-border",
        "bg-card p-3 shadow-lifted print:hidden",
        "animate-in fade-in-0 slide-in-from-bottom-2 duration-buehne ease-out-strong",
        // Über dem Knopf, der seinerseits über Tab-Leiste und Composer sitzt.
        "bottom-[calc(var(--rl-unten,0px)+var(--rl-composer,0px)+5.25rem)]",
        "desk:right-6 desk:bottom-[calc(var(--rl-composer,0px)+5.5rem)]",
      )}
    >
      <button
        type="button"
        aria-label="Nicht jetzt"
        onClick={() => { merkeStand(nachNein(leseStand())); setSichtbar(false); melde("nudge_dismissed"); }}
        className="absolute right-1.5 top-1.5 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X className="h-3.5 w-3.5" aria-hidden />
      </button>
      <div className="flex items-start gap-2.5">
        <Mascot regung="hebt-hand" decorative className="h-8 w-8 flex-none" />
        <div className="min-w-0">
          <p className="pr-4 text-hinweis text-foreground">
            Hast du eine Frage zu dem, was du siehst?
          </p>
          <button
            type="button"
            onClick={() => {
              merkeStand(nachJa(leseStand(), Date.now()));
              setSichtbar(false);
              melde("nudge_accepted");
              onJa();
            }}
            className="mt-2 inline-flex min-h-8 items-center rounded-full bg-primary px-3 text-[12.5px] font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Ja, frag Lotti
          </button>
        </div>
      </div>
    </div>
  );
}
