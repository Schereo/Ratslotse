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
// „Wie rede ich mit?" —, und `/haushalt/jahr` war im ganzen Frontend über
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
// DER RAHMEN LIEGT HIER, der Inhalt in den `abschnitt-*.tsx`: Quellenkontext
// und Verzeichnis führen die VEREINIGUNG aller Quellen, und der Beleg-Chip
// nummeriert seitenweise. Verschachtelte Quellenkontexte hätten
// konkurrierende Nummerierungen ergeben.

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, SeitenbuehneLaedt, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { deDatum } from "@/lib/haushalt-jahr";
import { TermineAbschnitt } from "@/components/haushalt/abschnitt-termine";
import { StreitAbschnitt } from "@/components/haushalt/abschnitt-streit";

/** Termine und Streit belegen sich mit dem Ratsinformationssystem; seit die
 *  Änderungslisten gelesen werden, kommt deren Dokumentquelle dazu — der
 *  Block „Was in den Listen stand" zeigt Positionen aus echten Papieren.
 *  (`tests/test_quellen_dokumente.py` liest die Literale dieser Liste, um
 *  stumme Beleg-Chips zu finden.) */
const QUELLEN: QuellenSchluessel[] = ["ratsbeschluss", "aenderungsliste"];

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
    naechster: { datum: string; gremium: string } | null;
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

        {/* Die Bühne (H5-02/H5-09): der nächste Termin der Beratungsfolge,
            in Tagen — steht keiner im Ratskalender, tragen die Wortbeiträge
            des Streit-Abschnitts die Bühne, statt dass ein Termin erfunden
            wird. Das Minibild ist der Zeitstrahl (schematisch, der nächste
            Termin trägt den Halo) und klickt zu den Terminen. */}
        {termine === undefined && streit === undefined ? (
          <SeitenbuehneLaedt kicker="Ratskalender" />
        ) : (() => {
          const heute0 = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate()).getTime();
          const naechster = termine?.naechster ?? null;
          const tage = naechster
            ? Math.round((new Date(naechster.datum).getTime() - heute0) / 86400000)
            : null;
          const streitSatz = streit
            ? `${streit.beitraege.toLocaleString("de-DE")} Wortbeiträge zum Streit ums Geld`
            : null;
          const minibild = {
            href: naechster ? "#termine" : "#streit",
            label: naechster
              ? "Zeitstrahl der Beratungsfolge — der nächste Termin trägt den Halo, klickt zu den Terminen"
              : "Zeitstrahl der Beratungsfolge — klickt zum Streit ums Geld",
            skizze: (
              <span className="relative block h-[18px]">
                <span className="absolute inset-x-0 top-2 h-[2px]" style={{ background: "var(--sb-blass)" }} />
                <span className="absolute left-[4%] top-[5px] h-2 w-2 rounded-full" style={{ background: "var(--sb-voll)" }} />
                <span className="absolute left-[26%] top-[5px] h-2 w-2 rounded-full" style={{ background: "var(--sb-voll)" }} />
                {naechster ? (
                  <span className="absolute left-[55%] top-[3px] h-3 w-3 rounded-full shadow-[0_0_0_3.5px_hsl(var(--primary)/0.18)]" style={{ background: "var(--sb-voll)" }} />
                ) : (
                  <span className="absolute left-[55%] top-[5px] h-2 w-2 rounded-full" style={{ background: "var(--sb-voll)" }} />
                )}
                <span className="absolute left-[84%] top-[5px] h-2 w-2 rounded-full border-[1.5px] bg-transparent" style={{ borderColor: "var(--sb-strich)" }} />
              </span>
            ),
          };
          if (naechster && tage != null && tage >= 0) {
            return (
              <Seitenbuehne
                kicker="Ratskalender · Beratungsfolge des Haushalts"
                zahl={tage === 0 ? <>Nächster Termin: heute</>
                  : tage === 1 ? <>Nächster Termin: morgen</>
                    : <>Nächster Termin: in <ZaehlZahl wert={tage} /> Tagen</>}
                sub={`${naechster.gremium} am ${deDatum(naechster.datum)}${streitSatz ? ` — dazu ${streitSatz}` : ""}`}
                minibild={minibild}
              />
            );
          }
          if (streit) {
            return (
              <Seitenbuehne
                kicker={`Haushaltsberatungen ${streit.von}–${streit.bis}`}
                zahl={<><ZaehlZahl wert={streit.beitraege} /> Wortbeiträge zum Streit ums Geld</>}
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
          Ein Haushalt ist kein Rechenergebnis, sondern ein Kompromiss — und er
          entsteht in öffentlichen Sitzungen. Hier steht, wann darüber entschieden
          wird und worüber die Fraktionen gestritten haben. Selbst an den
          Stellschrauben drehen kannst du danach im{" "}
          <Link href="/haushalt/labor" className="font-semibold text-primary">
            Haushalts-Labor
          </Link>.
        </p>

        <Abschnitte marken={MARKEN} />

        {/* `scroll-mt` an jedem Abschnitt: Der klebende Streifen deckt die
            Überschrift sonst zu, wenn jemand mit einem `#anker` von außen
            kommt — dann läuft unser eigener Sprung-Rechner gar nicht. */}
        <section id="termine" className="scroll-mt-20">
          <TermineAbschnitt onBestand={setTermine} />
        </section>

        <section id="streit" className="scroll-mt-20 border-t border-border pt-4">
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
  // `useSearchParams` im Streit-Abschnitt (`?jahr=`) braucht eine
  // Suspense-Grenze — sie lag vorher an der Streit-Seite und zieht mit um.
  return (
    <Suspense
      fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}
    >
      <MitredenInner />
    </Suspense>
  );
}
