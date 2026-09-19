"use client";

// Auszählungs-Simulator — NUR auf dev (`NEXT_PUBLIC_RATSLOTSE_ENV=dev`,
// deploy-dev.yml; im Prod-Build ist die Komponente ein `null` und der Code
// fällt beim Bauen weg).
//
// **Was er tut und was er NICHT tut.** Die Generalprobe gibt es im Backend
// längst (`?probe=2021&counted=N`): Sie rechnet echte Zahlen des ersten
// Wahlgangs bezirksweise hoch, ohne irgendetwas zu schreiben. Sie war nur
// nicht bedienbar — man musste die Adresse von Hand tippen und kannte die
// Sprungmarken nicht. Diese Leiste ist die Bedienung dazu: ein Regler, ein
// paar Sprünge, ein Abspielknopf. Kein zweiter Datenpfad, keine erfundenen
// Zahlen, kein Schreibzugriff.
//
// Warum das gebraucht wird: Vor dem 27.09. lässt sich sonst nicht sehen, wie
// die Seite bei 3, bei 60 und bei 133 Bezirken aussieht — und genau dort
// liegen die Zustände, die am Abend zählen (kein Ergebnis / Auszählung läuft
// / Hochrechnung steht / entschieden / Endstand).

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronDown, Pause, Play, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

/** Nur auf dev. Als Konstante, damit der Prod-Build den Rest wegwirft. */
const AUF_DEV = process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev";

/** So viele Wahlbezirke hat Oldenburg — dieselbe Zahl, mit der die
 *  Generalprobe im Backend rechnet (`mayor.probe`, `election.service.probe`). */
export const BEZIRKE = 133;

/** Die Stationen, an denen sich das Verhalten der Seite ändert. Gemessen,
 *  nicht geraten: Bei 0 gibt es keine Zahlen, ab dem ersten Bezirk läuft die
 *  Auszählung, die Hochrechnung braucht eine Weile, und der Endstand ist der
 *  einzige Zustand mit „ausgezählt". */
const SPRUENGE: { wert: number; label: string; hinweis: string }[] = [
  { wert: 0, label: "Vor 18 Uhr", hinweis: "Noch nichts ausgezählt" },
  { wert: 1, label: "1. Bezirk", hinweis: "Die erste Zahl des Abends" },
  { wert: 12, label: "12", hinweis: "Früher Stand, große Sprünge" },
  { wert: 45, label: "45", hinweis: "Ein Drittel" },
  { wert: 90, label: "90", hinweis: "Zwei Drittel" },
  { wert: 132, label: "132", hinweis: "Einer fehlt noch" },
  { wert: BEZIRKE, label: "Endstand", hinweis: "Alle Bezirke ausgezählt" },
];

/** Schrittweite und Takt des Abspielens: 4 Bezirke je 1,2 s sind schnell
 *  genug für einen Durchlauf in gut einer halben Minute und langsam genug,
 *  dass man die Bewegung auf der Seite noch sieht. */
const SCHRITT = 4;
const TAKT_MS = 1200;

export function AuszaehlungsSimulator() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const probeAn = params.get("probe") !== null;
  const counted = Number(params.get("counted") ?? "0");
  const [offen, setOffen] = useState(true);
  const [laeuft, setLaeuft] = useState(false);
  // Der Abspiel-Takt liest den Stand über eine Ref: Ein Intervall, das bei
  // jedem neuen `counted` neu aufgesetzt wird, springt sichtbar.
  const standRef = useRef(counted);
  standRef.current = counted;

  const setze = useCallback((wert: number | null) => {
    const q = new URLSearchParams(params.toString());
    if (wert === null) {
      q.delete("probe");
      q.delete("counted");
    } else {
      q.set("probe", "2021");
      q.set("counted", String(Math.max(0, Math.min(BEZIRKE, wert))));
    }
    const s = q.toString();
    // `replace`, nicht `push`: Ein Regler soll keine hundert Einträge in der
    // Zurück-Liste hinterlassen.
    router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
  }, [params, pathname, router]);

  useEffect(() => {
    if (!laeuft) return;
    const id = window.setInterval(() => {
      const naechster = standRef.current + SCHRITT;
      if (naechster >= BEZIRKE) {
        setze(BEZIRKE);
        setLaeuft(false);
        return;
      }
      setze(naechster);
    }, TAKT_MS);
    return () => window.clearInterval(id);
  }, [laeuft, setze]);

  if (!AUF_DEV) return null;

  const station = SPRUENGE.find((s) => s.wert === counted);
  const phase = !probeAn ? "live" : counted === 0 ? "vor der Auszählung" : counted >= BEZIRKE ? "ausgezählt" : "Auszählung läuft";

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center px-3 pb-[calc(env(safe-area-inset-bottom)+10px)]">
      <div
        data-testid="auszaehlungs-simulator"
        className={cn(
          "pointer-events-auto w-full max-w-2xl rounded-2xl border border-amber-300/70 bg-amber-50/95 shadow-[0_12px_40px_-12px_rgba(0,0,0,0.35)] backdrop-blur",
          "dark:border-amber-500/40 dark:bg-amber-950/90",
        )}
      >
        <div className="flex items-center gap-2.5 px-3.5 py-2">
          <span className="rounded-full bg-amber-200/80 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-amber-900 dark:bg-amber-500/25 dark:text-amber-100">
            nur dev
          </span>
          <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-amber-900 dark:text-amber-100">
            Auszählungs-Simulator ·{" "}
            <span className="font-normal">
              {probeAn ? `${counted}/${BEZIRKE} Bezirke · ${phase}` : "aus (echte Daten)"}
            </span>
          </span>
          <button
            type="button"
            onClick={() => setOffen((o) => !o)}
            aria-expanded={offen}
            aria-label={offen ? "Simulator einklappen" : "Simulator ausklappen"}
            className="flex h-7 w-7 flex-none items-center justify-center rounded-lg text-amber-900 hover:bg-amber-200/60 dark:text-amber-100 dark:hover:bg-amber-500/20"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", !offen && "rotate-180")} />
          </button>
        </div>

        {offen ? (
          <div className="border-t border-amber-300/60 px-3.5 py-3 dark:border-amber-500/30">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => { if (!probeAn) setze(0); setLaeuft((l) => !l); }}
                className="flex h-9 flex-none items-center gap-1.5 rounded-lg bg-amber-900 px-3 text-[13px] font-semibold text-amber-50 hover:bg-amber-800 dark:bg-amber-100 dark:text-amber-950 dark:hover:bg-white"
              >
                {laeuft ? <><Pause className="h-3.5 w-3.5" /> Pause</> : <><Play className="h-3.5 w-3.5" /> Abspielen</>}
              </button>
              <input
                type="range"
                min={0}
                max={BEZIRKE}
                step={1}
                value={probeAn ? counted : 0}
                aria-label="Ausgezählte Wahlbezirke"
                onChange={(e) => { setLaeuft(false); setze(Number(e.target.value)); }}
                className="h-9 min-w-0 flex-1 accent-amber-700 dark:accent-amber-300"
              />
              <span className="w-[74px] flex-none text-right font-mono text-[13px] tabular-nums text-amber-900 dark:text-amber-100">
                {probeAn ? counted : 0}/{BEZIRKE}
              </span>
              <button
                type="button"
                onClick={() => { setLaeuft(false); setze(null); }}
                title="Zurück zu den echten Daten"
                aria-label="Zurück zu den echten Daten"
                className="flex h-9 w-9 flex-none items-center justify-center rounded-lg border border-amber-300 text-amber-900 hover:bg-amber-200/60 dark:border-amber-500/40 dark:text-amber-100 dark:hover:bg-amber-500/20"
              >
                <RotateCcw className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {SPRUENGE.map((s) => (
                <button
                  key={s.wert}
                  type="button"
                  title={s.hinweis}
                  onClick={() => { setLaeuft(false); setze(s.wert); }}
                  className={cn(
                    "rounded-lg px-2.5 py-1 text-[12px] font-medium transition-colors",
                    probeAn && counted === s.wert
                      ? "bg-amber-900 text-amber-50 dark:bg-amber-100 dark:text-amber-950"
                      : "border border-amber-300/80 text-amber-900 hover:bg-amber-200/60 dark:border-amber-500/40 dark:text-amber-100 dark:hover:bg-amber-500/20",
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>

            <p className="mt-2 text-[11.5px] leading-relaxed text-amber-900/80 dark:text-amber-100/80">
              {station ? `${station.hinweis}. ` : ""}
              Die Zahlen sind die des ersten Wahlgangs, bezirksweise hochgerechnet — nichts davon ist ein Ergebnis vom
              27. September, und es wird nichts gespeichert.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
