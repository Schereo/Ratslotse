"use client";

// Anzeigetafel des Haushalts-Einstiegs (Entwurf H2-01 Desktop, H2-11 mobil,
// H2-12 dunkel): eine abgesetzte Fläche, auf der die Kernzahl des Jahres
// steht, daneben die drei Summen und darunter das Kern-Visual.
//
// Warum „Tafel" und nicht „Bühne": In `DESIGNSPRACHE.md` heißt die
// Tonfläche hsl(205 42% 96,5%) bereits Bühne. Zwei Flächen unter einem Namen
// löst später niemand mehr auf, deshalb trägt diese hier einen eigenen —
// die Farb- und Rampenbindung dazu steht als `.hh-tafel` in `app/globals.css`.
// Dort steht auch, warum die Fläche seit 16.08. dem Theme folgt, statt in
// beiden dunkel zu sein: Im Hellmodus war ein schwarzblaues Feld über die
// halbe Seite schlicht zu viel.
//
// Drei Dinge sind an den Texten wichtig, weil sie sonst still falsch werden:
//
//  1. **Jahresabhängige Sätze werden gerechnet.** Für 2020–2022 plante die
//     Stadt einen Überschuss, ab 2023 ein Minus; ein fester Satz „71,1 Mio.
//     fehlen" wäre beim Umschalten auf 2021 schlicht gelogen.
//  2. **„plant" ist Pflicht.** `council_haushalt` trägt Planwerte, und die
//     Ist-Jahre widersprechen ihnen regelmäßig (2023 geplant −9,8, tatsächlich
//     +50,0). Für abgeschlossene Jahre steht der Satz deshalb im Präteritum.
//  3. **Die Summe ist nicht das Budget.** 883,9 Mio. sind der
//     Ergebnishaushalt; die Investitionen des Finanzhaushalts fehlen darin.
//     Der Hinweis steht auf der Tafel neben der Zahl, nicht als Fußnote
//     irgendwo unten — wer nur die große Zahl liest, soll ihn mitlesen. Seit
//     08/2026 verweist er auf `/haushalt/investitionen`: Bis dahin nannte der
//     Bereich diese Zahl nirgends, der Satz endete also in einer Sackgasse.

import Link from "next/link";
import type { ReactNode } from "react";
import { Beleg } from "@/components/haushalt/quelle";
import { HaushaltZeile, deMio, mio, summe } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

function Summe({ label, wert, ton }: {
  label: string; wert: number | null; ton?: "signal";
}) {
  return (
    <div className="min-w-0">
      <p className={cn(
        "text-[11.5px] leading-none",
        ton === "signal" ? "text-signal" : "text-muted-foreground",
      )}>
        {label}
      </p>
      <p className={cn(
        "mt-1.5 font-display text-[21px] font-bold leading-none tracking-tight tabular-nums sm:text-[27px]",
        ton === "signal" ? "text-signal" : "text-foreground",
      )}>
        {deMio(wert)}
      </p>
    </div>
  );
}

export function Tafel({ zeilen, jahr, aktuell, aktion, children }: {
  zeilen: HaushaltZeile[];
  jahr: number;
  /** Ist das das jüngste Haushaltsjahr? Steuert nur die Zeitform. */
  aktuell: boolean;
  /** Umschalter o. Ä., sitzt im Fuß der Tafel. */
  aktion?: ReactNode;
  /** Das Kern-Visual (Gegenbalken bzw. 100-Euro-Ansicht). */
  children?: ReactNode;
}) {
  const gesamt = summe(zeilen);
  const einMio = mio(gesamt?.ertraege);
  const ausMio = mio(gesamt?.aufwendungen);
  // Saldo aus den Rohwerten runden: 812,9 − 883,9 ergäbe −71,0, tatsächlich
  // sind es −71,1 (dieselbe Falle wie in `gegenbalken.tsx`).
  const saldo = gesamt?.ertraege != null && gesamt?.aufwendungen != null
    ? mio(gesamt.ertraege - gesamt.aufwendungen)
    : null;
  if (ausMio == null) return null;

  const fehlt = saldo != null && saldo < 0 ? -saldo : null;
  const ueber = saldo != null && saldo > 0 ? saldo : null;

  return (
    <div className="hh-tafel rounded-2xl p-4 sm:p-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-primary sm:text-[10.5px]">
            Stadthaushalt Oldenburg {jahr}
          </p>
          {/* 19ch war zu eng: Der Satz passt in zwei Zeilen, die Begrenzung erzwang
              aber eine dritte — und weil `hyphens: auto` auf allen Überschriften
              steht (globals.css, für Komposita auf schmalen Screens), trennte der
              Browser mitten in „Millionen", während rechts 400 px frei blieben.
              `text-balance` verteilt die Zeilen gleichmäßig, statt die letzte
              mit einem Wort stehen zu lassen. */}
          <h1 className="mt-2.5 max-w-[30ch] text-balance font-display text-[23px] font-bold leading-[1.15] tracking-tight sm:text-[32px]">
            {aktuell
              ? <>Oldenburg plant {deMio(ausMio)} Millionen&nbsp;Euro.</>
              : <>{jahr} plante Oldenburg {deMio(ausMio)} Millionen&nbsp;Euro.</>}
          </h1>
          {fehlt != null && (
            <p className="mt-3 max-w-[52ch] text-[13.5px] leading-relaxed text-muted-foreground sm:text-[15px]">
              {deMio(fehlt)} Millionen Euro davon sind durch Einnahmen nicht gedeckt —
              sie {aktuell ? "kommen" : "kamen"} aus dem Ersparten der Stadt.
            </p>
          )}
          {ueber != null && (
            <p className="mt-3 max-w-[52ch] text-[13.5px] leading-relaxed text-muted-foreground sm:text-[15px]">
              {aktuell ? "Geplant sind" : "Geplant waren"} {deMio(ueber)} Millionen Euro mehr
              Einnahmen als Ausgaben. Was am Jahresende wirklich herauskam, steht
              erst im Jahresabschluss.
            </p>
          )}
        </div>

        <div className="flex flex-none gap-6 sm:gap-7 sm:pt-1">
          <Summe label={aktuell ? "nimmt ein" : "nahm ein"} wert={einMio} />
          <Summe label={aktuell ? "gibt aus" : "gab aus"} wert={ausMio} />
          {fehlt != null
            ? <Summe label="fehlt" wert={fehlt} ton="signal" />
            : ueber != null
              ? <Summe label="bleibt übrig" wert={ueber} />
              : null}
        </div>
      </div>

      {/* Steht bei der Zahl, nicht in einer Fußnote: Wer „883,9 Millionen"
          liest, hält das sonst für das ganze Budget der Stadt. */}
      <p className="mt-3.5 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Diese Summe ist der{" "}
        <strong className="font-semibold text-foreground/90">Ergebnishaushalt</strong>
        <Beleg q="plan" />: alles Laufende eines Jahres. Investitionen — Neubauten,
        Fahrzeuge, Grundstücke — stehen in einem eigenen Haushalt und damit{" "}
        <Link href="/haushalt/investitionen" className="text-primary hover:underline">
          auf einer eigenen Seite
        </Link>
        . Das Budget der Stadt ist also größer als die Zahl oben.
      </p>

      {children && <div className="mt-5">{children}</div>}

      {aktion && (
        <div className="mt-5 flex justify-end border-t border-border pt-4">{aktion}</div>
      )}
    </div>
  );
}
