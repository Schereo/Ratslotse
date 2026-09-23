"use client";

// Die Momente des Stichwahl-Abends, die man nicht übersehen soll — Tims
// Wunsch 23.09.2026: „sehr offensichtlich machen, wenn neue Zahlen
// reinkommen", und wer mag, fiebert mit.
//
// Drei Signale, alle nur bei einer ECHTEN neuen Meldung (mehr gezählte
// Bezirke als beim vorigen Abruf), nie beim ersten Laden — der erste Auftritt
// bewegt sich nicht (DESIGNSPRACHE §7):
//
// 1. **Aufleuchten.** Der Bildschirm glüht einmal kurz in der Farbe dessen,
//    der die neuen Bezirke gewonnen hat. Das ist eine Parteifarben-Fläche und
//    damit die zweite Ausnahme neben der Stichwahl-Karte (DESIGNSPRACHE §2):
//    zwei Namen, eine Frage — „wer hat diese Bezirke geholt?".
// 2. **Leiste.** Wer weit unten auf der Karte ist, sieht die Meldung oben
//    nicht; eine Leiste unten nennt sie für ein paar Sekunden.
// 3. **Konfetti** — nur für die Person, der man hier die Daumen drückt, und
//    nur, wenn man das selbst eingestellt hat. Der Favorit bleibt im eigenen
//    Browser; der Server erfährt ihn nie.
//
// `prefers-reduced-motion`: kein Aufleuchten, kein Konfetti. Die Leiste und
// die Meldung oben tragen dieselbe Nachricht ohne Bewegung.

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { zahl } from "@/lib/wahlabend";
import {
  fuehrend,
  meldungsGewinner,
  nachStimmen,
  nachname,
  speichereFavorit,
  type Meldung,
  type Stichwahl,
  type StichwahlKandidat,
} from "@/lib/stichwahl";

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

function stilleBewegung(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** `#E3000F` + Deckkraft → `#E3000F33`. Eine Farbe, die kein sechsstelliges
 *  Hex ist, gibt es hier nicht — dann bleibt es beim Grundton. */
function mitAlpha(hex: string, a: number): string {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) return `hsl(var(--primary) / ${a})`;
  return `${hex}${Math.round(a * 255).toString(16).padStart(2, "0")}`;
}

function farben(k: StichwahlKandidat): { hell: string; dunkel: string } {
  return { hell: k.color || "#6b7a8c", dunkel: k.color_dark || k.color || "#a3b1c2" };
}

/* ── Konfetti ─────────────────────────────────────────────────────────── */

/** Die Bibliothek kommt erst, wenn es etwas zu feiern gibt — sie gehört
 *  nicht in das Bündel, das jede Besucherin lädt. */
export async function konfetti(k: StichwahlKandidat, staerke: "klein" | "gross"): Promise<void> {
  if (stilleBewegung()) return;
  const { default: confetti } = await import("canvas-confetti");
  const c = farben(k);
  const basis = { colors: [c.hell, c.dunkel, "#ffffff", "#f5c542"], disableForReducedMotion: true, zIndex: 60 };
  if (staerke === "klein") {
    confetti({ ...basis, particleCount: 80, spread: 75, startVelocity: 38, scalar: 0.9, origin: { y: 0.3 } });
    return;
  }
  // Groß: zwei Kanonen von den Seiten, gut zwei Sekunden lang.
  const ende = Date.now() + 2200;
  const runde = () => {
    confetti({ ...basis, particleCount: 6, angle: 60, spread: 60, origin: { x: 0, y: 0.7 } });
    confetti({ ...basis, particleCount: 6, angle: 120, spread: 60, origin: { x: 1, y: 0.7 } });
    if (Date.now() < ende) window.requestAnimationFrame(runde);
  };
  runde();
}

/* ── Die Momente ──────────────────────────────────────────────────────── */

type Moment = { schluessel: number; meldung: Meldung; gewinner: StichwahlKandidat | null };

export function StichwahlMomente({ daten, favorit }: { daten: Stichwahl; favorit: string | null }) {
  const vorher = useRef<{ n: number; entschieden: boolean; vorn: string | null; stimmen: Record<string, number> } | null>(null);
  const glut = useRef<HTMLDivElement>(null);
  const [moment, setMoment] = useState<Moment | null>(null);
  // Der Favorit per Ref: Wer ihn umstellt, soll nicht die letzte Meldung
  // ein zweites Mal gefeiert bekommen.
  const favoritRef = useRef(favorit);
  favoritRef.current = favorit;

  useEffect(() => {
    const jetzt = {
      n: daten.reports_received,
      entschieden: Boolean(daten.projection?.decided),
      vorn: fuehrend(daten.candidates),
      stimmen: Object.fromEntries(daten.candidates.map((k) => [k.slug, k.votes ?? 0])),
    };
    const alt = vorher.current;
    vorher.current = jetzt;
    if (!alt || daten.phase === "before") return;

    const fav = daten.candidates.find((k) => k.slug === favoritRef.current) ?? null;
    // Gerade entschieden — für wen?
    if (!alt.entschieden && jetzt.entschieden && fav && daten.projection?.actual_leader === fav.slug) {
      void konfetti(fav, "gross");
    }
    if (jetzt.n <= alt.n) return;

    // Der Zuwachs seit dem, was DIESER Schirm zuletzt zeigte — nicht die
    // letzte Zeile des Verlaufs: Kamen zwischen zwei Abrufen zwei Meldungen,
    // nennt der Verlauf nur die zweite, sichtbar geändert haben sich beide.
    const m: Meldung = {
      at: daten.fetched_at ?? "",
      bezirke: jetzt.n - alt.n,
      zuwachs: Object.fromEntries(Object.entries(jetzt.stimmen).map(([slug, v]) => [slug, v - (alt.stimmen[slug] ?? 0)])),
    };
    const slug = meldungsGewinner(m);
    const gewinner = daten.candidates.find((k) => k.slug === slug) ?? null;
    setMoment({ schluessel: jetzt.n, meldung: m, gewinner });

    if (gewinner && glut.current && !stilleBewegung()) {
      const c = farben(gewinner);
      glut.current.style.background =
        `radial-gradient(130% 95% at 50% 45%, light-dark(${mitAlpha(c.hell, 0.05)}, ${mitAlpha(c.dunkel, 0.07)}) 0%, ` +
        `light-dark(${mitAlpha(c.hell, 0.14)}, ${mitAlpha(c.dunkel, 0.18)}) 62%, ` +
        `light-dark(${mitAlpha(c.hell, 0.34)}, ${mitAlpha(c.dunkel, 0.4)}) 100%)`;
      glut.current.animate(
        [{ opacity: 0 }, { opacity: 1, offset: 0.12 }, { opacity: 1, offset: 0.35 }, { opacity: 0 }],
        { duration: 2400, easing: "ease-out" },
      );
    }
    if (fav && gewinner?.slug === fav.slug && !(jetzt.entschieden && !alt.entschieden)) {
      // Übernimmt der Favorit gerade die Führung, darf es mehr sein.
      void konfetti(fav, alt.vorn !== fav.slug && jetzt.vorn === fav.slug ? "gross" : "klein");
    }
  }, [daten]);

  // Die Leiste verschwindet nach sieben Sekunden von selbst.
  useEffect(() => {
    if (!moment) return;
    const id = window.setTimeout(() => setMoment(null), 7000);
    return () => window.clearTimeout(id);
  }, [moment]);

  return (
    <>
      <div ref={glut} aria-hidden className="pointer-events-none fixed inset-0 z-30 opacity-0" data-testid="aufleuchten" />
      {moment ? <Leiste moment={moment} daten={daten} weg={() => setMoment(null)} /> : null}
    </>
  );
}

/** Die Leiste unten: „12 weitere Bezirke — Rohr +312, Prange +298". Ein
 *  Tipp darauf führt nach oben zum Stand. Oben an der Seite ist sie
 *  überflüssig — dort steht die Meldung schon. */
function Leiste({ moment, daten, weg }: { moment: Moment; daten: Stichwahl; weg: () => void }) {
  const [unten, setUnten] = useState(false);
  useEffect(() => {
    const pruefen = () => setUnten(window.scrollY > 320);
    pruefen();
    window.addEventListener("scroll", pruefen, { passive: true });
    return () => window.removeEventListener("scroll", pruefen);
  }, []);
  if (!unten) return null;
  const { meldung: m, gewinner } = moment;
  // Wer die Meldung gewonnen hat, zuerst — das ist die Farbe des Punkts.
  const teile = nachStimmen(daten.candidates)
    .sort((a, b) => (m.zuwachs[b.slug] ?? 0) - (m.zuwachs[a.slug] ?? 0))
    .map((k) => `${nachname(k)} ${(m.zuwachs[k.slug] ?? 0) >= 0 ? "+" : "−"}${zahl(Math.abs(m.zuwachs[k.slug] ?? 0))}`);
  const c = gewinner ? farben(gewinner) : null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+1rem)] z-50 flex justify-center px-4">
      <button
        key={moment.schluessel}
        type="button"
        onClick={() => {
          window.scrollTo({ top: 0, behavior: stilleBewegung() ? "auto" : "smooth" });
          weg();
        }}
        className="pointer-events-auto flex max-w-full items-center gap-2.5 rounded-full border border-border bg-card px-4 py-2.5 text-left text-[13px] shadow-lifted animate-in fade-in-0 slide-in-from-bottom-2 duration-buehne ease-out-strong"
        data-testid="neue-zahlen"
        role="status"
      >
        {c ? (
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 flex-none rounded-full"
            style={{ background: `light-dark(${c.hell}, ${c.dunkel})` }}
          />
        ) : null}
        <span className="min-w-0 truncate">
          <strong className="font-semibold">+{zahl(m.bezirke)} {m.bezirke === 1 ? "Bezirk" : "Bezirke"}</strong>
          <span className="text-muted-foreground"> · </span>
          {teile.join(" · ")}
        </span>
        <span className="flex-none font-medium text-primary">
          <span className="hidden sm:inline">Zum Stand </span>↑
        </span>
      </button>
    </div>
  );
}

/* ── Mitfiebern ───────────────────────────────────────────────────────── */

/** „Wem drückst du die Daumen?" — unten auf der Seite, weil es eine
 *  Einstellung ist und kein Inhalt. Vorgabe ist „niemand"; die Reihenfolge
 *  ist die des Stimmzettels, nicht die des Stands. */
export function Mitfiebern({
  daten,
  favorit,
  setFavorit,
}: {
  daten: Stichwahl;
  favorit: string | null;
  setFavorit: (slug: string | null) => void;
}) {
  const waehle = (slug: string | null) => {
    setFavorit(slug);
    speichereFavorit(daten.election.slug, slug);
    const k = daten.candidates.find((x) => x.slug === slug);
    // Ein kleiner Vorgeschmack — so sieht man, was man eingeschaltet hat.
    if (k) void konfetti(k, "klein");
  };
  const optionen: { slug: string | null; label: string; k?: StichwahlKandidat }[] = [
    { slug: null, label: "Niemandem" },
    ...daten.candidates.map((k) => ({ slug: k.slug, label: k.name, k })),
  ];
  return (
    <section className="mt-8 rounded-2xl border border-border bg-card p-5" aria-labelledby="mitfiebern-titel" data-testid="mitfiebern">
      <p className={KICKER}>Mitfiebern</p>
      <h2 id="mitfiebern-titel" className="mt-1 font-display text-[17px] font-bold tracking-tight">
        Wem drückst du die Daumen?
      </h2>
      <p className="mt-1.5 max-w-[62ch] text-[13px] leading-relaxed text-muted-foreground">
        Holt deine Wahl in einer neuen Meldung mehr Stimmen als die andere Seite, gibt es Konfetti. Die Einstellung bleibt
        in diesem Browser; wir speichern sie nicht.
      </p>
      <div role="radiogroup" aria-labelledby="mitfiebern-titel" className="mt-3 flex flex-wrap gap-2">
        {optionen.map((o) => {
          const an = favorit === o.slug;
          const c = o.k ? farben(o.k) : null;
          return (
            <button
              key={o.slug ?? "niemand"}
              type="button"
              role="radio"
              aria-checked={an}
              onClick={() => waehle(o.slug)}
              className={cn(
                "inline-flex min-h-10 items-center gap-2 rounded-full border px-4 text-[13.5px] font-medium transition-colors duration-tipp",
                an ? "border-foreground bg-foreground text-background" : "border-border bg-card text-foreground hover:bg-primary/5",
              )}
            >
              {c ? (
                <span
                  aria-hidden
                  className="inline-block h-2 w-2 flex-none rounded-full"
                  style={{ background: `light-dark(${c.hell}, ${c.dunkel})` }}
                />
              ) : null}
              {o.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
