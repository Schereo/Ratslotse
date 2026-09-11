"use client";

// Mitmachen (Screen 1b) — die QR-Ansicht, solange noch kein Ergebnis da ist.
//
// Abweichung vom Entwurf: Der Countdown zeigt KEINE tickende MM:SS-Uhr. Der
// Server nennt bewusst keinen festen Zeitpunkt für den Tipp-Schluss (PR 1,
// „Der Server nennt keine feste Uhrzeit, solange der Tipp-Schluss noch nicht
// gesetzt ist" — er kommt erst mit der ersten echten Hochrechnung oder Tims
// Klick auf „Tippen jetzt schließen"). Eine Uhr ohne echtes Ziel wäre Theater
// statt Information; `deadline_hint` steht deshalb als Text da, nicht als
// tickende Zahl.

import { apiUrl } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { BrandMark } from "@/components/brand";
import { Lotti } from "@/components/lotti";

type PredictionGame = ApiAntwort<"/tipp/setup">;

export function BeamerMitmachen({ game, tipCount }: { game: PredictionGame; tipCount: number }) {
  return (
    <div className="grid h-full grid-cols-1 items-center gap-10 px-6 py-8 sm:px-14 lg:grid-cols-[1fr_620px]">
      {/* `min-w-0` auf beiden Spalten: Ein Grid-Item ist ohne das erst ab der
          Breite seines INHALTS schrumpfbar — die 560px-QR-Karte hätte sonst
          die ganze Seite auf schmalen Schirmen aufgeweitet (gemessen: 194px
          Überbreite bei 390px). */}
      <div className="flex min-w-0 flex-col items-start">
        <div className="flex items-center gap-2.5">
          <BrandMark className="h-8 w-8" />
          <span className="font-mono text-[12px] uppercase tracking-[0.14em] text-primary">Tippspiel</span>
        </div>
        <h1 className="mt-5 max-w-[14ch] text-balance font-display text-[64px] font-black leading-[0.98] tracking-tight sm:text-[88px] lg:text-[104px]">
          {game.title}
        </h1>
        <p className="mt-5 max-w-[46ch] text-[17px] leading-relaxed text-muted-foreground sm:text-[19px]">
          Wie viele Sitze bekommt jede Liste im neuen Rat, und wer wird
          Oberbürgermeister*in? Mit dem Handy den QR-Code scannen, Namen
          eintippen, tippen — fertig in einer Minute.
        </p>

        <div className="hh-tafel mt-7 flex items-center gap-3 rounded-2xl px-5 py-3.5">
          <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">Tippen noch</span>
          <span className="font-display text-lg font-bold">{game.deadline_hint}</span>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <Lotti regung="zeigt-rechts" className="h-14 w-14 flex-none" decorative />
          <p className="text-[15px] font-medium">
            <span className="font-display text-xl font-bold tabular-nums">{tipCount}</span>{" "}
            Mitspielende {tipCount === 1 ? "hat" : "haben"} schon getippt.
          </p>
        </div>
      </div>

      <div className="mx-auto flex w-full min-w-0 max-w-[560px] flex-col items-center gap-4">
        <div className="flex aspect-square w-full items-center justify-center overflow-hidden rounded-[28px] bg-white p-8 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.35)]">
          {/* `w-full max-w-[560px]` statt `w-[560px] max-w-full`: Mit einer
              festen Breite VOR der Kappung trägt das Element seine 560px als
              bevorzugte Größe durch Flex/Grid nach oben, bevor `max-width`
              greift — genau das erzeugte die 194px Überbreite bei 390px. Mit
              `width:100%` zuerst übernimmt die Karte direkt, was der (durch
              `min-w-0` korrekt geschrumpfte) Elternrahmen ihr tatsächlich
              zuteilt, und `max-w-[560px]` deckelt nur die Obergrenze.
              `max-w-full h-auto` auf dem Bild selbst: Die HTML-Attribute
              `width`/`height` legen nur das SEITENVERHÄLTNIS fest (verhindert
              Ruckeln beim Nachladen) und dürfen die Karte nicht aufweiten,
              wenn das Bild gerade lädt oder mal nicht erreichbar ist.
              `overflow-hidden` zusätzlich auf der Karte: Ein NICHT geladenes
              Bild rendert seinen Alt-Text im Browser ohne Rücksicht auf
              `max-width` (gemessen: 194px Überbreite bei 390px trotz `max-w-
              full` auf dem `img`) — die Karte selbst darf das nie nach außen
              tragen. */}
          {/* eslint-disable-next-line @next/next/no-img-element -- externes PNG vom Backend, kein next/image-Fall */}
          <img src={apiUrl("/tipp/qr.png")} alt="QR-Code zum Tippspiel" width={480} height={480} className="h-auto max-w-full" />
        </div>
        <p className="font-mono text-[20px] font-semibold tracking-tight text-foreground">ratslotse.de/tipp</p>
      </div>
    </div>
  );
}
