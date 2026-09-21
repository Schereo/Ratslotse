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
        "fixed right-4 z-50 flex h-14 w-14 items-center justify-center rounded-full",
        "overflow-hidden bg-primary text-primary-foreground shadow-lifted print:hidden",
        "transition-[transform,background-color] duration-tipp ease-out-strong",
        "hover:bg-primary/90 active:scale-95",
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
            className="pointer-events-none h-[4.4rem] w-[4.4rem] translate-y-[3px] select-none"
          />
        )}
    </button>
  );
}
