"use client";

/**
 * Der Story-Spieler zu „Neu bei Ratslotse" — ein Tipp auf eine Video-Kachel
 * öffnet ihn (`components/release-news-card.tsx`).
 *
 * **Ein echter Dialog** (Radix): Fokusfalle, `Esc` schließt, der Fokus kehrt
 * zur Kachel zurück. Dazu die Bedienung, die man von Stories kennt:
 *
 * - oben je Clip ein Balken, der **mit der Videozeit** läuft — man sieht,
 *   wie lange dieser noch dauert und wie viele danach kommen;
 * - `←`/`→` und die Knöpfe „‹ Zurück"/„Weiter ›" blättern, `Leertaste`
 *   hält an;
 * - am Telefon: Tipp links/rechts blättert, Tipp in die Mitte hält an,
 *   **Wischen nach unten schließt**, seitwärts wischen blättert;
 * - „<Feature> ausprobieren →" führt zum Feature und schließt den Spieler.
 *
 * **Am Ende eines Clips kommt der nächste** — das ist der eine Selbstlauf,
 * und er ist keiner im Sinn von DESIGNSPRACHE §7: Ein Mensch hat den Spieler
 * geöffnet, um die Clips zu sehen; gewechselt wird erst, wenn der laufende zu
 * Ende ist, und die Balken kündigen es an. Mit `prefers-reduced-motion`
 * startet kein Clip von selbst (Standbild + Abspielknopf), und es schaltet
 * nichts weiter (`nachDemEnde` in `lib/neuigkeiten.ts`).
 *
 * **Immer dunkel**, auch im hellen Design — die Kinofläche eines
 * Videoplayers, keine dunkle Karte auf heller Seite (DESIGNSPRACHE, „Story-
 * Spieler"). Die Clips sind hell aufgenommen und stehen darauf als Bild.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ArrowRight, ChevronLeft, ChevronRight, Pause, Play, RotateCcw, X } from "lucide-react";
import {
  kachelFarbe, nachDemEnde, seitenVerhaeltnis, type Highlight,
} from "@/lib/neuigkeiten";
import { cn } from "@/lib/utils";

/** Läuft die Person mit abgeschalteter Bewegung? Dann steht das Standbild
 *  statt des Clips, und am Ende schaltet nichts weiter. */
export function useRuhigeBewegung(): boolean {
  // Gleich beim ersten Rendern lesen, nicht erst im Effekt: Der Spieler
  // entsteht erst auf einen Tipp (also immer im Browser), und ein erster
  // Durchlauf mit „Bewegung an" hatte den Clip schon gestartet, bevor der
  // Effekt „reduziert" meldete (Browsertest 26-neuigkeiten).
  const [ruhig, setRuhig] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const lies = () => setRuhig(mq.matches);
    lies();
    mq.addEventListener("change", lies);
    return () => mq.removeEventListener("change", lies);
  }, []);
  return ruhig;
}

type Props = {
  offen: boolean;
  /** Die Abfolge: alle Kacheln — oder ein einzelnes Nebenbei-Highlight. */
  folge: Highlight[];
  start: number;
  /** Ein Nebenbei-Clip steht allein: kein „2 von 3", kein Weiterschalten. */
  nebenbei: boolean;
  /** Ein Clip wurde aufgeschlagen — die Kachel bekommt ihren Haken. */
  onGesehen: (h: Highlight) => void;
  onSchliessen: () => void;
  /** Wohin der Fokus nach dem Schließen zurückkehrt: die Kachel, die den
   *  Spieler geöffnet hat. Radix tut das nur für einen `Dialog.Trigger` —
   *  ohne ihn landete der Fokus nach `Esc` im Nichts (gemessen). */
  rueckkehr?: HTMLElement | null;
};

export function NeuigkeitenSpieler({ offen, folge, start, nebenbei, onGesehen, onSchliessen, rueckkehr }: Props) {
  // Festhalten, auch wenn die Karte den Spieler-Zustand beim Schließen
  // leert — Radix fragt erst NACH dem Ausblenden, wohin der Fokus soll.
  const ziel = useRef<HTMLElement | null>(null);
  useEffect(() => { if (rueckkehr) ziel.current = rueckkehr; }, [rueckkehr]);
  return (
    <DialogPrimitive.Root open={offen} onOpenChange={(o) => { if (!o) onSchliessen(); }}>
      <DialogPrimitive.Portal>
        {/* Die Kinofläche: die dunkle Seitenfarbe, deckend. Halb durchsichtig
            (der Entwurf hatte 92 %) schimmerte die Startseite als graue
            Schrift durch — neben einem Clip, der selbst Schrift zeigt. */}
        <DialogPrimitive.Overlay
          className="fixed inset-0 z-[var(--level-dialog)] bg-[hsl(213_50%_7%)] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:duration-buehne data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:duration-abgang"
        />
        <DialogPrimitive.Content
          onCloseAutoFocus={(e) => {
            const el = ziel.current;
            if (!el?.isConnected) return;
            e.preventDefault();
            el.focus();
          }}
          className="fixed inset-0 z-[var(--level-dialog)] text-white outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:duration-buehne data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:duration-abgang"
        >
          {offen && folge.length > 0 && (
            <Inhalt
              key={`${start}-${nebenbei}-${folge.length}`}
              folge={folge} start={start} nebenbei={nebenbei}
              onGesehen={onGesehen} onSchliessen={onSchliessen}
            />
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function Inhalt({ folge, start, nebenbei, onGesehen, onSchliessen }: Omit<Props, "offen" | "rueckkehr">) {
  const ruhig = useRuhigeBewegung();
  const [i, setI] = useState(() => Math.max(0, Math.min(start, folge.length - 1)));
  const [spielt, setSpielt] = useState(false);
  const [zuEnde, setZuEnde] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const balken = useRef<HTMLSpanElement>(null);
  const buehne = useRef<HTMLDivElement>(null);
  const h = folge[i];
  const n = folge.length;
  const farbe = kachelFarbe(h.color);
  const media = h.media;
  const ratio = seitenVerhaeltnis(media?.aspect);

  // Aufgeschlagen = angesehen (s. lib/neuigkeiten.ts).
  useEffect(() => { onGesehen(h); }, [h, onGesehen]);

  // Starten per Aufruf statt per `autoPlay`-Attribut: So entscheidet der
  // Bewegungs-Wunsch, bevor ein einziges Bild läuft.
  useEffect(() => {
    if (ruhig) return;
    void video.current?.play().catch(() => { /* verweigert: der Knopf bleibt da */ });
  }, [i, ruhig]);

  const zeige = useCallback((ziel: number) => {
    if (ziel < 0 || ziel >= n) return;
    setZuEnde(false);
    setSpielt(false);
    setI(ziel);
  }, [n]);
  const weiter = useCallback(() => { if (i < n - 1) zeige(i + 1); else onSchliessen(); }, [i, n, zeige, onSchliessen]);
  const zurueck = useCallback(() => zeige(i - 1), [i, zeige]);

  const umschalten = useCallback(() => {
    const v = video.current;
    if (!v) return;
    if (v.paused || v.ended) {
      if (v.ended) v.currentTime = 0;
      setZuEnde(false);
      void v.play().catch(() => { /* Autoplay verweigert: der Knopf bleibt da */ });
    } else {
      v.pause();
    }
  }, []);

  // Der Balken läuft mit der Videozeit. Direkt am Element statt über den
  // Zustand: sechzig Neuzeichnungen des ganzen Spielers je Sekunde für einen
  // Balken wären Verschwendung. Nur `transform` (DESIGNSPRACHE §7).
  useEffect(() => {
    let rahmen = 0;
    const schritt = () => {
      const v = video.current;
      const el = balken.current;
      if (el) {
        const anteil = v && v.duration > 0 ? Math.min(1, v.currentTime / v.duration) : 0;
        el.style.transform = `scaleX(${anteil})`;
      }
      rahmen = requestAnimationFrame(schritt);
    };
    rahmen = requestAnimationFrame(schritt);
    return () => cancelAnimationFrame(rahmen);
  }, [i]);

  const amEnde = () => {
    if (nachDemEnde({ index: i, anzahl: n, ruhig, nebenbei }) === "weiter") zeige(i + 1);
    else setZuEnde(true);
  };

  // Tastatur: Pfeile blättern, Leertaste hält an. Auf einem Knopf gehört die
  // Leertaste dem Knopf.
  const tasten = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") { e.preventDefault(); if (i < n - 1) zeige(i + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); zurueck(); }
    else if (e.key === " " && !(e.target instanceof HTMLButtonElement || e.target instanceof HTMLAnchorElement)) {
      e.preventDefault();
      umschalten();
    }
  };

  // Finger: Tipp links/rechts blättert, Mitte hält an; nach unten wischen
  // schließt, seitwärts wischen blättert. Die Maus klickt nur an und aus —
  // ein Klick rechts aufs Video, der weiterspringt, überrascht am Schreibtisch.
  const zeiger = useRef<{ x: number; y: number; art: string } | null>(null);
  const runter = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest("button, a")) return;
    zeiger.current = { x: e.clientX, y: e.clientY, art: e.pointerType };
  };
  const ziehen = (e: React.PointerEvent) => {
    const z = zeiger.current;
    if (!z || z.art === "mouse" || ruhig || !buehne.current) return;
    const dy = e.clientY - z.y;
    if (dy > 0 && Math.abs(dy) > Math.abs(e.clientX - z.x)) {
      buehne.current.style.transform = `translateY(${dy * 0.6}px)`;
      buehne.current.style.opacity = String(Math.max(0.4, 1 - dy / 600));
    }
  };
  const hoch = (e: React.PointerEvent) => {
    const z = zeiger.current;
    zeiger.current = null;
    if (buehne.current) { buehne.current.style.transform = ""; buehne.current.style.opacity = ""; }
    if (!z) return;
    const dx = e.clientX - z.x;
    const dy = e.clientY - z.y;
    const tipp = Math.abs(dx) < 10 && Math.abs(dy) < 10;
    if (z.art === "mouse") { if (tipp) umschalten(); return; }
    if (dy > 90 && dy > Math.abs(dx)) { onSchliessen(); return; }
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)) { if (dx < 0) { if (i < n - 1) zeige(i + 1); } else zurueck(); return; }
    if (!tipp) return;
    const breite = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const anteil = (e.clientX - breite.left) / breite.width;
    if (anteil < 0.3) zurueck();
    else if (anteil > 0.7) { if (i < n - 1) zeige(i + 1); }
    else umschalten();
  };

  const kennung = nebenbei ? `Außerdem · ${h.title}` : `${i + 1} von ${n} · ${h.title}`;
  const letzte = i >= n - 1;

  return (
    <div onKeyDown={tasten} className="flex h-full flex-col px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-[max(0.75rem,env(safe-area-inset-top))] sm:px-8 breit:px-14">
      {/* Kopf: Balken je Clip, darunter „2 von 3 · Mein Viertel" und ×. */}
      <div className="mx-auto w-full max-w-[1480px]">
        <div aria-hidden className="flex gap-1.5">
          {folge.map((k, j) => (
            <span key={`${k.url}#${k.title}`} className="h-1 flex-1 overflow-hidden rounded-full bg-white/25">
              <span
                ref={j === i ? balken : undefined}
                className="block h-full w-full origin-left bg-white"
                style={{ transform: `scaleX(${j < i ? 1 : 0})` }}
              />
            </span>
          ))}
        </div>
        <div className="mt-2 flex items-start justify-between gap-3">
          <DialogPrimitive.Title className="min-w-0 pt-1.5 text-[15px] font-semibold leading-snug sm:text-[17px]">
            {kennung}
          </DialogPrimitive.Title>
          <DialogPrimitive.Close
            aria-label="Schließen"
            className="-mr-2 grid h-11 w-11 shrink-0 place-items-center rounded-full text-white transition-colors duration-tipp maus:hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
          >
            <X className="h-6 w-6" />
          </DialogPrimitive.Close>
        </div>
      </div>

      {/* Die Bühne: der Clip, so groß wie der Platz erlaubt. */}
      <div
        ref={buehne}
        onPointerDown={runter}
        onPointerMove={ziehen}
        onPointerUp={hoch}
        onPointerCancel={() => { zeiger.current = null; if (buehne.current) { buehne.current.style.transform = ""; buehne.current.style.opacity = ""; } }}
        className="flex min-h-0 flex-1 touch-none select-none items-center justify-center py-3 transition-[transform,opacity] duration-fluss ease-out-strong"
      >
        <div
          className="relative overflow-hidden rounded-2xl bg-black shadow-[0_40px_80px_-30px_rgba(0,0,0,0.8)]"
          style={{
            aspectRatio: String(ratio),
            // So breit wie möglich, aber nie höher als der Platz zwischen Kopf
            // und Fuß (rund 17 rem) — sonst schöbe ein Querformat-Clip auf
            // einem flachen Fenster die Knöpfe aus dem Bild.
            width: `min(100%, 1240px, calc((100dvh - 17rem) * ${ratio.toFixed(4)}))`,
          }}
        >
          {media?.kind === "video" ? (
            <video
              key={i}
              ref={video}
              src={media.src}
              poster={media.poster ?? undefined}
              muted
              playsInline
              preload="auto"
              onPlay={() => { setSpielt(true); setZuEnde(false); }}
              onPause={() => setSpielt(false)}
              onEnded={amEnde}
              aria-label={media.alt}
              className="absolute inset-0 h-full w-full object-contain"
            />
          ) : media ? (
            // eslint-disable-next-line @next/next/no-img-element -- statische Datei
            <img src={media.src} alt={media.alt} className="absolute inset-0 h-full w-full object-contain" />
          ) : null}

          {media?.kind === "video" && (
            <>
              {/* Steht der Clip (reduzierte Bewegung, angehalten, zu Ende),
                  sagt ein großer Knopf in der Mitte, wie es weitergeht. */}
              {!spielt && (
                <button
                  type="button"
                  onClick={umschalten}
                  aria-label={zuEnde ? "Noch einmal ansehen" : "Abspielen"}
                  className="absolute left-1/2 top-1/2 grid h-[72px] w-[72px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white/[0.94] shadow-[0_10px_30px_-10px_rgba(0,0,0,0.5)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black"
                >
                  {zuEnde
                    ? <RotateCcw className="h-7 w-7" style={{ color: farbe }} />
                    : <Play className="ml-1 h-8 w-8" style={{ color: farbe, fill: farbe }} />}
                </button>
              )}
              <button
                type="button"
                onClick={umschalten}
                aria-label={spielt ? "Anhalten" : "Abspielen"}
                className="absolute bottom-2 left-2 grid h-8 w-8 place-items-center rounded-full bg-[hsl(212_55%_11%/0.7)] text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white sm:bottom-3 sm:left-3 sm:h-10 sm:w-10"
              >
                {spielt ? <Pause className="h-3.5 w-3.5 fill-current sm:h-4 sm:w-4" /> : <Play className="ml-0.5 h-3.5 w-3.5 fill-current sm:h-4 sm:w-4" />}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Fuß: was man sieht, und wohin es geht. */}
      <div className="mx-auto w-full max-w-[1240px]">
        <h3 className="font-display text-[19px] font-bold leading-snug sm:text-[22px]">{h.title}</h3>
        <DialogPrimitive.Description className="mt-1 max-w-[76ch] text-[14.5px] leading-relaxed text-white/[0.86]">
          {h.text}
        </DialogPrimitive.Description>
        {/* Schmal steht der Weg zum Feature allein in der ersten Zeile, Zurück
            und Weiter teilen sich die zweite: Drei Knöpfe nebeneinander
            brachen „Mein Viertel ausprobieren" auf 375 px in zwei Zeilen. */}
        <div className="mt-3 flex flex-wrap items-center justify-center gap-2.5 sm:mt-4 sm:flex-nowrap sm:gap-3.5">
          {!nebenbei && (
            <button
              type="button"
              onClick={zurueck}
              disabled={i === 0}
              className={cn(KNOPF_LEISE, "order-2 flex-1 sm:order-none sm:flex-none")}
            >
              <ChevronLeft aria-hidden className="h-5 w-5" />
              Zurück
            </button>
          )}
          <Link
            href={h.url}
            onClick={onSchliessen}
            className="order-1 inline-flex min-h-12 min-w-0 basis-full items-center justify-center gap-2 rounded-full px-5 text-center text-[15px] font-bold text-white sm:order-none sm:basis-auto transition-[filter] duration-tipp maus:hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black sm:flex-none sm:px-7 sm:text-[17px]"
            style={{ backgroundColor: farbe }}
          >
            {h.action} <ArrowRight aria-hidden className="h-4 w-4 shrink-0" />
          </Link>
          <button
            type="button"
            onClick={weiter}
            className={cn(KNOPF_LEISE, "order-3 flex-1 sm:order-none sm:flex-none")}
          >
            {letzte ? "Fertig" : "Weiter"}
            {!letzte && <ChevronRight aria-hidden className="h-5 w-5" />}
          </button>
        </div>
      </div>
    </div>
  );
}

const KNOPF_LEISE =
  "inline-flex min-h-12 shrink-0 items-center justify-center gap-1 rounded-full bg-white/[0.14] px-4 text-[15px] font-semibold text-white transition-colors duration-tipp maus:hover:bg-white/[0.22] disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white sm:px-6 sm:text-[17px]";
