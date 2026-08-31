"use client";

// /haushalt/mitreden — die Etappe „Mitreden" als EINE Seite.
//
// WARUM ZUSAMMENGELEGT (Tim, 21.08.2026): „Ganz generell bin ich auch gar kein
// Fan davon, dass wir jetzt irgendwie 19 Unterseiten haben. […] Man weiß gar
// nicht, wo man anfangen soll. […] Man wird erschlagen vor Inhalten."
//
// Gemessen war der Befund schärfer als „neunzehn sind viele": Mehrere Seiten
// waren entlang unserer EINLESE-Geschichte geschnitten, nicht entlang der
// Frage, die jemand hat. Diese Abschnitte beantworten zusammen eine einzige —
// „Wie rede ich mit?" —, und `/haushalt/year` war im ganzen Frontend über
// nichts als den Wegweiser erreichbar. Eine Seite, die sonst niemand
// verlinkt, trägt nicht als eigenes Ziel.
//
// DAS LABOR IST SEIT 24.08.2026 WIEDER EIGENE SEITE (/haushalt/labor). Es
// stand hier drei Tage als dritter Abschnitt; Tims Entscheidung: Es soll
// deutlich mehr Stellschrauben bekommen, und ein wachsendes Werkzeug braucht
// eine eigene Adresse. Der Befund von damals — nichts verlinkte hin — ist
// damit nicht zurück: Diese Seite, der Steuer-Steckbrief und die
// Weiter-Navigation am Fuß führen hin.
//
// Die Reihenfolge ist die des Mitredens: erst WANN (sonst kommt man zu spät),
// dann WORÜBER gestritten wurde — ausprobieren geht danach im Labor.
//
// DER RAHMEN LIEGT HIER, der Inhalt in den `section-*.tsx`: Quellenkontext
// und Verzeichnis führen die VEREINIGUNG aller Quellen, und der Beleg-Chip
// nummeriert seitenweise. Verschachtelte Quellenkontexte hätten
// konkurrierende Nummerierungen ergeben.

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte, ANKER_KLASSE } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, SeitenbuehneLaedt, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { deDatum } from "@/lib/haushalt-jahr";
import { cn } from "@/lib/utils";
import { TermineAbschnitt } from "@/components/haushalt/section-termine";
import { StreitAbschnitt } from "@/components/haushalt/section-streit";

/** Termine und Streit belegen sich mit dem Ratsinformationssystem; seit die
 *  Änderungslisten gelesen werden, kommt deren Dokumentquelle dazu — der
 *  Block „Was in den Listen stand" zeigt Positionen aus echten Papieren.
 *  (`tests/test_quellen_dokumente.py` liest die Literale dieser Liste, um
 *  stumme Beleg-Chips zu finden.) */
const QUELLEN: QuellenSchluessel[] = ["ratsbeschluss", "aenderungsliste"];

/** „2025-10-01" → „1.10.2025" — die Kurzform für den Phasen-Strahl der
 *  Bühne; ausgeschrieben (`deDatum`) wären vier Zeilen zu lang. */
function deTagMonatJahr(iso: string): string {
  const [j, m, t] = iso.split("-").map(Number);
  return `${t}.${m}.${j}`;
}

const MARKEN = [
  { id: "termine", titel: "Wann entschieden wird" },
  { id: "streit", titel: "Der Streit ums Geld" },
];

function MitredenInner() {
  // Die Werte der Bühne kommen aus den Abschnitten selbst (`onBestand`) —
  // derselbe Ratskalender wie der Zeitstrahl, dieselbe Streit-Quelle wie die
  // Quellenzeile. Kein zweiter Abruf, keine zweite Wahrheit.
  // `undefined` = lädt, `null`/leer = entschieden nichts.
  const [termine, setTermine] = useState<{
    naechster: { datum: string; committee: string } | null;
    phasen: { titel: string; datum: string | null; erledigt: boolean; aktuell: boolean }[];
    year: number;
  } | null | undefined>(undefined);
  const [streit, setStreit] = useState<{ beitraege: number; von: number; bis: number } | null | undefined>(undefined);
  const heute = useMemo(() => new Date(), []);
  return (
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Mitreden</span>
        </div>

        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/mitreden" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Mitreden
            </h1>
          </div>
          <SchrittPfad href="/haushalt/mitreden" />
        </div>

        {/* Die Bühne (H5-02/H5-09). Zwei Nachsteuerungen aus Tims Review
            (26.08.): Der Kopf sagt „in den Ratsdebatten zum Haushalt" statt
            „Streit ums Geld" — die Seite berichtet über Ratsdebatten, sie
            kündigt kein Format an. Und rechts steht kein schematischer
            Strahl mit unbeschrifteten Punkten mehr, sondern der WEG des
            jüngsten Haushalts mit seinen vier Phasen und ihren Daten;
            markiert ist die, in der wir gerade stecken. Er verlinkt bewusst
            nicht: Die Auskunft steht in ihm selbst, und der ausführliche
            Zeitstrahl folgt ohnehin direkt darunter. */}
        {termine === undefined && streit === undefined ? (
          <SeitenbuehneLaedt kicker="Ratskalender" />
        ) : (() => {
          const heute0 = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate()).getTime();
          const naechster = termine?.naechster ?? null;
          const tage = naechster
            ? Math.round((new Date(naechster.datum).getTime() - heute0) / 86400000)
            : null;
          const phasen = termine?.phasen ?? [];
          const minibild = phasen.length ? {
            label: `Der Weg des Haushalts ${termine!.year} — der Punkt mit dem Ring ist der Stand heute`,
            skizze: phasen.map((ph, i) => (
              // Eine Zeile je Phase: Punkt, Titel, Datum rechtsbündig. Die
              // Linie läuft DURCH die Zeile (nicht als Stummel unter dem
              // Punkt, das sah aus wie Karten-Pins), und vier flache Zeilen
              // halten die Bühne so hoch wie ihren Text — kein Loch daneben.
              <span key={ph.titel} className="relative flex items-center gap-2 py-[3px]">
                <span aria-hidden className="relative flex h-4 w-2.5 flex-none items-center justify-center">
                  {i > 0 && (
                    <span className="absolute bottom-1/2 left-1/2 h-[11px] w-[1.5px] -translate-x-1/2" style={{
                      background: ph.erledigt ? "var(--sb-voll)" : "var(--sb-blass)",
                    }} />
                  )}
                  {i < phasen.length - 1 && (
                    <span className="absolute left-1/2 top-1/2 h-[11px] w-[1.5px] -translate-x-1/2" style={{
                      background: phasen[i + 1].erledigt ? "var(--sb-voll)" : "var(--sb-blass)",
                    }} />
                  )}
                  {ph.aktuell ? (
                    <span className="relative h-2.5 w-2.5 rounded-full border-2 bg-card shadow-[0_0_0_2.5px_hsl(var(--primary)/0.16)]"
                      style={{ borderColor: "var(--sb-voll)" }} />
                  ) : (
                    <span className="relative h-2 w-2 rounded-full" style={{
                      background: ph.erledigt ? "var(--sb-voll)" : "var(--sb-blass)",
                    }} />
                  )}
                </span>
                <span className={cn("min-w-0 flex-1 truncate text-[10px] leading-none",
                  ph.aktuell ? "font-semibold text-foreground" : "text-muted-foreground")}>
                  {ph.titel}
                </span>
                {ph.datum && (
                  <span className="flex-none font-mono text-[9px] leading-none tabular-nums text-muted-foreground">
                    {ph.titel.startsWith("Haushaltsjahr")
                      ? (ph.aktuell ? "läuft" : "beendet")
                      : deTagMonatJahr(ph.datum)}
                  </span>
                )}
              </span>
            )),
          } : undefined;
          if (naechster && tage != null && tage >= 0) {
            return (
              <Seitenbuehne
                kicker="Ratskalender · Beratungsfolge des Haushalts"
                zahl={tage === 0 ? <>Nächster Termin: heute</>
                  : tage === 1 ? <>Nächster Termin: morgen</>
                    : <>Nächster Termin: in <ZaehlZahl wert={tage} /> Tagen</>}
                sub={`${naechster.committee} am ${deDatum(naechster.datum)}`}
                minibild={minibild}
              />
            );
          }
          if (streit) {
            return (
              <Seitenbuehne
                kicker={`Haushaltsberatungen ${streit.von}–${streit.bis}`}
                zahl={<><ZaehlZahl wert={streit.beitraege} /> Wortbeiträge in den
                  Ratsdebatten zum Haushalt</>}
                sub="ein nächster Termin steht noch nicht im Ratskalender"
                minibild={minibild}
              />
            );
          }
          // Einer von beiden lädt noch: Platzhalter statt Sprung.
          if (termine === undefined || streit === undefined) {
            return <SeitenbuehneLaedt kicker="Ratskalender" />;
          }
          // Kein künftiger Termin und keine Streit-Quelle: keine Bühne —
          // die Abschnitte darunter erklären ihre Leere selbst.
          return null;
        })()}

        {/* Einstiegstext unter der Bühne, kleiner (Tim, 26.08.). */}
        <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">
          Über den Haushalt wird politisch entschieden: Die Verwaltung legt einen
          Entwurf vor, Ausschüsse beraten darüber und der Rat beschließt den endgültigen
          Plan. Hier siehst du die Termine und die Streitpunkte der Fraktionen. Eigene
          Annahmen kannst du anschließend im{" "}
          <Link href="/haushalt/labor" className="font-semibold text-primary">
            Haushalts-Labor
          </Link>.
        </p>

        <Abschnitte marken={MARKEN} />

        {/* `ANKER_KLASSE` an jedem Abschnitt: Der klebende Stapel (mobil
            Header + Streifen, ab `desk` nur der Streifen) deckt die
            Überschrift sonst zu, wenn jemand mit einem `#anker` von außen
            kommt — dann läuft unser eigener Sprung-Rechner gar nicht. */}
        <section id="termine" className={ANKER_KLASSE}>
          <TermineAbschnitt onBestand={setTermine} />
        </section>

        <section id="streit" className={`${ANKER_KLASSE} border-t border-border pt-4`}>
          <StreitAbschnitt onBestand={setStreit} />
        </section>

        {/* Die Anschlussstelle zum Labor — bewusst eine Karte statt nur des
            Satzes im Kopf: Wer bis hierher gelesen hat, weiß, worum gestritten
            wurde, und ist genau die Person, die jetzt selbst drehen will. */}
        <Link
          href="/haushalt/labor"
          className="group flex items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40"
        >
          <span>
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Selbst ausprobieren
            </span>
            <span className="mt-1 block text-[13.5px] font-semibold">
              Haushalts-Labor: an den Stellschrauben drehen und sehen, was das ausmacht
            </span>
          </span>
          <ArrowRight size={16} strokeWidth={2}
            className="shrink-0 text-primary transition-transform group-hover:translate-x-0.5" />
        </Link>

        <SchrittWeiter href="/haushalt/mitreden" />

        <Quellenverzeichnis schluessel={QUELLEN} />

        <Link
          href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary"
        >
          Zurück zur Übersicht über den Haushalt
          <ChevronRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </Quellenkontext>
  );
}

export default function MitredenPage() {
  // `useSearchParams` im Streit-Abschnitt (`?year=`) braucht eine
  // Suspense-Grenze — sie lag vorher an der Streit-Seite und zieht mit um.
  return (
    <Suspense
      fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}
    >
      <MitredenInner />
    </Suspense>
  );
}
