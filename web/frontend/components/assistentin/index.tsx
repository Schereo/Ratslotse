"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { useFeature } from "@/lib/features";
import { pfad } from "@/lib/utils";

import { Anstupser, merkeBenutzung } from "./anstupser";
import { ErklaerModus } from "./erklaer-modus";
import { LottiKnopf } from "./knopf";
import { LottiPanel, useMarkierung, useTastatur } from "./panel";
import { ernteElement, routeAus, ueberschriftenPfad } from "@/lib/assistentin";
import { anstupserErlaubt } from "@/lib/anstupser-seiten";
import { knopfVersteckt, LOTTI_SICHT_EVENT } from "@/lib/lotti-sichtbar";

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
/** Ein angeklickter Baustein, so wie er ans Backend geht.
 *
 *  `pfad` gehört nicht zum Element, sondern sagt, WO auf der Seite es steht
 *  („Schulden › Rate-Treppe"). Er wird beim Antippen berechnet, weil nur dort
 *  der DOM-Knoten noch vorliegt. */
export type ElementFrage = {
  key: string | null; title: string; text: string; pfad?: string;
};

const OHNE_LOTTI = ["/admin", "/account"];

/** Öffnen von außen — dasselbe Muster wie `openCommandPalette()`. */
const EREIGNIS = "ratslotse:lotti-oeffnen";

/** Lottis Fenster öffnen; mit `gespraech` lädt es ein gespeichertes Gespräch.
 *
 *  **Warum überhaupt mit Kennung.** Ein Lotti-Gespräch in der Liste „Gespräche"
 *  gehört hierher, nicht ins Ratsgespräch: Dort erschiene ein Verlauf, der
 *  nie so entstanden ist — ohne Bildschirm-Bezug, ohne die Chips, die zu ihm
 *  gehören. */
export function openLotti(gespraech?: number) {
  window.dispatchEvent(new CustomEvent(EREIGNIS, { detail: { gespraech } }));
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
  const sp = useSearchParams();
  const [offen, setOffen] = useState(false);
  // Der Erklär-Modus SCHLIESST das Fenster, statt neben ihm zu laufen: Die
  // Abzeichen stehen auf der Seite, und auf dem Handy deckt das Fenster genau
  // die Seite ab, auf die man zeigen soll. Ein Tipp auf ein Abzeichen öffnet
  // es wieder — mit der Antwort darin.
  const [modus, setModus] = useState(false);
  const [element, setElement] = useState<ElementFrage | null>(null);
  const markierung = useMarkierung();
  // Steht die Tastatur, liegt der Knopf hinter ihr — ein Knopf, den man nicht
  // sieht und nicht trifft, ist kein Knopf. Dieselbe Regel wie in der App.
  const tastatur = useTastatur();
  // Ausgeblendet heißt: kein Knopf und kein Anklopfen — aber das Fenster
  // bleibt erreichbar (⌘K). Sonst hieße „ausblenden" in Wahrheit „abschalten".
  const [versteckt, setVersteckt] = useState(false);
  useEffect(() => {
    const sync = () => setVersteckt(knopfVersteckt());
    sync();
    window.addEventListener(LOTTI_SICHT_EVENT, sync);
    return () => window.removeEventListener(LOTTI_SICHT_EVENT, sync);
  }, []);

  const schliessen = useCallback(() => setOffen(false), []);

  const [ladeGespraech, setLadeGespraech] = useState<number | null>(null);

  useEffect(() => {
    const auf = (e: Event) => {
      const id = (e as CustomEvent<{ gespraech?: number }>).detail?.gespraech;
      if (id) setLadeGespraech(id);
      setOffen(true);
    };
    window.addEventListener(EREIGNIS, auf);
    return () => window.removeEventListener(EREIGNIS, auf);
  }, []);

  // Das Küken tritt beiseite, solange das Fenster offen ist: Zwei Möwen in
  // derselben Ecke sind eine zu viel.
  useEffect(() => {
    window.dispatchEvent(new CustomEvent("ratslotse:lotti-offen", { detail: { offen } }));
    // Wer das Fenster geöffnet hat, braucht heute kein Anklopfen mehr — und
    // in dieser Sitzung gar keins.
    if (offen) merkeBenutzung();
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
        ladeGespraech={ladeGespraech}
        onGespraechGeladen={() => setLadeGespraech(null)}
        onModus={() => setModus(true)}
      />
      <ErklaerModus
        aktiv={modus}
        onBeenden={() => setModus(false)}
        onWaehlen={(el) => {
          setElement({ ...ernteElement(el), pfad: ueberschriftenPfad(el, document) });
          setModus(false);
          setOffen(true);
        }}
      />
      <Anstupser
        erlaubt={!versteckt && anstupserErlaubt(routeAus(pathname, sp.toString()))}
        onJa={() => setOffen(true)}
      />
      {(!versteckt || offen || modus) && tastatur === 0 && (
        <LottiKnopf
          offen={offen || modus}
          onToggle={() => {
            if (modus) { setModus(false); return; }
            setOffen((o) => !o);
          }}
        />
      )}
    </>
  );
}
