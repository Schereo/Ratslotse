"use client";

// /haushalt/investitionen — was gebaut werden soll, und was daraus wurde.
//
// Dritte von fünf Zusammenlegungen (Tims Weg A, 21.08.2026). Plan und Ist
// derselben Sache standen bis dahin auf zwei Seiten in ZWEI VERSCHIEDENEN
// ETAPPEN — „Was wird gebaut?" unter „Die Zahlen", „Was wurde davon wirklich
// gebaut?" unter „Die Gegenprobe". Das war als Konzept gedacht, hieß aber für
// Leserinnen: Wer wissen will, was aus einem Vorhaben geworden ist, muss die
// Seite wechseln und die Etappe verlassen.
//
// Die Reihenfolge bleibt die alte — erst der Plan, dann das Ist —, weil die
// zweite Zahl ohne die erste nichts bedeutet. Sie ist jetzt nur die
// Reihenfolge der Abschnitte.
//
// Die Etappe „Die Gegenprobe" behält ihre Aussage: `plan-ist` ist die
// Gegenprobe des Ergebnishaushalts, die Prüfung die des ganzen Abschlusses.
// Die des Finanzhaushalts steht dort, wo ihr Plan steht.

import { Suspense, useState } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte, ANKER_KLASSE } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, SeitenbuehneLaedt, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { InvestitionsplanAbschnitt } from "@/components/haushalt/abschnitt-investitionsplan";
import { GebautAbschnitt } from "@/components/haushalt/abschnitt-gebaut";

/** Ausgeschrieben, nicht zusammengesetzt: `tests/test_quellen_dokumente.py`
 *  liest die Literale dieser Liste. Reihenfolge = Nummerierung der Chips,
 *  also nach Leserichtung: erst der Plan, dann das Ist. */
const QUELLEN: QuellenSchluessel[] = [
  "investitionen", "investitionsprogramm", "gebaut", "jahresabschluss",
];

const MARKEN = [
  { id: "plan", titel: "Was gebaut werden soll" },
  { id: "gebaut", titel: "Was daraus wurde" },
];

function InvestitionenInner() {
  // Die Zahlen der Bühne kommen aus den beiden Abschnitten selbst
  // (`onBestand`) — dieselben Antworten, die unten Vorhaben-Listen und
  // NahtSäulen tragen. Kein zweiter Abruf, keine zweite Wahrheit.
  // `undefined` = lädt, `null` = entschieden nichts — dann keine Bühne.
  const [plan, setPlan] = useState<{ vorhaben: number; von: number; bis: number } | null | undefined>(undefined);
  const [gebaut, setGebaut] = useState<{ jahrgaenge: number; luecken: number[] } | null | undefined>(undefined);
  return (
    // KEIN gemeinsames `jahr`: Der Plan zeigt den gewählten Jahrgang (`?jahr=`),
    // das Ist den jüngsten abgeflossenen — die liegen naturgemäß auseinander,
    // das ist ja der Gegenstand dieser Seite. Ohne den Wert nimmt jeder Beleg
    // das jüngste Dokument SEINER Quelle und schreibt den Jahrgang an.
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Was gebaut wird</span>
        </div>

        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/investitionen" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Was gebaut wird — und was daraus wurde
            </h1>
          </div>
          <SchrittPfad href="/haushalt/investitionen" />
        </div>

        {/* Die Bühne (H5-02/H5-09). Minibild: die Kachelfläche des
            Vorhaben-Explorers, verkleinert — klickt zum Plan-Abschnitt. */}
        {plan ? (
          <Seitenbuehne
            kicker={`Investitionsprogramm · Pläne ${plan.von}–${plan.bis}`}
            zahl={<><ZaehlZahl wert={plan.vorhaben} /> Vorhaben sind einzeln aufgeführt</>}
            sub={gebaut
              ? `dazu ${gebaut.jahrgaenge} Jahrgänge Gebautes${gebaut.luecken.length
                ? ` — mit sichtbarer Lücke ${gebaut.luecken.join(", ")}` : ""}`
              : "dazu, was am Jahresende tatsächlich abgeflossen ist"}
            minibild={{
              href: "#plan",
              label: "Kachelfläche der Vorhaben — klickt zum Plan",
              skizze: (
                <>
                  <span className="flex h-8 gap-[3px]">
                    <span className="flex-[3] rounded-[4px]" style={{ background: "var(--sb-voll)" }} />
                    <span className="flex-[2] rounded-[4px]" style={{ background: "var(--sb-mittel)" }} />
                  </span>
                  <span className="flex h-5 gap-[3px]">
                    <span className="flex-[2] rounded-[4px]" style={{ background: "var(--sb-mittel)" }} />
                    <span className="flex-[1.4] rounded-[4px]" style={{ background: "var(--sb-blass)" }} />
                    <span className="flex-1 rounded-[4px]" style={{ background: "var(--sb-blass)" }} />
                  </span>
                </>
              ),
            }}
          />
        ) : plan === undefined ? (
          <SeitenbuehneLaedt kicker="Investitionsprogramm" />
        ) : null}

        {/* BEWUSST kein Einstiegstext mehr zwischen Bühne und Abschnitten
            (Tim, 26.08.): Der Plan-Abschnitt beginnt mit fast demselben Satz
            („Alles, was du auf den anderen Seiten siehst …") — der
            Kopf-Absatz war seine Dublette. */}
        <Abschnitte marken={MARKEN} />

        <section id="plan" className={ANKER_KLASSE}>
          <InvestitionsplanAbschnitt onBestand={setPlan} />
        </section>

        <section id="gebaut" className={`${ANKER_KLASSE} border-t border-border pt-4`}>
          <GebautAbschnitt onBestand={setGebaut} />
        </section>

        <SchrittWeiter href="/haushalt/investitionen" />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function InvestitionenSeite() {
  // `useSearchParams` im Plan-Abschnitt braucht eine Suspense-Grenze.
  return (
    <Suspense
      fallback={
        <div className="py-16 text-center text-sm text-muted-foreground">
          Investitionen werden geladen …
        </div>
      }
    >
      <InvestitionenInner />
    </Suspense>
  );
}
