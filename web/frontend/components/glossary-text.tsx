"use client";

import {
  Fragment, createContext, useCallback, useContext, useEffect, useMemo, useRef,
  useState, type ReactNode,
} from "react";
import { GLOSSARY } from "@/lib/glossary";
// Die Erkennung steht in `lib/glossar-treffer.ts` — dieselbe, die Lottis
// Anschluss-Chip „Was heißt …?" benutzt. Zwei Fassungen hätten unterstrichen,
// was kein Chip anbietet, und umgekehrt.
import { BEGRIFF_KANON as CANON, BEGRIFF_RE as RE } from "@/lib/glossar-treffer";

/**
 * Die AUFKLAPP-Fassung: ein Block unter dem Absatz statt eines Popovers.
 *
 * **Warum es zwei Formen gibt.** Der Popover liegt `absolute left-0 top-full`
 * und ist bis zu 17 rem breit. In einer Seitenspalte ist das richtig; in
 * Lottis Fenster (384 px, `overflow-hidden`) ist es falsch: Steht das Wort
 * rechts, schneidet der Fensterrand die Erklärung ab — Tims Befund am
 * 22.09.2026 („Wirtschaftsplan" halb sichtbar). Gemessen: ein Begriff, der
 * bei x = 210 px im Fenster beginnt, braucht 272 px und hat 174 px.
 *
 * Ein Popover, der sich nach links ausrichtet, wäre die andere Lösung
 * gewesen — sie scheitert am `overflow-hidden` des Fensters, das jede Ebene
 * darin beschneidet, egal wohin sie zeigt. Also: kein Überhang, sondern ein
 * Block IM Textfluss, unter der Antwort.
 *
 * Wer diese Form will, legt `GlossarAufklappBereich` um den Text. Alles
 * darin schaltet um; alles ohne den Bereich bleibt beim Popover.
 */
type Aufgeklappt = { label: string; def: string } | null;

const AufklappKontext = createContext<{
  auswahl: Aufgeklappt;
  waehlen: (a: Aufgeklappt) => void;
} | null>(null);

/**
 * Der Bereich, in dem Fachwörter nach UNTEN aufklappen statt zu überlagern.
 *
 * Der Block steht hinter `children`, nicht im Wort: Mitten im Satz würde er
 * die Zeile aufreißen und den Absatz beim Lesen umbauen. Unter dem Absatz
 * bleibt der Text, wo er war, und die Erklärung steht wie eine stille
 * Zwischenzeile darunter.
 *
 * **Nur EIN Block je Bereich.** Ein zweites Wort ersetzt das erste — in
 * 384 px Breite sind zwei offene Erklärungen unter einem Absatz eine
 * Bleiwüste. Der Bereich gehört deshalb um EINE Antwort, nicht um den
 * ganzen Verlauf.
 */
export function GlossarAufklappBereich(
  { children, className }: { children: ReactNode; className?: string },
) {
  const [auswahl, setAuswahl] = useState<Aufgeklappt>(null);
  const waehlen = useCallback((a: Aufgeklappt) => setAuswahl(a), []);
  const wert = useMemo(() => ({ auswahl, waehlen }), [auswahl, waehlen]);
  // Esc schließt — auch wenn der Fokus inzwischen woanders steht (man klappt
  // auf, liest, scrollt weiter). Nur registriert, solange etwas offen ist.
  useEffect(() => {
    if (!auswahl) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      // Das Fenster der Assistentin schließt sich ebenfalls auf Esc. Solange
      // eine Erklärung offen steht, nimmt sie den Tastendruck für sich —
      // sonst verschwindet mit dem ersten Esc gleich das ganze Fenster.
      e.stopPropagation();
      setAuswahl(null);
    };
    // In der Erfassungsphase, damit der Griff vor dem Fenster-Handler sitzt.
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [auswahl]);
  return (
    <AufklappKontext.Provider value={wert}>
      <div className={className}>
        {children}
        {auswahl && (
          <div
            data-glossar-aufklapp
            role="note"
            className="mt-2 rounded-lg border border-border bg-muted/40 p-2.5 text-left text-xs font-normal normal-case leading-relaxed text-muted-foreground"
          >
            <span className="mb-0.5 block font-semibold text-foreground">{auswahl.label}</span>
            {auswahl.def}
          </div>
        )}
      </div>
    </AufklappKontext.Provider>
  );
}

/** Ein erklärter Fachbegriff: gepunktet unterstrichen, zeigt beim Überfahren
 *  (Desktop) bzw. Antippen (mobil) eine kurze Erklärung. */
function Term({ label, def }: { label: string; def: string }) {
  const aufklapp = useContext(AufklappKontext);
  if (aufklapp) return <TermAufklapp label={label} def={def} ctx={aufklapp} />;
  return <TermPopover label={label} def={def} />;
}

/** Die Fassung für schmale Flächen: der Block steht unter dem Absatz. */
function TermAufklapp({ label, def, ctx }: {
  label: string; def: string;
  ctx: { auswahl: Aufgeklappt; waehlen: (a: Aufgeklappt) => void };
}) {
  const offen = ctx.auswahl?.label === label;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const umschalten = () => ctx.waehlen(offen ? null : { label, def });
  // Am Zeigergerät reicht Überfahren — mit kurzer Ruhepause, damit ein
  // Mauszeiger, der nur über den Satz fährt, nicht drei Erklärungen
  // nacheinander aufklappt. `maus:` gibt es nur als Tailwind-Variante, im
  // Ereignis-Code muss dieselbe Frage von Hand gestellt werden.
  const zeigergeraet = () =>
    typeof window !== "undefined" && window.matchMedia?.("(pointer: fine)").matches;
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); umschalten(); }}
      onMouseEnter={() => {
        if (!zeigergeraet()) return;
        timer.current = setTimeout(() => ctx.waehlen({ label, def }), 220);
      }}
      onMouseLeave={() => { if (timer.current) clearTimeout(timer.current); }}
      // Kein Schließen beim Verlassen: Der Block steht unter dem Absatz, nicht
      // am Wort — der Weg dorthin führte über „außerhalb", und die Erklärung
      // wäre weg, bevor man sie gelesen hat.
      aria-expanded={offen}
      aria-label={`Was bedeutet ${label}?`}
      className="max-w-full cursor-help whitespace-normal break-words border-b border-dotted border-primary/70 text-left font-medium text-inherit"
    >
      {label}
    </button>
  );
}

/** Die Fassung für breite Flächen: ein Popover am Wort. */
function TermPopover({ label, def }: { label: string; def: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [open]);
  return (
    <span ref={ref} className="relative inline-block max-w-full">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="max-w-full cursor-help whitespace-normal break-words border-b border-dotted border-primary/70 text-left font-medium text-inherit"
        aria-label={`Was bedeutet ${label}?`}
      >
        {label}
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-1 block w-[min(17rem,78vw)] rounded-lg border border-border bg-background p-2.5 text-left text-xs font-normal normal-case leading-relaxed text-muted-foreground shadow-lg"
        >
          <span className="mb-0.5 block font-semibold text-foreground">{label}</span>
          {def}
        </span>
      )}
    </span>
  );
}

/**
 * Ein Stück Text mit erklärten Fachbegriffen darin — als Knotenliste, damit
 * auch Aufrufer sie benutzen können, die den Text schon selbst zerlegt haben
 * (der Antworttext der KI-Frage tut das: Fußnoten-Chips, Fettdruck,
 * Personen-Badges).
 *
 * `gesehen` markiert nur die ERSTE Nennung eines Begriffs — dieselbe Regel wie
 * bei den Personen-Badges. Über eine lange Antwort verteilt wäre „Bebauungsplan"
 * fünfmal unterringelt: Das liest sich wie ein Fehler, nicht wie ein Angebot.
 * Ohne das Set wird jede Nennung markiert (so verhalten sich die
 * Haushalts-Seiten seit jeher).
 */
export function markiereBegriffe(
  text: string, keyBase: string | number = "g", gesehen?: Set<string>,
): ReactNode[] {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(RE)) {
    const key = CANON.get(m[1].toLowerCase());
    if (!key || gesehen?.has(key)) continue;
    gesehen?.add(key);
    const idx = m.index ?? 0;
    if (idx > last) parts.push(text.slice(last, idx));
    parts.push(<Term key={`${keyBase}-${idx}`} label={m[0]} def={GLOSSARY[key]} />);
    last = idx + m[0].length;
  }
  if (parts.length === 0) return [text];
  parts.push(text.slice(last));
  return parts;
}

/** Rendert Text und unterlegt bekannte Fachbegriffe mit einer Hover-Erklärung. */
export function GlossaryText({ text, className }: { text: string | null | undefined; className?: string }) {
  if (!text) return null;
  return (
    <span className={className}>
      {markiereBegriffe(text).map((n, i) => <Fragment key={i}>{n}</Fragment>)}
    </span>
  );
}
