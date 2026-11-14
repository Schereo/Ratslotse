"use client";

/* Fachwörter am Wort auf Punkt-, Beschluss- und Sitzungsseite: gepunktet unterstrichen, die
   Erklärung klappt unter dem Absatz auf (dieselbe Form wie in Lottis Fenster,
   `components/glossary-text.tsx`). Welche Wörter, entscheidet der Server —
   je Begriff nur die erste Nennung auf der Seite (`council/seitenbegriffe.py`). */

import { Fragment, createContext, useContext, type ReactNode } from "react";
import { Fachwort, GlossarAufklappBereich } from "@/components/glossary-text";
import { fuerKarte, zerlege, type SeitenBegriff } from "@/lib/seitenbegriffe";

const LEER: readonly SeitenBegriff[] = [];
const Kontext = createContext<readonly SeitenBegriff[]>(LEER);

/** Um die Seite: reicht die Begriffe des Punkts an alle Lesetexte darin. */
export function SeitenBegriffe({ begriffe, children }: { begriffe?: SeitenBegriff[] | null; children: ReactNode }) {
  return <Kontext.Provider value={begriffe ?? LEER}>{children}</Kontext.Provider>;
}

/** Ein Lesetext mit seinen erklärten Fachwörtern. Ohne `SeitenBegriffe`
 *  darum (Beschluss-Vorschau, Mitlesen) bleibt er schlichter Text. */
export function Erklaert({ text, punkt }: {
  text: string;
  /** Sitzungsseite: die Nummer des Punkts dieser Karte. Fundstellen, die der
   *  Server einer anderen Karte zugeordnet hat (`item`), gelten hier nicht —
   *  gleichlautende Kurzfassungen trügen sonst alle dieselbe Unterstreichung. */
  punkt?: string;
}) {
  const begriffe = fuerKarte(useContext(Kontext), punkt);
  if (begriffe.length === 0) return <>{text}</>;
  return (
    <>
      {zerlege(text, begriffe).map((s, i) => (typeof s === "string"
        ? <Fragment key={i}>{s}</Fragment>
        : <Fachwort key={i} label={s.text} def={s.begriff.explanation} ki={s.begriff.kind === "document"} />))}
    </>
  );
}

/** Der Absatz, unter dem die Erklärung aufklappt — je Absatz einer, damit sie
 *  direkt unter dem Satz steht, in dem das Wort vorkommt. */
export function ErklaerBereich({ children, className, nurKlick }: {
  children: ReactNode; className?: string;
  /** In einer Liste von Karten: aufklappen nur beim Klick (s. `GlossarAufklappBereich`). */
  nurKlick?: boolean;
}) {
  return <GlossarAufklappBereich lesegroesse nurKlick={nurKlick} className={className}>{children}</GlossarAufklappBereich>;
}
