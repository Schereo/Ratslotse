"use client";

/* Fachwörter am Wort auf der Punkt-Seite: gepunktet unterstrichen, die
   Erklärung klappt unter dem Absatz auf (dieselbe Form wie in Lottis Fenster,
   `components/glossary-text.tsx`). Welche Wörter, entscheidet der Server —
   je Begriff nur die erste Nennung auf der Seite (`council/seitenbegriffe.py`). */

import { Fragment, createContext, useContext, type ReactNode } from "react";
import { Fachwort, GlossarAufklappBereich } from "@/components/glossary-text";
import { zerlege, type SeitenBegriff } from "@/lib/seitenbegriffe";

const LEER: readonly SeitenBegriff[] = [];
const Kontext = createContext<readonly SeitenBegriff[]>(LEER);

/** Um die Seite: reicht die Begriffe des Punkts an alle Lesetexte darin. */
export function SeitenBegriffe({ begriffe, children }: { begriffe?: SeitenBegriff[] | null; children: ReactNode }) {
  return <Kontext.Provider value={begriffe ?? LEER}>{children}</Kontext.Provider>;
}

/** Ein Lesetext mit seinen erklärten Fachwörtern. Ohne `SeitenBegriffe`
 *  darum (Beschluss-Seite, Mitlesen) bleibt er schlichter Text. */
export function Erklaert({ text }: { text: string }) {
  const begriffe = useContext(Kontext);
  if (begriffe.length === 0) return <>{text}</>;
  return (
    <>
      {zerlege(text, begriffe).map((s, i) => (typeof s === "string"
        ? <Fragment key={i}>{s}</Fragment>
        : <Fachwort key={i} label={s.text} def={s.begriff.explanation} />))}
    </>
  );
}

/** Der Absatz, unter dem die Erklärung aufklappt — je Absatz einer, damit sie
 *  direkt unter dem Satz steht, in dem das Wort vorkommt. */
export function ErklaerBereich({ children, className }: { children: ReactNode; className?: string }) {
  return <GlossarAufklappBereich lesegroesse className={className}>{children}</GlossarAufklappBereich>;
}
