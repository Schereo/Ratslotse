"use client";

// /haushalt/produkte — vom Teilhaushalt zur einzelnen Aufgabe.
//
// Vierte von fünf Zusammenlegungen (Tims Weg A, 21.08.2026). „Was steckt
// hinter den Namen?" und „Was kostet eigentlich …?" waren zwei Schritte, gehen
// aber denselben Baum hinunter: erst die zehn Teilhaushalte im Klartext, dann
// die einzelnen Produkte darin. Wer den zweiten Schritt ohne den ersten liest,
// sucht Aufgaben in Bereichen, deren Namen ihm nichts sagen.
//
// DIE DRITTE EBENE BLEIBT EINE EIGENE SEITE: `/haushalt/bereich?thh=…` ist der
// Steckbrief eines einzelnen Teilhaushalts. Er hat bewusst keinen Schritt im
// Wegweiser — man kommt dorthin aus der Liste, nicht der Reihe nach.

import { Suspense, useState } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte, ANKER_KLASSE } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, SeitenbuehneLaedt, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { BereicheAbschnitt } from "@/components/haushalt/abschnitt-bereiche";
import { ProdukteAbschnitt } from "@/components/haushalt/abschnitt-produkte";

/** Ausgeschrieben, nicht zusammengesetzt: `tests/test_quellen_dokumente.py`
 *  liest die Literale dieser Liste. Vereinigung beider Abschnitte, in
 *  Leserichtung — die Bereichs-Übersicht belegt sich mit `plan`, die
 *  Produktebene mit `teilhaushalt`. */
const QUELLEN: QuellenSchluessel[] = [
  "plan", "steuern", "steuerkraft", "teilhaushalt",
];

const MARKEN = [
  { id: "bereiche", titel: "Was die Namen heißen" },
  { id: "produkte", titel: "Was einzelne Aufgaben kosten" },
];

function ProdukteSeiteInner() {
  // Die eine Zahl der Bühne kommt aus dem Produkte-Abschnitt selbst
  // (`onBestand`) — dieselbe Antwort, die unten den Satz „Hier stehen N
  // davon …" trägt. Kein zweiter Abruf, keine zweite Wahrheit.
  // `undefined` = lädt (Platzhalter hält die Höhe), `null` = entschieden
  // nichts (keine Bühne), sonst die Werte.
  const [bestand, setBestand] = useState<{
    count: number; year: number; beispiele: { name: string; wert: number }[];
  } | null | undefined>(undefined);
  return (
    // KEIN gemeinsames `year`: Die Bereichs-Übersicht zeigt den jüngsten
    // Ansatz, die Produktebene den jüngsten Jahrgang MIT Produktdaten — und
    // die liegen auseinander, weil die Produktebene erst mit dem Abschluss
    // vorliegt. Ohne den Wert nimmt jeder Beleg das jüngste Dokument seiner
    // Quelle und schreibt den Jahrgang an.
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Was kostet eigentlich …?</span>
        </div>

        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/produkte" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Was kostet eigentlich …?
            </h1>
          </div>
          <SchrittPfad href="/haushalt/produkte" />
        </div>

        {/* Die Bühne (H5-02/H5-09). Minibild: der Produktbaum — ein
            Teilhaushalt, darunter eingerückt seine Aufgaben — klickt zur
            Suche. Bis die Antwort des Abschnitts da ist, hält der
            Platzhalter die Höhe, damit die Seite nicht springt. */}
        {bestand ? (
          <Seitenbuehne
            kicker={`Produktebene · Haushaltsjahr ${bestand.year}`}
            zahl={<><ZaehlZahl wert={bestand.count} /> einzelne Aufgaben, vom Stadtarchiv
              bis zum Schwimmbad</>}
            sub="jede mit Kosten, zuständigem Amt und Auftragsgrundlage"
            minibild={{
              href: "#produkte",
              label: "die drei größten nach Zuschussbedarf — klickt zur Suche",
              skizze: (() => {
                // Echte Namen statt Baum-Skizze (Tim, 26.08.: „übersichtlicher
                // umbauen") — dieselben Zeilen, die die Trefferliste oben
                // trägt, verkleinert.
                const max = Math.max(...bestand.beispiele.map((b) => b.wert), 1);
                return bestand.beispiele.map((b) => (
                  <span key={b.name} className="flex flex-col gap-[3px]">
                    <span className="truncate text-[9.5px] leading-none text-muted-foreground">{b.name}</span>
                    <span className="block h-3 rounded-[4px]" style={{
                      width: `${Math.max((b.wert / max) * 100, 4)}%`,
                      background: "var(--sb-voll)",
                    }} />
                  </span>
                ));
              })(),
            }}
          />
        ) : bestand === undefined ? (
          <SeitenbuehneLaedt kicker="Produktebene" />
        ) : null}

        {/* BEWUSST kein Einstiegstext mehr zwischen Bühne und Abschnitten
            (Tim, 26.08.): Der Bereichs-Abschnitt beginnt mit fast demselben
            Satz („Der Haushalt ist in Teilhaushalte geteilt …") — der
            Kopf-Absatz war seine Dublette. */}
        <Abschnitte marken={MARKEN} />

        <section id="bereiche" className={ANKER_KLASSE}>
          <BereicheAbschnitt />
        </section>

        <section id="produkte" className={`${ANKER_KLASSE} border-t border-border pt-4`}>
          <ProdukteAbschnitt onBestand={setBestand} />
        </section>

        <SchrittWeiter href="/haushalt/produkte" />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function ProdukteSeite() {
  // `useSearchParams` im Produkte-Abschnitt braucht eine Suspense-Grenze.
  return (
    <Suspense
      fallback={
        <div className="py-16 text-center text-sm text-muted-foreground">
          Produkte werden geladen …
        </div>
      }
    >
      <ProdukteSeiteInner />
    </Suspense>
  );
}
