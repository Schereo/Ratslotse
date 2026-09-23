"use client";

import Image from "next/image";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { auswahlErlaubt, ernteElement, ohneNamen, ueberschriftenPfad } from "@/lib/assistentin";
import {
  knopfPosition, markierungAufbereiten, markierungInZeile, type KnopfLage, type Rechteck,
} from "@/lib/markieren";
import { cn } from "@/lib/utils";

import type { ElementFrage } from "./index";

/**
 * „Lotti fragen" an der Markierung — der Ersatz für den Erklär-Modus.
 *
 * **Tims Befund (23.09.2026):** „Dieses ‚Frag mich zu dieser Seite‘ und dann
 * kann man irgendwas anklicken — das ist so mega komisch, keiner versteht,
 * wie das funktioniert." Der Modus verlangte zwei Dinge, die man nicht sieht:
 * dass es ihn gibt, und was er mit einem macht. Markieren kann jede*r; der
 * Knopf erscheint als ANTWORT auf diese Handlung, direkt an ihr, und
 * verschwindet mit ihr.
 *
 * **Was mitgeht.** Der markierte Text IN SEINER ZEILE (`»8,0 Mio. €«` samt
 * „Mai 2026 · … · 3,43 %" drumherum, gekürzt auf `SELECTION_MAX`, s.
 * `lib/markieren.ts::markierungInZeile`), der Überschriften-Pfad darüber und — falls die
 * Markierung in einem erklärbaren Baustein liegt — dieser Baustein als
 * Kontext (nächster `data-erklaer`-Vorfahr). Liegt sie in keinem, geht
 * keiner mit: Ein geratener Ausschnitt sähe aus, als wüsste Lotti mehr, als
 * sie weiß — dieselbe Regel, die schon für die Abzeichen galt.
 *
 * **Was NICHT zählt:** eine Markierung in Lottis Fenster (man zitiert sie,
 * man fragt sie nicht über sich selbst), in einem Eingabefeld (getippter Text
 * der Person), ein einzelnes Zeichen (ein verrutschter Klick).
 *
 * **Handy.** Markiert wird per Langdruck; das System legt dann sein eigenes
 * Menü ÜBER die Auswahl und einen Anfasser UNTER ihr Ende. Der Knopf steht
 * deshalb unter dem Ende, mit so viel Abstand, dass der Anfasser frei bleibt
 * (`ABSTAND_TOUCH`), und `selectionchange` wird entprellt — beim Ziehen am
 * Anfasser feuert es bei jedem Zeichen.
 */

/** Wie lange die Auswahl ruhen muss, bevor der Knopf kommt. Dieselbe Pause
 *  wie `useMarkierung` im Fenster — sonst stünde der Knopf schon da, während
 *  die Kontext-Pille noch den alten Text zeigt. */
const RUHE_MS = 250;

/** Abstand unter dem Auswahl-Ende. Am Touchgerät sitzt dort der Anfasser des
 *  Systems (iOS ~ 22 pt, Android ~ 22 dp hoch); 34 px halten ihn frei, sonst
 *  träfe, wer die Auswahl verlängern will, den Knopf. */
const ABSTAND_MAUS = 8;
const ABSTAND_TOUCH = 34;

/** Solange der Knopf noch nicht gemessen ist — ungefähr seine Größe, damit
 *  der erste Stand schon im Fenster liegt und nicht nachspringt. */
const SCHAETZUNG = { breite: 132, hoehe: 36 };

export type MarkierFrage = {
  /** Die Markierung, aufbereitet — so steht sie als Zitat im Verlauf. */
  text: string;
  /** Was ans Backend geht: die Markierung IN IHRER ZEILE
   *  („… Bäderbetrieb Oldenburg · »8,0 Mio. €« 3,43 %"), s.
   *  `lib/markieren.ts::markierungInZeile`. */
  auswahl: string;
  /** Wurde sie gekürzt? Dann sagt es das Fenster dazu. */
  gekuerzt: boolean;
  /** Der erklärbare Baustein um die Markierung, falls es einen gibt. */
  element: ElementFrage | null;
  /** Wo auf der Seite markiert wurde: „Schulden › Rate-Treppe". */
  pfad: string;
};

type Stand = { frage: MarkierFrage; range: Range };

/** Was als „eine Zeile" gilt: eine Listen- oder Tabellenzeile, ein Absatz,
 *  eine Überschrift. `td` steht bewusst NICHT darin — die Zelle allein wäre
 *  „8,0 Mio. €", erst die Tabellenzeile sagt, wessen. */
const ZEILE = "li, tr, p, dt, dd, h1, h2, h3, h4, h5, h6, figcaption, caption, blockquote, summary, label";

/** Die Zeile, in der die Markierung steht — oder `null`.
 *
 *  Erst die ausdrücklichen Zeilen-Elemente; sonst das nächste Element, das
 *  als Block gesetzt ist (eine `div`-Zeile in einem Raster). Nie über den
 *  Baustein hinaus: Dessen ganzen Text schickt `element` ohnehin mit. */
function zeileVon(range: Range): Element | null {
  const knoten = range.commonAncestorContainer;
  const start = knoten.nodeType === 1 ? (knoten as Element) : knoten.parentElement;
  if (!start) return null;
  const grenze = start.closest("[data-erklaer]");
  const ausdruecklich = start.closest(ZEILE);
  if (ausdruecklich && (!grenze || grenze.contains(ausdruecklich))) return ausdruecklich;
  for (let el: Element | null = start; el && el !== grenze && el !== document.body;
    el = el.parentElement) {
    const d = getComputedStyle(el).display;
    if (!d.startsWith("inline") && d !== "contents") return el;
  }
  return null;
}

/** Ist dieses Element als eigene Zeile oder Spalte gesetzt? Flex- und
 *  Grid-Kinder sind es immer („blockified") — genau so stehen in „Kredite
 *  und Zinsen" Betrag und Zinssatz nebeneinander, ohne ein Leerzeichen im
 *  Quelltext. */
function eigenerBlock(el: Element): boolean {
  return !getComputedStyle(el).display.startsWith("inline");
}

/** Der Text der Zeile VOR und NACH der Markierung.
 *
 *  **Nicht `Range.toString()`**: Das klebt die Texte nebeneinanderstehender
 *  Blöcke ohne Trenner zusammen — aus „8,0 Mio. €" und „3,43 %" würde
 *  „8,0 Mio. €3,43 %". Zwischen zwei Textstücken aus verschiedenen Blöcken
 *  steht hier deshalb ein Leerzeichen. */
function zeilenText(zeile: Element, range: Range): { vor: string; nach: string } {
  let vor = "";
  let nach = "";
  let letzterBlock: Element | null = null;
  const gang = document.createTreeWalker(zeile, NodeFilter.SHOW_TEXT);
  for (let n = gang.nextNode() as Text | null; n; n = gang.nextNode() as Text | null) {
    const eltern = n.parentElement;
    if (!eltern || eltern.closest("script, style, [aria-hidden='true'], [hidden]")) continue;
    let block: Element = eltern;
    while (block !== zeile && !eigenerBlock(block) && block.parentElement) block = block.parentElement;
    const trenner = letzterBlock && block !== letzterBlock ? " " : "";
    letzterBlock = block;
    const daten = n.data;
    const istStart = n === range.startContainer;
    const istEnde = n === range.endContainer;
    if (istStart || istEnde) {
      if (istStart) vor += trenner + daten.slice(0, range.startOffset);
      if (istEnde) nach += (istStart ? "" : trenner) + daten.slice(range.endOffset);
      continue;
    }
    const lage = range.comparePoint(n, 0);
    if (lage < 0) vor += trenner + daten;
    else if (lage > 0) nach += trenner + daten;
    // lage === 0: ganz innerhalb der Markierung — die kommt aus `toString()`.
  }
  return { vor, nach };
}

/** Anfang und Ende einer Auswahl als Rechtecke. `getClientRects` liefert je
 *  Zeile eines — plus leere an Zeilenenden, die hier nichts zu suchen haben. */
function auswahlRechtecke(range: Range): { start: Rechteck; ende: Rechteck } | null {
  const zeilen = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
  if (zeilen.length) return { start: zeilen[0], ende: zeilen[zeilen.length - 1] };
  const r = range.getBoundingClientRect();
  if (!r.width && !r.height) return null;
  return { start: r, ende: r };
}

function istTouch(): boolean {
  return window.matchMedia?.("(pointer: coarse)").matches ?? false;
}

export function MarkierKnopf({ aktiv, anzeigename, onFragen }: {
  aktiv: boolean;
  /** Wird aus dem Überschriften-Pfad gestrichen (lib/assistentin.ts::ohneNamen). */
  anzeigename: string | null;
  onFragen: (frage: MarkierFrage) => void;
}) {
  const [stand, setStand] = useState<Stand | null>(null);
  const [lage, setLage] = useState<KnopfLage | null>(null);
  const knopfRef = useRef<HTMLButtonElement>(null);
  /** Misst die Tab-Leiste: `--rl-unten` ist ein `calc()` mit
   *  `env(safe-area-inset-bottom)`, den nur der Browser auflösen kann. Am
   *  Schreibtisch gibt es die Leiste nicht (`desk:h-0`). */
  const leisteRef = useRef<HTMLSpanElement>(null);
  /** Die erste Tabulatortaste nach einer neuen Markierung führt zum Knopf.
   *  Sonst läge er in der Tab-Reihenfolge irgendwo hinter der App-Hülle —
   *  erreichbar in der Theorie, nach zwanzig Stopps. */
  const tabZumKnopf = useRef(false);
  /** Zieht die Maus gerade eine Auswahl auf? Dann noch keinen Knopf: Er
   *  spränge bei jeder Pause hinter dem Zeiger her. */
  const zieht = useRef(false);

  const weg = useCallback(() => {
    setStand(null);
    setLage(null);
    tabZumKnopf.current = false;
  }, []);

  /** Wo der Knopf zu `range` steht — oder `null`, wenn sie aus dem Bild ist. */
  const vermessen = useCallback((range: Range) => {
    const rechtecke = auswahlRechtecke(range);
    if (!rechtecke) return null;
    const k = knopfRef.current?.getBoundingClientRect();
    return knopfPosition({
      ...rechtecke,
      knopf: k && k.width ? { breite: k.width, hoehe: k.height } : SCHAETZUNG,
      // `clientWidth` ohne Scrollleiste; der Knopf soll nicht unter ihr liegen.
      fenster: { breite: document.documentElement.clientWidth, hoehe: window.innerHeight },
      abstand: istTouch() ? ABSTAND_TOUCH : ABSTAND_MAUS,
      unten: leisteRef.current?.getBoundingClientRect().height ?? 0,
    });
  }, []);

  const lesen = useCallback(() => {
    const sel = document.getSelection();
    const tabu = document.querySelector("[data-lotti-fenster]");
    if (!sel || !auswahlErlaubt(sel, tabu, document.activeElement)) { weg(); return; }
    const aufbereitet = markierungAufbereiten(sel.toString());
    if (!aufbereitet) { weg(); return; }
    const range = sel.getRangeAt(0).cloneRange();
    const knoten = range.commonAncestorContainer;
    const drin = knoten.nodeType === 1 ? (knoten as Element) : knoten.parentElement;
    const baustein = drin?.closest<HTMLElement>("[data-erklaer]") ?? null;
    const startEl = range.startContainer.nodeType === 1
      ? (range.startContainer as Element) : range.startContainer.parentElement;
    // Die Zeile drumherum — nur sie sagt, WELCHE „8,0 Mio. €" gemeint sind.
    const zeile = zeileVon(range);
    const { vor, nach } = zeile ? zeilenText(zeile, range) : { vor: "", nach: "" };
    // Der Anzeigename geht auch über die Zeile nicht mit (auf `/dashboard`
    // steht er in der `h1`) — dieselbe Regel wie beim Überschriften-Pfad.
    // Gestrichen wird im FERTIGEN Text: `ohneNamen` putzt die Ränder, und an
    // den Rändern von `vor`/`nach` stehen die Leerzeichen zur Markierung.
    const mitZeile = markierungInZeile(vor, sel.toString(), nach) ?? aufbereitet;
    const frage: MarkierFrage = {
      ...aufbereitet,
      auswahl: ohneNamen(mitZeile.text, anzeigename) || aufbereitet.text,
      element: baustein ? ernteElement(baustein) : null,
      pfad: ueberschriftenPfad(baustein ?? startEl, document, anzeigename),
    };
    setStand((alt) => {
      // Dieselbe Markierung noch einmal gemeldet (Fokuswechsel, Klick in die
      // Auswahl): nichts Neues, auch kein neuer Tab-Sprung.
      if (alt && alt.frage.text === frage.text && alt.range.compareBoundaryPoints(Range.START_TO_START, range) === 0) {
        return { ...alt, range };
      }
      tabZumKnopf.current = true;
      return { frage, range };
    });
    setLage(vermessen(range));
  }, [anzeigename, vermessen, weg]);

  useEffect(() => {
    if (!aktiv) { weg(); return; }
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onAuswahl = () => {
      clearTimeout(timer);
      const sel = document.getSelection();
      // Leer heißt SOFORT weg — nur das Erscheinen wartet.
      if (!sel || sel.isCollapsed) { weg(); return; }
      if (zieht.current) return;
      timer = setTimeout(lesen, RUHE_MS);
    };
    const onDown = (e: PointerEvent) => {
      if (knopfRef.current?.contains(e.target as Node)) return;
      // Ein Klick daneben: weg. Beginnt damit eine neue Auswahl, meldet sie
      // sich nach dem Loslassen.
      weg();
      if (e.pointerType === "mouse" && e.button === 0) zieht.current = true;
    };
    const onUp = () => {
      if (!zieht.current) return;
      zieht.current = false;
      clearTimeout(timer);
      // Ein Tick Luft: Beim Doppelklick setzt der Browser die Wortauswahl
      // erst NACH dem `pointerup`.
      timer = setTimeout(lesen, 30);
    };
    // Eine Auswahl, die schon VOR dem Einhängen stand, meldet sich nie: Die
    // Funktionsschalter kommen erst mit `/api/app-config`, und wer auf einer
    // frisch geladenen Seite schnell markiert, war schneller als sie.
    onAuswahl();
    document.addEventListener("selectionchange", onAuswahl);
    document.addEventListener("pointerdown", onDown, true);
    document.addEventListener("pointerup", onUp, true);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("selectionchange", onAuswahl);
      document.removeEventListener("pointerdown", onDown, true);
      document.removeEventListener("pointerup", onUp, true);
    };
  }, [aktiv, lesen, weg]);

  // Mitwandern beim Scrollen und Größenwechsel — im nächsten Frame, sonst
  // rechnet man bei jedem Pixel. `capture`, weil auch innere Bereiche
  // scrollen (breite Tabellen, das Fenster selbst).
  useEffect(() => {
    if (!stand) return;
    let frame = 0;
    const planen = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setLage(vermessen(stand.range)));
    };
    window.addEventListener("scroll", planen, { capture: true, passive: true });
    window.addEventListener("resize", planen);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", planen, { capture: true });
      window.removeEventListener("resize", planen);
    };
  }, [stand, vermessen]);

  // Nach dem ersten Zeichnen mit der ECHTEN Größe nachrechnen: Die Schätzung
  // hält den ersten Stand im Fenster, die Messung macht ihn genau.
  useLayoutEffect(() => {
    if (!stand || !lage || !knopfRef.current) return;
    const neu = vermessen(stand.range);
    if (neu && (neu.x !== lage.x || neu.y !== lage.y)) setLage(neu);
  }, [stand, lage, vermessen]);

  // Esc und Tab. **Esc schließt nur den Knopf**, nicht auch gleich Lottis
  // Fenster — dieselbe Regel wie beim aufgeklappten Fachwort: Esc nimmt das
  // Oberste weg, nicht alles. Deshalb in der Capture-Phase und mit
  // `stopPropagation`: Das Fenster hört auf `window` in der Bubble-Phase.
  useEffect(() => {
    if (!stand || !lage) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        weg();
        return;
      }
      if (e.key === "Tab" && !e.shiftKey && !e.altKey && !e.metaKey && !e.ctrlKey
          && tabZumKnopf.current && document.activeElement !== knopfRef.current) {
        e.preventDefault();
        tabZumKnopf.current = false;
        knopfRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [stand, lage, weg]);

  if (!aktiv) return null;

  return (
    <>
      <span ref={leisteRef} aria-hidden
        className="pointer-events-none invisible fixed bottom-0 left-0 w-0 h-[var(--rl-unten,0px)] desk:h-0" />
      {stand && lage && (
        <button
          ref={knopfRef}
          type="button"
          data-lotti-markierknopf
          // Die Auswahl nicht wegklicken: Ein `mousedown` auf einen Knopf
          // beginnt sonst eine neue (leere) Auswahl, und die Kontext-Pille
          // im Fenster sähe nichts mehr.
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            onFragen(stand.frage);
            weg();
            // Auf dem Handy steht das Fenster über der Seite; das Menü des
            // Systems hinge sonst über ihm. Am Schreibtisch bleibt die
            // Markierung stehen — man sieht neben dem Fenster, wonach man
            // gefragt hat, und die nächste Frage bezieht sich weiter darauf.
            if (istTouch()) document.getSelection()?.removeAllRanges();
          }}
          aria-label={`Lotti fragen: Was bedeutet „${stand.frage.text.length > 60
            ? `${[...stand.frage.text].slice(0, 60).join("")} …` : stand.frage.text}“?`}
          style={{ left: lage.x, top: lage.y }}
          className={cn(
            "fixed z-50 flex items-center gap-1.5 rounded-full border border-primary/30 bg-card",
            "py-1 pl-1 pr-3 text-[13px] font-medium text-primary shadow-lifted print:hidden",
            "select-none touch-manipulation",
            // Touch braucht die volle Bedienhöhe (44 px, Designsprache § 6),
            // die Maus nicht.
            "h-11 maus:h-9",
            "animate-in fade-in-0 zoom-in-95 duration-fluss ease-out-strong",
            lage.lage === "ueber" ? "slide-in-from-bottom-1" : "slide-in-from-top-1",
            "motion-reduce:animate-none",
            "transition-colors duration-tipp maus:hover:bg-primary/[0.06]",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          )}
        >
          <span className="flex h-7 w-7 flex-none items-center justify-center overflow-hidden rounded-full bg-primary">
            <Image
              src="/lotti/kopf.png"
              alt=""
              width={192}
              height={192}
              className="pointer-events-none h-9 w-9 max-w-none translate-y-[2px] select-none"
            />
          </span>
          Lotti fragen
        </button>
      )}
    </>
  );
}
