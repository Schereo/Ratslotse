"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { Button } from "@/components/ui";
import { Mascot, type MascotPose } from "@/components/mascot";
import { reportBadgeEvent } from "@/components/badges";

/**
 * Geführte Lotti-Tour: Spotlight auf echte UI-Elemente (per data-tour-Anker),
 * Lotti erklärt daneben in einer Sprechblase. Läuft über mehrere Routen
 * (Dashboard → Beschlüsse); nach einem Routenwechsel wird auf den Anker
 * gewartet. Elemente werden über den ersten SICHTBAREN Treffer aufgelöst,
 * sodass Desktop-Sidebar und mobile Bottom-Nav denselben Anker tragen können.
 *
 * Start: `startGuidedTour()` (z. B. Button in der „Erste Schritte“-Karte).
 * Bedienung: Weiter/Zurück, Pfeiltasten, Esc zum Beenden.
 */
type TourStep = {
  id: string;
  /** data-tour-Wert des Zielelements; ohne Anker wird die Karte zentriert. */
  anchor?: string;
  /** Route, auf der der Schritt spielt (Pfad + nötige Query-Params). */
  route?: string;
  pose: MascotPose;
  title: string;
  text: string;
};

const STEPS: TourStep[] = [
  {
    id: "willkommen", route: "/dashboard", anchor: "erste-schritte", pose: "wave",
    title: "Moin, ich bin Lotti!",
    text: "Ich lotse dich einmal durch Ratslotse — dauert keine Minute. Diese Checkliste hakt nebenbei ab, was du schon entdeckt hast.",
  },
  {
    id: "ratsinfo", route: "/dashboard", anchor: "nav-ratsinfo", pose: "point",
    title: "Das Ratsinfo",
    text: "Hier liegen alle Beschlüsse, Sitzungen, Themen und Analysen des Stadtrats — durchsuchbar statt PDF-Stapel.",
  },
  {
    id: "suche", route: "/council?tab=decisions&mode=suchen", anchor: "beschluss-suche", pose: "search",
    title: "Beschlüsse durchsuchen",
    // Ohne Wegbeschreibung: Der frühere Tipp „die Taste / springt hierher" ist
    // auf dem Handy nicht ausführbar — die Tour läuft aber in der App wie im
    // Browser. Ein Nav-Label ginge auch nicht: Es heißt am Rechner „Suchen &
    // Fragen" und auf dem Handy „Ratsinfo". Also nur, was überall gilt.
    text: "Volltextsuche über alle Beschlüsse — eingrenzen lässt sich nach Ergebnis, Themenfeld, Ausschuss und Zeitraum.",
  },
  {
    id: "ki", route: "/council?tab=decisions", anchor: "ki-frage-tab", pose: "celebrate",
    title: "Oder frag einfach",
    text: "Stell deine Frage in normaler Sprache — ich suche die passenden Beschlüsse raus und antworte mit Quellen.",
  },
  {
    id: "themen", route: "/council?tab=decisions", anchor: "nav-themen", pose: "point",
    title: "Deine Themen",
    text: "Lege Suchbegriffe an, die dich interessieren — bei neuen Beschlüssen dazu melde ich mich per Push oder E-Mail.",
  },
  {
    id: "fertig", pose: "celebrate",
    title: "Leinen los!",
    text: "Das war’s schon. Alles Weitere zeigt dir die „Erste Schritte“-Karte auf der Übersicht — oder du legst direkt mit deiner ersten Frage los.",
  },
];

const SEEN_KEY = "ratslotse:tour-seen";
const START_EVENT = "ratslotse:start-tour";

/** Tour von außen starten (Button in „Erste Schritte“). */
export function startGuidedTour() {
  window.dispatchEvent(new Event(START_EVENT));
}

type Rect = { top: number; left: number; width: number; height: number };

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Erstes SICHTBARES Element mit diesem data-tour-Wert (Sidebar vs. Bottom-Nav). */
function findAnchor(name: string): HTMLElement | null {
  return (
    Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${name}"]`)).find(
      (el) => el.offsetParent !== null,
    ) ?? null
  );
}

/** Pfad gleich + alle in der Step-Route geforderten Query-Params gesetzt? */
function routeMatches(route: string): boolean {
  const [path, qs] = route.split("?");
  if (window.location.pathname !== path) return false;
  const cur = new URLSearchParams(window.location.search);
  const want = new URLSearchParams(qs ?? "");
  for (const [k, v] of want.entries()) if (cur.get(k) !== v) return false;
  return true;
}

function toRect(el: HTMLElement): Rect {
  const r = el.getBoundingClientRect();
  const pad = 8;
  return { top: r.top - pad, left: r.left - pad, width: r.width + pad * 2, height: r.height + pad * 2 };
}

export function GuidedTour() {
  const router = useRouter();
  const [stepIndex, setStepIndex] = useState(-1);
  const [rect, setRect] = useState<Rect | null>(null);
  const [ready, setReady] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const [cardPos, setCardPos] = useState<{ top: number; left: number } | null>(null);

  const active = stepIndex >= 0;
  const step = active ? STEPS[stepIndex] : null;
  const isLast = stepIndex === STEPS.length - 1;

  const end = useCallback(() => {
    setStepIndex(-1);
    setRect(null);
    setReady(false);
    try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* ignore */ }
  }, []);

  const next = useCallback(() => setStepIndex((i) => (i >= STEPS.length - 1 ? i : i + 1)), []);
  const prev = useCallback(() => setStepIndex((i) => (i <= 0 ? i : i - 1)), []);

  const finishToQa = useCallback(() => {
    reportBadgeEvent("tour"); // RL-U12: Kompass — nur beim echten Durchlauf
    end();
    router.push("/council?tab=decisions&mode=fragen");
  }, [end, router]);

  // Start-Event von außen.
  useEffect(() => {
    const onStart = () => setStepIndex(0);
    window.addEventListener(START_EVENT, onStart);
    return () => window.removeEventListener(START_EVENT, onStart);
  }, []);

  // Pro Schritt: ggf. navigieren, Anker abwarten, hinscrollen, vermessen.
  useEffect(() => {
    if (!active || !step) return;
    let cancelled = false;
    setReady(false);
    setCardPos(null); // keine Position vom vorigen Schritt weiterverwenden

    (async () => {
      if (step.route && !routeMatches(step.route)) router.push(step.route);
      if (!step.anchor) {
        if (!cancelled) { setRect(null); setReady(true); }
        return;
      }
      // Nach einem Routenwechsel braucht die Zielseite einen Moment.
      const deadline = Date.now() + 4000;
      let el: HTMLElement | null = null;
      while (!cancelled && Date.now() < deadline) {
        el = findAnchor(step.anchor);
        if (el) break;
        await sleep(120);
      }
      if (cancelled) return;
      if (!el) { next(); return; } // Anker fehlt (z. B. Feature ausgeblendet) → Schritt überspringen
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      el.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
      await sleep(reduce ? 60 : 380);
      if (cancelled) return;
      setRect(toRect(el));
      setReady(true);
    })();

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepIndex, active]);

  // Spotlight folgt bei Scroll/Resize.
  useEffect(() => {
    if (!active || !ready || !step?.anchor) return;
    const update = () => {
      const el = findAnchor(step.anchor!);
      if (el) setRect(toRect(el));
    };
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [active, ready, step]);

  // Karte positionieren: unterm Ziel, sonst darüber; horizontal geklemmt.
  // Der ankerlose Fall (Finale) wird rein per CSS zentriert — kein Messen nötig.
  useLayoutEffect(() => {
    if (!ready || !rect) return;
    const card = cardRef.current;
    if (!card) return;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const cw = card.offsetWidth;
    const ch = card.offsetHeight;
    const below = rect.top + rect.height + 12;
    const top = below + ch + 12 <= vh ? below : Math.max(12, rect.top - ch - 12);
    const left = Math.min(Math.max(12, rect.left + rect.width / 2 - cw / 2), Math.max(12, vw - cw - 12));
    setCardPos({ top, left });
  }, [ready, rect, stepIndex]);

  // Fokus auf die Karte, Tastatur-Bedienung.
  useEffect(() => {
    if (!ready) return;
    cardRef.current?.focus();
  }, [ready, stepIndex]);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); end(); }
      else if (e.key === "ArrowRight" && !isLast) { e.preventDefault(); next(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); prev(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, isLast, end, next, prev]);

  if (!active || !step) return null;

  return (
    <div className="fixed inset-0 z-[70]" role="dialog" aria-modal="true" aria-label={`Tour: ${step.title}`}>
      {/* Abdunkelung — mit Spotlight-Loch, solange es ein Ziel gibt. */}
      {rect ? (
        <div
          // Der Spotlight wandert zwischen Zielen (Onboarding, selten) — Bewegung
          // auf dem Screen bekommt die starke in-out-Kurve; Properties explizit.
          className="pointer-events-none fixed rounded-xl transition-[top,left,width,height] duration-300 ease-in-out-strong"
          style={{
            top: rect.top,
            left: rect.left,
            width: rect.width,
            height: rect.height,
            boxShadow: "0 0 0 9999px hsl(213 60% 5% / 0.62)",
          }}
          aria-hidden
        />
      ) : (
        <div className="fixed inset-0 bg-[hsl(213_60%_5%/0.62)]" aria-hidden />
      )}

      <div
        ref={cardRef}
        tabIndex={-1}
        // Ankerlos (Finale): über ein Grid zentriert — bewusst ohne Transform,
        // damit kein Compositing-Versatz entsteht. Mit Anker: gemessene Position.
        className={rect ? "fixed w-[min(92vw,360px)] outline-none" : "fixed inset-0 grid place-items-center p-4 outline-none"}
        style={rect ? (cardPos ? { top: cardPos.top, left: cardPos.left } : { visibility: "hidden", top: 0, left: 0 }) : undefined}
      >
        <div className={rect ? "flex items-end gap-2" : "flex w-[min(92vw,360px)] items-end gap-2"}>
          <Mascot pose={step.pose} className="h-16 w-16 shrink-0 drop-shadow-lg" />
          <div className="relative min-w-0 flex-1 rounded-2xl rounded-bl-sm border border-border bg-card p-4 shadow-lifted">
            <button
              type="button"
              onClick={end}
              aria-label="Tour beenden"
              className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
            <p className="pr-6 font-display text-base font-bold text-foreground">{step.title}</p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{step.text}</p>
            <div className="mt-3.5 flex flex-wrap items-center justify-end gap-x-2 gap-y-2">
              <div className="mr-auto flex items-center gap-1" aria-label={`Schritt ${stepIndex + 1} von ${STEPS.length}`}>
                {STEPS.map((s, i) => (
                  <span
                    key={s.id}
                    className={`h-1.5 rounded-full transition-[width,background-color] duration-200 ease-out-strong ${i === stepIndex ? "w-4 bg-primary" : "w-1.5 bg-muted-foreground/30"}`}
                  />
                ))}
              </div>
              <div className="flex items-center gap-1.5">
                {stepIndex > 0 && (
                  <Button variant="ghost" size="sm" onClick={prev}>
                    Zurück
                  </Button>
                )}
                {isLast ? (
                  <Button size="sm" onClick={finishToQa}>Erste Frage stellen</Button>
                ) : (
                  <Button size="sm" onClick={next}>Weiter</Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
