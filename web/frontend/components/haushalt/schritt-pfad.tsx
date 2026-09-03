"use client";

// Der Schritt-Pfad im Kopf jeder Schritt-Seite — Nachfolger der Zeichen-Kachel
// (Design H5-09; die Kachel stand hier seit 24.08., „hässlich", Tim 26.08.).
//
// Die Kachel wiederholte das Zeichen des Schritts und sagte sonst nichts. Der
// Pfad zeigt stattdessen, WO im Weg man steht: zwölf Punkte in den vier
// Etappen-Gruppen des Wegweisers, besuchte Seiten gefüllt (derselbe lokale
// Lesestand wie dort, lib/haushalt-fortschritt.ts), die aktuelle als Ring.
// Die Zeichen selbst bleiben an den kleinen Orten — Wegweiser-Zeile,
// Weiter-Fuß und das Fähnchen hier.
//
// Bis zur Hydration ist der Lesestand leer (Server und erster Client-Render
// deterministisch gleich, wie beim Wegweiser) — dann sind alle Punkte offen
// und nur der Ring gesetzt.
//
// Unter 640 px verschwindet er ersatzlos, wie vorher die Kachel: Mobil gibt
// es die leere Ecke rechts neben dem gedeckelten Kopf-Absatz nicht, und die
// Bühne darunter trägt die Schritt-Auskunft in ihrem Kicker mit. Kein
// erfundener Stand: Seiten ohne Schritt (Steckbriefe) bekommen keinen Pfad.
//
// DIE PUNKTE SIND DIE NAVIGATION (26.08., Tim: „ein bisschen interaktiver").
// Bis dahin war der ganze Pfad EIN Link zum Wegweiser: Die zwölf Punkte
// zeigten den Stand, führten aber alle an dieselbe Stelle — man sah, dass es
// einen Schritt 3 gibt, konnte aber weder erfahren, was darin steht, noch
// hingehen. Jeder Punkt ist jetzt ein eigener Link auf seine Seite, und wer
// darauf zeigt, liest ihren Titel. Drei Dinge gehören zu dieser Form:
//
//  * **Die Zeile darunter bleibt, wie sie war.** „Schritt 11 von 12 ·
//    Mitreden" führt weiter zum Wegweiser und sagt, wo man IST; das Fähnchen
//    sagt, worauf man ZEIGT. Zwei Aussagen, zwei Orte — das Fähnchen
//    überschreibt den Stand nicht, und ohne Zeiger steht er trotzdem da.
//  * **Das Fähnchen steht ÜBER dem Pfad und ist absolut gesetzt**, im leeren
//    Streifen rechts neben der Brotkrume. Es muss aus dem Fluss heraus: Ein
//    Titel wie „Was gebaut wird — und was daraus wurde" ist gut doppelt so
//    breit wie die Zeile darunter, und läge er im Fluss, ruckelte bei jedem
//    Zeigen die Überschrift daneben.
//
//    Das ist die bewusste Ausnahme von der Leisten-Regel des Grafik-Baukastens
//    (`components/grafik/ablesen.tsx`: „Ein Tooltip ist immer die zweite
//    Wahl"). Dort trägt die Leiste den Messwert, den es sonst nirgends zu
//    lesen gibt — hier ist der Titel ohnehin dauerhaft im Wegweiser
//    ausgeschrieben, steht am Link als `aria-label` und die Zeile unter den
//    Punkten zeigt auch ohne jedes Zeigen, wo man steht. Wer den Pfad
//    ausdruckt oder vorlesen lässt, verliert also nichts.
//  * **Die Fangfläche ist größer als der Punkt** — 12 × 22 px um einen 7-px-
//    Punkt — und hängt in negativen Rändern: Sichtbar bleibt der Pfad so
//    flach wie vorher, greifbar ist er weit darüber hinaus. Die Punkte
//    stehen dafür ein wenig weiter auseinander als vor dem Umbau; der Pfad
//    bleibt schmaler als die Zeile darunter, die Blockbreite ändert sich
//    also nicht.
//
// Vergrößert wird der Punkt aus dem React-Zustand heraus, nicht per
// `:hover` — dann gilt dieselbe Hervorhebung für die Tastatur (`focus`), und
// das Fähnchen, das ohnehin am Zustand hängt, kann nicht danebenliegen.

import { useState } from "react";
import Link from "next/link";
import { ETAPPEN, SCHRITTE } from "@/components/haushalt/wegweiser";
import { useFortschritt } from "@/lib/haushalt-fortschritt";
import { cn } from "@/lib/utils";

type Zustand = "aktuell" | "gelesen" | "offen";

/** Der Punkt selbst — die Fangfläche darum steckt im Link, damit sich die
 *  sichtbare Größe unabhängig von der greifbaren wählen lässt. */
function Punkt({ zustand, zeigt }: { zustand: Zustand; zeigt: boolean }) {
  return (
    <span
      className={cn(
        "block flex-none rounded-full transition-[transform,background-color,box-shadow,border-color] duration-150 ease-out",
        zustand === "aktuell"
          ? "h-2 w-2 border-2 border-primary bg-card shadow-[0_0_0_3px_hsl(var(--primary)/0.14)]"
          : zustand === "gelesen"
            ? "h-[7px] w-[7px] bg-primary"
            : "h-[7px] w-[7px] bg-border",
        zeigt && "scale-[1.6]",
        // Der offene Punkt färbt sich beim Zeigen an — sonst wäre die
        // Vergrößerung eines grauen Punkts die einzige Rückmeldung, und die
        // ist bei 7 px kaum zu sehen. Halbe Deckkraft, nicht voll: Er ist
        // damit angetippt, nicht plötzlich gelesen.
        zeigt && zustand === "offen" && "bg-primary/45",
        zeigt && zustand !== "aktuell" && "shadow-[0_0_0_3px_hsl(var(--primary)/0.16)]",
      )}
    />
  );
}

export function SchrittPfad({ href, className }: {
  href: string;
  className?: string;
}) {
  const besucht = useFortschritt();
  // `zuletzt` hält den Titel im Fähnchen fest, während es ausblendet — sonst
  // spränge der Text beim Weggehen des Zeigers auf den aktuellen Schritt um,
  // mitten in der Blende.
  const [gezeigt, setGezeigt] = useState<number | null>(null);
  const [zuletzt, setZuletzt] = useState<number | null>(null);

  const schritt = SCHRITTE.find((s) => s.href === href);
  if (!schritt) return null;
  const etappe = ETAPPEN.find((e) => schritt.nr >= e.von && schritt.nr <= e.bis)!;

  const zeige = (nr: number | null) => {
    setGezeigt(nr);
    if (nr !== null) setZuletzt(nr);
  };

  const zeig = SCHRITTE.find((s) => s.nr === (gezeigt ?? zuletzt ?? schritt.nr))!;
  const zustandVon = (nr: number, ziel: string): Zustand =>
    nr === schritt.nr ? "aktuell" : besucht.has(ziel) ? "gelesen" : "offen";

  return (
    <nav
      aria-label="Der Weg durch den Haushalt"
      onPointerLeave={() => zeige(null)}
      className={cn(
        "relative hidden flex-none flex-col items-end gap-[5px] pt-1.5 sm:flex",
        className,
      )}
    >
      {/* Das Fähnchen: immer im DOM, damit es ein- und ausblenden kann.
          `aria-hidden`, weil jeder Punkt seinen Titel schon als `aria-label`
          trägt — vorgelesen wäre es die zweite Stimme zur selben Sache. */}
      <span
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute bottom-full right-0 mb-1.5 flex items-center gap-1.5",
          "whitespace-nowrap rounded-lg border border-border bg-card px-2 py-1 shadow-sm",
          "transition-[opacity,transform] duration-150 ease-out",
          // Gedeckelt, damit das Fähnchen der Brotkrume links nicht ins Wort
          // fährt: Sie steht in derselben Zeile und wächst mit dem Titel der
          // Seite. Bei 640 px — dem schmalsten Fenster, in dem es den Pfad
          // überhaupt gibt — blieben zwischen dem längsten Krümel und dem
          // längsten Fähnchen sonst 12 px. 60 vw lassen ihr sicher Platz;
          // gekürzt wird dabei einzig „Was gebaut wird — und was daraus
          // wurde" auf der eigenen Seite, und auch das nur unter ~740 px.
          "max-w-[min(460px,60vw)] overflow-hidden",
          gezeigt !== null ? "translate-y-0 opacity-100" : "translate-y-[3px] opacity-0",
        )}
      >
        <zeig.zeichen size={12} strokeWidth={2} className="flex-none text-muted-foreground" />
        <span className="font-mono text-[9px] font-medium uppercase tracking-[0.1em] tabular-nums text-muted-foreground">
          Schritt {zeig.nr}
        </span>
        <span className="min-w-0 truncate text-[11.5px] font-semibold leading-none text-foreground">
          {zeig.title}
        </span>
        {zeig.nr === schritt.nr && (
          <span className="font-mono text-[9px] font-medium uppercase tracking-[0.09em] text-primary">
            Du bist hier
          </span>
        )}
      </span>

      {/* Die negativen Ränder machen die 22-px-Fangflächen wieder so flach,
          wie die Punkte aussehen (22 − 2 × 7 = 8 px) — der Abstand zur Zeile
          darunter bleibt damit derselbe wie vor dem Umbau. */}
      <span className="-my-[7px] flex items-center gap-[5px]">
        {ETAPPEN.map((e) => (
          <span key={e.kicker} className="flex items-center">
            {SCHRITTE.slice(e.von - 1, e.bis).map((s) => {
              const zustand = zustandVon(s.nr, s.href);
              return (
                <Link
                  key={s.nr}
                  href={s.href}
                  aria-current={zustand === "aktuell" ? "page" : undefined}
                  aria-label={`Schritt ${s.nr}: ${s.title}${
                    zustand === "aktuell" ? " (diese Seite)"
                      : zustand === "gelesen" ? " (schon aufgerufen)" : ""
                  }`}
                  onPointerEnter={() => zeige(s.nr)}
                  onFocus={() => zeige(s.nr)}
                  onBlur={() => zeige(null)}
                  className="flex h-[22px] w-3 items-center justify-center rounded-[3px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Punkt zustand={zustand} zeigt={gezeigt === s.nr} />
                </Link>
              );
            })}
          </span>
        ))}
      </span>

      {/* Der Weg als Ganzes bleibt einen Klick entfernt: Wer wissen will, was
          ALLE Punkte heißen, landet an der Liste, die sie erklärt. */}
      <Link
        href="/haushalt#wegweiser"
        className="font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-muted-foreground transition-colors hover:text-primary"
      >
        Schritt {schritt.nr} von {SCHRITTE.length} · {etappe.kicker}
      </Link>
    </nav>
  );
}
