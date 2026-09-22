"use client";

import Image from "next/image";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Der schwebende Lotti-Knopf — unten rechts, auf jeder Seite, auf jedem Gerät.
 *
 * **Die Bauform ist Absicht** (Tim, 21.09.2026): der Chat-Knopf, wie man ihn
 * von Hilfe- und Sales-Seiten kennt. Der erste Entwurf hatte ihn auf dem Handy
 * in die Kopfleiste gelegt, mit Verweis auf Design 9a③ („kein FAB mehr") —
 * das war zu vorsichtig gelesen: 9a③ hat den **Navigations**-FAB aus der
 * Tab-Leiste genommen, den angehobenen „Fragen"-Knopf. Ein Chat-Knopf ist
 * keine Navigation.
 *
 * **Wo er sitzt, rechnet er sich aus zwei Variablen zusammen**, nie aus einer
 * eigenen Zahl:
 * - `--rl-unten` ist die Höhe der Tab-Leiste (aus `components/nav.tsx`, im
 *   App-Layout gesetzt). Darüber muss er liegen, sonst verdeckt er sie.
 * - `--rl-composer` ist die Höhe des Andock-Composers auf `/fragen` (dort live
 *   gemessen, weil sie mit Chips und Karten wächst). Ohne sie läge der Knopf
 *   genau auf dem Senden-Pfeil — derselbe Konflikt, wegen dem `BackToTop` auf
 *   der Fragen-Seite gar nicht erst erscheint.
 *
 * `z-50`, damit er über der Tab-Leiste (`z-40`) und dem Composer liegt.
 *
 * **Das Gesicht ist die 3D-Lotti, nicht das flache Logo** (Tims Wunsch
 * 21.09.2026). Der Kopf ist aus dem Standbild der Ruhe-Pose geschnitten
 * (`public/lotti/kopf.png`, 192 px, aus `standbild-ruht.png`) — die anderen
 * Posen taugen nicht: `mag-das` hat geschlossene Augen und sähe auf einem
 * Knopf aus wie eingeschlafen, bei `lacht` verdeckt die Mütze die Augen.
 * Die runde Fläche kommt aus dem CSS und nicht aus dem Bild, damit sie im
 * Dunkelmodus den dortigen Primärton nimmt; der Kopf ist etwas größer als
 * der Kreis und wird von ihm beschnitten — wie ein Porträt.
 *
 * **Unter dem Zeiger schaut Lotti auf** (Tims Wunsch 22.09.2026: „dass ich
 * außerhalb des Mauszeigers weiß, dass ich den anklicken kann"). Der Knopf
 * hebt sich 2 px, der Schatten öffnet sich (`shadow-knopf-hover`), und der
 * Kopf darin richtet sich auf: aus seinen +3 px auf 0, 6° geneigt, 5 %
 * größer. Alles in `duration-fluss`/`ease-out-strong`, alles in einem Zug —
 * eine Regung, kein Effekt, und nichts, was ohne Zeiger von allein läuft
 * (Regel „Endlos laufende Bewegung braucht eine Pause", § 7).
 *
 * Drei Gitter davor, jedes aus einer eigenen Regel:
 * - `maus:` (pointer: fine) statt `hover:` — Touch-Browser lassen den Hover
 *   nach dem Tippen kleben; auf dem Handy darf sich gar nichts ändern.
 * - `motion-safe:` nur um die Bewegung, nicht um Farbe und Schatten: Wer
 *   reduzierte Bewegung eingestellt hat, soll trotzdem sehen, dass hier
 *   etwas anklickbar ist.
 * - Der Fokus-Ring bleibt unangetastet. Er ist in Tailwind ein eigener
 *   Box-Shadow-Kanal (`--tw-ring-shadow`); der Hover-Schatten füllt
 *   `--tw-shadow` und verdrängt ihn deshalb nicht.
 */
export function LottiKnopf({ offen, onToggle, className }: {
  offen: boolean;
  onToggle: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={offen}
      aria-controls="lotti-fenster"
      aria-label={offen ? "Lotti schließen" : "Lotti fragen"}
      data-lotti-knopf
      className={cn(
        "group fixed right-4 z-50 flex h-14 w-14 items-center justify-center rounded-full",
        "overflow-hidden bg-primary text-primary-foreground shadow-lifted print:hidden",
        "transition-[transform,background-color,box-shadow] duration-fluss ease-out-strong",
        // Der Zeiger-Zustand (s. Kopfkommentar): Farbe und Schatten IMMER,
        // das Anheben nur unter `motion-safe`. `maus:` statt blankem `hover:`,
        // weil Touch-Browser den Hover nach dem Tippen kleben lassen — der
        // Knopf bliebe dann angehoben stehen, ohne dass ein Zeiger da wäre.
        "maus:hover:bg-primary/90 maus:hover:shadow-knopf-hover",
        "maus:motion-safe:hover:-translate-y-0.5",
        "active:scale-95",
        // Die Tastatur bleibt der lauteste Zustand: Der Ring ist ein eigener
        // Box-Shadow-Kanal (`--tw-ring-shadow`) und wird vom Hover-Schatten
        // nicht überschrieben — beides steht nebeneinander.
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        // Über Tab-Leiste UND Composer. `--rl-composer` ist 0, wo es keinen
        // gibt — die Formel gilt damit auf jeder Seite unverändert.
        "bottom-[calc(var(--rl-unten,0px)+var(--rl-composer,0px)+0.75rem)]",
        "desk:right-6 desk:bottom-[calc(var(--rl-composer,0px)+1.5rem)]",
        className,
      )}
    >
      {offen
        ? <X className="h-6 w-6" aria-hidden />
        : (
          <Image
            src="/lotti/kopf.png"
            alt=""
            width={192}
            height={192}
            priority
            // Größer als der Kreis (70 px in 56 px) und leicht nach unten gerückt:
            // Der Kopf soll die Fläche FÜLLEN und vom Rand beschnitten werden wie
            // ein Porträt. Passgenau eingesetzt bliebe rundherum Blau stehen, und
            // die Figur sähe verloren aus.
            // Der Kopf hebt sich und neigt sich, sobald ein Zeiger da ist:
            // aus +3 px auf 0 und 6° nach links, dazu ein Hauch Vergrößerung.
            // Das ist eine Regung, kein Effekt — dieselbe Bewegung, die die
            // 3D-Lotti macht, wenn sie aufschaut. `data-[offen]` gibt es
            // nicht: Offen steht hier das Kreuz, nicht der Kopf.
            className={cn(
              "pointer-events-none h-[4.4rem] w-[4.4rem] translate-y-[3px] select-none",
              "transition-transform duration-fluss ease-out-strong",
              "maus:motion-safe:group-hover:translate-y-[1px]",
              "maus:motion-safe:group-hover:-rotate-[5deg] maus:motion-safe:group-hover:scale-[1.03]",
            )}
          />
        )}
    </button>
  );
}
