"use client";

// Mitmachen (Screen 1b) — die QR-Ansicht, solange noch kein Ergebnis da ist.
// Maße aus dem Artboard (1920×1080), skaliert von `buehne.tsx`: links Marke,
// Kicker, der 104-px-Titel, der Kasten „Tippen noch", Lotti mit der Zahl der
// Mitspielenden; rechts die 560-px-QR-Karte und die Adresse in Mono.
//
// Abweichung vom Entwurf: Der Kasten zeigt KEINE tickende MM:SS-Uhr. Der
// Server nennt bewusst keinen festen Zeitpunkt für den Tipp-Schluss — er
// kommt mit der ersten echten Hochrechnung oder Tims Klick. Eine Uhr ohne
// echtes Ziel wäre Theater; der Kasten trägt stattdessen „bis ca. 20 Uhr"
// und nach dem Schluss die Uhrzeit, zu der er fiel.

import { apiUrl } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { BrandMark } from "@/components/brand";
import { Lotti } from "@/components/lotti";
import { uhrzeitKurz } from "@/lib/tipp";

type PredictionGame = ApiAntwort<"/tipp/setup">;

export function BeamerMitmachen({ game, tipCount }: { game: PredictionGame; tipCount: number }) {
  const schluss = uhrzeitKurz(game.locked_at);
  return (
    <div className="grid h-full grid-cols-[1fr_620px] gap-20 px-[120px] py-24 text-foreground">
      <div className="flex flex-col justify-center">
        <div className="flex items-center gap-[18px]">
          <BrandMark className="h-14 w-14" />
          <span className="font-display text-[36px] font-bold tracking-[-0.02em]">Ratslotse</span>
          <span className="border-l-2 border-border pl-[18px] text-[28px] text-muted-foreground">Wahlabend 13.09.2026</span>
        </div>
        <p className="mt-14 font-mono text-[26px] uppercase tracking-[0.11em] text-signal">Tippspiel</p>
        <h1 className="mt-3.5 text-balance font-display text-[104px] font-bold leading-none tracking-[-0.03em]">
          Wer tippt den Rat am besten?
        </h1>
        <p className="mt-[34px] max-w-[26ch] text-[36px] leading-[1.4] text-foreground/80">
          {game.seats_total} Sitze, {game.parties.length} Listen. Wer will, tippt auch die OB-Prozente. Nur ein Name, kein Konto.
        </p>

        <div className="mt-14 flex items-center gap-7">
          <div className="rounded-[24px] border-2 border-border px-[30px] py-[22px]">
            <p className="font-mono text-[22px] uppercase tracking-[0.1em] text-muted-foreground">
              {game.locked ? "Tipp-Schluss" : "Tippen noch"}
            </p>
            <p className="mt-1.5 font-display text-[64px] font-bold leading-none tabular-nums">
              {game.locked ? (schluss ?? "vorbei") : "bis ca. 20 Uhr"}
            </p>
            <p className="mt-2 text-[24px] text-muted-foreground">
              {game.locked ? "Nachtippen läuft außer Konkurrenz" : "bis zur ersten Hochrechnung"}
            </p>
          </div>
          <div className="flex items-center gap-[22px]">
            <Lotti regung="zeigt-rechts" className="h-[150px] w-[150px] flex-none" decorative />
            <p className="max-w-[16ch] text-[28px] leading-[1.45] text-foreground/80">
              <span className="font-semibold text-foreground">{tipCount}</span>{" "}
              Mitspielende {tipCount === 1 ? "hat" : "haben"} schon getippt.
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-col items-center justify-center gap-[34px]">
        <div className="h-[560px] w-[560px] rounded-[32px] bg-white p-[34px]">
          {/* eslint-disable-next-line @next/next/no-img-element -- externes PNG vom Backend, kein next/image-Fall */}
          <img src={apiUrl("/tipp/qr.png")} alt="QR-Code zum Tippspiel" width={492} height={492} className="h-full w-full" />
        </div>
        <p className="font-mono text-[40px] text-primary">ratslotse.de/tipp</p>
      </div>
    </div>
  );
}
