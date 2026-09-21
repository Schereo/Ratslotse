"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { useFeature } from "@/lib/features";
import { pfad } from "@/lib/utils";

import { ErklaerModus } from "./erklaer-modus";
import { LottiKnopf } from "./knopf";
import { LottiPanel, useMarkierung } from "./panel";
import { ernteElement } from "@/lib/assistentin";

/**
 * Lotti als Assistentin — Knopf und Fenster, eingehängt in die App-Hülle.
 *
 * **Warum in der Hülle und nicht je Seite.** Der Verlauf soll den
 * Seitenwechsel überleben: Wer auf der Schulden-Seite fragt und dann zur
 * Tilgung blättert, führt dasselbe Gespräch weiter. Läge das Fenster in einer
 * Seite, stürbe es mit ihr.
 *
 * **Wo es Lotti nicht gibt.** Auf den Seiten mit fremden oder eigenen
 * Kontodaten — `/admin` und `/account`. Die Liste steht im Backend
 * (`kern/knowledge.py::OHNE_ERKLAERUNG`) und wird hier gespiegelt, damit der
 * Knopf gar nicht erst erscheint; das Backend weist die Route zusätzlich ab.
 * Zwei Stellen, aber die vordere ist Höflichkeit und die hintere die Sperre —
 * dieselbe Aufteilung wie beim Rechte-Gate (web/frontend/CLAUDE.md).
 */
/** Ein angeklickter Baustein, so wie er ans Backend geht. */
export type ElementFrage = { key: string | null; title: string; text: string };

const OHNE_LOTTI = ["/admin", "/account"];

/** Öffnen von außen — dasselbe Muster wie `openCommandPalette()`. */
const EREIGNIS = "ratslotse:lotti-oeffnen";

export function openLotti() {
  window.dispatchEvent(new Event(EREIGNIS));
}

export function LottiAssistentin() {
  return (
    // `useSearchParams` im Fenster verlangt eine Suspense-Grenze (CSR-Bailout
    // beim Prerender) — wie bei BackToTop und ScrollMemory.
    <Suspense fallback={null}>
      <LottiInner />
    </Suspense>
  );
}

function LottiInner() {
  const an = useFeature("lotti-assistentin");
  const pathname = pfad(usePathname());
  const [offen, setOffen] = useState(false);
  // Der Erklär-Modus SCHLIESST das Fenster, statt neben ihm zu laufen: Die
  // Abzeichen stehen auf der Seite, und auf dem Handy deckt das Fenster genau
  // die Seite ab, auf die man zeigen soll. Ein Tipp auf ein Abzeichen öffnet
  // es wieder — mit der Antwort darin.
  const [modus, setModus] = useState(false);
  const [element, setElement] = useState<ElementFrage | null>(null);
  const markierung = useMarkierung();

  const schliessen = useCallback(() => setOffen(false), []);

  useEffect(() => {
    const auf = () => setOffen(true);
    window.addEventListener(EREIGNIS, auf);
    return () => window.removeEventListener(EREIGNIS, auf);
  }, []);

  // Das Küken tritt beiseite, solange das Fenster offen ist: Zwei Möwen in
  // derselben Ecke sind eine zu viel.
  useEffect(() => {
    window.dispatchEvent(new CustomEvent("ratslotse:lotti-offen", { detail: { offen } }));
  }, [offen]);

  const gesperrt = OHNE_LOTTI.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (!an || gesperrt) return null;

  return (
    <>
      <LottiPanel
        offen={offen && !modus}
        onSchliessen={schliessen}
        markierung={markierung}
        element={element}
        onElementVerbraucht={() => setElement(null)}
        onModus={() => setModus(true)}
      />
      <ErklaerModus
        aktiv={modus}
        onBeenden={() => setModus(false)}
        onWaehlen={(el) => {
          setElement(ernteElement(el));
          setModus(false);
          setOffen(true);
        }}
      />
      <LottiKnopf
        offen={offen || modus}
        onToggle={() => {
          if (modus) { setModus(false); return; }
          setOffen((o) => !o);
        }}
      />
    </>
  );
}
