"use client";

// /haushalt/pruefung — „Die Gegenprobe" in ihrer zweiten Hälfte: geprüft und
// zusammengefasst.
//
// Zweite von fünf Zusammenlegungen (Tims Weg A, 21.08.2026). Bis dahin waren
// das zwei Schritte: „Die Prüfung" (was das Rechnungsprüfungsamt fand) und
// „Die dreizehn Zahlen" (womit die Stadt ihren eigenen Abschluss zusammenfasst).
// Sie beantworten dieselbe Frage aus zwei Richtungen — von außen geprüft, von
// innen zusammengefasst —, und nebeneinander sind sie mehr wert als
// hintereinander: Die Kennzahlen sagen, wie die Stadt dasteht, die
// Feststellungen, wie verlässlich diese Auskunft ist.
//
// Der Rahmen liegt hier, der Inhalt in den beiden `abschnitt-*.tsx` (die
// Begründung steht im Kopf von `abschnitt-termine.tsx`).

import { Suspense, useState } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte, ANKER_KLASSE } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, SeitenbuehneLaedt, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { PruefungAbschnitt } from "@/components/haushalt/abschnitt-pruefung";
import { KennzahlenAbschnitt } from "@/components/haushalt/abschnitt-kennzahlen";

/** Ausgeschrieben, nicht zusammengesetzt: `tests/test_quellen_dokumente.py`
 *  liest die Literale dieser Liste, um stumme Beleg-Chips zu finden. */
const QUELLEN: QuellenSchluessel[] = ["pruefbericht", "kennzahlen", "bilanz"];

const MARKEN = [
  { id: "feststellungen", titel: "Was geprüft wurde" },
  { id: "kennzahlen", titel: "Die dreizehn Zahlen" },
];

function PruefungInner() {
  // Die Zahlen der Bühne kommen aus dem Feststellungs-Abschnitt selbst
  // (`onBestand`) — dieselbe Antwort, die unten die KettenMatrix trägt.
  const [bestand, setBestand] = useState<{
    gesamt: number;
    jeJahr: { jahr: number; anzahl: number }[];
    ohneBericht: number[];
  } | null | undefined>(undefined);
  return (
    // KEIN `jahr` am Kontext. Die beiden Abschnitte führen verschiedene
    // Jahrgänge — der Prüfbericht den gewählten (`?jahr=`), die Kennzahlen den
    // jüngsten Rechenschaftsbericht. Ein gemeinsamer Wert wäre für einen von
    // beiden der falsche; ohne ihn nimmt jeder Beleg das jüngste Dokument
    // seiner Quelle und schreibt den Jahrgang an.
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Geprüft und zusammengefasst</span>
        </div>

        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/pruefung" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Geprüft und zusammengefasst
            </h1>
          </div>
          <SchrittPfad href="/haushalt/pruefung" />
        </div>

        {/* Die Bühne (H5-02/H5-09). Die fehlenden Jahrgänge stehen im Kopf,
            nicht in der Fußnote: als Signal-Zeile und als gestrichelter
            Leerplatz im Minibild (LückenFeld-Regel). */}
        {bestand ? (
          <Seitenbuehne
            kicker={`Rechnungsprüfung ${Math.min(...bestand.jeJahr.map((j) => j.jahr))}–${Math.max(...bestand.jeJahr.map((j) => j.jahr))}`}
            zahl={<><ZaehlZahl wert={bestand.gesamt} /> Feststellungen
              aus {bestand.jeJahr.length} Jahren</>}
            sub={bestand.ohneBericht.length > 0 ? (
              <span className="font-semibold text-[color:hsl(var(--signal))]">
                {bestand.ohneBericht.join(" und ")} {bestand.ohneBericht.length > 1 ? "fehlen" : "fehlt"} ersatzlos —
                geprüft wurde, der Schlussbericht ist nicht lesbar veröffentlicht
              </span>
            ) : "erstmalige und wiederholte Beanstandungen, Hinweise und Klarstellungen"}
            minibild={{
              href: "#feststellungen",
              label: "Feststellungen je Jahrgang · gestrichelt = Bericht fehlt — klickt zur Matrix",
              skizze: (() => {
                const max = Math.max(...bestand.jeJahr.map((j) => j.anzahl), 1);
                const saeulen = [
                  ...bestand.jeJahr.map((j) => ({ jahr: j.jahr, anzahl: j.anzahl as number | null })),
                  ...bestand.ohneBericht.map((j) => ({ jahr: j, anzahl: null })),
                ].sort((a, b) => a.jahr - b.jahr);
                return (
                  <span className="flex items-end gap-1" style={{ height: 44 }}>
                    {saeulen.map((sl) => sl.anzahl != null ? (
                      <span key={sl.jahr} className="w-5 rounded-[3px]" style={{
                        height: `${Math.max((sl.anzahl / max) * 100, 8)}%`,
                        background: "var(--sb-voll)",
                      }} />
                    ) : (
                      <span key={sl.jahr} className="w-5 rounded-[3px]" style={{
                        height: "68%",
                        border: "1.5px dashed hsl(var(--signal))",
                      }} />
                    ))}
                  </span>
                );
              })(),
            }}
          />
        ) : bestand === undefined ? (
          <SeitenbuehneLaedt kicker="Rechnungsprüfung" />
        ) : null}

        {/* Einstiegstext unter der Bühne, kleiner (Tim, 26.08.). */}
        <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">
          Jeder Jahresabschluss wird von einer eigenen Stelle geprüft, die dem Rat
          berichtet und nicht der Verwaltungsspitze untersteht. Und am Ende jedes
          Rechenschaftsberichts fasst die Stadt denselben Abschluss selbst in
          dreizehn Kennzahlen zusammen. Beides gehört nebeneinander: Die Kennzahlen
          sagen, wie die Stadt dasteht — die Feststellungen, wie verlässlich diese
          Auskunft ist.
        </p>

        <Abschnitte marken={MARKEN} />

        <section id="feststellungen" className={ANKER_KLASSE}>
          <PruefungAbschnitt onBestand={setBestand} />
        </section>

        <section id="kennzahlen" className={`${ANKER_KLASSE} border-t border-border pt-4`}>
          <KennzahlenAbschnitt />
        </section>

        <SchrittWeiter href="/haushalt/pruefung" />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function PruefungPage() {
  // `useSearchParams` im Prüfungs-Abschnitt (`?jahr=`) braucht eine
  // Suspense-Grenze — sie lag vorher an der Prüfungs-Seite und bleibt hier.
  return (
    <Suspense
      fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}
    >
      <PruefungInner />
    </Suspense>
  );
}
