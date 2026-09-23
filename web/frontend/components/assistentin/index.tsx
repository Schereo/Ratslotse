"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { useFeature } from "@/lib/features";
import { pfad } from "@/lib/utils";

import { Anstupser, merkeBenutzung } from "./anstupser";
import { LottiKnopf } from "./knopf";
import { MarkierKnopf, type MarkierFrage } from "./markier-knopf";
import { LottiPanel, useMarkierung, useTastatur } from "./panel";
import { routeAus } from "@/lib/assistentin";
import { useAuth } from "@/lib/auth";
import { anstupserErlaubt } from "@/lib/anstupser-seiten";
import { knopfVersteckt, LOTTI_SICHT_EVENT } from "@/lib/lotti-sichtbar";
import { useVollbild } from "@/lib/vollbild";

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
 *
 * **Und nicht, solange ein Vollbild-Ablauf läuft** — Einrichtungs-Assistent,
 * Tour-Einladung, geführte Tour. Das Signal kommt als `window`-Ereignis
 * (`lib/vollbild.ts`), nicht als Kontext: Die Assistentin hängt in der
 * App-Hülle, die Abläufe daneben.
 */
/** Ein Baustein der Seite, so wie er ans Backend geht — aus einem „…
 *  erklären"-Chip oder als Umgebung einer Markierung.
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
  // Eine Markierung, zu der gerade gefragt wurde („Lotti fragen" an der
  // Auswahl). Gesetzt heißt: Das Fenster stellt die Frage sofort.
  //
  // **Bis 23.09.2026 stand hier der Erklär-Modus** — ein Knopf im Fenster,
  // der es schloss und „?"-Abzeichen auf die Bausteine setzte. Tim: „keiner
  // versteht, wie das funktioniert, selbst bei mir hat es gedauert."
  const [markiert, setMarkiert] = useState<MarkierFrage | null>(null);
  const markierung = useMarkierung();
  // Nur zum STREICHEN, nie zum Mitschicken: Der Anzeigename steht auf
  // `/dashboard` in der `h1` und wäre sonst über den Überschriften-Pfad im
  // Prompt gelandet (lib/assistentin.ts::ohneNamen).
  const anzeigename = useAuth().user?.display_name ?? null;
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

  // Läuft ein Vollbild-Ablauf (Einrichtungs-Assistent, Tour-Einladung, Tour),
  // tritt Lotti komplett weg: kein Knopf, kein Anklopfen, kein Fenster.
  // Vorher stand der Knopf im DOM, war mit Tab erreichbar und von der Fläche
  // verdeckt — wer ihn traf, öffnete ein Fenster HINTER dem Assistenten und
  // bekam Seitenwissen zu einer Seite, die gerade gar nicht zu sehen war
  // (Befund B4 der zweiten Durchsicht, 21.09.2026).
  const vollbild = useVollbild();
  useEffect(() => {
    // Ein bereits offenes Fenster schließt sich — die Tour startet aus der
    // ⌘K-Palette heraus, also auch bei offenem Lotti.
    if (vollbild) setOffen(false);
  }, [vollbild]);

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
  if (!an || gesperrt || vollbild) return null;

  return (
    <>
      <LottiPanel
        offen={offen}
        onSchliessen={schliessen}
        markierung={markierung}
        markiert={markiert}
        onMarkiertVerbraucht={() => setMarkiert(null)}
        ladeGespraech={ladeGespraech}
        onGespraechGeladen={() => setLadeGespraech(null)}
      />
      {/* „Lotti fragen" an der Markierung. **Dieselben Bedingungen wie der
          schwebende Knopf**: ausgeblendet heißt auch hier ausgeblendet — wer
          Lotti aus dem Weg haben will, will keinen Knopf an jeder Markierung.
          Schalter, gesperrte Seiten und Vollbild-Abläufe greifen schon oben
          (`return null`); ohne Konto gibt es die App-Hülle gar nicht. Steht
          die Tastatur, markiert man in einem Eingabefeld — das zählt ohnehin
          nicht. */}
      <MarkierKnopf
        aktiv={!versteckt && tastatur === 0}
        anzeigename={anzeigename}
        onFragen={(f) => {
          setMarkiert(f);
          setOffen(true);
        }}
      />
      <Anstupser
        erlaubt={!versteckt && anstupserErlaubt(routeAus(pathname, sp.toString()))}
        onJa={() => setOffen(true)}
      />
      {(!versteckt || offen) && tastatur === 0 && (
        <LottiKnopf
          offen={offen}
          onToggle={() => setOffen((o) => !o)}
        />
      )}
    </>
  );
}
