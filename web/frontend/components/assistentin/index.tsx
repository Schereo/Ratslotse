"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { useFeature } from "@/lib/features";
import { pfad } from "@/lib/utils";

import { LottiKnopf } from "./knopf";
import { LottiPanel, useMarkierung } from "./panel";

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
      <LottiPanel offen={offen} onSchliessen={schliessen} markierung={markierung} />
      <LottiKnopf offen={offen} onToggle={() => setOffen((o) => !o)} />
    </>
  );
}
