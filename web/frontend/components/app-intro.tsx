"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { isNativeApp } from "@/lib/platform";
import { Button } from "@/components/ui";
import { Mascot, type MascotPose } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";

const DONE_KEY = "ratslotse.intro.done";

const SLIDES: { pose: MascotPose; title: string; text: string }[] = [
  {
    pose: "wave",
    title: "Moin, ich bin Lotti!",
    text: "Ich lotse dich durch die Oldenburger Ratspolitik — Beschlüsse, Sitzungen und was sie für deine Stadt bedeuten.",
  },
  {
    pose: "point",
    title: "Deine Themen im Blick",
    text: "Folge Themen wie „Radwege“ oder deinem Viertel. Entscheidet der Rat dazu, bekommst du eine Mitteilung.",
  },
  {
    pose: "celebrate",
    title: "Frag den Rat",
    text: "Stell Fragen in normalem Deutsch — die KI-Suche findet die passenden Beschlüsse, immer mit Quellen.",
  },
];

/** First-Run-Intro (RL-1103): drei Karten beim allerersten App-Start, danach
 *  nie wieder (localStorage). Nur transform/opacity — animationsarm genug,
 *  dass es auch mit reduzierter Bewegung nicht stört. */
export function AppIntro() {
  const theme = useMascotTheme();
  const [visible, setVisible] = useState(false);
  const [i, setI] = useState(0);

  useEffect(() => {
    if (isNativeApp() && !localStorage.getItem(DONE_KEY)) setVisible(true);
  }, []);

  if (!visible) return null;

  const done = () => {
    localStorage.setItem(DONE_KEY, "1");
    setVisible(false);
  };
  const last = i === SLIDES.length - 1;

  return (
    <div className="fixed inset-0 z-[100] flex flex-col bg-background pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-[calc(1rem+env(safe-area-inset-top))]">
      <div className="flex justify-end px-5">
        <button type="button" onClick={done} className="p-2 text-sm text-muted-foreground hover:text-foreground">
          Überspringen
        </button>
      </div>

      {/* Slides: eine Spur, per translateX verschoben. */}
      <div className="flex-1 overflow-hidden">
        <div
          className="flex h-full transition-transform duration-300 ease-out"
          style={{ transform: `translateX(-${i * 100}%)` }}
        >
          {SLIDES.map((s) => (
            <div key={s.title} className="flex w-full shrink-0 flex-col items-center justify-center px-8 text-center">
              <Mascot pose={s.pose} theme={theme} bob decorative className="h-32 w-32" />
              <h2 className="mt-6 font-display text-[26px] font-extrabold tracking-tight text-foreground">{s.title}</h2>
              <p className="mt-3 max-w-xs text-[15px] leading-relaxed text-muted-foreground">{s.text}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col items-center gap-5 px-8">
        <div className="flex gap-1.5" aria-hidden>
          {SLIDES.map((_, d) => (
            <span
              key={d}
              className={cn(
                "h-1.5 rounded-full transition-all duration-300",
                d === i ? "w-5 bg-primary" : "w-1.5 bg-muted-foreground/30",
              )}
            />
          ))}
        </div>
        <Button
          variant={last ? "signal" : "primary"}
          className="h-11 w-full max-w-xs"
          onClick={() => (last ? done() : setI(i + 1))}
        >
          {last ? "Los geht’s" : "Weiter"}
        </Button>
      </div>
    </div>
  );
}
