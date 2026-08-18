"use client";

// /haushalt/kennzahlen — „Die dreizehn Zahlen"
//
// Am Ende jedes Rechenschaftsberichts steht eine Anlage, die den ganzen
// Jahresabschluss auf dreizehn Zahlen eindampft. Das ist die Zusammenfassung,
// die die Stadt für ihre Ratsmitglieder schreibt — und sie ist die einzige
// Stelle im ganzen Bereich, an der die **Rechenwege mitgedruckt** sind.
//
// DAS IST DER GRUND FÜR DIESE SEITE. Überall sonst müssten wir eine Kennzahl
// selbst definieren, und dann stünde da eine Zahl, die es so nirgends gibt.
// Hier zitieren wir: „Ermittlung: Sachvermögen * 100 / Bilanzsumme". Wer
// nachrechnen will, kann es — und wir haben es getan: Drei der Quoten lassen
// sich aus unserer eigenen Bilanz nachrechnen und stimmen auf die letzte
// gedruckte Nachkommastelle.
//
// DIE NACHRICHT DER SEITE IST NICHT EINE ZAHL, SONDERN EIN WIDERSPRUCH. Jeder
// Bericht druckt fünf Jahre, nicht eins — die sechs Berichte überlappen sich
// also, und an sieben Stellen widersprechen sie sich. Die Steuerquote 2021
// heißt im Bericht 2021 45,90 %, im Bericht 2022 49,05 % und im Bericht 2023
// wieder 45,92 %: hoch und zurück, ohne ein Wort dazu. Solche Korrekturen
// stehen in keiner Pressemitteilung; sie fallen nur auf, wenn jemand zwei
// Berichte nebeneinanderlegt.
//
// KEINE BEWERTUNG, und hier ist das besonders leicht falsch zu machen. Eine
// „Eigenkapitalquote von 50 %" klingt nach einer Note. Sie ist keine: Ob 50 %
// gut sind, hängt davon ab, was die Stadt mit dem Rest finanziert hat. Die
// Seite zeigt Verläufe und die gedruckte Formel, sie vergibt keine Ampel —
// keine Bewertungsfarben (DESIGNSPRACHE.md § 7), keine Schwellenwerte, die
// wir uns ausgedacht hätten.
//
// WO EINE REIHE BRICHT, entscheiden die Daten (lib/haushalt-kennzahlen.ts):
// Ein geänderter Rechenweg allein reicht nicht — er muss auch zu anderen
// Werten geführt haben. Von drei Wechseln im Bestand ist genau einer echt.

import { useMemo, useState } from "react";
import { FileText } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { haushaltUrl, type HaushaltAuswahl } from "@/lib/haushalt";
import {
  GRUPPEN, differenzFormatVon, einheitWort, formatVon, formelVon, juengstesJahr,
  korrekturenVon, punkteVon, reiheVon, schreibe,
} from "@/lib/haushalt-kennzahlen";
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";

//: Kleine Zahlen schreibt der Bereich aus („aus sechs Berichten"), große als
//: Ziffern. Die Grenze liegt bei zwölf — darüber wird es zum Zungenbrecher.
const ZAHLWORT: Record<number, string> = {
  1: "einem", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs",
  7: "sieben", 8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwölf",
};

const QUELLEN = ["kennzahlen", "bilanz"] as const;
const FELDER = ["kennzahlen"] as const;
type Daten = HaushaltAuswahl<(typeof FELDER)[number]>;

/** Der Stand des jüngsten Jahres, alle dreizehn auf einmal.
 *
 *  Die Nicht-Chart-Entsprechung, die jede Grafik in diesem Bereich hat — und
 *  hier ausnahmsweise das ERSTE, was man sieht: Dreizehn Kennzahlen sind eine
 *  Liste, kein Verlauf. Der Verlauf kommt darunter, eine nach der anderen.
 *
 *  Nicht jede Kennzahl steht in jedem Jahrgang (die Einwohnerzahl erst ab dem
 *  Bericht 2021, die Reinvestitionsquote erst ab 2022). Was fehlt, fehlt
 *  sichtbar. */
function Standtafel({
  daten, jahr, gewaehlt, aufWahl,
}: {
  daten: NonNullable<Daten["kennzahlen"]>;
  jahr: number;
  gewaehlt: string;
  aufWahl: (key: string) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {GRUPPEN.map((g, i) => (
        <section key={g.titel} className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {g.titel}
          </p>
          <p className="mt-1 max-w-[70ch] text-[13px] leading-relaxed text-muted-foreground">
            {g.frage}
            {/* Der Hinweis steht EINMAL, an der ersten Gruppe. Dreimal
                wiederholt las er sich wie eine Warnung. */}
            {i === 0 && (
              <span className="text-foreground/70"> Eine Zahl antippen zeigt
              ihren Verlauf.</span>
            )}
          </p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2 desk:grid-cols-3">
            {g.keys.map((key) => {
              const punkte = punkteVon(daten, key);
              const hier = punkte.find((p) => p.jahr === jahr) ?? null;
              const einheit = daten.einheit[key] ?? "eur";
              const aktiv = key === gewaehlt;
              return (
                <li key={key}>
                  <button
                    type="button"
                    onClick={() => aufWahl(key)}
                    aria-pressed={aktiv}
                    /* Eigener Name, weil der aus dem Inhalt gebaute keiner
                       wäre: Zahl und Beschriftung stehen in zwei Spans
                       untereinander und laufen ohne Trennung zusammen
                       („50,11 %Eigenkapitalquote I"). Hier steht der Satz, den
                       die Vorlesehilfe vorlesen soll — samt dem, was ein Tipp
                       bewirkt. */
                    aria-label={`${daten.label[key] ?? key}: ${
                      hier ? schreibe(einheit, hier.wert, hier.stellen)
                           : `für ${jahr} nicht ausgewiesen`
                    }${hier ? ` im Jahr ${jahr}` : ""} — Verlauf anzeigen`}
                    className={`flex w-full flex-col items-start gap-0.5 rounded-xl border px-3 py-2.5 text-left transition-colors ${
                      aktiv
                        ? "border-primary/40 bg-primary/[0.06]"
                        : "border-border bg-background hover:bg-muted/60"
                    }`}
                  >
                    <span className="font-display text-[19px] font-bold leading-none tracking-tight tabular-nums">
                      {hier
                        ? schreibe(einheit, hier.wert, hier.stellen)
                        : <span className="text-muted-foreground">—</span>}
                    </span>
                    <span className="text-[12px] leading-snug text-muted-foreground">
                      {daten.label[key] ?? key}
                    </span>
                    {!hier && (
                      <span className="text-[11px] leading-snug text-muted-foreground">
                        für {jahr} nicht ausgewiesen
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

/** Eine Kennzahl im Verlauf — mit dem Rechenweg, den die Stadt danebendruckt.
 *
 *  DIE FORMEL STEHT ALS ZITAT, nicht als unsere Erklärung. Sie ist der Grund,
 *  warum diese Seite eine Kennzahl überhaupt zeigen darf: Wir haben sie nicht
 *  erfunden, und wer sie nachprüfen will, findet den Satz im Dokument wieder.
 *
 *  Die Korrekturen stehen darunter — beim Verlauf und nicht nur im
 *  Sammelblock, weil sie genau diese Linie betreffen. */
function Verlauf({
  daten, gewaehlt,
}: {
  daten: NonNullable<Daten["kennzahlen"]>;
  gewaehlt: string;
}) {
  const einheit = daten.einheit[gewaehlt] ?? "eur";
  const label = daten.label[gewaehlt] ?? gewaehlt;
  const { reihe, anmerkung } = useMemo(() => reiheVon(daten, gewaehlt), [daten, gewaehlt]);
  const formel = formelVon(daten, gewaehlt);
  const korrekturen = korrekturenVon(daten, gewaehlt);
  const format = formatVon(einheit);
  if (!reihe.length) return null;

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <Zeitreihe
        reihe={reihe}
        einheit={einheitWort(einheit)}
        format={format}
        nachkomma={einheit === "anzahl" ? 0 : 2}
        titel={label}
        ariaTitel={`${label} im Verlauf, wie die Rechenschaftsberichte sie ausweisen`}
        vorjahresdifferenz
        differenzFormat={differenzFormatVon(einheit)}
        tabelle
        annotationen={anmerkung ? [anmerkung] : undefined}
      />

      {formel && (
        <div className="rounded-xl bg-muted/60 px-3 py-2.5">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            So rechnet die Stadt
          </p>
          <p className="mt-1 max-w-[80ch] text-[13px] leading-relaxed text-foreground/90">
            <span className="font-medium">{formel.ueberschrift}</span> — „Ermittlung:{" "}
            {formel.formel}“<Beleg q="kennzahlen" />
          </p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
            {formel.von_bericht === formel.bis_bericht
              ? `So gedruckt im Rechenschaftsbericht ${formel.von_bericht}.`
              : `So gedruckt in den Rechenschaftsberichten ${formel.von_bericht} `
                + `bis ${formel.bis_bericht}.`}
          </p>
        </div>
      )}

      {korrekturen.length > 0 && (
        <div className="border-t border-dashed border-border pt-3">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Später korrigiert
          </p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {korrekturen.map((k) => (
              <li key={`${k.jahr}-${k.neu_bericht}`}
                className="text-[12.5px] leading-relaxed text-muted-foreground">
                <span className="tabular-nums text-foreground">{k.jahr}</span>:{" "}
                {schreibe(einheit, k.alt)} im Bericht {k.alt_bericht}, dann{" "}
                {schreibe(einheit, k.neu)} im Bericht {k.neu_bericht}.
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/** Alle Korrekturen auf einen Blick — die eigentliche Nachricht.
 *
 *  Bewusst OHNE Vorwurf im Ton: Dass ein Abschluss nachträglich korrigiert
 *  wird, ist normal; dass es nirgends steht, ist der Punkt. Die Liste sagt,
 *  was sich geändert hat, und überlässt die Einordnung den Lesenden. */
function Korrekturen({ daten }: { daten: NonNullable<Daten["kennzahlen"]> }) {
  const alle = korrekturenVon(daten);
  if (!alle.length) return null;
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Zwischen zwei Berichten
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          {alle.length === 1
            ? "Eine Zahl wurde später still korrigiert"
            : `${alle.length} Zahlen wurden später still korrigiert`}
        </h2>
        <p className="mt-1.5 max-w-[74ch] text-[13px] leading-relaxed text-muted-foreground">
          Weil jeder Bericht fünf Jahre druckt, steht dasselbe Jahr in bis zu fünf
          Berichten. Meistens steht dort dieselbe Zahl. Hier nicht — und angesagt
          wurde es an keiner Stelle.<Beleg q="kennzahlen" />
        </p>
      </div>
      <ul className="flex flex-col divide-y divide-border">
        {alle.map((k) => {
          const einheit = daten.einheit[k.kennzahl] ?? "eur";
          return (
            <li key={`${k.kennzahl}-${k.jahr}-${k.neu_bericht}`}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2 first:pt-0 last:pb-0">
              <span className="min-w-0 flex-1 text-[13px] leading-snug text-foreground">
                {daten.label[k.kennzahl] ?? k.kennzahl}{" "}
                <span className="tabular-nums text-muted-foreground">{k.jahr}</span>
              </span>
              <span className="flex-none text-[13px] tabular-nums text-muted-foreground">
                {schreibe(einheit, k.alt)}
                <span className="px-1.5 text-muted-foreground">→</span>
                <span className="font-semibold text-foreground">
                  {schreibe(einheit, k.neu)}
                </span>
              </span>
              <span className="flex-none text-[11.5px] tabular-nums text-muted-foreground">
                Bericht {k.alt_bericht} → {k.neu_bericht}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default function KennzahlenSeite() {
  const { data } = useFetch<Daten>(haushaltUrl([...FELDER]));
  const [gewaehlt, setGewaehlt] = useState("eigenkapitalquote_1");

  const daten = data?.kennzahlen ?? null;
  const jahr = daten ? juengstesJahr(daten) : null;
  const jahre = useMemo(
    () => (daten ? [...new Set(daten.reihe.map((p) => p.jahr))].sort((a, b) => a - b) : []),
    [daten],
  );

  if (!daten || jahr == null || !daten.reihe.length) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="font-display text-2xl font-bold tracking-tight">Die dreizehn Zahlen</h1>
        <p className="max-w-[64ch] text-sm leading-relaxed text-muted-foreground">
          Für diese Seite ist noch kein Rechenschaftsbericht eingelesen.
        </p>
      </div>
    );
  }

  const korrekturen = korrekturenVon(daten);
  const berichte = [...new Set(daten.reihe.map((p) => p.bericht_jahr))];
  const quelleUrl = "https://buergerinfo.oldenburg.de";

  return (
    <Quellenkontext schluessel={[...QUELLEN]} jahr={jahr}>
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Stadtfinanzen Oldenburg · Schritt 10
            </p>
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Die dreizehn Zahlen
            </h1>
            <p className="mt-1.5 max-w-[66ch] text-sm leading-relaxed text-muted-foreground">
              Am Ende jedes Rechenschaftsberichts dampft die Stadt ihren ganzen
              Jahresabschluss auf dreizehn Kennzahlen ein — und druckt darunter,
              wie sie jede davon rechnet. {jahre[0]}–{jahre[jahre.length - 1]} aus{" "}
              {ZAHLWORT[berichte.length] ?? berichte.length} Berichten.
            </p>
          </div>
          <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
            className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
            <FileText className="h-3.5 w-3.5" /> Quelle öffnen
          </a>
        </div>

        {/* WARUM DIE FORMEL VORNE STEHT und nicht im Kleingedruckten: Sie ist
            der Unterschied zwischen einer zitierten und einer erfundenen
            Kennzahl. Ohne sie wäre jede Zahl auf dieser Seite eine Behauptung. */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Warum diese dreizehn
          </p>
          <p className="mt-1.5 max-w-[76ch] text-[13.5px] leading-relaxed text-foreground/90">
            Es sind nicht unsere Kennzahlen, sondern ihre: Die Stadt wählt sie aus,
            sie rechnet sie, und sie schreibt den Rechenweg daneben. Wir zeigen
            beides im Wortlaut. Drei der Quoten haben wir aus der Bilanz desselben
            Abschlusses nachgerechnet — sie stimmen auf die letzte gedruckte
            Nachkommastelle.<Beleg q="bilanz" />
          </p>
        </section>

        <Standtafel daten={daten} jahr={jahr} gewaehlt={gewaehlt} aufWahl={setGewaehlt} />

        <Verlauf daten={daten} gewaehlt={gewaehlt} />

        <Korrekturen daten={daten} />

        <LottiErklaert
          titel="Warum eine Kennzahl ohne ihren Rechenweg wenig wert ist"
          text={
            "Eine Quote ist immer ein Bruch: etwas geteilt durch etwas anderes. "
            + "Wer den Nenner ändert, ändert das Ergebnis, ohne dass sich in der "
            + "Stadt irgendetwas bewegt hätte. Genau das ist hier einmal passiert: "
            + "Bei der Personalintensität fielen die Versorgungsempfänger aus dem "
            + "Zähler, und die Quote sank für 2020 von 26,03 % auf 25,09 % — ohne "
            + "dass eine einzige Stelle gestrichen worden wäre. Deshalb steht auf "
            + "dieser Seite an jeder Reihe, wie die Stadt sie rechnet, und deshalb "
            + "läuft an dieser Stelle keine Linie durch."
          }
        />

        {korrekturen.length > 0 && (
          <p className="max-w-[78ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Angezeigt wird jeweils der Wert aus dem <strong>jüngsten</strong> Bericht,
            in dem das Jahr vorkommt. Die älteren Stände stehen weiter in unserer
            Datenbank — sie sind der Beleg dafür, dass es die Korrektur gab.
          </p>
        )}

        <Quellenverzeichnis schluessel={[...QUELLEN]} />
        <SchrittWeiter href="/haushalt/kennzahlen" />
      </div>
    </Quellenkontext>
  );
}
