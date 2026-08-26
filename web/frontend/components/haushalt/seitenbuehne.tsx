"use client";

// Die Seitenbühne — der Kopf-Blickfang jeder Schritt-Seite (Design H5-02,
// eingebettet je Seite in H5-09). EINE Baukasten-Form statt zwölf
// Einzelköpfen (H5-08).
//
// Anatomie, von links: Mono-Kicker (was gemessen wurde), darunter EINE
// gemessene Zahl im bestehenden gerechneten Satz der Seite — nur größer
// gesetzt —, darunter eine Zeile Einordnung. Rechts das MINIBILD: die
// verkleinerte Hauptform der Seite (Waffel, Treppe, Punktreihe …), als Link
// dorthin. Keine neue Grafikart, keine Bewertung, kein Beleg-Chip — die
// Belege trägt der Abschnitt, zu dem das Minibild springt.
//
// Drei Regeln aus dem Board, die diese Datei durchsetzt:
//  * **Hell, nicht Tafel.** Die Fläche ist `.hh-seitenbuehne`
//    (app/globals.css) — eine Stufe leiser als die Anzeigetafel, die
//    exklusiv der Übersicht gehört. Sonst wäre die Hierarchie
//    Bereich → Seite nicht mehr lesbar.
//  * **Die Zahl zählt beim ersten Sichtkontakt** (H5-07): Zähl-Tween
//    600 ms, ease-out-cubic, tabellarische Ziffern, Nachkommastelle läuft
//    mit; einmal pro Seitenaufruf, nie beim Zurück-Scrollen. Bei
//    `prefers-reduced-motion` steht sie sofort im Endzustand.
//  * **Ausnahmen sind Ausnahmen.** Das Labor (Werkzeug, keine Lektüre) und
//    der Bereichs-Steckbrief (trägt seit 24.08. die Anzeigetafel) haben
//    keine Bühne — wer hier eine „nachrüsten" will, liest erst H5-09.
//
// Unter ~512 px Container-Innenbreite stapelt die Bühne: Kicker → Zahl →
// Satz → Minibild als schmaler Streifen. Container-Query, nicht
// Fensterbreite (Designsprache § 4).

import { useEffect, useRef } from "react";
import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Eine Zahl, die beim ersten Sichtkontakt von 0 auf ihren Wert zählt.
 *
 *  Server und erster Client-Render zeigen den ENDWERT — wer ohne JavaScript
 *  liest oder Bewegung reduziert hat, sieht nie einen Zwischenstand. Erst
 *  danach setzt der Tween die Anzeige auf 0 zurück und zählt hoch, sobald
 *  das Element zum ersten Mal im Bild ist. Direkt am Textknoten, ohne
 *  setState (kein Re-Render des Kopfes bei 60 fps).
 *
 *  `verzoegerungMs` ist für Sequenzen gedacht, in denen die Reihenfolge die
 *  Aussage trägt (Schulden-Treppe: eng → weiter → ganz, H5-06) — nicht für
 *  Dekor-Stagger; Listen und Zeilen bewegen sich nie (H5-07). */
export function ZaehlZahl({ wert, nachkomma = 0, dauerMs = 600, verzoegerungMs = 0, className }: {
  wert: number;
  /** Nachkommastellen — fest, damit die Stelle beim Zählen mitläuft statt zu springen. */
  nachkomma?: number;
  dauerMs?: number;
  verzoegerungMs?: number;
  className?: string;
}) {
  const knoten = useRef<HTMLSpanElement>(null);
  const gespielt = useRef(false);

  useEffect(() => {
    const el = knoten.current;
    if (!el || gespielt.current) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const fmt = new Intl.NumberFormat("de-DE", {
      minimumFractionDigits: nachkomma, maximumFractionDigits: nachkomma,
    });
    let raf = 0;
    let timeout = 0;
    const spiele = () => {
      const start = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - start) / dauerMs);
        const e = 1 - Math.pow(1 - p, 3);
        el.textContent = fmt.format(wert * e);
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };

    // Erst beim Sichtkontakt auf 0 stellen, nicht schon beim Mount: Wer über
    // einen Anker tiefer einsteigt, sieht bis zum Hochscrollen den Endwert —
    // eine 0 wäre dort eine falsche Zahl, keine wartende Animation.
    const io = new IntersectionObserver((eintraege) => {
      if (!eintraege.some((e) => e.isIntersecting) || gespielt.current) return;
      gespielt.current = true;
      io.disconnect();
      el.textContent = fmt.format(0);
      timeout = window.setTimeout(spiele, verzoegerungMs);
    });
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
      window.clearTimeout(timeout);
      // Beim Abbruch mitten im Tween (Navigation innerhalb der Seite) den
      // Endwert stehen lassen, falls das Element weiterlebt.
      if (gespielt.current) el.textContent = fmt.format(wert);
    };
  }, [wert, nachkomma, dauerMs, verzoegerungMs]);

  const fmt = new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: nachkomma, maximumFractionDigits: nachkomma,
  });
  return (
    <span ref={knoten} className={cn("tabular-nums", className)}>
      {fmt.format(wert)}
    </span>
  );
}

export type Minibild = {
  /** Anker der Hauptform auf derselben Seite — das Minibild klickt dorthin. */
  href: string;
  /** Eine Zeile darunter: was die Form ist und dass sie klickt. */
  label: string;
  /** Die Skizze selbst — aria-hidden, Farben aus `--sb-voll/-mittel/-blass`. */
  skizze: ReactNode;
};

export function Seitenbuehne({ kicker, zahl, sub, minibild, className }: {
  kicker: string;
  /** Der gerechnete Satz der Seite mit seiner Zahl (`<ZaehlZahl>`), groß gesetzt. */
  zahl: ReactNode;
  sub?: ReactNode;
  minibild?: Minibild;
  className?: string;
}) {
  return (
    <div className={cn("hh-seitenbuehne @container rounded-2xl", className)}>
      <div className={cn(
        "flex flex-col gap-4 px-5 py-[18px]",
        minibild && "@lg:grid @lg:grid-cols-[1fr_224px] @lg:items-center",
      )}>
        <div className="flex min-w-0 flex-col gap-1.5">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {kicker}
          </p>
          <p className="font-display text-[27px] font-bold leading-[1.12] tracking-tight @lg:text-[32px]">
            {zahl}
          </p>
          {sub && (
            <p className="text-[12px] leading-relaxed text-muted-foreground">{sub}</p>
          )}
        </div>
        {minibild && (
          <Link
            href={minibild.href}
            className="group flex min-w-0 flex-col gap-1.5"
            aria-label={minibild.label}
          >
            <span aria-hidden="true" className="sb-minibild flex flex-col gap-1">
              {minibild.skizze}
            </span>
            <span className="text-[9.5px] leading-snug text-muted-foreground transition-colors group-hover:text-primary">
              {minibild.label}
            </span>
          </Link>
        )}
      </div>
    </div>
  );
}

/** Ladeplatzhalter in der Höhe der fertigen Bühne — für Seiten, deren Werte
 *  aus den Abschnitts-Daten kommen: Der Kopf steht sofort, die Zahl kommt
 *  mit denselben Daten wie der Inhalt darunter. Ohne den Platzhalter spränge
 *  beim Eintreffen die ganze Seite. */
export function SeitenbuehneLaedt({ kicker }: { kicker: string }) {
  return (
    <div className="hh-seitenbuehne @container rounded-2xl">
      <div className="flex flex-col gap-1.5 px-5 py-[18px]">
        <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {kicker}
        </p>
        <span className="mt-1 h-[27px] w-[min(340px,80%)] animate-pulse rounded-md bg-[color:var(--sb-blass)] @lg:h-[32px]" />
        <span className="h-[15px] w-[min(220px,55%)] animate-pulse rounded-md bg-[color:var(--sb-blass)] opacity-60" />
      </div>
    </div>
  );
}
