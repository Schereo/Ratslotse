"use client";

// /haushalt/konzern — die ganze Stadt: Summe, Gesellschaften, Pläne, Gebühren.
//
// Fünfte und letzte Zusammenlegung (Tims Weg A, 21.08.2026; 19 → 11). VIER
// Seiten beantworteten dieselbe Frage — „Ist der Haushalt die ganze Stadt?" —
// und zwar in einer Kette, die man nur ganz versteht:
//
//   1. die SUMME       (Gesamtabschluss: Kernverwaltung plus alle Betriebe)
//   2. die BETEILIGTEN (jede Gesellschaft mit Auftrag und Aufsicht)
//   3. ihre PLÄNE      (was die Eigenbetriebe sich fürs Jahr vornehmen)
//   4. die FOLGE       (was davon als Gebühr bei den Leuten ankommt)
//
// Wer bei 4 anfängt, liest eine Zahl ohne Herkunft; wer bei 1 aufhört, weiß
// nicht, wer dahintersteckt. Als vier Schritte im Wegweiser standen sie
// nebeneinander wie vier Angebote.
//
// EIN DATENAUFRUF FÜR ZWEI ABSCHNITTE. Betriebe und Gebühren brauchen beide
// `herkunft`, und `useFetch` hat keinen Zwischenspeicher — zwei Abschnitte mit
// eigenem Aufruf wären zwei Requests auf fast dieselbe Adresse. Die Seite holt
// deshalb `wirtschaftsplaene`, `gebuehren`, `gebuehrensaetze` und `herkunft`
// zusammen und reicht
// sie durch. Sie braucht die Wirtschaftsplan-Zeilen ohnehin selbst: Aus ihnen
// entsteht `jeDokument`, die Nummerierung der einzelnen Pläne.

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltAuswahl, haushaltUrl, herkunftVon } from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte, ANKER_KLASSE } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, SeitenbuehneLaedt, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { KonzernAbschnitt } from "@/components/haushalt/section-konzern";
import { GesellschaftenAbschnitt } from "@/components/haushalt/section-gesellschaften";
import { BetriebeAbschnitt } from "@/components/haushalt/section-betriebe";
import { GebuehrenAbschnitt } from "@/components/haushalt/section-gebuehren";

const FELDER = ["wirtschaftsplaene", "gebuehren", "gebuehrensaetze", "herkunft"] as const;

/** Ausgeschrieben, nicht zusammengesetzt: `tests/test_quellen_dokumente.py`
 *  liest die Literale dieser Liste. Reihenfolge = Nummerierung der Chips, also
 *  die Reihenfolge der Abschnitte. */
const QUELLEN: QuellenSchluessel[] = [
  "gesamtabschluss", "beteiligungsbericht", "wirtschaftsplan", "gebuehren",
];

const MARKEN = [
  { id: "summe", titel: "Die ganze Stadt" },
  { id: "gesellschaften", titel: "Wer dahintersteckt" },
  { id: "betriebe", titel: "Was sie planen" },
  { id: "gebuehren", titel: "Was Sie zahlen" },
];

function KonzernSeiteInner() {
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(
    haushaltUrl(FELDER));
  // Die Zahlen der Bühne kommen aus den Abschnitten selbst (`onBestand`) —
  // dieselben Antworten, die unten Anteilsbalken und Gesellschafts-Liste
  // tragen. Kein zweiter Abruf, keine zweite Wahrheit.
  // `undefined` = lädt, `null` = entschieden nichts — dann keine Bühne.
  const [kern, setKern] = useState<{ anteil: number; year: number } | null | undefined>(undefined);
  const [bericht, setBericht] = useState<{
    gesellschaften: number; kennzahlen: number; von: number; bis: number;
  } | null | undefined>(undefined);

  // Die Adressen der Pläne, die die Betriebs-Karten zeigen — aus den KARTEN,
  // nicht aus dem Jahrgang: Den Stadthafen gibt es seit 2020 nicht mehr, die
  // Stadion-Planung endete 2024. Ihre Papiere stehen in keiner Jahrgangsliste
  // von 2026, ihre Karten aber sehr wohl auf der Seite.
  const jeDokument = useMemo(() => {
    const zeilen = data?.wirtschaftsplaene ?? [];
    const jeBetrieb = new Map<string, typeof zeilen>();
    for (const z of zeilen) jeBetrieb.set(z.betrieb, [...(jeBetrieb.get(z.betrieb) ?? []), z]);
    const gruppen = [...jeBetrieb.values()]
      .sort((a, b) => Math.abs(b.at(-1)?.result ?? 0) - Math.abs(a.at(-1)?.result ?? 0));
    const urls = gruppen
      .map((g) => [...g].sort((a, b) => a.year - b.year).at(-1))
      .map((z) => (z ? herkunftVon(data, z.herkunft_id)?.url : undefined))
      .filter((u): u is string => !!u);
    return urls.length ? { wirtschaftsplan: urls } : {};
  }, [data]);

  return (
    <Quellenkontext schluessel={QUELLEN} jeDokument={jeDokument}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Die ganze Stadt</span>
        </div>

        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/konzern" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Und ist das die ganze Stadt?
            </h1>
          </div>
          <SchrittPfad href="/haushalt/konzern" />
        </div>

        {/* Die Bühne (H5-02/H5-09). Minibild: der Anteilsbalken Kernhaushalt
            gegen den Rest des Konzerns — klickt zur gemeinsamen Rechnung. */}
        {kern ? (
          <Seitenbuehne
            kicker={`Gesamtabschluss · Konzern Oldenburg · ${kern.year}`}
            zahl={<>Der Kernhaushalt ist <ZaehlZahl wert={kern.anteil * 100} />&#8239;% der Stadt</>}
            sub={bericht
              ? `${bericht.gesellschaften} Betriebe und Gesellschaften · ${bericht.kennzahlen} Kennzahlen aus den Jahren ${bericht.von}–${bericht.bis}`
              : "gemessen an den Erträgen des jüngsten Gesamtabschlusses"}
            minibild={{
              href: "#summe",
              label: "Anteilsbalken: Kernhaushalt und Rest — klickt zur Summe",
              skizze: (() => {
                const prozent = Math.round(kern.anteil * 100);
                return (
                  <>
                    <span className="flex h-[22px] overflow-hidden rounded-[6px]">
                      <span style={{ width: `${prozent}%`, background: "var(--sb-voll)" }} />
                      <span className="flex-1" style={{ background: "var(--sb-blass)" }} />
                    </span>
                    <span className="flex justify-between text-[9.5px] text-muted-foreground">
                      <span>Kernhaushalt {prozent}&#8239;%</span>
                      <span>daneben {100 - prozent}&#8239;%</span>
                    </span>
                  </>
                );
              })(),
            }}
          />
        ) : kern === undefined ? (
          <SeitenbuehneLaedt kicker="Gesamtabschluss · Konzern Oldenburg" />
        ) : null}

        {/* Einstiegstext unter der Bühne, kleiner (Tim, 26.08.). */}
        <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">
          Nein. Der Kernhaushalt bildet vor allem die Stadtverwaltung ab. Klinikum,
          Busse, Bäder und die städtische Gebäudewirtschaft führen eigene Bücher. Diese
          Seite zeigt zunächst den zusammengefassten Konzernabschluss, anschließend die
          einzelnen Betriebe und Gesellschaften, ihre Wirtschaftspläne und die daraus
          berechneten Gebühren.
        </p>

        <Abschnitte marken={MARKEN} />

        <section id="summe" className={ANKER_KLASSE}>
          <KonzernAbschnitt onBestand={setKern} />
        </section>

        <section id="gesellschaften" className={`${ANKER_KLASSE} border-t border-border pt-4`}>
          <GesellschaftenAbschnitt onBestand={setBericht} />
        </section>

        <section id="betriebe" className={`${ANKER_KLASSE} border-t border-border pt-4`}>
          <BetriebeAbschnitt data={data} loading={loading} />
        </section>

        <section id="gebuehren" className={`${ANKER_KLASSE} border-t border-border pt-4`}>
          <GebuehrenAbschnitt data={data} loading={loading} />
        </section>

        <SchrittWeiter href="/haushalt/konzern" />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function KonzernSeite() {
  // `useSearchParams` im Gesellschaften-Abschnitt (`?g=`) braucht eine
  // Suspense-Grenze — sie lag vorher an der Beteiligungen-Seite.
  return (
    <Suspense
      fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}
    >
      <KonzernSeiteInner />
    </Suspense>
  );
}
