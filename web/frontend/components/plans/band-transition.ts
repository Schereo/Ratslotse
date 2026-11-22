"use client";

// Übersicht → Planseite: Das Zeitband der Zeile wird zum Band im Kopf des Plans.
//
// Die Bewegung erklärt, dass es DASSELBE Band ist — in der Übersicht auf der
// gemeinsamen Achse aller Pläne, auf der Planseite auf seiner eigenen
// (DESIGNSPRACHE § 7: Bewegung zeigt, wo etwas herkommt). Gebaut mit der View
// Transitions API des Browsers; alles hier ist Zugabe:
//
//  • Kann der Browser es nicht, ist der Klick ein gewöhnlicher Link.
//  • Bei `prefers-reduced-motion` ebenso.
//  • Strg/Cmd/Shift/Mitteltaste bleiben beim Browser (neuer Tab).
//  • Kommt die Planseite nicht rechtzeitig (langsames Netz), läuft die
//    Navigation ohne Bild weiter — der Übergang wartet höchstens WAIT_MS.
//
// Der Ablauf: Die Zeile bekommt den Namen `plan-band`, der Browser hält das
// alte Bild fest, Next navigiert. Die Planseite lädt ihren Plan nach; ihr
// Zeitband trägt denselben Namen (`data-plan-band`). Erst wenn es im Dokument
// steht, gibt die Funktion das neue Bild frei — sonst flöge das Band auf ein
// Skelett zu.

const NAME = "plan-band";
const WAIT_MS = 900;

let underway = false;

/** Läuft gerade ein Übergang auf die Planseite? Dann baut sich ihr Zeitband
 *  nicht noch einmal auf — es kommt ja schon an. */
export function arrivingByBand(): boolean {
  return underway;
}

type Starter = (update: () => Promise<void>) => { finished: Promise<void> };

export function bandTransition(e: React.MouseEvent, lane: HTMLElement | null): void {
  const start = (document as unknown as { startViewTransition?: Starter }).startViewTransition;
  if (!start || !lane || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  // Kein `preventDefault`: Next navigiert über seinen eigenen Klick-Handler am Link. Der Übergang
  // beginnt hier, vor der Navigation — der Browser hält das alte Bild im nächsten Frame fest, und
  // die Planseite braucht länger als einen Frame, bis sie im Dokument steht.
  lane.style.setProperty("view-transition-name", NAME);
  underway = true;
  const clear = () => { underway = false; lane.style.removeProperty("view-transition-name"); };
  try {
    const transition = start.call(document, () => new Promise<void>((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        observer.disconnect();
        window.clearTimeout(timer);
        resolve();
      };
      const observer = new MutationObserver(() => { if (document.querySelector("[data-plan-band]")) finish(); });
      observer.observe(document.body, { childList: true, subtree: true });
      const timer = window.setTimeout(finish, WAIT_MS);
    }));
    transition.finished.then(clear, clear);
  } catch {
    clear();
  }
}
