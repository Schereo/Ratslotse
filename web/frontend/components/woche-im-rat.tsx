"use client";

import { useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Card } from "@/components/ui";
import { parteiDot } from "@/components/qa-bausteine";
import { shortCommittee } from "@/lib/committees";
import { cn } from "@/lib/utils";

export type WochenSitzung = {
  ksinr: number | null; committee: string; session_date: string;
  session_time: string | null; location?: string | null; n_items: number;
};
export type WochenPunkt = {
  ksinr: number; item_number: string; title: string; titel_kurz?: string;
  antragsteller?: string | null; summary: string | null;
  vorlage_nr: string | null; kvonr: number | null;
  committee: string; session_date: string; topic_name?: string | null;
  /** Der EINE hervorgehobene Punkt der Karte (Design 14a). */
  top?: boolean;
};
export type Wochenvorschau = {
  found: boolean; von: string; bis: string;
  sitzungen: WochenSitzung[]; punkte: WochenPunkt[];
  relevant_je_sitzung?: Record<string, number>;
  treffer_gesamt?: number; inhaltlich_gesamt?: number;
};

/** Die drei Dichtestufen aus Design 14d. */
type Dichte = "mobil" | "ipad" | "desktop";

/* Gemessen wird die Breite der KARTE, nicht die des Fensters — dieselbe
   Lektion wie beim Raster (#464): Mit Seitenleiste bedeutet 1280 px etwas
   anderes als ohne, und auf dem Telefon gibt es sie gar nicht. Ein iPad hoch
   (834) trägt in dieser App die Leiste und lässt der Karte rund 550 px; quer
   (1194) sind es gut 900. Die Schwellen sind so gelegt, dass beide
   Ausrichtungen die mittlere Stufe bekommen — so wie der Entwurf das iPad
   führt (768–1279) — und erst der echte Desktop die volle.

   Im Browser nachgemessen (Inhaltsbreite der Karte, ohne ihre Polsterung):

     Fenster  390 (Telefon, keine Leiste) →  318
     Fenster  834 (iPad hoch, mit Leiste) →  504
     Fenster 1194 (iPad quer)             →  864
     Fenster 1280 (Desktop)               →  934                             */
const SCHWELLE_IPAD = 448;
const SCHWELLE_DESKTOP = 900;

/** Warum gemessen statt per CSS-Container-Query: Die Stufen unterscheiden sich
 *  nicht nur im Aussehen, sondern im **Inhalt** — mobil werden alle Sitzungen
 *  ohne eigene Treffer zu einer Zeile gebündelt, auf den größeren Stufen trägt
 *  jede ihre eigene. Das ließe sich in CSS nur durch doppeltes Markup
 *  nachbilden (beide Fassungen rendern, eine ausblenden); dann stünde jede
 *  Sitzung zweimal im Dokument — auch für Screenreader und Suche. */
function useDichte<T extends HTMLElement>(ref: React.RefObject<T>): Dichte {
  const [dichte, setDichte] = useState<Dichte>("desktop");
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const messen = (w: number) =>
      setDichte(w >= SCHWELLE_DESKTOP ? "desktop" : w >= SCHWELLE_IPAD ? "ipad" : "mobil");
    messen(el.getBoundingClientRect().width);
    const ro = new ResizeObserver((eintraege) => {
      for (const e of eintraege) messen(e.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return dichte;
}

const fmtTag = (iso: string) =>
  new Date(iso + "T12:00:00")
    .toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })
    .toUpperCase()
    .replace(",", "");

/** „13.–20. AUGUST" (Desktop) bzw. „13.–20. AUG" (iPad). */
function zeitraum(von: string, bis: string, kurz: boolean) {
  const a = new Date(von + "T12:00:00");
  const b = new Date(bis + "T12:00:00");
  const monat = b.toLocaleDateString("de-DE", { month: kurz ? "short" : "long" })
    .toUpperCase().replace(".", "");
  return `${a.getDate()}.–${b.getDate()}. ${monat}`;
}

/** Gremiumsname je Stufe (Matrix 14d): volle Bezeichnung → ohne „Ausschuss
 *  für" → Kurzform. `shortCommittee` macht genau den mittleren Schritt. */
function gremium(name: string, dichte: Dichte) {
  return dichte === "desktop" ? name : shortCommittee(name);
}

/** Antragsteller in einzelne Fraktionen zerlegen und auf den nackten Namen
 *  kürzen: „BSW-Fraktion und SPD-Fraktion" → ["BSW", "SPD"].
 *
 *  Bewusst NICHT an „/" getrennt: „FDP/Volt" ist eine Gruppe, keine zwei
 *  Fraktionen — sie behält ihr kombiniertes Etikett und den neutralen Punkt.
 *  Genau darauf beruht auch die exakte Prüfung in `parteiDot`. */
function fraktionen(wer: string): string[] {
  return wer.split(/\s*(?:&|\bund\b|,)\s*/)
    .map((t) => t.replace(/[- ]?(Fraktion|Gruppe|Ratsgruppe)\b.*$/i, "").trim())
    .filter(Boolean);
}

/** Die farbigen Punkte vor dem Antragsteller. Mehrere Fraktionen („BSW & SPD")
 *  bekommen je einen Punkt — der Entwurf zeigt sie nebeneinander.
 *
 *  `parteiDot` prüft „fdp" EXAKT (damit die Gruppe FDP/Volt neutral bleibt) —
 *  mit dem rohen „FDP-Fraktion" fiel der Punkt deshalb auf Grau zurück statt
 *  gelb zu sein. Deshalb hier erst kürzen, dann fragen. */
function ParteiPunkte({ wer, size = 7 }: { wer: string; size?: number }) {
  const teile = fraktionen(wer).slice(0, 3);
  return (
    <span className="flex shrink-0 gap-0.5">
      {teile.map((t, i) => {
        const { bg, ring } = parteiDot(t);
        return (
          <span
            key={i}
            className="rounded-full"
            style={{
              width: size, height: size, background: bg,
              boxShadow: ring ? "inset 0 0 0 1px rgba(0,0,0,0.15)" : undefined,
            }}
          />
        );
      })}
    </span>
  );
}

/** Antragsteller-Kürzel fürs iPad: „CDU-Fraktion" → „CDU",
 *  „BSW-Fraktion und SPD-Fraktion" → „BSW · SPD". */
const kuerzel = (wer: string) => fraktionen(wer).join(" · ");

/** Desktop-Label. Eine Fraktion steht voll da („Antrag CDU-Fraktion"); bei
 *  mehreren würde das die Zeile sprengen, deshalb die Kurzform — genau so
 *  führt der Entwurf die beiden Fälle vor („Antrag FDP-Fraktion" neben
 *  „Antrag BSW & SPD"). */
const desktopName = (wer: string) => {
  const kurz = kuerzel(wer);
  return kurz.includes(" · ") ? kurz.replace(/ · /g, " & ") : wer;
};

function topHref(ksinr: number, itemNumber: string) {
  return `/council?tab=sessions&ksinr=${ksinr}` +
    (itemNumber ? `&top=${encodeURIComponent(itemNumber)}` : "");
}

/**
 * „Die Woche im Rat" (Design 14) — **eine** Karte statt zweier.
 *
 * Der Entwurf hat den Doppelbau erkannt: „Nächste Sitzungen" war vollständig
 * ohne Inhalt, „Diese Woche im Rat" inhaltlich ohne Vollständigkeit. Hier
 * bekommt jede Sitzung der Woche eine Zeile; die mit relevanten Punkten
 * klappen sie auf, die anderen bleiben eine ruhige Zeile mit Punktzahl.
 * Dadurch stimmt auch die Zählung — „5 Sitzungen“ statt „3“ plus „alle“.
 *
 * Die drei Dichtestufen sind nicht skaliert, sondern inhaltlich abgestuft
 * (Matrix 14d). Prinzip ①: erst Zeilen weglassen, dann Wörter, zuletzt
 * Schrift — die Schriftgrößen laufen nur von 13,5 über 13 auf 12,5.
 * Prinzip ②: jede Stufe bleibt vollständig in der Zählung; die Karte darf
 * verkürzen, aber nicht verschweigen.
 */
export function WocheImRat({ vorschau, heuteIso }: {
  vorschau: Wochenvorschau;
  /** Heutiges Datum als ISO — für den „HEUTE"-Chip. */
  heuteIso: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const dichte = useDichte(ref);
  const [ruhigeOffen, setRuhigeOffen] = useState(false);

  const maxPunkte = dichte === "desktop" ? 3 : 2;
  const relevant = vorschau.relevant_je_sitzung ?? {};

  const punkteVon = (ksinr: number | null) =>
    ksinr == null ? [] : vorschau.punkte.filter((p) => p.ksinr === ksinr);

  const sitzungen = vorschau.sitzungen;
  const mitPunkten = sitzungen.filter((s) => punkteVon(s.ksinr).length > 0);
  const ohnePunkte = sitzungen.filter((s) => punkteVon(s.ksinr).length === 0);
  const treffer = vorschau.treffer_gesamt ?? 0;

  // Auf den großen Stufen laufen alle Sitzungen in einer Tages-Rail; mobil
  // stehen nur die mit Punkten einzeln, der Rest wird gebündelt (Matrix 14d).
  const inRail = dichte === "mobil" ? mitPunkten : sitzungen;

  // Tagesweise gruppieren — die Rail trägt den Tag einmal, nicht je Sitzung.
  const tage: { datum: string; sitzungen: WochenSitzung[] }[] = [];
  for (const s of inRail) {
    const letzter = tage[tage.length - 1];
    if (letzter && letzter.datum === s.session_date) letzter.sitzungen.push(s);
    else tage.push({ datum: s.session_date, sitzungen: [s] });
  }

  const kicker = [
    dichte !== "mobil" && zeitraum(vorschau.von, vorschau.bis, dichte === "ipad"),
    // Prinzip ②: Die Sitzungszahl steht auf JEDER Stufe.
    `${sitzungen.length} ${sitzungen.length === 1 ? "SITZUNG" : "SITZUNGEN"}`,
    dichte === "desktop" && treffer > 0 &&
      `${treffer} ${treffer === 1 ? "PUNKT" : "PUNKTE"} ZU DEINEN THEMEN`,
  ].filter(Boolean).join(" · ");

  return (
    <Card className="p-5" data-tour="woche-im-rat">
      {/* Gemessen wird dieser innere Container, nicht die Karte: `Card` ist eine
          einfache Funktionskomponente ohne forwardRef, und die INHALTS-Breite
          ist ohnehin das, worauf die Schwellen kalibriert sind. */}
      <div ref={ref} className="flex flex-col" data-dichte={dichte}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-base font-bold text-foreground">Die Woche im Rat</h2>
        <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          {kicker}
        </span>
      </div>

      {dichte === "mobil" ? (
        <div className="mt-3 flex flex-1 flex-col gap-3">
          {tage.map(({ datum, sitzungen: tagesSitzungen }) =>
            tagesSitzungen.map((s, i) => (
              <MobilSitzung
                key={s.ksinr ?? `${s.committee}|${datum}`}
                sitzung={s}
                punkte={punkteVon(s.ksinr).slice(0, maxPunkte)}
                weitere={Math.max((relevant[String(s.ksinr)] ?? 0) - maxPunkte, 0)}
                badge={relevant[String(s.ksinr)] ?? 0}
                heute={datum === heuteIso}
                /* Trennlinie erst ab der zweiten Zeile — die erste sitzt
                   direkt unter der Kopfzeile. */
                mitTrennlinie={!(tage[0].datum === datum && i === 0)}
              />
            )),
          )}
          {ohnePunkte.length > 0 && (
            <RuhigGebuendelt
              sitzungen={ohnePunkte}
              offen={ruhigeOffen}
              onToggle={() => setRuhigeOffen((v) => !v)}
              heuteIso={heuteIso}
            />
          )}
        </div>
      ) : (
        <div
          className="mt-3 grid flex-1"
          style={{
            gridTemplateColumns: `${dichte === "desktop" ? 92 : 74}px 1fr`,
            columnGap: dichte === "desktop" ? 16 : 13,
          }}
        >
          {tage.map(({ datum, sitzungen: tagesSitzungen }, ti) => (
            <RailTag
              key={datum}
              datum={datum}
              heute={datum === heuteIso}
              letzter={ti === tage.length - 1}
              dichte={dichte}
            >
              {tagesSitzungen.map((s) => {
                const p = punkteVon(s.ksinr);
                return p.length > 0 ? (
                  <RailSitzung
                    key={s.ksinr ?? `${s.committee}|${datum}`}
                    sitzung={s}
                    punkte={p.slice(0, maxPunkte)}
                    weitere={Math.max((relevant[String(s.ksinr)] ?? 0) - maxPunkte, 0)}
                    badge={relevant[String(s.ksinr)] ?? 0}
                    dichte={dichte}
                  />
                ) : (
                  <RuhigeZeile
                    key={s.ksinr ?? `${s.committee}|${datum}`}
                    sitzung={s}
                    dichte={dichte}
                  />
                );
              })}
            </RailTag>
          ))}
        </div>
      )}

      {/* Mobil steht der Link IM Satz (14c) statt rechts daneben: In einer
          Zeile nebeneinander bricht der Hinweis um und drängt sich an den
          Link. Ab iPad ist Platz für beides nebeneinander (14a/14b). */}
      {dichte === "mobil" ? (
        <p className="mt-2.5 border-t border-border/60 pt-2.5 text-[10.5px] leading-relaxed text-muted-foreground/85">
          Entschieden wird in der Sitzung.{" "}
          <Link href="/council?tab=sessions" className="font-semibold text-primary hover:underline">
            Sitzungskalender →
          </Link>
        </p>
      ) : (
        <div className="mt-3 flex items-center justify-between gap-3 border-t border-border/60 pt-2.5">
          <span className="text-[11.5px] leading-relaxed text-muted-foreground/85">
            {dichte === "desktop"
              ? "Steht auf der Tagesordnung — entschieden wird in der Sitzung."
              : "Entschieden wird in der Sitzung."}
          </span>
          <Link
            href="/council?tab=sessions"
            className="shrink-0 text-xs font-semibold text-primary hover:underline"
          >
            Sitzungskalender →
          </Link>
        </div>
      )}
      </div>
    </Card>
  );
}

/* ------------------------------- Rail (Desktop / iPad) ------------------------------- */

function RailTag({ datum, heute, letzter, dichte, children }: {
  datum: string; heute: boolean; letzter: boolean; dichte: Dichte; children: React.ReactNode;
}) {
  return (
    <>
      <div className="flex flex-col items-start pt-px">
        {heute ? (
          <span className="inline-flex items-center rounded-full bg-signal/[0.12] px-2 py-0.5 font-mono text-[9.5px] font-semibold uppercase tracking-[0.08em] text-signal">
            Heute
          </span>
        ) : (
          <span className="pl-0.5 font-mono text-[9.5px] font-medium tracking-[0.08em] text-muted-foreground">
            {fmtTag(datum)}
          </span>
        )}
        {/* Die Linie verbindet die Tage; am letzten endet die Rail. */}
        {!letzter && <span className="mt-1.5 w-px flex-1 bg-border/70" style={{ marginLeft: dichte === "desktop" ? 12 : 11 }} />}
      </div>
      <div className={cn("flex flex-col", letzter ? "" : dichte === "desktop" ? "pb-3.5" : "pb-3", "gap-2")}>
        {children}
      </div>
    </>
  );
}

/** Sitzung mit relevanten Punkten — sie klappt ihre Punkte auf. */
function RailSitzung({ sitzung, punkte, weitere, badge, dichte }: {
  sitzung: WochenSitzung; punkte: WochenPunkt[]; weitere: number; badge: number; dichte: Dichte;
}) {
  const desktop = dichte === "desktop";
  const zeit = (sitzung.session_time || "").slice(0, 5);
  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <span className={cn("font-bold text-foreground", desktop ? "text-[13.5px]" : "text-[13px]")}>
          {gremium(sitzung.committee, dichte)}
        </span>
        <span className={cn("text-muted-foreground", desktop ? "text-[11.5px]" : "text-[11px]")}>
          {/* Matrix 14d: Desktop zeigt Uhrzeit UND Ort, iPad nur die Uhrzeit. */}
          {zeit}{desktop && sitzung.location ? ` · ${sitzung.location}` : ""}
        </span>
        {badge > 0 && (
          <span className={cn(
            "inline-flex shrink-0 items-center rounded-full bg-primary/10 font-bold text-primary",
            desktop ? "px-2 py-px text-[10px]" : "px-1.5 py-px text-[9.5px]",
          )}>
            {badge} für dich
          </span>
        )}
      </div>
      <div className="mt-1.5">
        {punkte.map((p) => (
          <RailPunkt key={`${p.ksinr}-${p.item_number}`} punkt={p} top={!!p.top} dichte={dichte} />
        ))}
        {weitere > 0 && (
          <div className={cn(desktop ? "px-2.5 py-1.5" : "px-2 py-1.5")}>
            <Link
              href={`/council?tab=sessions&ksinr=${sitzung.ksinr}`}
              className="text-[11.5px] font-medium text-primary hover:underline"
            >
              {weitere === 1 ? "1 weiterer Punkt für dich" : `${weitere} weitere Punkte für dich`}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

/** Ein Tagesordnungspunkt in der Rail. Der oberste ist hervorgehoben und trägt
 *  auf dem Desktop die Kurzbegründung (Matrix 14d). */
function RailPunkt({ punkt, top, dichte }: { punkt: WochenPunkt; top: boolean; dichte: Dichte }) {
  const desktop = dichte === "desktop";
  const wer = punkt.antragsteller;
  return (
    <Link
      href={topHref(punkt.ksinr, punkt.item_number)}
      className={cn(
        "group flex items-start gap-3 transition-colors",
        top
          ? "rounded-lg border border-primary/[0.12] bg-primary/[0.04] hover:bg-primary/[0.07]"
          : "border-b border-border/60 last:border-b-0 hover:bg-accent/60",
        desktop ? (top ? "px-2.5 py-2" : "px-2.5 py-1.5") : (top ? "px-2.5 py-1.5" : "px-2 py-1.5"),
      )}
    >
      <span className="min-w-0 flex-1">
        <span className={cn(
          "block leading-snug text-foreground",
          top ? "font-semibold" : "",
          desktop ? "text-[13px]" : "text-[12.5px]",
          desktop ? "" : "truncate",
        )}>
          {punkt.titel_kurz || punkt.title}
        </span>
        {/* Kurzbegründung: nur Desktop, nur am obersten Punkt. */}
        {desktop && top && punkt.summary && (
          <span className="mt-0.5 block text-[11.5px] leading-relaxed text-muted-foreground">
            {punkt.summary}
            {punkt.topic_name && (
              <> — passt zu deinem Thema{" "}
                <span className="font-medium text-foreground/90">{punkt.topic_name}</span>.</>
            )}
          </span>
        )}
      </span>
      {wer && (
        <span className="flex shrink-0 items-center gap-1.5 pt-0.5">
          <ParteiPunkte wer={wer} />
          <span className={cn("whitespace-nowrap text-muted-foreground", desktop ? "text-[11px]" : "text-[10.5px]")}>
            {desktop ? `Antrag ${desktopName(wer)}` : kuerzel(wer)}
          </span>
        </span>
      )}
      {top && desktop ? (
        <span className="shrink-0 whitespace-nowrap pt-0.5 text-[11.5px] font-semibold text-primary">
          Öffnen →
        </span>
      ) : (
        /* Der Entwurf zeichnet hier ein Chevron nach UNTEN. Das steht für
           „aufklappen" — die Zeile führt aber auf den Tagesordnungspunkt.
           Deshalb nach rechts: gleiche Zurückhaltung, ehrliche Richtung. */
        <ChevronRight
          className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", top ? "text-primary" : "text-muted-foreground/60")}
          aria-hidden
        />
      )}
    </Link>
  );
}

/** Sitzung ohne relevante Punkte — eine ruhige Zeile mit Punktzahl.
 *  Genau hier steckt die Vollständigkeit, die vorher „Nächste Sitzungen" trug. */
function RuhigeZeile({ sitzung, dichte }: { sitzung: WochenSitzung; dichte: Dichte }) {
  const desktop = dichte === "desktop";
  const zeit = (sitzung.session_time || "").slice(0, 5);
  // Ohne einen einzigen öffentlichen Punkt ist die Sitzung nicht öffentlich —
  // dann führt auch kein Link zu einer Tagesordnung.
  const oeffentlich = sitzung.n_items > 0;
  const inhalt = (
    <>
      <span className={cn(
        "font-semibold text-foreground/90",
        desktop ? "text-[13.5px]" : "text-[13px]",
      )}>
        {gremium(sitzung.committee, dichte)}
      </span>
      <span className={cn("text-muted-foreground", desktop ? "text-[11.5px]" : "text-[11px]")}>
        {zeit}
        {oeffentlich
          ? ` · ${sitzung.n_items} ${desktop ? (sitzung.n_items === 1 ? "Punkt auf der Tagesordnung" : "Punkte auf der Tagesordnung") : "Punkte"}`
          : " · nicht öffentlich"}
      </span>
      {oeffentlich && desktop && (
        <span className="text-[11.5px] font-medium text-primary">Tagesordnung →</span>
      )}
    </>
  );
  return oeffentlich && sitzung.ksinr ? (
    <Link
      href={`/council?tab=sessions&ksinr=${sitzung.ksinr}`}
      className="-mx-1.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 rounded-lg px-1.5 py-0.5 transition-colors hover:bg-accent/60"
    >
      {inhalt}
    </Link>
  ) : (
    <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 px-1.5 py-0.5">{inhalt}</div>
  );
}

/* --------------------------------- Mobile --------------------------------- */

/** Mobil wird die Rail-Spalte zur Zeile: Der Tag steht als Chip VOR dem
 *  Sitzungsnamen und spart damit die 74 px Spaltenbreite. Die Punkte hängen an
 *  einer 2-px-Kante. */
function MobilSitzung({ sitzung, punkte, weitere, badge, heute, mitTrennlinie }: {
  sitzung: WochenSitzung; punkte: WochenPunkt[]; weitere: number;
  badge: number; heute: boolean; mitTrennlinie: boolean;
}) {
  const zeit = (sitzung.session_time || "").slice(0, 5);
  return (
    <div className={cn(mitTrennlinie && "border-t border-border/60 pt-2.5")}>
      <div className="flex items-center gap-1.5">
        {heute ? (
          /* Matrix 14d: Uhrzeit mobil nur bei „heute" — dort ist sie die
             eigentliche Information. */
          <span className="inline-flex shrink-0 items-center rounded-full bg-signal/[0.12] px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-signal">
            Heute {zeit}
          </span>
        ) : (
          <span className="w-[68px] shrink-0 whitespace-nowrap font-mono text-[10px] font-medium tracking-[0.06em] text-muted-foreground">
            {fmtTag(sitzung.session_date)}
          </span>
        )}
        <span className="min-w-0 flex-1 truncate text-[12.5px] font-bold text-foreground">
          {shortCommittee(sitzung.committee)}
        </span>
        {badge > 0 && (
          /* Matrix 14d: mobil nur die Zahl, ohne „für dich". */
          <span className="inline-flex shrink-0 items-center rounded-full bg-primary/10 px-1.5 py-px text-[9px] font-bold text-primary">
            {badge}
          </span>
        )}
      </div>
      <div className="ml-[3px] mt-1.5 flex flex-col gap-1.5 border-l-2 border-primary/25 pl-2.5">
        {punkte.map((p) => (
          <Link
            key={`${p.ksinr}-${p.item_number}`}
            href={topHref(p.ksinr, p.item_number)}
            className="flex items-start gap-1.5"
          >
            {/* Matrix 14d: mobil nur der Punkt, kein Antragsteller-Text. */}
            {p.antragsteller
              ? <span className="mt-[5px]"><ParteiPunkte wer={p.antragsteller} size={6} /></span>
              : <span className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/40" />}
            <span className="text-[12.5px] leading-snug text-foreground">
              {p.titel_kurz || p.title}
            </span>
          </Link>
        ))}
        {weitere > 0 && (
          <Link
            href={`/council?tab=sessions&ksinr=${sitzung.ksinr}`}
            className="text-[11.5px] font-medium text-primary"
          >
            {weitere === 1 ? "1 weiterer Punkt" : `${weitere} weitere Punkte`}
          </Link>
        )}
      </div>
    </div>
  );
}

/** Mobil zu EINER Zeile gebündelt (Matrix 14d) — aufklappbar, damit die
 *  Vollständigkeit erhalten bleibt. */
function RuhigGebuendelt({ sitzungen, offen, onToggle, heuteIso }: {
  sitzungen: WochenSitzung[]; offen: boolean; onToggle: () => void; heuteIso: string;
}) {
  const tage = [...new Set(sitzungen.map((s) => s.session_date))];
  return (
    <div className="border-t border-border/60 pt-2.5">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={offen}
        className="flex w-full items-center gap-2 text-left"
      >
        <ChevronDown
          className={cn("h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform", offen && "rotate-180")}
          aria-hidden
        />
        <span className="flex-1 text-xs text-muted-foreground">
          {sitzungen.length} {sitzungen.length === 1 ? "Sitzung" : "Sitzungen"} ohne deine Themen
        </span>
        {!offen && (
          <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
            {tage.length === 1 && tage[0] === heuteIso ? "HEUTE" : fmtTag(tage[0])}
          </span>
        )}
      </button>
      {offen && (
        <div className="ml-[22px] mt-2 flex flex-col gap-1.5">
          {sitzungen.map((s) => (
            <Link
              key={s.ksinr ?? `${s.committee}|${s.session_date}`}
              href={s.ksinr && s.n_items > 0 ? `/council?tab=sessions&ksinr=${s.ksinr}` : "/council?tab=sessions"}
              className="flex items-baseline gap-2"
            >
              <span className="w-[68px] shrink-0 whitespace-nowrap font-mono text-[10px] text-muted-foreground">
                {s.session_date === heuteIso ? "HEUTE" : fmtTag(s.session_date)}
              </span>
              <span className="min-w-0 flex-1 truncate text-[12.5px] text-foreground/90">
                {shortCommittee(s.committee)}
              </span>
              <span className="shrink-0 text-[10.5px] text-muted-foreground">
                {s.n_items > 0 ? `${s.n_items} Punkte` : "nicht öffentlich"}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
