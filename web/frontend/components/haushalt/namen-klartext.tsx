"use client";

// Verzeichnis der Teilhaushalte — Betrag, Name, eine Zeile Klartext UND die
// Zusammensetzung, in EINER Zeile je Bereich (H4-02).
//
// Der Verständlichkeits-Durchgang hat eine Frage als die drängendste notiert:
// „Soziales", „Finanzmanagement" — was heißt das eigentlich? Die Namen kommen
// aus der Verwaltungsgliederung und sagen von außen nichts; wer sie zum ersten
// Mal liest, rät. Diese Liste beantwortet das für alle Teilhaushalte an einer
// Stelle, statt die Erklärung über die Seiten zu verstreuen.
//
// KLARTEXT UND ZAHLEN SIND EINE ZEILE (Review H4-02): Bis 17.08. führte die
// Seite die 13 Namen praktisch zweimal — einmal als Klartext-Liste, einmal
// (auf der Übersicht) als Zahlen-Tabelle. Zwei Listen derselben 13 Namen sind
// eine zu viel; jetzt trägt jede Zeile beides: den Satz UND den Balken mit
// Betrag. Der Balken ist dieselbe Aussage wie in der Bereichstabelle der
// Übersicht (dunkel = schießt die Stadt zu, hell = nimmt der Bereich selbst
// ein, EINE Skala für alle) — dieselbe Grammatik, damit niemand zwei
// Bildsprachen für dieselbe Sache lernt.
//
// Die Klartext-Zeile kommt aus `lib/haushalt-bereiche.ts` und NICHT aus einer
// eigenen Namensliste. Die Stadt benennt Teilhaushalte um, ohne den Zuschnitt
// zu ändern — Teilhaushalt 9 trägt in sieben Jahrgängen vier Schreibweisen.
// Eine zweite Map hier hätte beim nächsten Jahrgang still Zeilen verloren.
// Umgekehrt verschwindet ein Bereich, den das Wörterbuch nicht kennt, auch
// nicht: Er steht mit seinem Rohnamen da und sagt, dass die Erklärung fehlt.
//
// SORTIERUNG per Umschalter (H4-A: „Sortier-Select statt Spaltenköpfe"),
// Vorgabe Ausgaben: Die Nummer im Haushaltsplan ist eine Verwaltungsordnung,
// die Größe die Antwort auf „worum geht es hier überhaupt". Die Labels sind
// seit 24.08. ein Verb-Paar hinter dem Kicker REIHENFOLGE: „nach Ausgaben" /
// „nach Kosten für die Stadt" las sich wie ein Ansichts-Wechsel zwischen
// zwei Synonymen, dabei sortiert der Schalter nur (Tims Befund). Unter 744 px
// Containerbreite zeigt die Liste erst fünf Zeilen und den Rest hinter
// „alle N zeigen" (H4-A-Regel ab 8 Zeilen) — Weglassen heißt „hinter einen
// Auslöser", nie ersatzlos.

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Segmented } from "@/components/ui";
import { bereichKanon } from "@/lib/haushalt-bereiche";
import { HaushaltZeile, bereichSlug, bereiche, deMio, mio } from "@/lib/haushalt";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";

export type KlartextZeile = {
  zeile: HaushaltZeile;
  /** Ausgaben in Mio. — die Größe, nach der beschriftet wird. */
  aus: number;
  /** Zuschussbedarf in Mio. (Ausgaben − eigene Erträge); negativ heißt
   *  Überschuss. `null`, wenn eine Seite fehlt. */
  stadt: number | null;
  /** Eigene Erträge in Mio. */
  eigen: number | null;
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
        stadt: z.ergebnis != null ? mio(-z.ergebnis) : null,
        eigen: mio(z.ertraege),
        // Der Anzeigename ist die jüngste amtliche Schreibweise; verlinkt wird
        // weiter über den Slug des DB-Namens (Regel 2 des Wörterbuchs).
        name: k.name,
        klartext: k.klartext,
        slug: bereichSlug(z.bereich),
      };
    })
    .sort((a, b) => b.aus - a.aus);
}

/** Zwei Balkenstücke auf gemeinsamer Skala: dunkel = schießt die Stadt zu,
 *  hell = nimmt der Bereich selbst ein — dieselbe Kodierung wie die
 *  Bereichstabelle der Übersicht. Dekorativ (`aria-hidden`): Was er zeigt,
 *  steht als Text in der Zeile. */
function Balken({ z, skala }: { z: KlartextZeile; skala: number }) {
  const b = (v: number) => `${Math.max((v / skala) * 100, 0)}%`;
  const dunkel = Math.max(z.stadt ?? 0, 0);
  const hell = Math.min(z.eigen ?? 0, z.aus);
  return (
    <span aria-hidden="true" className="flex h-3 w-full items-center gap-[1.5px]">
      <span className="h-full rounded-l-[3px]" style={{ width: b(dunkel), background: "var(--hh-ein-0)" }} />
      <span className={cn("h-full", dunkel <= 0 && "rounded-l-[3px]", "rounded-r-[3px]")}
        style={{ width: b(hell), background: "var(--hh-ein-3)" }} />
    </span>
  );
}

/** Der Zahlen-Halbsatz unter dem Klartext: was die Stadt trägt, was der
 *  Bereich selbst hereinholt — oder der Überschuss-Fall, gerechnet statt
 *  behauptet (Finanzmanagement, manche Jahrgänge auch die Stiftungen). */
function ZahlenZeile({ z }: { z: KlartextZeile }) {
  if (z.stadt == null || z.eigen == null) {
    return (
      <span className="mt-1 block text-[11.5px] tabular-nums text-muted-foreground">
        {deMio(z.aus)}&#8239;Mio.&nbsp;€ Ausgaben — die Ertragsseite fehlt in diesem Jahrgang.
      </span>
    );
  }
  if (z.stadt <= 0) {
    return (
      <span className="mt-1 block text-[11.5px] tabular-nums text-muted-foreground">
        {deMio(z.aus)}&#8239;Mio.&nbsp;€ Ausgaben · trägt sich selbst — Überschuss{" "}
        {deMio(-z.stadt)}&#8239;Mio.&nbsp;€ für den allgemeinen Topf
      </span>
    );
  }
  return (
    <span className="mt-1 block text-[11.5px] tabular-nums text-muted-foreground">
      {deMio(z.stadt)}&#8239;Mio.&nbsp;€ schießt die Stadt zu · {deMio(z.eigen)}&#8239;Mio.&nbsp;€
      nimmt der Bereich selbst ein
    </span>
  );
}

/** Eine Zeile: Name + Klartext, Balken, Betrag. Die ganze Zeile ist der
 *  Link — ein eigener „mehr"-Anhang neben 13 Einträgen wäre 13-mal dasselbe
 *  Wort. */
function Zeile({ z, skala, breit, aktiv }: {
  z: KlartextZeile; skala: number; breit: boolean; aktiv: boolean;
}) {
  return (
    <Link
      href={`/haushalt/bereich?name=${z.slug}`}
      aria-current={aktiv ? "page" : undefined}
      className={cn(
        "group block rounded-xl px-2.5 py-3 transition-colors hover:bg-accent",
        breit && "grid grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)_64px_14px] items-center gap-x-4",
        aktiv && "bg-primary/[0.06]",
      )}
    >
      <span className="min-w-0">
        <span className="text-[13.5px] font-bold leading-snug">
          {z.name}
          {!breit && (
            <ChevronRight
              aria-hidden
              className="ml-1 inline-block h-3.5 w-3.5 align-[-2px] text-muted-foreground transition-transform group-hover:translate-x-0.5"
            />
          )}
        </span>
        {z.klartext ? (
          <span className="mt-0.5 block text-[12.5px] leading-relaxed text-foreground/75">
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
        {!breit && (
          <>
            <span className="mt-1.5 block"><Balken z={z} skala={skala} /></span>
            <ZahlenZeile z={z} />
          </>
        )}
      </span>
      {breit && (
        <>
          <span className="flex flex-col">
            <Balken z={z} skala={skala} />
            <ZahlenZeile z={z} />
          </span>
          <span className="text-right font-mono text-[12.5px] font-medium tabular-nums">
            {deMio(z.aus)}
          </span>
          <ChevronRight
            aria-hidden
            className="h-3.5 w-3.5 justify-self-end text-muted-foreground transition-transform group-hover:translate-x-0.5"
          />
        </>
      )}
      {!breit && (
        <span className="sr-only">Gesamt {deMio(z.aus)} Millionen Euro</span>
      )}
    </Link>
  );
}

type Sortierung = "aus" | "stadt";

/** Das Verzeichnis. `aktiv` hebt den Bereich hervor, von dem man kommt. */
export function NamenKlartext({ zeilen, jahr, aktiv, className }: {
  zeilen: HaushaltZeile[];
  jahr: number;
  /** Bereichsname (DB-Schreibweise) der aufrufenden Seite. */
  aktiv?: string;
  className?: string;
}) {
  const [sortierung, setSortierung] = useState<Sortierung>("aus");
  const [alle, setAlle] = useState(false);
  // Gemessen statt Fenster-Breakpoint (Designsprache §4): Am Desktop liegt
  // die Liste neben der Seitenleiste, auf dem iPad nicht.
  const { box, breite } = useBreite(1024, 280);
  const breit = breite >= 744;

  const rows = useMemo(() => {
    const r = klartextZeilen(zeilen);
    return sortierung === "aus"
      ? r
      : [...r].sort((a, b) => (b.stadt ?? -Infinity) - (a.stadt ?? -Infinity));
  }, [zeilen, sortierung]);
  if (!rows.length) return null;

  const aktivSlug = aktiv ? bereichSlug(aktiv) : null;
  // Eine Skala für alle Balken — der größte Bereich ist 100 %.
  const skala = Math.max(...rows.map((z) => z.aus), 1);
  // Schmal: erst fünf, der Rest hinter dem Auslöser (H4-A, ab 8 Zeilen).
  const gezeigt = breit || alle ? rows : rows.slice(0, 5);
  const rest = rows.length - gezeigt.length;

  return (
    <div ref={box} className={className}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-2.5">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="shrink-0 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Reihenfolge
          </span>
          <div className="scrollbar-none -mx-1 overflow-x-auto px-1">
            <Segmented className="w-max" value={sortierung} onChange={setSortierung} tone="primary"
              options={[
                { value: "aus", label: "was ein Bereich ausgibt" },
                { value: "stadt", label: "was die Stadt zuschießt" },
              ]} />
          </div>
        </div>
        <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Mio. € · {jahr} · {rows.length} Teilhaushalte
        </span>
      </div>
      {/* Die Balken-Legende einmal für alle Zeilen — dieselben zwei Töne wie
          in der Bereichstabelle der Übersicht. */}
      <div className="mb-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 px-2.5">
        <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-[3px]" style={{ background: "var(--hh-ein-0)" }} />
          schießt die Stadt zu (allgemeiner Topf)
        </span>
        <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-[3px]" style={{ background: "var(--hh-ein-3)" }} />
          nimmt der Bereich selbst ein
        </span>
      </div>

      <div>
        {gezeigt.map((z) => (
          <Zeile key={z.zeile.bereich} z={z} skala={skala} breit={breit}
            aktiv={z.slug === aktivSlug} />
        ))}
      </div>

      {rest > 0 && (
        <button type="button" onClick={() => setAlle(true)}
          className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-border px-2.5 py-2.5 text-[12.5px] font-semibold text-primary transition-colors hover:bg-accent">
          alle {rows.length} Bereiche zeigen
          <ChevronDown aria-hidden className="h-3.5 w-3.5" />
        </button>
      )}
      {!breit && alle && (
        <button type="button" onClick={() => setAlle(false)}
          className="mt-1.5 px-2.5 text-xs font-semibold text-primary">
          Weniger anzeigen
        </button>
      )}
    </div>
  );
}
