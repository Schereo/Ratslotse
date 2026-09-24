"use client";

// „Woher die Zahlen kommen" — der Umfang des Haushalts-Bereichs auf /haushalt.
//
// Tims Wunsch (24.09.2026): zeigen, wie viel hinter der Übersicht steckt.
// Die Antwort ist gezählt, nicht behauptet — `council/quellenzahlen.py` liest
// bei jedem Aufruf (zehn Minuten gepuffert) jede Datentabelle und jeden
// Beleg. Eine Zahl, die hier von Hand stünde, wäre nach dem nächsten Ingest
// falsch.
//
// EINGEKLAPPT UNTEN, nicht als Karte oben (Tim, 24.09.2026, nach dem ersten
// Bild): Die Zählung belegt die Seite, sie ist nicht ihr Inhalt. Sie steht
// deshalb als Lade im Apparat neben „Stand der Daten" und dem
// Quellenverzeichnis — zugeklappt mit der einen Zeile, die neugierig macht.
//
// Drei Ebenen, vom Großen ins Kleine: die vier Kennzahlen, die Dokumente
// nach veröffentlichender Stelle (ein geteilter Balken, eine Farbe in
// Abstufungen — kein Rang, keine Wertung), und je Datenschicht Dokumente
// und Zahlen in der Reihenfolge der Registry (`finanzquellen.REIHENFOLGE`),
// nicht nach Größe sortiert.

import { useState } from "react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deZahl } from "@/components/grafik/format";
import { Apparat } from "@/components/haushalt/source";

type Antwort = ApiAntwort<"/council/budget/source-stats">;

const SICHTBAR = 8;
/** Abstufungen EINER Farbe — die Stellen sind Kategorien, keine Rangfolge. */
const TOENE = ["bg-primary", "bg-primary/75", "bg-primary/55", "bg-primary/40",
  "bg-primary/30", "bg-primary/20", "bg-primary/15", "bg-primary/10"];

/** „rund 62.000" — die Zählung ist eine von Zellen, auf den Hunderter genau
 *  zu tun wäre Scheingenauigkeit. */
function rund(n: number): string {
  const stufe = n >= 10_000 ? 1000 : n >= 1000 ? 100 : 1;
  return deZahl(Math.round(n / stufe) * stufe, 0);
}

function Kennzahl({ wert, einheit, text }: { wert: string; einheit: string; text: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 px-3 py-2.5">
      <dd className="font-display text-[18px] font-bold leading-none tabular-nums text-foreground">
        {wert}
      </dd>
      <dt className="mt-1.5 text-[12.5px] font-semibold text-foreground">{einheit}</dt>
      <dd className="mt-0.5 text-[11.5px] leading-snug text-muted-foreground">{text}</dd>
    </div>
  );
}

function Zeile({ titel, unter, dokumente, zahlen, groesste }: {
  titel: string; unter: string; dokumente: number; zahlen: number; groesste: number;
}) {
  return (
    <li className="flex flex-col gap-1.5 px-3 py-2.5 sm:flex-row sm:items-center sm:gap-4">
      <div className="min-w-0 flex-1">
        <span className="block text-[13px] font-semibold leading-snug text-foreground">{titel}</span>
        <span className="mt-0.5 block text-[11.5px] text-muted-foreground">{unter}</span>
      </div>
      <div className="flex items-center gap-3 text-[12px] sm:w-[330px] sm:flex-none sm:justify-end">
        <span className="whitespace-nowrap text-muted-foreground">
          <span className="font-mono tabular-nums text-foreground">{deZahl(dokumente, 0)}</span>{" "}
          {dokumente === 1 ? "Dokument" : "Dokumente"}
        </span>
        <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted sm:w-24 sm:flex-none" aria-hidden>
          <span className="block h-full rounded-full bg-primary/50"
            style={{ width: `${(100 * zahlen) / groesste}%` }} />
        </span>
        <span className="whitespace-nowrap text-muted-foreground sm:w-[92px] sm:text-right">
          {zahlen > 0
            ? <><span className="font-mono tabular-nums text-foreground">{deZahl(zahlen, 0)}</span> Zahlen</>
            : "Wortlaut"}
        </span>
      </div>
    </li>
  );
}

export function QuellenUmfang() {
  const { data } = useFetch<Antwort>("/council/budget/source-stats");
  const [alle, setAlle] = useState(false);
  if (!data || data.documents === 0) return null;

  const schichten = data.layers.filter((s) => s.rows > 0);
  const zeigen = alle ? schichten : schichten.slice(0, SICHTBAR);
  const groesste = Math.max(...schichten.map((s) => s.numbers), data.other.numbers, 1);
  const stellen = data.sources.length;

  return (
    <Apparat kicker="Umfang der Daten"
      zusatz={`rund ${rund(data.numbers)} Zahlen aus ${deZahl(data.documents, 0)} Dokumenten`}>
    <div className="mt-3 flex flex-col gap-4">
      <p className="max-w-[74ch] text-[12.5px] leading-relaxed text-muted-foreground">
        Der Haushaltsbereich führt zusammen, was sonst über Haushaltspläne, Jahresabschlüsse,
        Ratsvorlagen, Prüfberichte, Wirtschaftspläne und amtliche Statistiken verteilt ist — aus{" "}
        {stellen} veröffentlichenden Stellen. Jede Zahl behält ihren Beleg, und beim Einlesen
        muss sie Proben bestehen: Summen gegen ihre Teile, der Plan gegen den Abschluss, eine
        zweite Quelle gegen die erste. Was nicht aufgeht, bleibt draußen.
      </p>

      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kennzahl wert={rund(data.numbers)} einheit="Zahlen"
          text={`in ${deZahl(data.rows, 0)} Datenzeilen aus ${data.tables} Tabellen`} />
        <Kennzahl wert={deZahl(data.documents, 0)} einheit="Dokumente"
          text={`aus ${stellen} Stellen, von der Ratsanlage bis zur Bundesstatistik`} />
        <Kennzahl wert={deZahl(data.citations, 0)} einheit="Belegstellen"
          text="Fundstellen, auf die die Zahlen einzeln verweisen" />
        <Kennzahl wert={deZahl(data.probe_runs, 0)} einheit="bestandene Proben"
          text={`${data.probe_kinds} verschiedene Rechenproben beim Einlesen`} />
      </dl>

      <div className="flex flex-col gap-2">
        <h3 className="text-[13px] font-semibold text-foreground">Dokumente nach Stelle</h3>
        <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
          {data.sources.map((s, i) => (
            <div key={s.kind} className={TOENE[i % TOENE.length]}
              style={{ width: `${(100 * s.documents) / data.documents}%` }} />
          ))}
        </div>
        <ul className="grid gap-x-5 gap-y-1 text-[12px] sm:grid-cols-2">
          {data.sources.map((s, i) => (
            <li key={s.kind} className="flex items-baseline gap-2">
              <span className={`inline-block h-2.5 w-2.5 flex-none translate-y-[1px] rounded-sm ${TOENE[i % TOENE.length]}`} />
              <span className="min-w-0 flex-1 text-foreground/90">{s.label}</span>
              <span className="font-mono tabular-nums text-foreground">{deZahl(s.documents, 0)}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-[13px] font-semibold text-foreground">Je Datenschicht</h3>
        {/* Eigene Zeilen statt ZahlenTabelle: Deren Handy-Form stellt die
            Zellen unbeschriftet untereinander — „7" und „392" ohne zu sagen,
            was Dokumente und was Zahlen sind. Hier trägt jede Zahl ihr Wort. */}
        <ul className="flex flex-col divide-y divide-border rounded-xl border border-border">
          {zeigen.map((s) => (
            <Zeile key={s.keys.join("+")} titel={s.labels.join(" · ")} unter={s.sources.join(" · ")}
              dokumente={s.documents} zahlen={s.numbers} groesste={groesste} />
          ))}
          {alle && data.other.rows > 0 && (
            <Zeile titel="Weitere Tabellen"
              unter={`${data.other.tables} Tabellen, die mehrere Seiten teilen — etwa Änderungslisten, Spenden und Hebesätze`}
              dokumente={data.other.documents} zahlen={data.other.numbers} groesste={groesste} />
          )}
        </ul>
        {schichten.length > SICHTBAR && (
          <button type="button" onClick={() => setAlle((o) => !o)}
            className="w-fit text-[12.5px] font-semibold text-primary">
            {alle ? "Weniger zeigen" : `Alle ${schichten.length} Schichten zeigen`}
          </button>
        )}
      </div>

      <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Gezählt aus dem aktuellen Bestand. „Zahlen“ sind die einzelnen Werte — Beträge, Quoten,
        Stellen, Einwohnerzahlen —, ohne Jahreszahlen, Seitenzahlen und Kennungen. Ein Dokument
        ist eine Ratsanlage, eine Liste oder ein Datensatz. Mehrere Schichten können dasselbe
        Dokument lesen; die Zeilen lassen sich deshalb nicht zur Summe oben addieren.
      </p>
    </div>
    </Apparat>
  );
}
