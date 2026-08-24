"use client";

// „Der Streit ums Geld" — der ZWEITE Abschnitt von /haushalt/mitreden.
//
// Bis zum 21.08.2026 die eigene Seite /haushalt/streit. Zusammengelegt mit
// „Wann entschieden wird" und dem Haushalts-Labor; Begründung im Kopf von
// `abschnitt-termine.tsx`. Der Jahrgangs-Umschalter arbeitet weiter mit
// `?jahr=` — die Suspense-Grenze dafür liegt jetzt bei der Seite.

// /haushalt/streit — „Der Streit ums Geld".
//
// Der Bereich zeigt auf zwölf Seiten Zahlen: Plan, Ist, Produkte, Konzern,
// Prüfberichte. Keine davon zeigt, dass über diese Zahlen gestritten wurde.
// Genau das ist der Teil, den kein Open-Data-Portal liefern kann — Zahlen hat
// jedes, die Debatte hat nur, wer die Protokolle hat.
//
// Leserichtung (H3-04): Jahrgang wählen → Verhandlungsbilanz (das tragende
// Bild: Punkte statt Prozente, <PunkteBilanz> aus dem Grafik-Baukasten) →
// wie es ausging → die Listen im Einzelnen → was gesagt wurde → ohne
// Zuordnung → was hier fehlt → Quellen.
//
// DIE HALTUNG DIESER SEITE ist die schwierigste im ganzen Bereich, weil hier
// Personen zitiert werden und jede Anordnung eine Aussage ist. Vier Regeln,
// die man sonst unbemerkt bricht (ausführlich in lib/haushalt-streit.ts):
//
//  * **Protokollreihenfolge, nie sortiert.** Nicht nach Fraktionsgröße, nicht
//    nach Redelänge, nicht „die wichtigsten zuerst".
//  * **Eine Kürzungsregel für alle.** Jede Rede zeigt dieselbe Zeichenzahl
//    und klappt auf denselben Klick vollständig auf. Es gibt keine Auswahl
//    „der aussagekräftigsten Stellen" — die träfe jemand.
//  * **Keine Wertung, auch nicht durch Farbe.** Grün/Rot stehen ausschließlich
//    am Abstimmungs-ERGEBNIS (angenommen/abgelehnt — das ist eine Tatsache,
//    keine Note). Parteifarben bleiben 8-px-Punkte, nie Flächen
//    (Designsprache §2/§7, components/grafik/hantel.tsx).
//  * **Keine Stimmgrafik.** Das Ratsinformationssystem kennt kein
//    Stimmverhalten einzelner Ratsmitglieder, nur das Ergebnis je Abstimmung.
//
// EINE LESEBREITE FÜR ALLES, WAS DAS PROTOKOLL SAGT (17.08.). Diese Seite ist
// die einzige im Bereich, deren Hauptinhalt fremder Fließtext ist — und der
// kommt ohne jede Gliederung: 214 Wortbeiträge im Bestand, KEIN einziger mit
// Absatzumbruch, der längste 12.392 Zeichen am Stück. Bis hierher liefen sie
// über die volle Kartenbreite (gemessen 1.102 px ≙ rund 129 Zeichen je Zeile,
// kursiv); aufgeklappt war das eine Wand von fast hundert Zeilen, in der das
// Auge beim Rücksprung die Zeile verliert. Jetzt hält jeder Wortlaut 76
// Zeichen — dieselbe Breite, die der Beteiligungs-Steckbrief für fremden
// Fließtext führt. Das ist KEINE Kürzung: Weder Text noch Reihenfolge noch
// die Vorschau-Regel ändern sich, nur die Spalte, in der sie stehen.
//
// KEIN „Stand der Daten“-Block. Der Baustein beschreibt, bis wann die neun
// FINANZschichten reichen — auf einer Seite ohne eine einzige Zahl daraus wäre
// das eine Angabe über fremde Daten. Die ehrliche Reichweite dieser Seite steht
// stattdessen am Jahrgangs-Umschalter: ab wann Protokolle im Bestand sind.
//
// UND EINE EHRLICHKEIT, die der Seite ihre Grenze setzt: Was in einer
// Änderungsliste stand — welche Position um welchen Betrag —, steht in den
// Anlagen-PDFs der Vorlage und liegt nicht als Volltext im Bestand. Die Seite
// sagt deshalb „wer wollte ändern und kam damit durch", nicht „was genau".
// Das steht im Block „Was hier fehlt", nicht im Kleingedruckten.

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight, ExternalLink, FileText } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { sessionHref } from "@/lib/routes";
import {
  EINZELNE, HINWEIS_REDE, StreitAntrag, StreitDaten, StreitStation, StreitWortbeitrag,
  antragsStationen, bestand, datumLang, debattenStation, gremiumKurz,
  jahrgaenge, ohneZuordnung, redenJeFraktion, runde, schlussbeschluss,
  verhandlungsBilanz, vorschau,
} from "@/lib/haushalt-streit";
import { Beleg } from "@/components/haushalt/quelle";
import { PunkteBilanz, PunkteZeile } from "@/components/grafik/punkte-bilanz";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { OutcomeBadge, OutcomeDot } from "@/components/decision-ui";
import { parteiDot } from "@/components/qa-bausteine";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";


/** Der neutrale Punkt für kombinierte Label (Designsprache §2). */
const NEUTRAL = { bg: "hsl(209 18% 65%)", ring: false };

/** Fraktions-/Gruppenmarke: 8-px-Punkt plus Label. Nie eine Fläche — eine
 *  parteigefärbte Karte macht aus einer Wortmeldung ein Plakat.
 *
 *  Jedes Label mit Schrägstrich bekommt den NEUTRALEN Punkt, nicht die Farbe
 *  der erstbesten Partei darin. `parteiDot` sucht nach Teilzeichenketten und
 *  gäbe „SPD / CDU und FDP" das SPD-Rot — eine gemeinsame Änderungsliste
 *  dreier Fraktionen erschiene als Antrag einer einzigen. Dieselbe Regel gilt
 *  für Ratsgruppen („FDP/Volt", „Die Linke/Piraten"): Die Designsprache gibt
 *  ihnen ausdrücklich den neutralen Punkt und das kombinierte Label. */
function Fraktion({ label, unklar = false }: { label: string | null; unklar?: boolean }) {
  if (unklar) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground">
        <span aria-hidden className="h-2 w-2 rounded-full border border-dashed border-muted-foreground/60" />
        Fraktion nicht eindeutig
      </span>
    );
  }
  if (!label) return null;
  const dot = label.includes("/") ? NEUTRAL : parteiDot(label);
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-foreground">
      <span
        aria-hidden
        className="h-2 w-2 flex-none rounded-full"
        style={{
          background: dot.bg,
          boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,.15)" : undefined,
        }}
      />
      {label}
    </span>
  );
}

/** Eine Rede: Kopf (wer), Wortlaut (Protokoll), bei Bedarf aufklappbar.
 *  Der Wortlaut steht an einer Randlinie wie auf /haushalt/pruefung — so ist
 *  auf einen Blick klar, wo das Protokoll spricht und wo wir.
 *
 *  DIE LESEBREITE IST HIER KEINE KOSMETIK. Protokollreden tragen im ganzen
 *  Bestand KEINEN einzigen Absatzumbruch (214 Wortbeiträge geprüft, 0 mit
 *  „\n") — der längste läuft über 12.392 Zeichen am Stück. Ohne Deckel nahm
 *  der Absatz die volle Kartenbreite: gemessen 1.102 px, rund 129 Zeichen je
 *  Zeile, kursiv. Aufgeklappt waren das knapp hundert Zeilen, bei denen das
 *  Auge den Zeilenanfang verliert. 76 Zeichen sind die Breite, die der
 *  Beteiligungs-Steckbrief für denselben Fall führt (Fließtext aus einer
 *  fremden Quelle) — dieselbe Regel, damit die Seiten eine Sprache sprechen.
 *  Gekürzt wird dadurch nichts: Der Wortlaut bleibt Zeichen für Zeichen der
 *  des Protokolls. */
/** Der Punkt an der Rednerliste — wer spricht, in der Marken-Grammatik der
 *  Fraktions-Chips darüber.
 *
 *  Drei Lagen, drei Formen, alle drei gibt es im Bereich schon:
 *  * **Ratsmitglied mit Fraktion** — gefüllter Parteipunkt, dieselbe Farbe
 *    wie im Chip „CDU 4" am Kopf der Karte.
 *  * **Fraktion nicht eindeutig** — gestrichelter Hohlpunkt, wie ihn die
 *    `Fraktion`-Zeile für diesen Fall schon führt (Namensvettern-Regel:
 *    eine geratene Fraktion wäre schlimmer als eine fehlende).
 *  * **Verwaltung und Sitzungsleitung** — Hohlpunkt mit fester Kontur: Sie
 *    sprechen für ihr Amt, nicht für eine Fraktion, und eine Parteifarbe
 *    stünde ihnen falsch. Gruppen-Labels mit Schrägstrich bekommen den
 *    neutralen Punkt, aus demselben Grund wie in den Chips (s. NEUTRAL). */
function RednerPunkt({ b, rechts }: { b: StreitWortbeitrag; rechts: boolean }) {
  const lage = cn(
    "absolute top-[18px] h-[11px] w-[11px] rounded-full",
    // Schmale Karte: alle Punkte links übereinander. Breite Karte: der Punkt
    // sitzt am ÄUSSEREN Ufer seiner Karte — der Pfad pendelt dadurch über die
    // volle Breite, nicht nur bis zur Mitte.
    rechts ? "left-1 @2xl:left-auto @2xl:right-1" : "left-1",
  );
  if (b.rolle !== "rat") {
    return <span aria-hidden data-punkt className={cn(lage, "border-[1.5px] border-muted-foreground/70 bg-card")} />;
  }
  if (b.fraktion_unklar || !b.fraktion) {
    return <span aria-hidden data-punkt className={cn(lage, "border border-dashed border-muted-foreground/60 bg-card")} />;
  }
  const dot = b.fraktion.includes("/") ? NEUTRAL : parteiDot(b.fraktion);
  return (
    <span aria-hidden data-punkt className={lage} style={{
      background: dot.bg,
      boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,.15)" : undefined,
    }} />
  );
}

/** Die Debatte als geschlungener Pfad (Tims Wunsch, 21.08.2026: „Wäre cool,
 *  wenn der Pfeil nicht linear wäre, sondern so geschlungen von rechts nach
 *  links — und die Personen/Parteien tauchen erst beim Scrollen mit Animation
 *  auf").
 *
 *  DREI TEILE, ALLE OHNE FREMDBIBLIOTHEK:
 *
 *  1. **Die Schlange.** Jede zweite Rede rückt auf breiten Karten nach rechts
 *     (s. `Rede`), und ein SVG-Pfad verbindet die Redner-Punkte mit weichen
 *     S-Kurven — gemessen an den echten Punkt-Positionen, nicht an einer
 *     angenommenen Geometrie: Aufgeklappte Reden ändern die Höhen, der
 *     ResizeObserver zeichnet dann neu. Auf schmalen Karten stehen alle
 *     Punkte übereinander und dieselbe Rechnung ergibt von allein eine
 *     gerade Linie — kein zweiter Codepfad.
 *  2. **Der Pfeil wandert mit.** Über dem blassen Gesamtpfad liegt eine
 *     zweite, kräftigere Kopie, die per `stroke-dashoffset` genau so weit
 *     gezeichnet ist, wie die Liste gescrollt wurde — die Debatte „läuft" zur
 *     Schlussabstimmung. Am Ende sitzt eine Pfeilspitze: Der Weg führt
 *     irgendwohin, nämlich zur Abstimmung darunter. Direktes DOM statt
 *     React-State: Ein setState je Scroll-Ereignis renderte 21 Reden neu.
 *  3. **Der Auftritt.** Jede Rede steht anfangs leicht abgesenkt und
 *     durchsichtig (`data-reveal="aus"`) und tritt beim ersten Sichtkontakt
 *     auf (IntersectionObserver, einmalig je Rede).
 *
 *  `prefers-reduced-motion` schaltet alles Bewegte ab: Der Pfad steht dann
 *  fertig gezeichnet, die Reden stehen sichtbar da — die `motion-safe:`-
 *  Varianten an den Reveal-Klassen und die Weiche unten sorgen dafür. Ohne
 *  JavaScript passiert schlicht nichts: kein Observer, kein `data-reveal`,
 *  alles bleibt sichtbar. */
function DebattenListe({ reden }: { reden: StreitWortbeitrag[] }) {
  const huelle = useRef<HTMLDivElement>(null);
  const liste = useRef<HTMLOListElement>(null);
  const stift = useRef<SVGPathElement>(null);
  const [pfad, setPfad] = useState<{ d: string; w: number; h: number } | null>(null);

  // Die Kurve aus den echten Punkt-Positionen.
  useEffect(() => {
    const ol = liste.current;
    if (!ol) return;
    const messen = () => {
      const basis = ol.getBoundingClientRect();
      const punkte = [...ol.querySelectorAll<HTMLElement>("[data-punkt]")].map((el) => {
        const r = el.getBoundingClientRect();
        return { x: r.left - basis.left + r.width / 2, y: r.top - basis.top + r.height / 2 };
      });
      if (punkte.length < 2) { setPfad(null); return; }
      // EIN weicher Bogen je Übergang, kein Eckwerk: Die Steuerpunkte liegen
      // senkrecht unter bzw. über den Ankern — die Kurve verlässt einen Punkt
      // nach unten, schwingt über die volle Breite und kommt von oben beim
      // nächsten an. Weil die Karten opak sind, darf sie dabei überall
      // langlaufen; auf schmalen Karten (alle Punkte übereinander) ergibt
      // dieselbe Rechnung von allein eine gerade Linie.
      let d = `M ${punkte[0].x.toFixed(1)} ${punkte[0].y.toFixed(1)}`;
      for (let i = 1; i < punkte.length; i++) {
        const a = punkte[i - 1], b = punkte[i];
        const zug = Math.max(36, (b.y - a.y) * 0.55);
        d += ` C ${a.x.toFixed(1)} ${(a.y + zug).toFixed(1)}, ${b.x.toFixed(1)} ${(b.y - zug).toFixed(1)}, ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
      }
      setPfad({ d, w: basis.width, h: basis.height });
    };
    messen();
    const ro = new ResizeObserver(messen);
    ro.observe(ol);
    return () => ro.disconnect();
  }, [reden.length]);

  // Der wandernde Stift — direktes DOM, s. Kopfkommentar.
  useEffect(() => {
    const el = stift.current;
    if (!el || !pfad) return;
    const laenge = el.getTotalLength();
    // Erst OHNE Übergang auf den Startzustand setzen — sonst „malt" sich der
    // ganze Pfad beim ersten Rendern einmal quer durchs Bild. Der weiche
    // Übergang kommt danach: Er lässt den Strich dem Scrollen mit einer
    // halben Sekunde Nachlauf folgen, statt hart an der Scroll-Position zu
    // kleben — das war Tims „keine schöne Animation".
    el.style.transition = "none";
    el.style.strokeDasharray = `${laenge}`;
    el.style.strokeDashoffset = `${laenge}`;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.style.strokeDashoffset = "0";
      return;
    }
    void el.getBoundingClientRect();
    el.style.transition = "stroke-dashoffset 0.55s cubic-bezier(0.22, 0.61, 0.36, 1)";
    let angemeldet = 0;
    const zeichnen = () => {
      angemeldet = 0;
      const ol = liste.current;
      if (!ol) return;
      const r = ol.getBoundingClientRect();
      // Gezeichnet ist, was über der Lese-Linie (85 % der Fensterhöhe) liegt.
      const anteil = Math.min(1, Math.max(0, (window.innerHeight * 0.85 - r.top) / r.height));
      el.style.strokeDashoffset = `${laenge * (1 - anteil)}`;
    };
    const aufScroll = () => {
      if (!angemeldet) angemeldet = requestAnimationFrame(zeichnen);
    };
    zeichnen();
    window.addEventListener("scroll", aufScroll, { passive: true });
    window.addEventListener("resize", aufScroll);
    return () => {
      if (angemeldet) cancelAnimationFrame(angemeldet);
      window.removeEventListener("scroll", aufScroll);
      window.removeEventListener("resize", aufScroll);
    };
  }, [pfad]);

  // Der Auftritt der Reden.
  useEffect(() => {
    const ol = liste.current;
    if (!ol) return;
    const lis = [...ol.querySelectorAll<HTMLElement>(":scope > li")];
    const io = new IntersectionObserver((eintraege) => {
      for (const e of eintraege) {
        if (!e.isIntersecting) continue;
        (e.target as HTMLElement).dataset.reveal = "an";
        io.unobserve(e.target);
      }
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.1 });
    for (const li of lis) {
      li.dataset.reveal = "aus";
      io.observe(li);
    }
    return () => io.disconnect();
  }, [reden.length]);

  return (
    <div ref={huelle} className="relative">
      {pfad && (
        <svg
          aria-hidden
          className="pointer-events-none absolute inset-0 text-border"
          width={pfad.w} height={pfad.h}
          viewBox={`0 0 ${pfad.w} ${pfad.h}`}
          fill="none"
        >
          <defs>
            {/* Die Spitze sitzt am BLASSEN Gesamtpfad, nicht am Stift: Dort
                flackerte sie beim Scrollen mit jedem Dashoffset-Schritt. */}
            {/* Der Chevron zeigt im Marker-Raum nach +x; `orient="auto"`
                dreht ihn in die Laufrichtung des Pfads — am Ende also nach
                unten, auf die Schlussabstimmung zu. */}
            <marker id="debatten-pfeil" viewBox="0 0 8 8" refX="6" refY="4"
              markerWidth="8" markerHeight="8" orient="auto">
              <path d="M 2 1 L 6 4 L 2 7" stroke="currentColor" strokeWidth="1.5"
                fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </marker>
          </defs>
          <path d={pfad.d} stroke="currentColor" strokeWidth="1.5"
            markerEnd="url(#debatten-pfeil)" />
          {/* Der Stift etwas kräftiger als die blasse Vorzeichnung — er ist
              die Route, die man schon gegangen ist. */}
          <path ref={stift} d={pfad.d} className="text-primary/45" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" />
        </svg>
      )}
      <ol ref={liste} className="relative list-none">
        {reden.map((b, i) => <Rede key={i} b={b} rechts={i % 2 === 1} />)}
      </ol>
    </div>
  );
}

function Rede({ b, rechts }: { b: StreitWortbeitrag; rechts: boolean }) {
  const [offen, setOffen] = useState(false);
  const { kopf, rest } = vorschau(b.text);

  return (
    <li className={cn(
      "group relative pb-7 last:pb-0",
      "transition-opacity duration-700 ease-out motion-safe:data-[reveal=aus]:opacity-0",
    )}>
      <RednerPunkt b={b} rechts={rechts} />
      {/* DIE KARTE IST OPAK, und das ist keine Kosmetik, sondern die Statik
          dieses Elements: Der Pfad darf dadurch frei und mit vollem Schwung
          HINTER den Wortbeiträgen durchlaufen — ein erster Entwurf ließ den
          Text transparent und musste den Pfad in schmalen Gassen daran
          vorbeiführen: kantig, halbbreit, und bei schmaleren Fenstern lief
          er doch durch den Text (Tims Befund). Die Verschiebung beim
          Auftritt liegt an der Karte, NICHT am <li>: Der Punkt ist der
          Messanker des Pfads und muss stehen bleiben. */}
      <div className={cn(
        "relative ml-7 rounded-xl border border-border bg-card p-3.5 shadow-sm",
        "transition-transform duration-700 ease-out",
        "@2xl:w-[56%]",
        rechts
          ? "@2xl:ml-auto @2xl:mr-7 motion-safe:group-data-[reveal=aus]:translate-x-4"
          : "motion-safe:group-data-[reveal=aus]:-translate-x-4",
      )}>
        <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
          <span className="text-[13px] font-semibold leading-snug text-foreground">{b.name}</span>
          {/* Bei Verwaltung und Sitzungsleitung sagt die Anrede die Rolle
              schon („Oberbürgermeister", „Stadtkämmerin") — ein zusätzliches
              „Verwaltung" daneben wäre dieselbe Angabe zweimal. */}
          {b.rolle === "rat" && (b.fraktion_unklar ? (
            <span className="text-[11.5px] text-muted-foreground">Fraktion nicht eindeutig</span>
          ) : b.fraktion && (
            <span className="text-[11.5px] font-medium text-foreground/80">{b.fraktion}</span>
          ))}
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/80">
            {b.anrede}
          </span>
        </div>
        <p className="mt-1.5 text-[13.5px] leading-relaxed text-foreground/90">
          {offen ? b.text : kopf}
          {!offen && rest && <span className="text-muted-foreground"> …</span>}
        </p>
        {rest && (
          <button
            type="button"
            onClick={() => setOffen((o) => !o)}
            className="mt-1 inline-flex min-h-[32px] items-center text-[11.5px] font-semibold text-primary"
          >
            {offen ? "Weniger" : `Ganzen Beitrag lesen (${b.zeichen.toLocaleString("de-DE")} Zeichen)`}
          </button>
        )}
      </div>
    </li>
  );
}

/** Eine Änderungsliste mit ihrem Ergebnis. */
function AntragsZeile({ a }: { a: StreitAntrag }) {
  return (
    <div className="flex flex-col gap-1 border-t border-border/60 py-2 first:border-t-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
      <div className="min-w-0">
        {a.ist_verwaltung ? (
          <span className="text-[12px] font-semibold text-muted-foreground">Verwaltung</span>
        ) : (
          <Fraktion label={a.urheber} />
        )}
        <p className="mt-0.5 max-w-[86ch] text-[12.5px] leading-relaxed text-muted-foreground">
          {a.titel}
        </p>
      </div>
      <span className="flex-none">
        <OutcomeDot outcome={(a.outcome ?? null) as DecisionOutcome | null} />
      </span>
    </div>
  );
}

function StationsAntraege({ s }: { s: StreitStation }) {
  const fraktionen = s.antraege.filter((a) => !a.ist_verwaltung);
  const verwaltung = s.antraege.filter((a) => a.ist_verwaltung);
  return (
    <section className="border-t border-dashed border-border pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h3 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-foreground/70">
          {gremiumKurz(s.gremium)}
        </h3>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          {datumLang(s.datum)} · {fraktionen.length} aus dem Rat
          {verwaltung.length > 0 && ` · ${verwaltung.length} der Verwaltung`}
        </span>
      </div>
      <div className="mt-1">
        {fraktionen.map((a, i) => <AntragsZeile key={`f${i}`} a={a} />)}
      </div>
      {verwaltung.length > 0 && (
        <details className="group mt-2 border-t border-dashed border-border pt-2">
          <summary className="cursor-pointer list-none text-[11.5px] font-semibold text-primary">
            {verwaltung.length} Änderungslisten der Verwaltung anzeigen
          </summary>
          {/* Getrennt, weil es keine Fraktionsanträge sind: Die Verwaltung
              schreibt ihren eigenen Entwurf fort. Zwischen den anderen
              stehend sähe es aus, als hätte jemand neunmal gewonnen. */}
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Die Verwaltung bringt eigene Änderungslisten ein — das ist kein Antrag aus dem Rat,
            sondern die Fortschreibung ihres eigenen Entwurfs, etwa wenn zwischen Entwurf und
            Beschluss neue Zahlen eintreffen.
          </p>
          <div className="mt-1">
            {verwaltung.map((a, i) => <AntragsZeile key={`v${i}`} a={a} />)}
          </div>
        </details>
      )}
    </section>
  );
}

export function StreitAbschnitt() {
  const gewaehltesJahr = Number(useSearchParams().get("jahr")) || null;
  const { data, loading } = useFetch<StreitDaten>("/council/haushalt/streit");

  const jahre = useMemo(() => jahrgaenge(data ?? null), [data]);
  const jahr = gewaehltesJahr && jahre.includes(gewaehltesJahr) ? gewaehltesJahr : jahre[0] ?? null;
  const r = useMemo(() => runde(data ?? null, jahr), [data, jahr]);

  const debatte = debattenStation(r);
  const schluss = schlussbeschluss(r);
  const antragsSt = antragsStationen(r);
  const jeFraktion = redenJeFraktion(debatte);

  // Die Verhandlungsbilanz des gewählten Jahrgangs. Kombinierte Labels
  // (gemeinsame Listen, Gruppen) und „Einzelne Ratsmitglieder" bekommen
  // KEINEN Parteipunkt — dieselbe Regel wie in <Fraktion> oben.
  const bilanzZeilen: PunkteZeile[] = useMemo(
    () => verhandlungsBilanz(r).map((z) => ({
      fraktion: z.urheber,
      farbe: z.urheber.includes("/") || z.urheber === EINZELNE
        ? undefined
        : parteiDot(z.urheber),
      gremien: { fa: z.fa, rat: z.rat },
    })),
    [r],
  );
  const zuordnung = useMemo(() => ohneZuordnung(data ?? null), [data]);
  const quelle = useMemo(() => bestand(data ?? null), [data]);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  if (!jahr || !r) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für keinen Jahrgang liegt bisher ein ausgelesenes Protokoll vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  return (
      <div className="flex flex-col gap-4">
        <div>
          <h2 className="font-display text-xl font-bold tracking-tight sm:text-[22px]">
            Der Streit ums Geld
          </h2>
          <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
            Ein Haushalt ist kein Rechenergebnis, sondern ein Kompromiss. Bevor er beschlossen
            wird, legen die Fraktionen Änderungslisten vor, und im Rat wird stundenlang darüber
            geredet. Beides steht in den Protokollen — hier ist es, Jahrgang für Jahrgang.
          </p>
        </div>

        {/* Jahrgangs-Umschalter. Query-Param statt dynamischem Segment: Der
            Capacitor-Export kennt die Jahre zur Bauzeit nicht — dieselbe
            Konvention wie /haushalt/plan-ist?jahr=… */}
        <div className="rounded-2xl border border-border bg-card p-3.5 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Haushaltsjahr
          </p>
          {/* H4-A: mobil ein Scrollband (nie ein Dropdown — der Vergleichs-
              Blick über die Jahre ist der Sinn des Umschalters), ab 744 px
              passen alle Pillen nebeneinander. */}
          <div className="scrollbar-none -mx-1 mt-2 flex gap-1.5 overflow-x-auto px-1 pb-0.5 [@media(min-width:744px)]:flex-wrap">
            {jahre.map((j) => (
              <Link
                key={j}
                href={`/haushalt/streit?jahr=${j}`}
                scroll={false}
                className={cn(
                  "flex-none rounded-full border px-3 py-1 font-mono text-[12px] font-medium tabular-nums transition-colors",
                  j === jahr
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
                )}
              >
                {j}
              </Link>
            ))}
          </div>
          <p className="mt-2 max-w-[70ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Der Haushalt für ein Jahr wird meist im Dezember davor beschlossen — der für 2026
            erst im Februar 2026. Das Jahr hier ist das Haushaltsjahr, nicht das Sitzungsjahr.
            Protokolle liegen ab Januar 2018 im Bestand; deshalb ist der Haushalt 2019 der
            erste Jahrgang, dessen Beratung hier steht.
          </p>
        </div>

        {/* Die Verhandlungsbilanz — das tragende Bild der Seite (H3-04):
            Punkte statt Prozente, alphabetisch, Finanzausschuss und Rat
            getrennt. Die Fairness-Regeln stecken in <PunkteBilanz> selbst. */}
        {bilanzZeilen.length > 0 && (
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Verhandlungsbilanz
              </h2>
              <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                Haushalt {jahr}
              </span>
            </div>
            <p className="mt-1 text-[15px] font-bold leading-snug">
              Wer wollte den Haushalt {jahr} ändern — und kam damit durch?
            </p>
            <p className="mt-1 max-w-[66ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Jeder Punkt ist eine Abstimmung über eine Änderungsliste, gefüllt heißt: fand eine
              Mehrheit. Die Bilanz sagt, wer ändern wollte — was genau, steckt in Anlagen ohne
              Volltext und wird nicht behauptet. Eine Erfolgsquote steht hier bewusst nicht:
              Eingebracht und abgelehnt ist parlamentarischer Alltag der Opposition, kein
              Zeugnis.
            </p>
            <PunkteBilanz
              className="mt-3"
              zeilen={bilanzZeilen}
              beleg={<Beleg q="ratsbeschluss" />}
            />
            {/* Bewusst ohne Breitendeckel: Das ist eine Quellenzeile, keine
                Prosa — sie wird nicht zeilenweise gelesen, sondern einmal
                gescannt. Mit Deckel brach „214 Wortbeiträge" allein in eine
                zweite Zeile, was schlechter aussah als die lange erste. */}
            {quelle.jahrgaenge > 0 && (
              <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                Ratsinformationssystem, Änderungslisten und Protokolle {quelle.von}–{quelle.bis}{" "}
                · {quelle.listen.toLocaleString("de-DE")} Listen ·{" "}
                {quelle.beitraege.toLocaleString("de-DE")} Wortbeiträge
              </p>
            )}
          </div>
        )}

        {/* Wie es ausging. */}
        {schluss?.beschluss && (
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Wie es ausging
              </h2>
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                {gremiumKurz(schluss.gremium)} · {datumLang(schluss.datum)}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <OutcomeBadge outcome={(schluss.beschluss.outcome ?? null) as DecisionOutcome | null} />
              <span className="text-[13.5px] font-semibold text-foreground">
                Haushaltssatzung und Haushaltsplan {r.jahr}
              </span>
            </div>
            {schluss.beschluss.wortlaut && (
              <p className="mt-2 max-w-[76ch] border-l-2 border-border pl-3 text-[13px] leading-relaxed text-foreground/90">
                {schluss.beschluss.wortlaut}
              </p>
            )}
            <p className="mt-2 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
              Wie die einzelnen Ratsmitglieder gestimmt haben, führt das Ratsinformationssystem
              nicht — es hält nur fest, ob einstimmig oder mehrheitlich beschlossen wurde und wie
              viele Gegenstimmen und Enthaltungen es gab.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-dashed border-border pt-2.5">
              <Link
                href={sessionHref(schluss.ksinr, schluss.beschluss.top ? [schluss.beschluss.top] : undefined)}
                className="text-[11.5px] font-semibold text-primary"
              >
                Sitzung im Ratsinformationssystem
              </Link>
              {schluss.protokoll_url && (
                <a
                  href={schluss.protokoll_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-primary"
                >
                  <FileText className="h-3 w-3" />
                  Protokoll als PDF
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        )}

        {/* Die Listen im Einzelnen — das Detail hinter der Bilanz. */}
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Die Listen im Einzelnen
            </h2>
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {antragsSt.reduce((n, s) => n + s.antraege.filter((a) => !a.ist_verwaltung).length, 0)}{" "}
              Änderungslisten aus dem Rat
            </span>
          </div>
          <p className="mt-1 max-w-[66ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Über jede Liste wird einzeln abgestimmt. Dieselbe Liste kann im Ausschuss anders
            ausgehen als im Rat — deshalb stehen beide Stationen hier, nicht eine
            zusammengefasste.
          </p>

          {antragsSt.length === 0 ? (
            <p className="mt-3 border-t border-dashed border-border pt-3 text-[12.5px] leading-relaxed text-muted-foreground">
              Für diesen Jahrgang weist das Protokoll keine einzeln abgestimmten Änderungslisten
              aus. Das heißt nicht, dass es keine gab: In manchen Jahren protokolliert der Rat nur
              die Schlussabstimmung über den fertigen Haushalt.
            </p>
          ) : (
            <div className="mt-3 flex flex-col gap-3.5">
              {antragsSt.map((s) => <StationsAntraege key={s.ksinr} s={s} />)}
            </div>
          )}
        </div>

        {/* Was gesagt wurde. */}
        {debatte && debatte.debatte.length > 0 && (
          <div className="@container rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Aus der Haushaltsdebatte
              </h2>
              <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                {debatte.debatte.length} Wortbeiträge · {gremiumKurz(debatte.gremium)},{" "}
                {datumLang(debatte.datum)}
              </span>
            </div>
            {/* Wer wie oft zu Wort kam. Vorher lief das als nackte Wortkette
                („Grüne 5 BSW 2 CDU 2 Für Oldenburg 2 …") über zwei Zeilen —
                zwischen Label und Zahl stand derselbe Abstand wie zwischen
                zwei Fraktionen, und mobil brach die Zeile mitten in einem
                Paar. Als Chips mit dem gewohnten 8-px-Punkt (Designsprache
                §2) hält jedes Paar zusammen und trägt dieselbe Marke wie die
                Rede darunter. Eine Zahl, keine Wertung: Redeanteile sind
                Geschäftsordnung, kein Zeugnis. */}
            {jeFraktion.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {jeFraktion.map((f) => {
                  const dot = f.label.includes("/") ? NEUTRAL : parteiDot(f.label);
                  return (
                    <li key={f.label}
                      className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-[11.5px] text-muted-foreground">
                      <span aria-hidden className="h-2 w-2 flex-none rounded-full"
                        style={{
                          background: dot.bg,
                          boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,.15)" : undefined,
                        }} />
                      <span className="font-medium text-foreground">{f.label}</span>
                      <span className="tabular-nums">{f.n}</span>
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="mt-2 max-w-[66ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Alle Wortbeiträge des Tagesordnungspunkts, in der Reihenfolge des Protokolls. Jeder
              ist auf dieselbe Länge gekürzt und lässt sich vollständig aufklappen — eine Auswahl
              „der wichtigsten Stellen" träfe sonst jemand.
            </p>
            <div className="mt-3 border-t border-dashed border-border pt-4">
              <DebattenListe reden={debatte.debatte} />
            </div>
            <p className="mt-3 max-w-[86ch] border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
              {HINWEIS_REDE}
            </p>
          </div>
        )}

        {/* Ohne Zuordnung — die Namensvettern-Karte (H3-04). Sie bleibt
            IMMER sichtbar, sobald Wortbeiträge im Bestand sind: Dass acht
            Beiträge keine Fraktion tragen, ist eine Eigenschaft des
            Bestands, kein Kleingedrucktes. Die Zahlen sind gezählt, nicht
            geschrieben. */}
        {zuordnung.gesamt > 0 && (
          <div className="rounded-2xl border border-dashed border-border bg-card p-4 shadow-sm">
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Ohne Zuordnung
            </h2>
            {zuordnung.ohne > 0 ? (
              <p className="mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
                <strong className="font-semibold">
                  {zuordnung.ohne} der {zuordnung.gesamt} Wortbeiträge
                </strong>{" "}
                aller Jahrgänge tragen keine Fraktion: In der Anwesenheitsliste stehen
                Namensvettern, und das Protokoll nennt nur den Nachnamen. Sie erscheinen so —
                es wird keine geraten. Die Sitzungsleitung zählt als Rolle, nicht als Fraktion.
              </p>
            ) : (
              <p className="mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
                Derzeit tragen alle {zuordnung.gesamt} Wortbeiträge eine eindeutige Zuordnung.
                Wo das nicht gelingt — etwa bei Namensvettern in der Anwesenheitsliste —,
                erscheint ein Beitrag ohne Fraktion; geraten wird keine. Die Sitzungsleitung
                zählt als Rolle, nicht als Fraktion.
              </p>
            )}
          </div>
        )}

        <LottiErklaert
          titel="Was eine Änderungsliste ist"
          pose="point"
          text={
            "Die Verwaltung legt einen Entwurf vor. Wer daran etwas ändern will, sammelt seine " +
            "Wünsche in einer Liste — mehr Geld hier, weniger dort. Über jede Liste stimmt der " +
            "Rat einzeln ab, und erst danach über den fertigen Haushalt."
          }
        />

        {/* Die Grenze der Seite — sichtbar, nicht im Kleingedruckten. */}
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was hier fehlt
          </h2>
          <ul className="mt-2 flex max-w-[70ch] list-disc flex-col gap-1.5 pl-4 text-[12.5px] leading-relaxed text-muted-foreground">
            <li>
              <strong className="font-semibold text-foreground">Der Inhalt der Änderungslisten.</strong>{" "}
              Welche Position eine Fraktion um welchen Betrag verschieben wollte, steht in den
              Anlagen zur Vorlage. Diese PDFs liegen nicht als Volltext vor, deshalb steht hier,
              wer etwas einbrachte und ob es durchkam — nicht, was genau darin stand.
            </li>
            <li>
              <strong className="font-semibold text-foreground">Das Stimmverhalten Einzelner.</strong>{" "}
              Das Ratsinformationssystem führt keine namentlichen Abstimmungen; nur das Ergebnis
              je Abstimmung ist bekannt.
            </li>
            <li>
              <strong className="font-semibold text-foreground">Reden außerhalb des Haushaltspunkts.</strong>{" "}
              Aufgeführt sind die Wortbeiträge unter dem Tagesordnungspunkt, unter dem der
              Haushalt beraten wurde. Über Geld wird auch anderswo gestritten.
            </li>
            <li>
              <strong className="font-semibold text-foreground">Einzelne Fraktionszuordnungen.</strong>{" "}
              Saßen zwei Ratsmitglieder mit demselben Nachnamen im Rat und nennt das Protokoll nur
              diesen, bleibt die Fraktion offen — eine geratene wäre schlimmer als eine fehlende.
            </li>
          </ul>
        </div>

      </div>
  );
}

