// Verzeichnis der Teilhaushalte — Betrag, Name, eine Zeile Klartext.
//
// Der Verständlichkeits-Durchgang hat eine Frage als die drängendste notiert:
// „Soziales", „Finanzmanagement" — was heißt das eigentlich? Die Namen kommen
// aus der Verwaltungsgliederung und sagen von außen nichts; wer sie zum ersten
// Mal liest, rät. Diese Liste beantwortet das für alle Teilhaushalte an einer
// Stelle, statt die Erklärung über die Seiten zu verstreuen.
//
// Die Klartext-Zeile kommt aus `lib/haushalt-bereiche.ts` und NICHT aus einer
// eigenen Namensliste. Die Stadt benennt Teilhaushalte um, ohne den Zuschnitt
// zu ändern — Teilhaushalt 9 trägt in sieben Jahrgängen vier Schreibweisen.
// Eine zweite Map hier hätte beim nächsten Jahrgang still Zeilen verloren.
// Umgekehrt verschwindet ein Bereich, den das Wörterbuch nicht kennt, auch
// nicht: Er steht mit seinem Rohnamen da und sagt, dass die Erklärung fehlt.
//
// Sortiert nach Ausgaben, nicht nach Teilhaushalts-Nummer: Die Nummer ist eine
// Verwaltungsordnung, die Größe die Antwort auf „worum geht es hier überhaupt".

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { bereichKanon } from "@/lib/haushalt-bereiche";
import { HaushaltZeile, bereichSlug, bereiche, deMio, mio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

export type KlartextZeile = {
  zeile: HaushaltZeile;
  /** Ausgaben in Mio. — die Größe, nach der sortiert und beschriftet wird. */
  aus: number;
  name: string;
  klartext: string | null;
  slug: string;
};

/** Die Bereichszeilen eines Jahres, aufgelöst und nach Ausgaben sortiert. */
export function klartextZeilen(zeilen: HaushaltZeile[]): KlartextZeile[] {
  return bereiche(zeilen)
    .map((z) => {
      const k = bereichKanon(z.bereich);
      return {
        zeile: z,
        aus: mio(z.aufwendungen) ?? 0,
        // Der Anzeigename ist die jüngste amtliche Schreibweise; verlinkt wird
        // weiter über den Slug des DB-Namens (Regel 2 des Wörterbuchs).
        name: k.name,
        klartext: k.klartext,
        slug: bereichSlug(z.bereich),
      };
    })
    .sort((a, b) => b.aus - a.aus);
}

/** Eine Zeile: Betrag, Name, Klartext. Die ganze Zeile ist der Link — ein
 *  eigener „mehr"-Anhang neben 13 Einträgen wäre 13-mal dasselbe Wort. */
function Zeile({ z, aktiv }: { z: KlartextZeile; aktiv: boolean }) {
  return (
    <Link
      href={`/haushalt/bereich?name=${z.slug}`}
      aria-current={aktiv ? "page" : undefined}
      className={cn(
        // `break-inside-avoid`: Ein Eintrag darf nicht über den Spaltenumbruch
        // zerfallen — Betrag oben, Erklärung in der nächsten Spalte wäre zwei
        // halbe Zeilen.
        "group flex break-inside-avoid items-start gap-3.5 rounded-xl px-2.5 py-3 transition-colors hover:bg-accent",
        aktiv && "bg-primary/[0.06]",
      )}
    >
      <span className="flex-none pt-px text-right font-mono text-[12.5px] font-medium tabular-nums">
        {deMio(z.aus)}
      </span>
      <span className="min-w-0 flex-1">
        {/* Der Pfeil steht IM Textfluss, nicht als Flex-Nachbar: Bei einem
            Namen, der umbricht („Wirtschaftsförderung, Liegenschaften" auf
            375 px), stand er sonst weit rechts neben der zweiten Zeile und
            gehörte sichtbar zu nichts. */}
        <span className="text-[13.5px] font-bold leading-snug">
          {z.name}
          <ChevronRight
            aria-hidden
            className="ml-1 inline-block h-3.5 w-3.5 align-[-2px] text-muted-foreground transition-transform group-hover:translate-x-0.5"
          />
        </span>
        {z.klartext ? (
          <span className="mt-1 block text-[12.5px] leading-relaxed text-foreground/75">
            {z.klartext}
          </span>
        ) : (
          /* Gestrichelt = „noch nicht von uns" (Designsprache §4). Ein neuer
             Jahrgang mit neuem Namen soll sichtbar auffallen, statt still
             ohne Erklärung dazustehen. */
          <span className="mt-1 block w-fit rounded border border-dashed border-border px-1.5 py-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Diesen Zuschnitt haben wir noch nicht erklärt.
          </span>
        )}
      </span>
    </Link>
  );
}

/** Das Verzeichnis. `aktiv` hebt den Bereich hervor, von dem man kommt. */
export function NamenKlartext({ zeilen, jahr, aktiv, className }: {
  zeilen: HaushaltZeile[];
  jahr: number;
  /** Bereichsname (DB-Schreibweise) der aufrufenden Seite. */
  aktiv?: string;
  className?: string;
}) {
  const rows = klartextZeilen(zeilen);
  if (!rows.length) return null;
  const aktivSlug = aktiv ? bereichSlug(aktiv) : null;

  return (
    <div className={cn("@container/klartext", className)}>
      <div className="mb-1.5 flex items-baseline gap-3.5 px-2.5">
        <span className="flex-none font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Mio. €
        </span>
        <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Ausgaben {jahr} · {rows.length} Teilhaushalte
        </span>
      </div>
      {/* Zwei Spalten am Container, nicht am Fenster (Designsprache §4): Auf
          dem iPad liegt die Liste ohne Seitenleiste, am Desktop mit — dieselbe
          Fensterbreite meint zwei verschiedene Platzangebote.

          Textspalten (`columns`) statt Raster (`grid`), und zwar aus zwei
          Gründen. Ein Raster füllt ZEILEN: Die Reihenfolge liefe dann
          links-rechts-links, obwohl die Liste sortiert ist, und jede Zeile
          würde so hoch wie ihr längerer Eintrag — unter dem kürzeren bliebe
          Leerraum stehen. Spalten fließen von oben nach unten, und jeder
          Eintrag ist so hoch, wie er ist. */}
      <div className="gap-x-8 @3xl/klartext:columns-2">
        {rows.map((z) => (
          <Zeile key={z.zeile.bereich} z={z} aktiv={z.slug === aktivSlug} />
        ))}
      </div>
    </div>
  );
}
