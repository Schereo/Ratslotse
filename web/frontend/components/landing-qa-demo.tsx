"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, RotateCcw, Send, Sparkles } from "lucide-react";
import { Mascot } from "@/components/mascot";

/**
 * Autoplay-Demo der KI-Frage für die Landing Page: Die Frage tippt sich selbst,
 * Lotti „sucht", die Antwort streamt herein, Quellen-Chips erscheinen — zum
 * Schluss der Registrieren-CTA. Startet beim Scrollen in den Viewport; bei
 * prefers-reduced-motion wird direkt der fertige Zustand gezeigt.
 * Deutlich als Demo gekennzeichnet — es läuft keine echte KI-Anfrage.
 */
const QUESTION = "Was wurde zum Radverkehr beschlossen?";
const ANSWER =
  "Der Rat hat sich zuletzt mehrfach mit dem Radverkehr befasst — von Fahrradstraßen über Abstellanlagen bis zum Radverkehrsplan. Jede Antwort nennt die zugehörigen Beschlüsse als Quellen, mit Link zum Original.";
const SOURCES = ["Ausschuss für Verkehr · Fahrradstraßen", "Stadtrat · Radverkehrsplan"];

type Phase = "idle" | "typing" | "thinking" | "answering" | "done";

export function LandingQaDemo() {
  const ref = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [typed, setTyped] = useState("");
  const [streamed, setStreamed] = useState("");
  const [started, setStarted] = useState(false);

  // Start, sobald die Sektion ins Bild scrollt.
  useEffect(() => {
    if (started) return;
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setTyped(QUESTION);
      setStreamed(ANSWER);
      setPhase("done");
      setStarted(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setStarted(true);
          setPhase("typing");
          io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [started]);

  // Phase 1: Frage tippen.
  useEffect(() => {
    if (phase !== "typing") return;
    if (typed.length >= QUESTION.length) {
      const t = setTimeout(() => setPhase("thinking"), 400);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setTyped(QUESTION.slice(0, typed.length + 1)), 45);
    return () => clearTimeout(t);
  }, [phase, typed]);

  // Phase 2: Lotti sucht.
  useEffect(() => {
    if (phase !== "thinking") return;
    const t = setTimeout(() => setPhase("answering"), 1700);
    return () => clearTimeout(t);
  }, [phase]);

  // Phase 3: Antwort streamen.
  useEffect(() => {
    if (phase !== "answering") return;
    if (streamed.length >= ANSWER.length) {
      setPhase("done");
      return;
    }
    const t = setTimeout(() => setStreamed(ANSWER.slice(0, streamed.length + 3)), 18);
    return () => clearTimeout(t);
  }, [phase, streamed]);

  const replay = () => {
    setTyped("");
    setStreamed("");
    setPhase("typing");
  };

  const showSources = phase === "answering" || phase === "done";

  return (
    <div ref={ref} className="relative mt-8 rounded-2xl border border-border bg-card p-5 shadow-lifted sm:p-6">
      {/* Sitzt auf der Kartenkante (halb über dem Rahmen) — dort kann kein
          Inhalt (z. B. der „Fragen"-Button) das Badge verdecken. */}
      <span className="absolute -top-2.5 right-5 rounded-full border border-border bg-muted px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground shadow-sm">
        Demo
      </span>

      {/* Nachgebaute Frage-Zeile — min-w-0, damit die nowrap-Frage auf schmalen
          Viewports das Feld nicht aufbläht und den Button aus der Karte drückt. */}
      <div className="flex gap-2">
        <div className="relative min-w-0 flex-1">
          <Sparkles className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <div className="flex h-10 items-center overflow-hidden whitespace-nowrap rounded-lg border border-input bg-background pl-9 pr-3 text-sm text-foreground">
            {typed || <span className="text-muted-foreground">Frag den Stadtrat…</span>}
            {phase === "typing" && <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-primary" />}
          </div>
        </div>
        <span className="inline-flex h-10 items-center gap-1.5 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground opacity-80">
          <Send className="h-4 w-4" /> Fragen
        </span>
      </div>

      {/* Lotti sucht */}
      {phase === "thinking" && (
        <div className="mt-4 flex items-center gap-3 text-sm">
          <Mascot pose="search" bob className="h-14 w-14 shrink-0" />
          <span className="font-medium text-foreground">Beschlüsse werden durchsucht und sortiert…</span>
        </div>
      )}

      {/* Antwort-Sprechblase */}
      {streamed && (
        <div className="mt-4 flex items-start gap-3">
          <Mascot pose={phase === "done" ? "point" : "search"} className="mt-1 hidden h-12 w-12 shrink-0 sm:block" />
          <div className="flex-1 rounded-2xl rounded-tl-sm border border-border bg-background p-4">
            <p className="text-sm leading-relaxed text-foreground">
              {streamed}
              {phase === "answering" && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-text-bottom" />}
            </p>
          </div>
        </div>
      )}

      {/* Quellen-Chips */}
      {showSources && (
        <div className="mt-3 flex flex-wrap gap-1.5 sm:pl-[3.75rem]">
          {SOURCES.map((s) => (
            <span key={s} className="rounded-full border border-primary/25 bg-primary/5 px-2.5 py-1 text-xs text-primary">
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Abschluss-CTA */}
      {phase === "done" && (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
          <Link
            href="/register"
            className="inline-flex items-center gap-1.5 rounded-xl bg-brand-gradient px-4 py-2 text-sm font-semibold text-primary-foreground shadow-lifted transition-all hover:-translate-y-0.5 hover:opacity-95"
          >
            Selbst fragen — kostenlos <ArrowRight className="h-4 w-4" />
          </Link>
          <button
            type="button"
            onClick={replay}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Demo erneut abspielen
          </button>
        </div>
      )}
    </div>
  );
}
