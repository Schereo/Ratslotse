"use client";

import { Suspense, useCallback, useEffect, useState, type ComponentProps, type ComponentType } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useFeature } from "@/lib/features";
import { pfad } from "@/lib/utils";

import { Anstupser, merkeBenutzung } from "./anstupser";
import { useMarkierung, useTastatur } from "./hooks";
import { LottiKnopf } from "./knopf";
import { MarkierKnopf, type MarkierFrage } from "./markier-knopf";
// Nur der Typ: Ein Wert-Import zöge das ganze Fenster wieder ins Bündel.
import type { LottiPanel as LottiPanelTyp } from "./panel";
import { oeffnenGewuenscht, ohneOeffnen, routeAus } from "@/lib/assistentin";
import { useAuth } from "@/lib/auth";
import { chunkFehlerHeilen } from "@/lib/chunk-fehler";
import { anstupserErlaubt } from "@/lib/anstupser-seiten";
import { knopfVersteckt, LOTTI_SICHT_EVENT } from "@/lib/lotti-sichtbar";
import { useVollbild } from "@/lib/vollbild";

/** Das Fenster selbst — mit Antwort-Bausteinen, Glossar und Diagrammen gut
 *  50 KB (gzip). Bis 11/2026 hing es statisch an jeder Seite der App, obwohl
 *  es zu ist, bis jemand den Knopf drückt. Jetzt kommt es im Leerlauf nach
 *  dem Laden (s. `fensterVorladen`) — oder beim ersten Öffnen, falls jemand
 *  schneller ist —, damit der erste Klick in aller Regel nicht wartet.
 *
 *  **Bewusst ohne `next/dynamic`.** Das lädt über `React.lazy` und eine
 *  Suspense-Grenze, und React drosselt das Aufdecken danach auf bis zu
 *  300 ms. Gemessen stand das Fenster so erst nach gut 300 ms statt nach
 *  10 ms da. Hier liegt die geladene Komponente fertig in einer Variablen.
 *
 *  `onBereit` meldet, dass das Fenster eingehängt ist. Es wird bewusst ZU
 *  eingehängt und erst danach geöffnet — wie vorher, als es mit der Seite kam.
 *  Seine Effekte (Frage zur Markierung, gespeichertes Gespräch laden) laufen
 *  beim Öffnen; käme es gleich offen zur Welt, liefen sie zusammen mit dem
 *  Einhängen, und Reacts StrictMode spielt das zur Probe doppelt ab (Frage
 *  doppelt gestellt bzw. vom Seitenwechsel-Abbruch sofort wieder gekappt). */
type FensterProps = ComponentProps<typeof LottiPanelTyp> & { onBereit: (bereit: boolean) => void };
type Fenster = ComponentType<FensterProps>;
let geladenesFenster: Fenster | null = null;
let fensterLaedt: Promise<Fenster> | null = null;

function fensterHolen(): Promise<Fenster> {
  fensterLaedt ??= import("./panel").then(({ LottiPanel }) => {
    function GeladenesFenster({ onBereit, ...props }: FensterProps) {
      useEffect(() => {
        onBereit(true);
        return () => onBereit(false);
      }, [onBereit]);
      return <LottiPanel {...props} />;
    }
    geladenesFenster = GeladenesFenster;
    return GeladenesFenster;
  }, (e: unknown) => {
    // Beim nächsten Versuch neu holen, statt am alten Fehler zu hängen.
    fensterLaedt = null;
    throw e;
  });
  return fensterLaedt;
}

/** Das Fenster-Bündel holen, sobald der Browser nichts Dringenderes vorhat:
 *  nach dem `load`-Ereignis, in der nächsten Leerlaufphase. */
function fensterVorladen(geladen: (f: Fenster) => void): () => void {
  const w = window as Window & {
    requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number;
    cancelIdleCallback?: (id: number) => void;
  };
  let idle: number | undefined;
  let zeit: ReturnType<typeof setTimeout> | undefined;
  // Scheitert das Vorladen (Funkloch, alte Seite nach einem Deploy), holt das
  // erste Öffnen es noch einmal — kein Grund für eine Fehlermeldung.
  const holen = () => { fensterHolen().then(geladen, () => {}); };
  const imLeerlauf = () => {
    if (w.requestIdleCallback) idle = w.requestIdleCallback(holen, { timeout: 4000 });
    else zeit = setTimeout(holen, 1500);
  };
  if (document.readyState === "complete") imLeerlauf();
  else window.addEventListener("load", imLeerlauf, { once: true });
  return () => {
    window.removeEventListener("load", imLeerlauf);
    if (idle !== undefined) w.cancelIdleCallback?.(idle);
    if (zeit !== undefined) clearTimeout(zeit);
  };
}

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
  const rohPfad = usePathname();
  const pathname = pfad(rohPfad);
  const sp = useSearchParams();
  const router = useRouter();
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

  // `?lotti=1` öffnet das Fenster beim Ankommen: „Lotti-Chat ausprobieren"
  // auf der Karte „Neu bei Ratslotse" führt so direkt in den Chat, statt auf
  // eine Seite, auf der man die Möwe erst suchen muss. Danach fliegt der
  // Parameter aus der Adresse — ein Neuladen soll das Fenster nicht wieder
  // aufreißen. Solange der Schalter aus ist oder ein Vollbild-Ablauf läuft,
  // bleibt er stehen und greift, sobald das Fenster gehen darf.
  useEffect(() => {
    if (!an || vollbild || !oeffnenGewuenscht(sp.toString())) return;
    setOffen(true);
    router.replace(ohneOeffnen(rohPfad, sp.toString(), window.location.hash), { scroll: false });
  }, [an, vollbild, sp, rohPfad, router]);

  // Das Küken tritt beiseite, solange das Fenster offen ist: Zwei Möwen in
  // derselben Ecke sind eine zu viel.
  useEffect(() => {
    window.dispatchEvent(new CustomEvent("ratslotse:lotti-offen", { detail: { offen } }));
    // Wer das Fenster geöffnet hat, braucht heute kein Anklopfen mehr — und
    // in dieser Sitzung gar keins.
    if (offen) merkeBenutzung();
  }, [offen]);

  const gesperrt = OHNE_LOTTI.some((p) => pathname === p || pathname.startsWith(`${p}/`));

  // Das Fenster wird eingehängt, sobald sein Bündel da ist — im Leerlauf oder
  // beim ersten Öffnen, was früher kommt — und bleibt es dann: Der Verlauf
  // soll den Seitenwechsel überleben (s. o.).
  const [GeladenesFenster, setGeladenesFenster] = useState<Fenster | null>(() => geladenesFenster);
  const [fensterBereit, setFensterBereit] = useState(false);
  const knopfDa = an && !gesperrt;
  useEffect(
    () => (knopfDa && !GeladenesFenster ? fensterVorladen((f) => setGeladenesFenster(() => f)) : undefined),
    [knopfDa, GeladenesFenster],
  );
  useEffect(() => {
    if (!offen || GeladenesFenster) return;
    fensterHolen().then((f) => setGeladenesFenster(() => f), (e: unknown) => {
      // Nach einem Deploy fehlt das alte Bündel: einmal neu laden, wie die
      // Fehlerseite es täte. Sonst den Knopf zurückstellen, statt „offen" zu
      // zeigen, ohne dass ein Fenster kommt.
      if (!chunkFehlerHeilen(e)) setOffen(false);
    });
  }, [offen, GeladenesFenster]);

  if (!an || gesperrt || vollbild) return null;

  return (
    <>
      {GeladenesFenster && (
        <GeladenesFenster
          offen={offen && fensterBereit}
          onBereit={setFensterBereit}
          onSchliessen={schliessen}
          markierung={markierung}
          markiert={markiert}
          onMarkiertVerbraucht={() => setMarkiert(null)}
          ladeGespraech={ladeGespraech}
          onGespraechGeladen={() => setLadeGespraech(null)}
        />
      )}
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
