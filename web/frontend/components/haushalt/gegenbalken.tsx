"use client";

// Kern-Visual der Haushalts-Übersicht (Design H-03, Empfehlung aus dem
// Variantenvergleich H-02…H-04): zwei gestapelte Leisten „Woher"/„Wohin" auf
// GEMEINSAMER Achse — 100 % = die größere der beiden Summen. Endet die
// Einnahmen-Leiste früher, ist der Überhang das Minus: Er wird als
// schraffierter Rücklagen-Kasten gezeigt (die eine Stärke des verworfenen
// Sankeys, hierher übernommen). Kein Sankey: Der Plan kennt keine
// Euro-zu-Zweck-Flüsse, jede Verbindungslinie wäre erfunden.

import { useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { HaushaltZeile, bereichSlug, deMio, mio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

type Seite = "ein" | "aus";

/** Beschriftungsregel (H-03) wörtlich: Ein Segment trägt seinen Text nur,
 *  wenn er WIRKLICH hineinpasst — gemessen, nicht geschätzt. Erst die lange
 *  Fassung (Name · Wert), dann der Kurzname, sonst nichts. Nie verkleinern,
 *  nie abschneiden: eine abgeschnittene 169,2 liest sich als 16.
 *
 *  Gemessen wird in einem UNSICHTBAREN Zwilling, nicht am sichtbaren Text.
 *  Die erste Fassung schaltete zum Messen kurz auf den Langtext und wieder
 *  zurück; bei Segmenten, deren Langtext knapp nicht passt („Finanzmanagement
 *  und Recht · 529,3"), stieß jeder Wechsel den ResizeObserver erneut an —
 *  sichtbares Dauerflackern (Tim, 16.08.). Jetzt bleibt der sichtbare Text
 *  während der Messung stehen, und der State wird nur gesetzt, wenn sich das
 *  Ergebnis wirklich ändert. */
function SegmentText({ lang, kurz }: { lang: string; kurz: string }) {
  const box = useRef<HTMLSpanElement>(null);
  const mess = useRef<HTMLSpanElement>(null);
  const [text, setText] = useState("");

  useLayoutEffect(() => {
    const el = box.current, m = mess.current;
    if (!el || !m) return;
    const entscheide = () => {
      // clientWidth SCHLIESST das Padding ein, der Zwilling misst nur den
      // Text — ohne Abzug hielten wir „Soziales" für passend, obwohl die
      // 16 px Innenabstand fehlten und es doch überlief.
      const stil = getComputedStyle(el);
      const platz = el.clientWidth
        - parseFloat(stil.paddingLeft || "0") - parseFloat(stil.paddingRight || "0");
      // Der Zwilling liegt absolut und unsichtbar im selben Span, erbt also
      // Schrift und Größe — seine scrollWidth ist die echte Textbreite.
      m.textContent = lang;
      const breiteLang = m.scrollWidth;
      m.textContent = kurz;
      const breiteKurz = m.scrollWidth;
      m.textContent = "";
      const passend = breiteLang <= platz ? lang : breiteKurz <= platz ? kurz : "";
      setText((alt) => (alt === passend ? alt : passend));
    };
    entscheide();
    const ro = new ResizeObserver(entscheide);
    ro.observe(el);
    return () => ro.disconnect();
  }, [lang, kurz]);

  return (
    <span ref={box} className="relative block w-full overflow-hidden whitespace-nowrap px-2">
      {text}
      <span ref={mess} aria-hidden="true" className="pointer-events-none invisible absolute left-0 top-0 whitespace-nowrap" />
    </span>
  );
}

function Leiste({
  seite, zeilen, skala, onHover, onPin, aktiv,
}: {
  seite: Seite;
  zeilen: { z: HaushaltZeile; wert: number }[];
  skala: number;
  onHover: (name: string) => void;
  onPin: (name: string) => void;
  aktiv: string | null;
}) {
  return (
    <div className="flex h-8 gap-[1.5px] overflow-hidden rounded-md" role="list">
      {zeilen.map(({ z, wert }, i) => {
        const breite = (wert / skala) * 100;
        const gewaehlt = aktiv === z.bereich;
        const kurz = z.bereich.split(" und ")[0].split(",")[0].split("/")[0];
        return (
          <button
            key={z.bereich}
            type="button"
            role="listitem"
            aria-label={`${z.bereich}: ${deMio(wert)} Mio. Euro`}
            onClick={() => onPin(z.bereich)}
            onMouseEnter={() => onHover(z.bereich)}
            onFocus={() => onHover(z.bereich)}
            className={cn(
              // KEIN Padding am Button: Es zählt zur Elementbreite und macht
              // die Leiste auf schmalen Bildschirmen unmaßstäblich — bei 13
              // Segmenten fraßen 13×16 px Innenabstand so viel Platz, dass der
              // größte Balken statt 65 % nur noch 23 % einnahm (Tim, 16.08.).
              // Der Innenabstand sitzt jetzt im Text-Span, wo er die Breite
              // des Balkens nicht verändert.
              "flex min-w-0 items-center overflow-hidden text-[11px] font-semibold transition-opacity",
              aktiv && !gewaehlt && "opacity-35",
              gewaehlt && "z-[2] rounded ring-2 ring-signal",
            )}
            style={{ width: `${breite}%`, background: `var(--hh-${seite}-${Math.min(i, seite === "ein" ? 6 : 9)})`, color: "var(--hh-seg-text)" }}
          >
            <SegmentText lang={`${z.bereich} · ${deMio(wert)}`} kurz={kurz} />
          </button>
        );
      })}
    </div>
  );
}

/** Detail zum gewählten Bereich (H-03): Ausgaben, eigene Einnahmen, Netto,
 *  Sprung ins Dossier. Sitzt direkt unter „seiner" Leiste und bleibt nach
 *  einem Klick offen (gepinnt) — inklusive Schließen-Knopf, weil sie dann
 *  nicht mehr von selbst verschwindet. */
function Detail({ z, gepinnt, onClose, onOpen }: {
  z: HaushaltZeile | null | undefined;
  gepinnt: boolean;
  onClose: () => void;
  onOpen: (bereich: string) => void;
}) {
  if (!z) return null;
  return (
    <div className="mt-2.5 inline-block rounded-xl border border-border bg-card px-3 py-2.5 shadow-[0_12px_32px_-10px_rgba(2,32,71,0.28)]">
      <div className="flex items-start gap-3">
        <p className="text-[12.5px] font-bold">{z.bereich}</p>
        {gepinnt && (
          <button type="button" onClick={onClose} aria-label="Schließen"
            className="-mr-1 -mt-0.5 rounded p-0.5 text-muted-foreground hover:text-foreground">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <p className="mt-1 text-[11.5px] leading-relaxed text-foreground/80">
        {deMio(mio(z.aufwendungen))}&#8239;Mio. Ausgaben · {deMio(mio(z.ertraege))} eigene Einnahmen
        <br />
        <strong className="text-foreground">{deMio(mio(z.ergebnis))}&#8239;Mio.</strong>{" "}
        {(z.ergebnis ?? 0) < 0 ? "trägt die Stadt" : "bleibt übrig"}
      </p>
      <button type="button" className="mt-1.5 text-[11.5px] font-semibold text-primary"
        onClick={() => onOpen(z.bereich)}>
        Bereich öffnen →
      </button>
    </div>
  );
}

export function Gegenbalken({ zeilen, jahr }: { zeilen: HaushaltZeile[]; jahr: number }) {
  const router = useRouter();
  // Zwei Zustände statt einem: `hover` ist flüchtig, `gepinnt` überlebt das
  // Verlassen des Segments. Vorher schloss das onMouseLeave des Segments die
  // Detail-Box genau in dem Moment, in dem man sie anklicken wollte
  // (Tim, 16.08.) — jetzt hält der Container den Hover, und ein Klick pinnt.
  type Wahl = { seite: Seite; bereich: string };
  const [hover, setHover] = useState<Wahl | null>(null);
  const [gepinnt, setGepinnt] = useState<Wahl | null>(null);
  const wahl = gepinnt ?? hover;
  const aktiv = wahl?.bereich ?? null;
  const pinnen = (w: Wahl) =>
    setGepinnt((g) => (g?.bereich === w.bereich && g.seite === w.seite ? null : w));

  const parts = zeilen.filter((z) => z.is_summe !== 1);
  const gesamt = zeilen.find((z) => z.is_summe === 1);
  if (!gesamt || !parts.length) return null;

  const einSumme = mio(gesamt.ertraege) ?? 0;
  const ausSumme = mio(gesamt.aufwendungen) ?? 0;
  const skala = Math.max(einSumme, ausSumme);
  // Saldo aus den Rohwerten runden — 812,9 − 883,9 ergäbe −71,0, tatsächlich −71,1.
  const saldo = mio((gesamt.ertraege ?? 0) - (gesamt.aufwendungen ?? 0)) ?? 0;
  const einEnde = (einSumme / skala) * 100; // wo die kürzere Leiste endet

  const sortiert = (key: "ertraege" | "aufwendungen") =>
    [...parts]
      .map((z) => ({ z, wert: mio(z[key]) ?? 0 }))
      .filter((x) => x.wert > 0)
      .sort((a, b) => b.wert - a.wert);

  const ein = sortiert("ertraege");
  const aus = sortiert("aufwendungen");
  const gewaehlte = aktiv ? parts.find((z) => z.bereich === aktiv) : null;
  const oeffnen = (bereich: string) => router.push(`/haushalt/bereich?name=${bereichSlug(bereich)}`);

  // Legende: alles, was in der Leiste kein Label mehr trägt, steht hier als Text.
  const legende = (rows: { z: HaushaltZeile; wert: number }[]) => {
    const klein = rows.filter(({ wert }) => (wert / skala) * 100 <= 7);
    const gezeigt = klein.slice(0, 4);
    const rest = klein.slice(4);
    return { gezeigt, rest, restSumme: rest.reduce((s, r) => s + r.wert, 0) };
  };
  const einLeg = legende(ein);
  const ausLeg = legende(aus);

  return (
    <div>
      <div className="mb-3.5 flex items-baseline justify-between gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Woher &amp; wohin · {jahr}
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {parts.length} Teilhaushalte · Mio. Euro
        </span>
      </div>

      {/* Ein Block = eine Hover-Fläche: Leiste, Legende UND Detail-Box liegen
          im selben Container, damit der Weg von der Leiste zur Box den Hover
          nicht abreißen lässt (Tim, 16.08.). */}
      <div onMouseLeave={() => setHover(null)}>
      {/* Diese Leiste hieß bis 16.08. „Woher das Geld kommt". Das ist sie
          nicht: Sie zeigt, WELCHER BEREICH eine Einnahme verbucht — und weil
          Steuern und Zuweisungen zentral in der Kämmerei auflaufen, liegen
          dort rund zwei Drittel. Wer die Überschrift wörtlich nahm, las
          heraus, das meiste Geld komme aus der Verwaltung selbst. Woher es
          wirklich stammt, beantwortet die Seite „Woher kommt das Geld?"
          und das Flussbild darunter. */}
      <p className="mb-1.5 text-[12.5px] font-semibold">
        Wo das Geld eingeht <span className="font-normal text-muted-foreground">— {deMio(einSumme)}&#8239;Mio.</span>
      </p>
      <div style={{ width: `${einEnde}%` }}>
        <Leiste seite="ein" zeilen={ein} skala={einSumme} aktiv={aktiv}
          onHover={(b) => setHover({ seite: "ein", bereich: b })}
          onPin={(b) => pinnen({ seite: "ein", bereich: b })} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1">
        {einLeg.gezeigt.map(({ z, wert }, i) => (
          <span key={z.bereich} className="inline-flex items-center gap-1.5 text-[11px] text-foreground/80">
            <span className="h-2 w-2 rounded-[2px]" style={{ background: `var(--hh-ein-${Math.min(ein.findIndex((e) => e.z === z), 6)})` }} />
            {z.bereich} {deMio(wert)}
          </span>
        ))}
        {einLeg.rest.length > 0 && (
          <span className="text-[11px] text-muted-foreground">{einLeg.rest.length} weitere {deMio(einLeg.restSumme)}</span>
        )}
      </div>
      {ein[0] && (
        <p className="mt-1.5 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
          Der große Block links ist keine Einnahmequelle: In „{ein[0].z.bereich}“ verbucht die
          Stadt Steuern und Zuweisungen zentral für alle Aufgaben. Aus welchen Quellen das Geld
          stammt, steht unter <em>Woher kommt das Geld?</em>
        </p>
      )}
      {wahl?.seite === "ein" && <Detail z={gewaehlte} gepinnt={!!gepinnt} onClose={() => { setGepinnt(null); setHover(null); }} onOpen={oeffnen} />}
      </div>

      {/* Achse mit Überhang: Bei Minus ein schraffierter Rücklagen-Kasten,
          bei Plus ein grüner Überschuss-Vermerk — nie interpoliert. Bei
          schmalem Überhang steht das Label rechtsbündig UNTER dem Kasten
          (wie H-03 mobil), sonst liefe es aus der Karte. */}
      <div className={cn("relative my-3.5", 100 - einEnde < 20 && saldo < 0 ? "h-10" : "h-6")}>
        <div className="absolute inset-x-0 top-3 border-t border-border/60" />
        {saldo < 0 && (
          <>
            <div className="absolute -top-1.5 h-9 border-l border-dashed border-signal" style={{ left: `${einEnde}%` }} />
            <div
              className="absolute top-1 flex h-4 items-center justify-center rounded border border-signal/55 hh-schraffur"
              style={{ left: `${einEnde}%`, right: 0 }}
            >
              {100 - einEnde >= 20 && (
                <span className="whitespace-nowrap font-mono text-[9.5px] font-bold uppercase text-signal">
                  {deMio(-saldo)} aus der Rücklage
                </span>
              )}
            </div>
            {100 - einEnde < 20 && (
              <p className="absolute right-0 top-6 font-mono text-[9.5px] font-bold uppercase text-signal">
                {deMio(-saldo)} aus der Rücklage
              </p>
            )}
          </>
        )}
        {/* Kein Grün. Ein geplanter Überschuss ist keine gute Note und ein
            geplantes Minus keine schlechte — dieselbe Regel, die für die
            Hantel gilt (components/haushalt/hantel.tsx). Der Überschuss trug
            bis 16.08. den Erfolgs-Tint aus der Beschluss-Semantik und stand
            damit als Gegenstück zum orangefarbenen Minus da: gut gegen
            schlecht, ohne dass irgendwer das behaupten wollte. */}
        {saldo > 0 && (
          <span className="absolute right-0 top-0 rounded-full border border-border bg-muted px-2 py-0.5 text-[10.5px] font-semibold text-foreground/80">
            +{deMio(saldo)}&#8239;Mio. Überschuss geplant
          </span>
        )}
      </div>

      <div onMouseLeave={() => setHover(null)}>
      <p className="mb-1.5 text-[12.5px] font-semibold">
        Wohin es fließt <span className="font-normal text-muted-foreground">— {deMio(ausSumme)}&#8239;Mio.</span>
      </p>
      <div style={{ width: `${(ausSumme / skala) * 100}%` }}>
        <Leiste seite="aus" zeilen={aus} skala={ausSumme} aktiv={aktiv}
          onHover={(b) => setHover({ seite: "aus", bereich: b })}
          onPin={(b) => pinnen({ seite: "aus", bereich: b })} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1">
        {ausLeg.gezeigt.map(({ z, wert }) => (
          <span key={z.bereich} className="inline-flex items-center gap-1.5 text-[11px] text-foreground/80">
            <span className="h-2 w-2 rounded-[2px]" style={{ background: `var(--hh-aus-${Math.min(aus.findIndex((a) => a.z === z), 9)})` }} />
            {z.bereich} {deMio(wert)}
          </span>
        ))}
        {ausLeg.rest.length > 0 && (
          <span className="text-[11px] text-muted-foreground">{ausLeg.rest.length} weitere {deMio(ausLeg.restSumme)}</span>
        )}
      </div>
      {wahl?.seite === "aus" && <Detail z={gewaehlte} gepinnt={!!gepinnt} onClose={() => { setGepinnt(null); setHover(null); }} onOpen={oeffnen} />}
      </div>

    </div>
  );
}
