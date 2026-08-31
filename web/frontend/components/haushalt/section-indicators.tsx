"use client";

// „Die dreizehn Zahlen" — der ZWEITE Abschnitt von /haushalt/pruefung.
//
// Bis zum 21.08.2026 die eigene Seite /haushalt/kennzahlen. Siehe den Kopf
// von `section-pruefung.tsx`.

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
} from "@/lib/haushalt-indicators";
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import { Beleg } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";

//: Kleine Zahlen schreibt der Bereich aus („aus sechs Berichten"), große als
//: Ziffern. Die Grenze liegt bei zwölf — darüber wird es zum Zungenbrecher.
const ZAHLWORT: Record<number, string> = {
  1: "einem", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs",
  7: "sieben", 8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwölf",
};

const FELDER = ["indicators"] as const;
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
  daten, year, gewaehlt, aufWahl,
}: {
  daten: NonNullable<Daten["indicators"]>;
  year: number;
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
            {g.question}
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
              const hier = punkte.find((p) => p.year === year) ?? null;
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
                           : `für ${year} nicht ausgewiesen`
                    }${hier ? ` im Jahr ${year}` : ""} — Verlauf anzeigen`}
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
                        für {year} nicht ausgewiesen
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
  daten: NonNullable<Daten["indicators"]>;
  gewaehlt: string;
}) {
  const einheit = daten.einheit[gewaehlt] ?? "eur";
  const label = daten.label[gewaehlt] ?? gewaehlt;
  const { series, anmerkung } = useMemo(() => reiheVon(daten, gewaehlt), [daten, gewaehlt]);
  const formula = formelVon(daten, gewaehlt);
  const korrekturen = korrekturenVon(daten, gewaehlt);
  const format = formatVon(einheit);
  if (!series.length) return null;

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <Zeitreihe
        series={series}
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

      {formula && (
        <div className="rounded-xl bg-muted/60 px-3 py-2.5">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            So rechnet die Stadt
          </p>
          <p className="mt-1 max-w-[80ch] text-[13px] leading-relaxed text-foreground/90">
            <span className="font-medium">{formula.heading}</span> — „Ermittlung:{" "}
            {formula.formula}“<Beleg q="indicators" />
          </p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
            {formula.von_bericht === formula.bis_bericht
              ? `So gedruckt im Rechenschaftsbericht ${formula.von_bericht}.`
              : `So gedruckt in den Rechenschaftsberichten ${formula.von_bericht} `
                + `bis ${formula.bis_bericht}.`}
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
              <li key={`${k.year}-${k.neu_bericht}`}
                className="text-[12.5px] leading-relaxed text-muted-foreground">
                <span className="tabular-nums text-foreground">{k.year}</span>:{" "}
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
function Korrekturen({ daten }: { daten: NonNullable<Daten["indicators"]> }) {
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
          wurde es an keiner Stelle.<Beleg q="indicators" />
        </p>
      </div>
      <ul className="flex flex-col divide-y divide-border">
        {alle.map((k) => {
          const einheit = daten.einheit[k.indicator] ?? "eur";
          return (
            <li key={`${k.indicator}-${k.year}-${k.neu_bericht}`}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2 first:pt-0 last:pb-0">
              <span className="min-w-0 flex-1 text-[13px] leading-snug text-foreground">
                {daten.label[k.indicator] ?? k.indicator}{" "}
                <span className="tabular-nums text-muted-foreground">{k.year}</span>
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

export function KennzahlenAbschnitt() {
  const { data } = useFetch<Daten>(haushaltUrl([...FELDER]));
  const [gewaehlt, setGewaehlt] = useState("eigenkapitalquote_1");

  const daten = data?.indicators ?? null;
  const year = daten ? juengstesJahr(daten) : null;
  const years = useMemo(
    () => (daten ? [...new Set(daten.series.map((p) => p.year))].sort((a, b) => a - b) : []),
    [daten],
  );

  if (!daten || year == null || !daten.series.length) {
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
  const n_reports = [...new Set(daten.series.map((p) => p.report_year))];
  const quelleUrl = "https://buergerinfo.oldenburg.de";

  return (
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <h2 className="font-display text-xl font-bold tracking-tight sm:text-[22px]">
              Die dreizehn Zahlen
            </h2>
            <p className="mt-1.5 max-w-[66ch] text-sm leading-relaxed text-muted-foreground">
              Am Ende jedes Rechenschaftsberichts fasst die Stadt ihren Jahresabschluss
              in dreizehn Kennzahlen zusammen. Zu jeder Kennzahl veröffentlicht sie auch
              den verwendeten Rechenweg. {years[0]}–{years[years.length - 1]} aus{" "}
              {ZAHLWORT[n_reports.length] ?? n_reports.length} Berichten.
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
            Die Stadt wählt diese Kennzahlen aus und veröffentlicht die jeweilige
            Berechnung. Wir geben Werte und Rechenwege im Wortlaut wieder. Drei Quoten
            haben wir anhand der Bilanz desselben Abschlusses geprüft; sie stimmen mit
            den veröffentlichten Nachkommastellen überein.<Beleg q="bilanz" />
          </p>
        </section>

        <Standtafel daten={daten} year={year} gewaehlt={gewaehlt} aufWahl={setGewaehlt} />

        <Verlauf daten={daten} gewaehlt={gewaehlt} />

        <Korrekturen daten={daten} />

        <LottiErklaert
          titel="Warum der Rechenweg zu jeder Kennzahl gehört"
          text={
            "Eine Quote setzt zwei Größen ins Verhältnis. Ändert sich ihre Definition, "
            + "kann sich die Quote verändern, obwohl die zugrunde liegende Situation gleich "
            + "bleibt. Bei der Personalintensität wurden Versorgungsempfänger später nicht "
            + "mehr mitgerechnet. Dadurch sank der Wert für 2020 von 26,03 % auf 25,09 %, "
            + "ohne dass dafür eine Stelle gestrichen wurde. Deshalb zeigen wir zu jeder "
            + "Reihe den Rechenweg und unterbrechen die Linie beim Definitionswechsel."
          }
        />

        {korrekturen.length > 0 && (
          <p className="max-w-[78ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Angezeigt wird jeweils der Wert aus dem <strong>jüngsten</strong> Bericht,
            in dem das Jahr vorkommt. Die älteren Stände stehen weiter in unserer
            Datenbank — sie sind der Beleg dafür, dass es die Korrektur gab.
          </p>
        )}

      </div>
  );
}
