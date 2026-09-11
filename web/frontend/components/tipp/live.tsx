"use client";

// Beamer-Rahmen (`/tipp/live`) — Schalter-Gate, Theme, Polling und die
// Automatik zwischen QR / Vergleich / Rangliste. Die drei Screens selbst
// stehen in eigenen Dateien (beamer-mitmachen/-vergleich, scoreboard).
//
// Der Seiten-Hintergrund bleibt das GEWÖHNLICHE `bg-background` — gemessen
// stimmen dessen `:root`/`.dark`-Werte bereits exakt mit der Design-Tabelle
// für „Seite" überein (Hell 204 45% 97.5 %, Dunkel 213 50% 7 %). Nur die
// hervorgehobene „Anzeigetafel" je Screen (Countdown-Rahmen, Vergleichs-Satz)
// trägt zusätzlich `.hh-tafel` — dieselbe Klasse, mit der auch der Haushalt
// seine Tafel absetzt, und deren Werte ebenso exakt zur Tabellenzeile
// „Karte" passen. Kein einziger Hex-/HSL-Wert musste dafür neu eingetragen
// werden.

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { applyTheme, getTheme } from "@/lib/theme";
import type { ApiAntwort } from "@/lib/vertrag";
import { Lotti } from "@/components/lotti";
import { WebThemeSwitch } from "@/components/web-theme-switch";
import { BeamerMitmachen } from "./beamer-mitmachen";
import { BeamerVergleich } from "./beamer-vergleich";
import { Scoreboard } from "./scoreboard";

type PredictionStand = ApiAntwort<"/tipp/stand">;
type PredictionGame = ApiAntwort<"/tipp/setup">;
type Ansicht = "qr" | "vergleich" | "rangliste";

async function holeStand(): Promise<PredictionStand> {
  return api.get<PredictionStand>("/tipp/stand");
}
async function holeSetup(): Promise<PredictionGame> {
  return api.get<PredictionGame>("/tipp/setup");
}

export function TippLive() {
  const schalterAn = useFeature("tippspiel");
  const params = useSearchParams();
  const erzwungen = params.get("ansicht") as Ansicht | null;

  // Erstbesuch: dunkles Theme (Regel 3). Merkt sich danach die Wahl des
  // Geräts wie überall sonst — kein zweites, seiteneigenes Theme-System,
  // nur eine andere Voreinstellung, solange nie aktiv gewählt wurde.
  useEffect(() => {
    if (getTheme() === "system") applyTheme("dark");
  }, []);

  const standQuery = useQuery({
    queryKey: ["tipp", "stand-live"],
    queryFn: holeStand,
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
          Am 13. September 2026 ab 18 Uhr zeigt diese Seite den Auszählungsstand der Ratswahl gegen die Tipps der Runde.
        </p>
      </div>
    );
  }

  if (!stand || !setupQuery.data) {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-background">
        <span className="text-sm text-muted-foreground">Lädt …</span>
      </div>
    );
  }

  const ansicht: Ansicht = erzwungen ?? (!hatErgebnis ? "qr" : auto);

  return (
    <div className="relative min-h-[100dvh] bg-background text-foreground">
      <div className="absolute right-5 top-5 z-10">
        <WebThemeSwitch />
      </div>
      {/* `key={ansicht}` baut den Screen beim Wechsel neu auf — der
          Wechsel BLENDET nur (Designsprache: nichts schiebt sich). */}
      <div key={ansicht} className="animate-fade-up min-h-[100dvh]">
        {ansicht === "qr" && <BeamerMitmachen game={setupQuery.data} tipCount={stand.tip_count} />}
        {ansicht === "vergleich" && <BeamerVergleich stand={stand} />}
        {ansicht === "rangliste" && <Scoreboard stand={stand} />}
      </div>
    </div>
  );
}
