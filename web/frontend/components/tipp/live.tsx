"use client";

// Beamer-Rahmen (`/tipp/live`) — Schalter-Gate, Theme, Polling und die
// Automatik zwischen QR / Vergleich / Rangliste. Die drei Screens selbst
// stehen in eigenen Dateien (beamer-mitmachen/-vergleich, scoreboard).
//
// Der Seiten-Hintergrund bleibt das GEWÖHNLICHE `bg-background` — gemessen
// stimmen dessen `:root`/`.dark`-Werte exakt mit der Design-Tabelle für
// „Seite" überein (Hell 204 45% 97.5 %, Dunkel 213 50% 7 %), die Karten mit
// der Zeile „Karte". Kein einziger Hex-/HSL-Wert musste dafür neu
// eingetragen werden; die Screens folgen damit dem Theme, und im Hellmodus
// steht keine dunkle Kachel (Tims stehende Regel, geprüft in
// `17-tippspiel-live.spec.ts`).

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { applyTheme, getTheme } from "@/lib/theme";
import { probePfad } from "@/lib/tipp";
import { cn } from "@/lib/utils";
import type { ApiAntwort } from "@/lib/vertrag";
import { Lotti } from "@/components/lotti";
import { WebThemeSwitch } from "@/components/web-theme-switch";
import { BeamerMitmachen } from "./beamer-mitmachen";
import { BeamerVergleich } from "./beamer-vergleich";
import { HandyRangliste, Scoreboard } from "./scoreboard";
import { Buehne, useSchmal } from "./buehne";

type PredictionStand = ApiAntwort<"/tipp/stand">;
type PredictionGame = ApiAntwort<"/tipp/setup">;
type Ansicht = "qr" | "vergleich" | "rangliste";

//: Die Wahl in der Ecke — „Automatik" ist der Abend-Betrieb, die drei
//: anderen halten je einen Screen fest.
const ANSICHTEN = [
  ["auto", "Automatik"],
  ["qr", "QR-Code"],
  ["vergleich", "Vergleich"],
  ["rangliste", "Rangliste"],
] as const;

async function holeStand(pfad: string): Promise<PredictionStand> {
  return api.get<PredictionStand>(pfad);
}
async function holeSetup(): Promise<PredictionGame> {
  return api.get<PredictionGame>("/tipp/setup");
}

export function TippLive() {
  const schalterAn = useFeature("tippspiel");
  const schmal = useSchmal();
  const params = useSearchParams();
  const erzwungen = params.get("ansicht") as Ansicht | null;
  const probe = params.get("probe");
  const counted = params.get("counted");
  const standPfad = probePfad("/tipp/stand", probe, counted);

  // Erstbesuch: dunkles Theme (Regel 3). Merkt sich danach die Wahl des
  // Geräts wie überall sonst — kein zweites, seiteneigenes Theme-System,
  // nur eine andere Voreinstellung, solange nie aktiv gewählt wurde.
  useEffect(() => {
    if (getTheme() === "system") applyTheme("dark");
  }, []);

  const standQuery = useQuery({
    queryKey: ["tipp", "stand-live", standPfad],
    queryFn: () => holeStand(standPfad),
    enabled: schalterAn,
    placeholderData: keepPreviousData,
    refetchInterval: (q) => {
      const hat = q.state.data?.compare.some((c) => c.actual !== null) ?? false;
      return hat ? 30_000 : 60_000;
    },
  });
  const setupQuery = useQuery({ queryKey: ["tipp", "setup-live"], queryFn: holeSetup, enabled: schalterAn });

  const stand = standQuery.data;
  const hatErgebnis = stand?.compare.some((c) => c.actual !== null) ?? false;

  const [auto, setAuto] = useState<"vergleich" | "rangliste">("vergleich");
  // Was der Raum gerade sehen soll. `auto` ist der Abend-Betrieb (QR bis zum
  // ersten Ergebnis, danach der 45-s-Wechsel); jede andere Wahl hält den
  // Screen fest — auch VOR dem ersten Ergebnis, damit Tim nach der
  // Tipprunde auf die Hochrechnung umschalten kann (sein Wunsch 11.09.).
  const [wahl, setWahl] = useState<Ansicht | "auto">(erzwungen ?? "auto");
  // Die Steuerung gehört nicht dauerhaft auf eine Leinwand: Sie kommt bei
  // Mausbewegung und geht nach vier Sekunden Ruhe wieder — wie bei einem
  // Videoplayer. Das Generalprobe-Schild bleibt davon unberührt.
  const [steuerungWach, setSteuerungWach] = useState(true);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const wach = () => {
      setSteuerungWach(true);
      clearTimeout(t);
      t = setTimeout(() => setSteuerungWach(false), 4000);
    };
    wach();
    for (const e of ["mousemove", "keydown", "touchstart"] as const) window.addEventListener(e, wach);
    return () => {
      clearTimeout(t);
      for (const e of ["mousemove", "keydown", "touchstart"] as const) window.removeEventListener(e, wach);
    };
  }, []);
  const computedAtRef = useRef<string | null>(null);
  const erzwingenBisRef = useRef(0);

  // Ein frischer `computed_at` (neue Hochrechnung eingetroffen) springt für
  // 60 s auf die Rangliste — den spannendsten Moment sieht der Raum zuerst.
  useEffect(() => {
    if (!stand) return;
    if (computedAtRef.current !== null && stand.computed_at !== computedAtRef.current) {
      setAuto("rangliste");
      erzwingenBisRef.current = Date.now() + 60_000;
    }
    computedAtRef.current = stand.computed_at;
    // Bewusst nur `computed_at`: `stand` selbst ist bei jedem Poll ein neues
    // Objekt, auch ohne neue Hochrechnung — ein Sprung auf die Rangliste soll
    // aber nur beim ECHTEN Wechsel passieren, nicht bei jedem Nachladen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stand?.computed_at]);

  useEffect(() => {
    const id = setInterval(() => {
      if (Date.now() < erzwingenBisRef.current) return;
      setAuto((a) => (a === "vergleich" ? "rangliste" : "vergleich"));
    }, 45_000);
    return () => clearInterval(id);
  }, []);

  if (!schalterAn) {
    return (
      <div className="mx-auto mt-24 flex max-w-md flex-col items-center px-6 text-center">
        <Lotti regung="schlaeft" className="h-28 w-28" decorative />
        <h1 className="mt-4 font-display text-[22px] font-bold tracking-tight">Das Tippspiel ist noch nicht freigeschaltet</h1>
        <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">
          Am 13. September 2026 ab 18 Uhr kannst du hier den Wahlabend verfolgen und die Ergebnisse mit den Tipps vergleichen.
        </p>
      </div>
    );
  }

  if (!stand || !setupQuery.data || schmal === null) {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-background">
        <span className="text-sm text-muted-foreground">Lädt …</span>
      </div>
    );
  }

  const ansicht: Ansicht = wahl === "auto" ? (!hatErgebnis ? "qr" : auto) : wahl;

  return (
    <div className="relative min-h-[100dvh] bg-background text-foreground">
      {/* Steuerung und Schild stehen OBEN MITTE: Der Kopf jedes Screens hat
          dort nichts stehen (links die Marke, rechts die Live-Zeile) — an der
          rechten Ecke lagen sie übereinander. */}
      <div className={cn(
        "absolute top-4 z-10 flex flex-col items-center gap-2",
        // Auf der Leinwand oben MITTE (der Kopf trägt links die Marke, rechts
        // die Live-Zeile). Auf dem Handy gibt es die Bühne nicht, sondern die
        // kompakte Rangliste — und deren Abzeichen steht genau in der Mitte
        // oben. Dort lagen Schalter und Abzeichen übereinander (Tims Bild vom
        // 11.09.); auf schmalen Geräten geht der Schalter deshalb nach rechts.
        schmal ? "right-4" : "left-1/2 -translate-x-1/2",
      )}>
        {probe && !schmal && (
          // Auf einem Beamer im vollen Raum darf die Generalprobe keine
          // Sekunde wie das echte Ergebnis aussehen (dieselbe Zusage wie im
          // Wahlabend, der seine Probe ebenfalls ausschildert) — das Schild
          // bleibt deshalb stehen, auch wenn die Steuerung verschwindet.
          <span className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1 font-mono text-[12px] uppercase tracking-[0.08em] text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200">
            Generalprobe · Zahlen von 2021
          </span>
        )}
        <div className={cn(
          "flex items-center gap-3 transition-opacity duration-500",
          steuerungWach ? "opacity-100" : "opacity-0",
          !steuerungWach && "pointer-events-none",
        )}>
          {!schmal && (
            <div role="group" aria-label="Was der Beamer zeigt" className="flex items-center gap-0.5 rounded-full border border-border bg-card/90 p-1 backdrop-blur">
              {ANSICHTEN.map(([wert, label]) => (
                <button
                  key={wert} type="button" aria-pressed={wahl === wert}
                  onClick={() => setWahl(wert)}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors duration-150",
                    wahl === wert ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
          <WebThemeSwitch />
        </div>
      </div>
      {schmal ? (
        // Handy und Tablet hochkant: statt der skalierten Leinwand die
        // kompakte Rangliste — die 1920er-Bühne wäre dort unlesbar klein.
        <HandyRangliste stand={stand} probe={!!probe} />
      ) : (
        // `key={ansicht}` baut den Screen beim Wechsel neu auf — der
        // Wechsel BLENDET nur (Designsprache: nichts schiebt sich).
        <div key={ansicht} className="animate-fade-up">
          <Buehne>
            {ansicht === "qr" && <BeamerMitmachen game={setupQuery.data} tipCount={stand.tip_count} />}
            {ansicht === "vergleich" && <BeamerVergleich stand={stand} />}
            {ansicht === "rangliste" && <Scoreboard stand={stand} />}
          </Buehne>
        </div>
      )}
    </div>
  );
}
