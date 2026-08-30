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
// über die volle Kartenbreite (gemessen 1.102 px ≙ rund 173 Zeichen je Zeile,
// kursiv); aufgeklappt war das eine Wand von fast hundert Zeilen, in der das
// Auge beim Rücksprung die Zeile verliert. Jetzt hält jeder Wortlaut `76ch`
// = rund 93 Zeichen — dieselbe Breite, die der Beteiligungs-Steckbrief für
// fremden Fließtext führt. (Die beiden Zahlen standen hier bis 24.08.2026 als
// „129" und „76 Zeichen": Das waren ch, nicht Zeichen — s. DESIGNSPRACHE § 4.)
// Das ist KEINE Kürzung: Weder Text noch Reihenfolge noch die Vorschau-Regel
// ändern sich, nur die Spalte, in der sie stehen.
//
// KEIN „Stand der Daten“-Block. Der Baustein beschreibt, bis wann die neun
// FINANZschichten reichen — auf einer Seite ohne eine einzige Zahl daraus wäre
// das eine Angabe über fremde Daten. Die ehrliche Reichweite dieser Seite steht
// stattdessen am Jahrgangs-Umschalter: ab wann Protokolle im Bestand sind.
//
// DIE GRENZE DER SEITE hat sich am 26.08.2026 verschoben: Seit
// `council/aenderungslisten.py` die EHH-Listen liest, zeigt der Block „Was
// in den Listen stand" (streit-listeninhalt.tsx) die Positionen der
// Verwaltungslisten und der beschlossenen Änderungen — Zeile für Zeile,
// beim Einlesen gegen die eigene Schlusssumme bewiesen. Was FEHLT, sind
// weiterhin die Fraktionslisten selbst: Tischvorlagen, in keinem
// RIS-Dokument; digital belegt ist nur ihre Summenzeile in der
// Beschluss-Datei. Das steht im Block „Was hier fehlt", nicht im
// Kleingedruckten.

import { useEffect, useMemo, useState } from "react";
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
import { StreitListenInhalt } from "@/components/haushalt/streit-listeninhalt";
import { StreitFinanzhaushalt } from "@/components/haushalt/streit-finanzhaushalt";
import type { AenderungslistenDaten } from "@/lib/haushalt-aenderungslisten";
import { PunkteBilanz, PunkteZeile } from "@/components/grafik/punkte-bilanz";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { OutcomeBadge, OutcomeDot } from "@/components/decision-ui";
import { parteiDot } from "@/components/qa-bausteine";
import type { DecisionOutcome } from "@/lib/types";
import { Schlangenpfad } from "@/components/grafik/schlangenpfad";
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
 *  der Absatz die volle Kartenbreite: gemessen 1.102 px, rund 173 Zeichen je
 *  Zeile, kursiv. Aufgeklappt waren das knapp hundert Zeilen, bei denen das
 *  Auge den Zeilenanfang verliert. `76ch` — rund 93 Zeichen, s.
 *  DESIGNSPRACHE § 4 — ist die Breite, die der Beteiligungs-Steckbrief für
 *  denselben Fall führt (Fließtext aus einer fremden Quelle); dieselbe Regel,
 *  damit die Seiten eine Sprache sprechen.
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

/** Die Debatte auf dem Schlangenpfad (`components/grafik/schlangenpfad.tsx`,
 *  dort steht der Vertrag des Bausteins): Jede Rede ist eine opake Station,
 *  ihr `RednerPunkt` der Anker der Route, und `data-auftritt` lässt sie beim
 *  ersten Sichtkontakt erscheinen.
 *
 *  Die Liste bekommt an der Aufrufstelle ein `key` je Jahrgang: Die
 *  Beobachter des Bausteins binden sich beim Einhängen, ein Jahrgangswechsel
 *  muss den Pfad deshalb neu aufsetzen. */
function DebattenListe({ reden }: { reden: StreitWortbeitrag[] }) {
  return (
    <Schlangenpfad>
      <ol className="relative list-none">
        {reden.map((b, i) => <Rede key={i} b={b} rechts={i % 2 === 1} />)}
      </ol>
    </Schlangenpfad>
  );
}

function Rede({ b, rechts }: { b: StreitWortbeitrag; rechts: boolean }) {
  const [offen, setOffen] = useState(false);
  const { kopf, rest } = vorschau(b.text);

  return (
    <li data-auftritt className={cn(
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

export function StreitAbschnitt({ onBestand }: {
  /** Meldet den Bestand der Streit-Quelle nach oben — die Subline der
   *  Seitenbühne zählt dieselben Wortbeiträge wie die Quellenzeile dieses
   *  Abschnitts, aus derselben Antwort (H5-02). */
  onBestand?: (b: { beitraege: number; von: number; bis: number } | null) => void;
} = {}) {
  const gewaehltesJahr = Number(useSearchParams().get("jahr")) || null;
  const { data, loading } = useFetch<StreitDaten>("/council/haushalt/streit");

  useEffect(() => {
    if (!onBestand || loading) return;
    const q = data ? bestand(data) : null;
    onBestand(q && q.beitraege > 0
      ? { beitraege: q.beitraege, von: q.von, bis: q.bis } : null);
  }, [onBestand, loading, data]);
  // Die Inhalts-Ebene lädt getrennt: Die Streit-Antwort ist schon ein halbes
  // MB Protokolle, und die Listen braucht erst, wer bis zu ihrem Block liest.
  const { data: listen } = useFetch<AenderungslistenDaten>("/council/haushalt/aenderungslisten");

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
            Vor dem Haushaltsbeschluss bringen Fraktionen und Verwaltung Änderungen ein.
            Ausschüsse und Rat beraten darüber und stimmen über die Listen sowie den fertigen
            Haushalt ab. Diese Seite ordnet die dokumentierten Änderungen und Wortbeiträge
            nach Haushaltsjahr.
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
              Jeder Punkt steht für die Abstimmung über eine Änderungsliste; ein gefüllter
              Punkt kennzeichnet eine Mehrheit. Die Übersicht zeigt, wer Änderungen
              eingebracht hat. Soweit die Listen vorliegen, stehen ihre Positionen weiter
              unten. Bei den Fraktionslisten ist nur die Gesamtsumme dokumentiert. Eine
              Erfolgsquote wäre keine sinnvolle Bewertung politischer Arbeit.
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

        {/* Was in den Listen stand — die Inhalts-Ebene (Positionen und
            Fraktions-Summen), seit die Änderungslisten gelesen werden. */}
        <StreitListenInhalt daten={listen ?? null} jahr={jahr} />

        {/* Der zweite Teil desselben Haushalts. Er steht DANACH, weil
            der Ergebnishaushalt die größere Geschichte ist — dort geht
            es um den laufenden Betrieb der Stadt; hier um einzelne
            Bauvorhaben. Fehlt sein Ingest, verschwindet die Karte. */}
        <StreitFinanzhaushalt daten={listen ?? null} jahr={jahr} />

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
              Gezeigt werden alle Wortbeiträge des Haushaltspunkts in der Reihenfolge des
              Protokolls. Die Vorschau ist einheitlich gekürzt; jeder Beitrag lässt sich
              vollständig öffnen. Eine redaktionelle Auswahl einzelner Beiträge nehmen wir nicht vor.
            </p>
            <div className="mt-3 border-t border-dashed border-border pt-4">
              {/* `key` je Jahrgang: setzt Pfad und Beobachter des
                  Bausteins beim Jahrgangswechsel neu auf. */}
              <DebattenListe key={jahr ?? 0} reden={debatte.debatte} />
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
                Namensvettern, und das Protokoll nennt nur den Nachnamen. Deshalb ist keine
                eindeutige Zuordnung möglich. Die Sitzungsleitung zählt als Rolle, nicht als Fraktion.
              </p>
            ) : (
              <p className="mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
                Derzeit tragen alle {zuordnung.gesamt} Wortbeiträge eine eindeutige Zuordnung.
                Wo das nicht gelingt — etwa bei Namensvettern in der Anwesenheitsliste —,
                erscheint ein Beitrag ohne Fraktion. Eine eindeutige Zuordnung ist dann
                nicht möglich. Die Sitzungsleitung zählt als Rolle, nicht als Fraktion.
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
        <div className="@container rounded-2xl border border-border bg-card p-4 shadow-sm">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was hier fehlt
          </h2>
          {/* Zwei Spalten, sobald die Karte Platz hat (Designsprache §4) —
              füllt die Fläche und kürzt die Zeile zugleich. */}
          <ul className="mt-2 grid max-w-[70ch] list-disc grid-cols-1 gap-x-8 gap-y-1.5 pl-4 text-[12.5px] leading-relaxed text-muted-foreground @3xl:max-w-none @3xl:grid-cols-2">
            <li>
              <strong className="font-semibold text-foreground">Die Fraktionslisten selbst.</strong>{" "}
              Die Änderungslisten der Verwaltung und die beschlossenen Änderungen des
              Finanzausschusses liegen als Dokumente vor und stehen oben Position für Position.
              Die Listen der Fraktionen wurden dagegen als Tischvorlagen verteilt und liegen in
              keinem Dokument des Ratsinformationssystems — digital belegt ist nur ihre
              Summenzeile in der Beschluss-Datei, mit dem Urheber daneben.
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
              Wenn mehrere Ratsmitglieder denselben Nachnamen tragen und das Protokoll nur
              diesen nennt, bleibt die Fraktion offen. Eine eindeutige Zuordnung ist dann nicht möglich.
            </li>
          </ul>
        </div>

      </div>
  );
}
