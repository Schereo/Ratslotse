"use client";

// /haushalt/schulden — „Wie viel Schulden hat Oldenburg?"
//
// Eine der häufigsten Fragen an den Haushalt, und der Bereich konnte sie bis
// jetzt nicht beantworten. Die Antwort ist eine Zahl — aber sie ist nur dann
// eine Antwort, wenn danebensteht, WAS sie zählt.
//
// DIE ABGRENZUNG IST DER GANZE PUNKT. Bei Kommunalschulden gibt es zwei
// Werte, die beide „die Schulden der Stadt" heißen: die der Stadt als
// Rechtsträger (Kernhaushalt plus Eigenbetriebe — das hier) und die des
// Konzerns mit allen Beteiligungen. Sie unterscheiden sich um ein Vielfaches.
// Deshalb steht die Abgrenzung nicht im Kleingedruckten, sondern direkt an
// der großen Zahl, und deshalb kommt ihr Wortlaut aus dem Backend
// (`council/schulden.py`) statt aus dieser Datei: Zwei Formulierungen für
// dieselbe Grenze wären zwei Grenzen.
//
// KEINE DRAMATISIERUNG, und das ist hier keine Zurückhaltung, sondern
// Genauigkeit: Über dreißig Jahre sind die Schulden absolut gestiegen und je
// Einwohner*in gesunken — die Stadt ist in derselben Zeit stark gewachsen.
// Wer nur die absolute Kurve zeigt, verkauft Bevölkerungswachstum als
// Schuldenaufbau. Deshalb der Umschalter, und deshalb nennt der Fließtext
// beide Richtungen.
//
// KEINE BEWERTUNGSFARBEN (components/grafik/hantel.tsx). Kein Rot für
// „viel". Die beiden größten Sprünge der Reihe zeigen, warum: 2001 fiel die
// Schuld um 139 Mio., weil die Stadt die Stadtentwässerung abgab — kein
// Sparerfolg. 2010 sprang eine Spalte um 100 Mio., ohne dass sich die Summe
// bewegte — eine Umbuchung. Farbe kann das nicht unterscheiden, Text schon.
//
// DAS BILD IST DIE GEMEINSAME <Zeitreihe> (GB-01,
// components/grafik/zeitreihe.tsx) und keine seiten-eigene Kurve mehr. Was
// hier bleibt, sind die Entscheidungen, die diese Seite trifft:
//
//  * DIE SPRUNG-MARKEN rechnet die Grafik (`spruenge`), nicht diese Datei.
//    Eine Seite, die „2001 fiel es am stärksten" als Text trägt, wird mit dem
//    nächsten Jahrgang still falsch. Was HINTER den Sprüngen steckt, steht
//    darunter als belegter Satz — im Bild steht nur die gemessene Bewegung.
//  * DIE ZINSLINIE (H4-13) nur in der absoluten Ansicht: Einen Pro-Kopf-Zins
//    weist keine Quelle aus, und wir dividieren nicht selbst. Sie liegt auf
//    DERSELBEN Skala — dass sie fast auf der Nulllinie klebt, ist die
//    Aussage und kein Darstellungsfehler.
//  * ZWEI ANSICHTEN, weil sie über dreißig Jahre in verschiedene Richtungen
//    zeigen (s. o.). Der Umschalter steht bewusst außerhalb der Grafik: Er
//    wechselt die DATEN, nicht die Darstellung.

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { deMio, haushaltUrl, type HaushaltAuswahl,
  type HaushaltssatzungZeile } from "@/lib/haushalt";
import {
  Ansicht, BuergschaftsVorlage, Herkunft, SchuldenDaten, aufteilungen, deEuro,
  herkunftVon,
  juengsteZinslast, ohneAufteilung, punkte,
} from "@/lib/haushalt-schulden";
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import type { JahrPunkt } from "@/components/grafik/daten";
import { deZahl } from "@/components/grafik/format";
import {
  Beleg, Dokumentbeleg, Quellenkontext, Quellenverzeichnis,
} from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { BilanzBlock } from "@/components/haushalt/bilanz-block";

// `jahresabschluss` stand bis zum 21.08.2026 NICHT hier, obwohl die Seite
// einen Beleg-Chip darauf setzt. `Beleg` rendert dann bewusst nichts
// („lieber keinen Chip als eine falsche Nummer") — und der Satz endete
// mit einer Fußnote, die es nicht gab.
const QUELLEN = ["schulden", "bilanz", "haushaltssatzung",
                 "jahresabschluss"] as const;

/** Die Haushaltssatzung wird über den Bausteine-Endpunkt geholt und nicht über
 *  `/haushalt/schulden`: Sie gehört inhaltlich hierher (was die Stadt sich
 *  leihen DARF, neben dem, was sie schuldet), ist aber eine eigene Schicht mit
 *  eigener Herkunft. Ein zweiter Abruf ist ehrlicher als ein Endpunkt, der
 *  zwei Quellen zu einer Antwort verrührt. */
// `herkunft` mit — der Rahmen-Block zeigte seine drei Zahlen bis zum
// 21.08.2026 ganz ohne Beleg: Die Quelle stand im Verzeichnis am Seitenfuß,
// an den Zahlen selbst stand nichts.
const SATZUNG_FELDER = ["haushaltssatzung", "herkunft"] as const;

/** Wo eine Angabe im Dokument steht: welcher Abschnitt, welcher Stand. Das
 *  Quellenverzeichnis am Seitenende beschreibt die Quelle der ganzen Seite;
 *  das hier gehört an die einzelne Zahl und ist der Grund, warum man sie in
 *  einem mehrseitigen PDF wiederfindet.
 *
 *  BEWUSST OHNE UNSERE PROBEN. Die erste Fassung dieser Seite zeigte hier die
 *  Sätze aus `herkunft.PROBEN` und darunter „Gemessen: Summenprobe 30 von
 *  31". Das sagt etwas über uns und nichts über die Schulden der Stadt —
 *  Selbstvergewisserung (DESIGNSPRACHE.md § 7), und `konzern/page.tsx` hat
 *  denselben Block am 16.08. aus demselben Grund verloren. Die Proben laufen
 *  unverändert weiter, die API liefert sie weiter, Tests halten sie fest und
 *  die Technik-Doku beschreibt sie. Nur die Zurschaustellung ist weg.
 *
 *  Was **inhaltlich** aus einer gerissenen Probe folgt, bleibt selbstver-
 *  ständlich stehen: dass für 2022 die Aufteilung fehlt, steht als Satz an
 *  der Aufteilung — das ist eine Grenze der Zahlen und keine Auskunft über
 *  unsere Sorgfalt.
 *
 *  Bewusst dieselbe Bauart wie in `konzern/page.tsx` und `vergleich/page.tsx`
 *  und bewusst nicht geteilt — die drei Seiten sollen einander nicht brechen. */
function Fundstelle({ h }: { h: Herkunft | null }) {
  // Ohne Fundstelle nichts — sonst bliebe eine Überschrift ohne Inhalt stehen.
  if (!h?.citation) return null;
  return (
    <div className="border-t border-dashed border-border pt-2.5">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Zahlen kommen
      </p>
      <p className="mt-1 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        {h.citation}{h.stand ? ` · ${h.stand}` : ""}
      </p>
    </div>
  );
}

/** Wofür die Stadt geradesteht — Bürgschaften neben den eigenen Schulden.
 *
 *  DREI ZAHLEN, DIE NUR ZUSAMMEN STIMMEN. Das Volumen allein liest sich wie
 *  eine Rechnung, die demnächst kommt; die Rückstellung allein wie das ganze
 *  Risiko. Deshalb stehen Bestand, eigene Geldschulden und die Rückstellung
 *  für den erwarteten Ausfall in einer Zeile.
 *
 *  KEINE BEWERTUNGSFARBE. Dass der Bestand sich verdreifacht hat, ist weder
 *  gut noch schlecht — es sind Bürgschaften für die eigenen Gesellschaften,
 *  ohne die deren Kredite teurer würden. Die Kurve steigt, der Satz daneben
 *  sagt warum, das Urteil bleibt bei den Lesenden.
 *
 *  Rendert nichts, solange kein Jahresabschluss eingelesen ist. */
/** Wörter, an denen eine Vorlage sich selbst als Fortschreibung ausweist.
 *
 *  Sie sind der BELEG für den Satz „nicht selbst addierbar" — und stehen
 *  deshalb hier und nicht im Fließtext: „Verlängerung Ausfallbürgschaft über
 *  300.000 Euro für die Volkshochschule" (25/0826) ist dieselbe Bürgschaft
 *  wie 23/0112 zwei Jahre zuvor. Wer beide addiert, zählt 600.000 € für eine
 *  Zusage über 300.000 €. */
const FORTSCHREIBUNG = /verlängerung|anpassung|erhöhung|verlängert|ablösung/i;

/** Der Zeitstrahl der Ratsbeschlüsse zum Bürgschaftsbestand.
 *
 *  KEINE SUMME, UND KEINE BALKEN. Die Versuchung wäre ein Diagramm mit
 *  Beträgen je Beschluss — es wäre falsch: Die Vorlagen schreiben einander
 *  fort, und eine Fläche darüber addierte, was sich ersetzt. Was bleibt, ist
 *  die Chronologie: wann der Rat worüber entschieden hat, mit dem Weg zur
 *  Beschluss-Seite.
 *
 *  Rendert nichts, solange keine Vorlage verknüpft ist. */
function BeschlussStrahl({ vorlagen }: { vorlagen: BuergschaftsVorlage[] }) {
  const [offen, setOffen] = useState(false);
  if (!vorlagen.length) return null;
  const gezeigt = offen ? vorlagen : vorlagen.slice(0, 5);
  const fortschreibungen = vorlagen.filter((v) => FORTSCHREIBUNG.test(v.title)).length;

  return (
    <div className="border-t border-dashed border-border pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was der Rat dazu beschlossen hat
        </p>
        <p className="font-mono text-[9.5px] uppercase tracking-[0.11em] text-muted-foreground">
          {vorlagen.length} Vorlagen
          {fortschreibungen > 0 && ` · ${fortschreibungen} davon Fortschreibungen`}
        </p>
      </div>
      <ol className="mt-2 flex flex-col">
        {gezeigt.map((v) => {
          const fort = FORTSCHREIBUNG.test(v.title);
          return (
            <li key={v.template_number}
              className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 border-l-2 border-border py-1.5 pl-3">
              <span className="flex-none font-mono text-[10.5px] tabular-nums text-muted-foreground">
                {v.datum ? v.datum.slice(0, 7).split("-").reverse().join("/") : "—"}
              </span>
              <span className="min-w-0 flex-1 text-[12.5px] leading-snug text-foreground/90">
                {v.decision_id ? (
                  <Link href={`/council/decision?id=${v.decision_id}`}
                    className="hover:text-primary">{v.title}</Link>
                ) : v.title}
              </span>
              {fort && (
                <span className="flex-none rounded border border-dashed border-border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
                  schreibt fort
                </span>
              )}
            </li>
          );
        })}
      </ol>
      {vorlagen.length > 5 && (
        <button type="button" onClick={() => setOffen(!offen)}
          className="mt-1.5 text-[12px] font-semibold text-primary">
          {offen ? "Weniger zeigen" : `Alle ${vorlagen.length} Vorlagen zeigen`}
        </button>
      )}
      <p className="mt-2 max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Bewusst ohne Beträge und ohne Summe: Diese Beschlüsse schreiben einander
        fort, statt sich zu addieren. Der Bestand oben ist der Stichtagswert aus
        dem Jahresabschluss — nicht die Summe dieser Liste.
      </p>
    </div>
  );
}

function BuergschaftsBlock({ daten }: { daten: SchuldenDaten | null }) {
  const b = daten?.buergschaften;
  const series = b?.series ?? [];
  if (!series.length) return null;

  const geld = new Map((b?.geldschulden ?? []).map((z) => [z.year, z.wert]));
  const rueck = new Map((b?.rueckstellung ?? []).map((z) => [z.year, z.wert]));
  const letzter = series[series.length - 1];
  const erster = series[0];
  const gsErst = geld.get(erster.year) ?? null;
  const gsLetzt = geld.get(letzter.year) ?? null;
  const rsLetzt = rueck.get(letzter.year) ?? null;
  // Der Jahrgang, der den Sprung erklärt — der mit der genannten Einzelzahl.
  const sprung = series.find((z) => z.single_amount != null) ?? null;
  // Der Jahrgang ohne eigene Fundstelle: Seine Zahl steht nur als
  // Anfangsbestand im Abschluss des Folgejahres.
  const nachgetragen = series.find((z) => z.out_next_year) ?? null;

  // BEIDE REIHEN IN EINER ZEICHENFLÄCHE. Die Aussage dieses Blocks ist kein
  // Stichtag, sondern eine Bewegung: Was die Stadt selbst schuldet, sinkt —
  // wofür sie geradesteht, steigt. Nebeneinander gezeichnet sieht man das;
  // untereinander gelistet (so stand es bis 08/2026 hier) muss man es rechnen.
  const verbuergt: JahrPunkt[] = series.map((z) => ({ year: z.year, wert: z.bestand / 1e6 }));
  const eigene: JahrPunkt[] = series.map((z) => {
    const w = geld.get(z.year);
    return w == null
      ? { year: z.year, fehlt: "für dieses Jahr liegt keine geparste Bilanz vor" }
      : { year: z.year, wert: w / 1e6 };
  });

  // DIE SCHERE WIRD GEMESSEN, NICHT BEHAUPTET. Der Kernsatz stimmt nur,
  // solange die eigenen Schulden wirklich fallen UND der Bestand wirklich
  // steigt. Kippt eine der beiden Richtungen, fällt der Satz weg statt falsch
  // zu werden — eine Überschrift, die ihre Daten überlebt hat, wäre der
  // schlimmere Fehler als gar keine.
  const schere =
    series.length > 1 && gsErst != null && gsLetzt != null
    && gsLetzt < gsErst && letzter.bestand > erster.bestand
      ? { rueckgang: (1 - gsLetzt / gsErst) * 100, faktor: letzter.bestand / erster.bestand }
      : null;

  // Die beiden Stellen, an denen die Quelle selbst etwas erklärt. Der Text
  // steht unter der Grafik (Kein-Tooltip-Regel, GB-01), die Marke im Bild.
  // JEDE Marke trägt eine Kurzform: Breit steht sie direkt an der Marke —
  // ein nacktes ⓘ sagt dort nur, DASS etwas war, nicht was (Tims Befund
  // 18.08.). `sprung` hat immer eine Einzelzahl — so ist er definiert (s. o.).
  const annotationen = [
    sprung?.grund
      ? {
          year: sprung.year,
          kurz: `${deMio((sprung.single_amount ?? 0) / 1e6)} Mio. €`,
          text: `${sprung.year}: ${sprung.grund}`,
        }
      : null,
    nachgetragen
      ? {
          year: nachgetragen.year,
          kurz: `aus dem Abschluss ${nachgetragen.year + 1}`,
          text: `Für ${nachgetragen.year} nennt der Jahresabschluss selbst keinen `
            + `Bestand; die Zahl steht als Anfangsbestand im Abschluss `
            + `${nachgetragen.year + 1}.`,
        }
      : null,
  ].filter((a): a is { year: number; kurz: string; text: string } => a !== null);

  // Wie genau die Quelle je Jahrgang ist. Das gehört an die Zahlen und nicht
  // in eine Fußnote am Seitenende — die Reihe mischt zwei Darreichungsformen.
  const cent = series.filter((z) => z.exact).map((z) => z.year);
  const gerundet = series.filter((z) => !z.exact && !z.out_next_year).map((z) => z.year);

  return (
    <section className="flex flex-col gap-3.5 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Wofür die Stadt außerdem geradesteht
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          {schere
            ? "Eigene Geldschulden sinken, Bürgschaften steigen"
            : <>Bürgschaften: {deMio(letzter.bestand / 1e6)}&#8239;Mio.&nbsp;€</>}
        </h2>
        {schere && gsLetzt != null ? (
          <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Seit {erster.year} hat die Stadt ihre eigenen Geldschulden um{" "}
            {deZahl(schere.rueckgang, 0)}&nbsp;% abgebaut — auf{" "}
            {deMio(gsLetzt / 1e6)}&#8239;Mio.&nbsp;€. Im selben Zeitraum ist das
            Volumen, für das sie bürgt, auf das {deZahl(schere.faktor, 1)}-Fache
            gestiegen: {deMio(letzter.bestand / 1e6)}&#8239;Mio.&nbsp;€. Beide
            Zahlen stehen in denselben Jahresabschlüssen.<Beleg q="bilanz" />
          </p>
        ) : null}
        <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
          {b?.abgrenzung}
        </p>
      </div>

      {/* Die Schere als Bild: der Bestand als Reihe, die eigenen Schulden als
          dünne zweite Linie IN derselben Fläche (GB-01). Zwei getrennte
          Grafiken nebeneinander hätten zwei Maßstäbe — und damit genau den
          Vergleich zerstört, um den es hier geht. */}
      <Zeitreihe
        series={verbuergt}
        zweitreihe={{ label: "eigene Geldschulden", series: eigene }}
        einheit="Mio. €"
        titel="Verbürgt und selbst geschuldet"
        ariaTitel={`Bürgschaftsbestand und eigene Geldschulden der Stadt Oldenburg, `
          + `${erster.year} bis ${letzter.year}, in Millionen Euro`}
        annotationen={annotationen}
        vorjahresdifferenz
        tabelle
      />

      {cent.length > 0 || gerundet.length > 0 ? (
        <p className="max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Wie genau die Quelle ist.</strong>{" "}
          {cent.length > 0 ? (
            <>Für {cent.join(" und ")} nennt der Jahresabschluss den Betrag auf
              den Cent{gerundet.length > 0 ? ", " : ". "}</>
          ) : null}
          {gerundet.length > 0 ? (
            <>ab {gerundet[0]} nur noch auf Zehntel-Millionen gerundet („rd.").{" "}
            </>
          ) : null}
          Die Reihe enthält daher unterschiedlich stark gerundete Werte aus derselben Quelle.
        </p>
      ) : null}

      {rsLetzt ? (
        <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Womit die Stadt rechnet:</strong>{" "}
          Für erwartete Ausfälle stehen {deEuro(rsLetzt)}&nbsp;€ in der Bilanz
          ({letzter.year})<Beleg q="bilanz" /> — {((rsLetzt / letzter.bestand) * 100).toFixed(2).replace(".", ",")}&nbsp;%
          des verbürgten Volumens. Die {deMio(letzter.bestand / 1e6)}&#8239;Mio.&nbsp;€ sind
          also nicht das, was die Stadt zu zahlen erwartet, sondern das, wofür sie
          im äußersten Fall einsteht.
        </p>
      ) : null}

      <p className="max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
        <strong className="text-foreground">Ein Bestand, keine Summe der Beschlüsse.</strong>{" "}
        Die einzelnen Bürgschaftsbeschlüsse lassen sich nicht addieren, weil Verlängerungen
        frühere Beschlüsse ersetzen können. Gezeigt wird der von der Stadt ausgewiesene Bestand —
        {erster.year === letzter.year ? " ein Stichtag." : ` ${series.length} Stichtage.`}
      </p>

      <BeschlussStrahl vorlagen={b?.vorlagen ?? []} />

      <Fundstelle h={herkunftVon(daten, letzter.herkunft_id)} />
    </section>
  );
}

/** Die dritte Schuldenzahl — und warum alle drei stimmen.
 *
 *  DIE STAFFEL IST DIE AUSSAGE. 43,7 → 294,9 → 740,3 Mio. €: Wer eine dieser
 *  Zahlen allein hört, hält die anderen für falsch. Nebeneinander erklärt sich
 *  jede durch das, was sie mitzählt.
 *
 *  ZWEI SÄTZE SIND PFLICHT und kommen aus dem Backend, nicht von hier: dass
 *  der größte Teil aus Beteiligungen unter 50 % stammt (für die die Stadt
 *  nicht haftet), und dass daraus keine Zeitreihe werden darf. Stünden sie im
 *  Frontend, könnten sie hier vergessen werden, während die Zahl bleibt.
 *
 *  Rendert nichts ohne eingelesenen Tabellenband. */
function DritteZahlBlock({ daten }: { daten: SchuldenDaten | null }) {
  const i = daten?.integrierte_schulden;
  if (!i?.as_of_date) return null;
  const s = i.as_of_date;
  const series = daten?.series ?? [];
  // Der Rechtsträger-Wert desselben Stichtags — die mittlere der drei Zahlen.
  const entity = series.find((z) => z.year === s.year)?.insgesamt ?? null;

  const stufen = [
    { titel: "Kernhaushalt", wert: s.core_budget,
      was: "Investitionskredite der Stadtverwaltung selbst" },
    { titel: "Stadt als Rechtsträger", wert: entity,
      was: "dazu die Eigenbetriebe — die Zahl oben auf dieser Seite" },
    { titel: "Der ganze Konzern", wert: s.insgesamt,
      was: "dazu Extrahaushalte und Beteiligungen, anteilig nach Beteiligungshöhe" },
  ].filter((x) => x.wert != null);

  return (
    <section className="flex flex-col gap-3.5 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Warum man drei Zahlen hört
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          {/* Gerechnet, nicht geschrieben — hier stand „43,7" als Text und
              wäre beim nächsten Tabellenband still falsch geworden. */}
          {s.core_budget != null ? `${deMio(s.core_budget / 1e6)} · ` : ""}
          {entity ? `${deMio(entity / 1e6)} · ` : ""}
          {deMio(s.insgesamt / 1e6)}&#8239;Mio.&nbsp;€ — drei unterschiedliche Abgrenzungen
        </h2>
        <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
          Die Beträge unterscheiden sich danach, welche Einheiten einbezogen werden.
          Stand 31.12.{s.year}:
        </p>
      </div>

      <ol className="flex flex-col gap-2">
        {stufen.map((x) => (
          <li key={x.titel}
            className="flex flex-col gap-0.5 rounded-xl border border-border bg-background/40 p-3">
            <span className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="text-[13px] font-semibold text-foreground">{x.titel}</span>
              <span className="font-semibold tabular-nums text-foreground">
                {deMio((x.wert as number) / 1e6)}&#8239;Mio.&nbsp;€
              </span>
            </span>
            <span className="text-[12px] leading-relaxed text-muted-foreground">{x.was}</span>
          </li>
        ))}
      </ol>

      {/* Der Satz, ohne den die 740 Millionen falsch gelesen werden. Er steht
          im Fließtext und nicht im Kleingedruckten — er ist die Aussage. */}
      <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-foreground/90">
        {i.abgrenzung}
        {i.anteil_unter_50 != null ? (
          <>
            {" "}Konkret sind das{" "}
            <strong className="text-foreground">
              {(i.anteil_unter_50 * 100).toFixed(0)}&nbsp;%
            </strong>{" "}
            der Summe.
          </>
        ) : null}
      </p>

      <p className="max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
        {/* Ohne eigenen Vorspann: Der Satz aus dem Backend beginnt selbst mit
            „Nur ein Stichtag" — ein Label davor sagte dasselbe zweimal. */}
        {i.keine_reihe}
      </p>

      <Fundstelle h={herkunftVon(daten, s.herkunft_id)} />
    </section>
  );
}

/** Was der Rahmen erlaubt — aus der Haushaltssatzung (§§ 2–4).
 *
 *  Diese Seite zeigt, was die Stadt SCHULDET. Die Satzung sagt, was sie
 *  DÜRFTE, und beides nebeneinander beantwortet erst die Frage, die Leute
 *  wirklich haben. Der interessanteste Wert ist dabei der, den man nicht
 *  erwartet: Die Kreditermächtigung steht in jedem gelesenen Jahrgang auf
 *  null.
 *
 *  DER ENTWURFS-HINWEIS IST PFLICHT, nicht Zierde. Im Ratsinformationssystem
 *  liegen ausschließlich Verwaltungsentwürfe; die beschlossene Satzung
 *  erscheint im Amtsblatt. Ohne den Satz behaupteten diese Zahlen einen
 *  Ratsbeschluss, den wir nicht belegt haben. */
function RahmenBlock({ zeile, herkunft }: {
  zeile: HaushaltssatzungZeile; herkunft: Herkunft | null;
}) {
  const posten: { label: string; wert: number | null; erklaerung: string }[] = [
    {
      label: "Kredite für Investitionen",
      wert: zeile.investment_loans,
      erklaerung: "Wie viel die Stadt sich im Haushaltsjahr für Investitionen "
        + "leihen darf (§ 2).",
    },
    {
      label: "Höchstbetrag für Liquiditätskredite",
      wert: zeile.liquidity_loans,
      erklaerung: "Bis zu diesem Höchstbetrag darf die Stadt kurzfristige Kredite "
        + "aufnehmen, um ihre Zahlungsfähigkeit zu sichern (§ 4). Der Betrag ist eine "
        + "Ermächtigung und nicht der tatsächlich genutzte Kredit.",
    },
    {
      label: "Verpflichtungsermächtigungen",
      wert: zeile.commitment_authorizations,
      erklaerung: "Was die Stadt in diesem Jahr bestellen darf, obwohl die "
        + "Rechnung erst in kommenden Jahren kommt (§ 3).",
    },
  ];

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-[17px] font-bold tracking-tight">
          Was der Rahmen erlaubt<Beleg q="haushaltssatzung" />
        </h2>
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          Satzung {zeile.year}
        </span>
      </div>
      <p className="mt-1.5 max-w-[64ch] text-[13px] leading-relaxed text-foreground/85">
        Oben steht, was die Stadt schuldet. Die Haushaltssatzung sagt, was sie
        im laufenden Jahr überhaupt aufnehmen dürfte.
      </p>

      {/* Steht VOR den Zahlen, nicht als Fußnote darunter: Wer sie erst liest
          und dann erfährt, dass sie nicht beschlossen sind, hat sie schon
          geglaubt (dieselbe Regel wie der Summen-Kasten auf /haushalt/betriebe). */}
      {zeile.fassung !== "beschlossen" && (
        <p className="mt-3 rounded-xl border border-signal/40 bg-signal/5 px-3 py-2
                      text-[12.5px] leading-relaxed text-foreground/85">
          <strong>Entwurf der Verwaltung, kein Ratsbeschluss.</strong> Im
          Ratsinformationssystem steht nur der Verwaltungsentwurf; die
          beschlossene Satzung erscheint im Amtsblatt. Was der Rat daraus
          gemacht hat, steht unter{" "}
          <Link href="/haushalt/mitreden#streit" className="font-semibold text-primary">
            Der Streit ums Geld
          </Link>.
        </p>
      )}

      <dl className="mt-3 flex flex-col gap-2.5">
        {posten.map((p) => (
          <div key={p.label} className="border-t border-border pt-2.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
              <dt className="text-[13px] font-semibold">{p.label}</dt>
              <dd className="font-display text-[15px] font-bold tabular-nums">
                {p.wert == null
                  ? <span className="font-normal text-muted-foreground"
                          title="Die Satzung sagt dazu nichts.">—</span>
                  : p.wert === 0
                    // NICHT „0 €". Die Satzung schreibt einen Satz, keine
                    // Ziffer, und der Satz ist die genauere Auskunft.
                    ? <span className="text-[13px]">nicht veranschlagt</span>
                    : <>{deMio(p.wert / 1e6)}&#8239;Mio.&nbsp;€</>}
              </dd>
            </div>
            <p className="mt-0.5 max-w-[62ch] text-[12px] leading-relaxed text-muted-foreground">
              {p.erklaerung}
            </p>
          </div>
        ))}
      </dl>
      <Dokumentbeleg h={herkunft} vorlageNr={zeile.template_number}
        className="mt-3 border-t border-dashed border-border pt-2.5" />
    </section>
  );
}


export default function SchuldenPage() {
  const { data, loading } = useFetch<SchuldenDaten>("/council/haushalt/schulden");
  const { data: satzungDaten } = useFetch<
    HaushaltAuswahl<typeof SATZUNG_FELDER[number]>>(haushaltUrl(SATZUNG_FELDER));
  const [ansicht, setAnsicht] = useState<Ansicht>("insgesamt");

  // Der jüngste Jahrgang — die Satzung, die gerade gilt bzw. vorgeschlagen
  // ist. Sortiert wird hier und nicht im Vertrauen auf die API.
  const satzung = useMemo(() => {
    const zeilen = (satzungDaten?.haushaltssatzung ?? [])
      .filter((z) => z.supplement === 0);
    return zeilen.length
      ? zeilen.reduce((a, b) => (b.year > a.year ? b : a))
      : null;
  }, [satzungDaten]);

  const series = data?.series ?? [];
  const kurve = useMemo(() => punkte(series, ansicht), [series, ansicht]);
  const teilung = useMemo(() => aufteilungen(series), [series]);
  const luecken = useMemo(() => ohneAufteilung(series), [series]);
  // Die Zinslinie in der Kurve (H4-13) — nur in der absoluten Ansicht: Die
  // Quelle weist keinen Pro-Kopf-Zins aus, und wir dividieren nicht selbst.
  const zinsreihe = useMemo(
    () => (ansicht === "insgesamt"
      ? (data?.zinslast ?? []).map((z) => ({ year: z.year, wert: z.expense / 1e6 }))
      : undefined),
    [data, ansicht]);

  if (loading) {
    return <div className="py-16 text-center text-sm text-muted-foreground">
      Schuldenzahlen werden geladen …
    </div>;
  }
  // Ohne eingelesene Zeitreihe gibt es diese Seite nicht — lieber ein
  // ehrlicher Hinweis als eine Seite voller Striche.
  if (!data || series.length < 2) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm leading-relaxed text-muted-foreground">
        Für diese Seite ist die Schuldenzeitreihe noch nicht eingelesen.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zurück zum Haushalt</Link>
      </div>
    );
  }

  const letzter = series[series.length - 1];
  const erster = series[0];
  const hLetzter = herkunftVon(data, letzter.herkunft_id);
  const quelleUrl = hLetzter?.url ?? null;

  // Die Richtungen über die ganze Reihe — gerechnet, nicht geschrieben: Eine
  // Seite, die „gestiegen" als Text trägt, wird mit dem nächsten Jahrgang
  // still falsch.
  const deltaAbs = letzter.insgesamt - erster.insgesamt;
  const proKopfDa = letzter.per_capita != null && erster.per_capita != null;
  const deltaKopf = proKopfDa ? letzter.per_capita! - erster.per_capita! : null;
  const gegenlaeufig = deltaKopf != null && Math.sign(deltaAbs) !== Math.sign(deltaKopf);

  // Der jüngste Jahrgang mit belegter Aufteilung — die Aufteilung ist nicht
  // für jedes Jahr gedeckt, und der Kopf soll dann nicht leer bleiben.
  const jTeilung = teilung.at(-1) ?? null;

  return (
    <Quellenkontext schluessel={[...QUELLEN]} year={letzter.year}>
      <div className="flex flex-col gap-4">
        {/* items-start statt items-end (24.08.): Rechts steht jetzt das
            Schritt-Zeichen über dem Quelle-Knopf — die Spalte ist so hoch wie
            der Text, eine Unterkanten-Ausrichtung hätte nichts mehr zu tun. */}
        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/schulden" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Wie viel Schulden hat Oldenburg?
            </h1>
          </div>
          <div className="flex flex-none flex-col items-end gap-2.5">
            <SchrittPfad href="/haushalt/schulden" />
            {quelleUrl && (
              <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
                className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
                <FileText className="h-3.5 w-3.5" /> Quelle öffnen
              </a>
            )}
          </div>
        </div>

        {/* Die Bühne (H5-02/H5-06/H5-09): die Staffel der drei
            Schuldenbegriffe als Treppe. Die Sequenz trägt die Aussage —
            eng → weiter → ganz —, deshalb zählen die drei Zahlen der Subline
            nacheinander (H5-07: 3 × 350 ms, Versatz 150 ms). Das Minibild ist
            die Treppe, maßstäblich zu den Zahlen, und klickt zum Block
            „Warum man drei Zahlen hört". Ohne Tabellenband keine Bühne. */}
        {(() => {
          const st = data?.integrierte_schulden?.as_of_date;
          if (!st) return null;
          const entity = (data?.series ?? []).find((z) => z.year === st.year)?.insgesamt ?? null;
          const stufen = [
            { titel: "Kernhaushalt", wert: st.core_budget },
            { titel: "Stadt als Rechtsträger", wert: entity },
            { titel: "der ganze Konzern", wert: st.insgesamt },
          ].filter((x): x is { titel: string; wert: number } => x.wert != null);
          if (stufen.length < 2) return null;
          const max = Math.max(...stufen.map((x) => x.wert));
          const toene = ["var(--sb-voll)", "var(--sb-mittel)", "var(--sb-blass)"];
          return (
            <Seitenbuehne
              kicker={`Drei Zählweisen, eine Stadt · Stand 31.12.${st.year}`}
              zahl={<><ZaehlZahl wert={st.insgesamt / 1e6} nachkomma={1} />&#8239;Mio.&nbsp;€
                im weitesten Begriff</>}
              sub={<>
                {stufen.map((x, i) => (
                  <span key={x.titel}>
                    {i > 0 && " · "}
                    {x.titel}{" "}
                    <ZaehlZahl wert={x.wert / 1e6} nachkomma={1} dauerMs={350}
                      verzoegerungMs={i * 150} className="font-semibold" />
                  </span>
                ))}
                {" "}Mio.&nbsp;€
              </>}
              minibild={{
                href: "#drei-zahlen",
                label: "Treppe der Schuldenbegriffe — jede Stufe zählt die vorige mit, klickt zur Erklärung",
                skizze: (
                  <span className="flex items-end gap-1.5" style={{ height: 64 }}>
                    {stufen.map((x, i) => (
                      <span key={x.titel} className="flex-1 rounded-t-[6px] rounded-b-[3px]"
                        style={{
                          height: `${Math.max((x.wert / max) * 100, 6)}%`,
                          background: toene[stufen.length - 1 - i] ?? toene[2],
                        }} />
                    ))}
                  </span>
                ),
              }}
            />
          );
        })()}

        {/* Einstiegstext unter der Bühne, kleiner (Tim, 26.08.). */}
        <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">
          Ende {letzter.year} waren es {deMio(letzter.insgesamt / 1e6)}&#8239;Mio.&nbsp;€.
          Was diese Zahl zählt und was nicht, steht direkt darunter — bei Schulden
          ist das der Unterschied zwischen zwei Antworten.
        </p>

        {/* Der Kopf: zwei Zahlen und die Abgrenzung. Mehr nicht — die
            Abgrenzung ist hier so wichtig wie die Beträge und steht deshalb
            in derselben Karte, nicht in einer Fußnote weiter unten. */}
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Stand 31.12.{letzter.year}
          </p>
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                {deMio(letzter.insgesamt / 1e6)}&#8239;Mio.&nbsp;€
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                insgesamt<Beleg q="schulden" />
              </p>
            </div>
            {letzter.per_capita != null && (
              <div>
                <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                  {deEuro(letzter.per_capita)}&nbsp;€
                </p>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  je Einwohner*in<Beleg q="schulden" />
                </p>
              </div>
            )}
          </div>
          {/* Der Wortlaut kommt aus dem Backend — s. Kopfkommentar. */}
          <p className="max-w-[76ch] rounded-xl bg-muted/60 px-3 py-2.5 text-[13px] leading-relaxed text-foreground/90">
            <strong>Gezählt wird:</strong> {data.abgrenzung}
          </p>
          {letzter.revised === 1 && (
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              Die Stadt hat die Werte für {letzter.year} nachträglich korrigiert; hier steht
              der korrigierte Stand.
            </p>
          )}
          <Fundstelle h={hLetzter} />
        </section>

        {/* WAS DER BESTAND IM JAHR KOSTET.
            Der Schuldenstand allein sagt wenig — 337 Mio. € sind eine Zahl ohne
            Erfahrungswert. Die Zinslast übersetzt sie in etwas, das jedes Jahr
            im Haushalt steht und mit allem anderen konkurriert.

            Sie kommt aus einer ANDEREN Quelle als der Bestand darüber: Der
            Stand steht im Statistischen Jahrbuch, die Zinsen im geprüften
            Jahresabschluss. Deshalb ein eigener Beleg und ein eigenes Jahr —
            die Abschlüsse enden früher als die Zeitreihe, und beide am selben
            Jahr aufzuhängen hieße, für die Zinsen dauerhaft nichts zu zeigen. */}
        {(() => {
          const zins = juengsteZinslast(data);
          if (!zins) return null;
          const hZins = herkunftVon(data, zins.herkunft_id);
          return (
            <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Was der Schuldenstand im Jahr kostet
              </p>
              <p className="mt-2 font-display text-[26px] font-extrabold leading-none tracking-tight text-foreground">
                {deMio(zins.expense / 1e6)}&#8239;Mio.&nbsp;€
              </p>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
                Zinsen im Jahr {zins.year} — aus dem Jahresabschluss
                <Beleg q="jahresabschluss" />, nicht aus der Reihe oben.
              </p>
              <p className="mt-2.5 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
                <strong>Zinsen, nicht Tilgung.</strong> Was die Stadt an ihren Krediten
                zurückzahlt, mindert den Schuldenstand und ist kein Aufwand — es steht im
                Finanzhaushalt und nicht in dieser Rechnung. Beide Beträge zusammenzuzählen
                ergäbe eine Zahl, die in keinem Dokument steht.
              </p>
              <Fundstelle h={hZins} />
            </section>
          );
        })()}

        <LottiErklaert
          titel="Warum es zwei Schuldenzahlen gibt"
          text={"Die Stadt hat Betriebe, die zu ihr gehören, und Gesellschaften, die ihr "
            + "gehören. Das ist nicht dasselbe: Ein Eigenbetrieb wie die Gebäudewirtschaft "
            + "ist rechtlich die Stadt — seine Schulden sind ihre Schulden. Eine GmbH oder "
            + "eine Anstalt wie das Klinikum ist eine eigene Rechtsperson und schuldet für "
            + "sich. Diese Seite zählt die erste Sorte mit und die zweite nicht. Deshalb "
            + "verschwanden die Kliniken 1999 aus der Reihe: Nicht ihre Schulden waren weg, "
            + "sondern ihre Rechtsform war eine andere geworden."}
        />

        {/* Die Zeitreihe */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {erster.year} bis {letzter.year}
          </p>
          <Segmented<Ansicht>
            value={ansicht}
            onChange={setAnsicht}
            options={[
              { value: "insgesamt", label: "Insgesamt" },
              { value: "per_capita", label: "Je Einwohner*in" },
            ]}
          />
        </div>
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
          {/* Die gemeinsame <Zeitreihe> des Baukastens (GB-01) — nicht mehr
              seiten-eigen: Zinslinie (`zweitreihe`), 2010-Marke
              (`annotationen`) und die beiden größten Bewegungen (`spruenge`)
              sind dort Vertrag.

              Zinslinie und 2010-Annotation direkt im Bild (H4-13): Was der
              Bestand im Jahr kostet, auf derselben Skala — und der Knick von
              2010 mit seiner Erklärung am Ort des Knicks. Der ganze Satz samt
              Beleg steht darunter in „Zwei Sprünge, die keine Politik waren". */}
          <Zeitreihe
            series={kurve}
            titel={ansicht === "insgesamt" ? "Schulden insgesamt" : "Schulden je Einwohner*in"}
            ariaTitel={`Schuldenstand ${erster.year} bis ${letzter.year}`}
            einheit={ansicht === "insgesamt" ? "Mio. €" : "€ je Einwohner*in"}
            // Millionen mit einer Stelle, Pro-Kopf-Beträge ohne — sonst stünde
            // „1.908,0 €" an einer Zahl, die die Quelle ganzzahlig ausweist.
            format={ansicht === "insgesamt" ? (v) => deMio(v) : deEuro}
            spruenge
            vorjahresdifferenz
            tabelle
            zweitreihe={zinsreihe && zinsreihe.length
              ? { label: "Zinslast p. a.", series: zinsreihe, format: (v) => deMio(v) }
              : undefined}
            annotationen={ansicht === "insgesamt" ? [{
              year: 2010,
              kurz: "108,9 Mio. € umgebucht",
              text: "2010 übertrug die Stadt 108,9 Mio. € Kredite an den neuen "
                + "Eigenbetrieb Gebäudewirtschaft. Dadurch änderte sich die Aufteilung, "
                + "während die Gesamtsumme nahezu gleich blieb.",
            }] : []}
            note="Jahr überfahren, antippen oder mit den Pfeiltasten wechseln."
          />
          {/* Die beiden Richtungen nebeneinander — der Grund, warum es den
              Umschalter überhaupt gibt. Gerechnet, nicht geschrieben. */}
          {gegenlaeufig && (
            <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Über {letzter.year - erster.year} Jahre gehen die beiden Ansichten
              auseinander: Insgesamt hat die Stadt heute{" "}
              {deMio(Math.abs(deltaAbs) / 1e6)}&#8239;Mio.&nbsp;€{" "}
              {deltaAbs > 0 ? "mehr" : "weniger"} Schulden als {erster.year}, je
              Einwohner*in aber {deEuro(Math.abs(deltaKopf!))}&nbsp;€{" "}
              {deltaKopf! > 0 ? "mehr" : "weniger"} — die Zahl der Einwohner*innen ist in
              derselben Zeit gewachsen.
            </p>
          )}
          <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Alle Beträge in Euro des jeweiligen Jahres — die Teuerung ist nicht
            herausgerechnet. Ein Teil der Bewegung ist also verändertes Preisniveau.
          </p>
        </section>

        {/* Was hinter den größten Sprüngen steckt. Alles steht als Fußnote in
            der Quelltabelle — deshalb darf es hier stehen. Ohne diesen Block
            liest sich die Kurve als Spar- und Schuldenpolitik, und beides wäre
            falsch.

            DIE LETZTEN ZWEI PUNKTE STEHEN NUR IN DER PRO-KOPF-ANSICHT, weil
            sie nur dort etwas verzerren: Sie liegen im NENNER. In der
            Gesamtsumme kommen sie nicht vor, und sie dort zu erwähnen hieße,
            einen Sprung zu behaupten, den man nicht sieht. */}
        <section className="@container rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {ansicht === "insgesamt"
              ? "Zwei Brüche durch organisatorische Änderungen"
              : "Drei Brüche durch Organisation oder Statistik"}
          </p>
          <ul className="mt-2 grid list-disc grid-cols-1 gap-x-8 gap-y-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90 @3xl:grid-cols-2">
            <li>
              <strong>2001 fiel die Schuld um mehr als die Hälfte.</strong> Die Stadt
              übertrug die Stadtentwässerung an den Oldenburgisch-Ostfriesischen
              Wasserverband; der übernahm dabei Darlehen über 139,5&#8239;Mio.&nbsp;€.
              Der Rückgang entstand damit durch die Aufgabenübertragung und nicht durch
              Tilgung.<Beleg q="schulden" />
            </li>
            <li>
              <strong>2010 verschob sich eine Spalte um 108,9&#8239;Mio.&nbsp;€</strong>,
              ohne dass die Summe folgte: Die Stadt gründete den Eigenbetrieb
              Gebäudewirtschaft und Hochbau und übertrug ihm diesen Teil ihres
              Kreditportfolios. Dieselbe Stadt, dieselben Schulden, andere
              Spalte.<Beleg q="schulden" />
            </li>
            {ansicht === "per_capita" && (
              <li>
                <strong>2023 sank der Betrag je Einwohner*in um 36&nbsp;€ — obwohl
                die Schulden stiegen.</strong> Der Zensus 2022 zählte 4.079 Menschen
                mehr, als die Statistik bis dahin fortgeschrieben hatte. Dieselbe
                Schuld auf mehr Schultern ergibt einen kleineren Betrag; die
                Gesamtsumme wuchs im selben Jahr von 281,5 auf
                281,9&#8239;Mio.&nbsp;€.<Beleg q="schulden" />
              </li>
            )}
          </ul>
          {ansicht === "per_capita" && (
            /* Der Vollständigkeit halber, aber NICHT als vierter Aufzählungspunkt:
               2012 wirkte dieselbe Mechanik, trug aber nur 30 der 125 € — den Rest
               hat die Stadt wirklich aufgenommen. Als gleichrangiger Punkt neben
               2023 gelistet, würde das eine Verzerrung behaupten, die es so nicht
               gab. Die Zahlen sind aus der Reihe selbst gerechnet (Betrag geteilt
               durch Pro-Kopf-Wert ergibt den Nenner, den die Statistik benutzt). */
            <p className="mt-2.5 max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
              Alle zehn Jahre zählt eine Volkszählung die Einwohner*innen neu, und
              die Statistik rechnet ab da mit der neuen Zahl. 2012 wirkte das
              ebenfalls, aber schwächer: Von den +125&nbsp;€ jenes Jahres gehen rund
              30&nbsp;€ auf den Zensus 2011 zurück, die übrigen 95&nbsp;€ auf echte
              Kredite. In der Ansicht „Insgesamt" kommt keiner dieser beiden
              Nenner-Effekte vor.
            </p>
          )}
        </section>

        {/* Die Aufteilung — nur wo sie belegt ist. */}
        {jTeilung && (
          <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Wer schuldet was ({jTeilung.year})
              </p>
              <span className="font-mono text-[10px] uppercase text-muted-foreground">
                {teilung.length} von {series.length} Jahren aufgeschlüsselt
              </span>
            </div>
            {/* --hh-aus-0 und --hh-aus-2, NICHT aus-3: Die Segmente tragen
                eine Beschriftung, und dafür verlangt die Designsprache (§4)
                4,5 : 1 gegen `--hh-seg-text`. Gemessen am 16.08.2026 hält
                aus-2 das in beiden Themes (hell 4,72 · dunkel 5,76), aus-3
                in keinem (3,18 · 4,04). */}
            <div className="mt-3 flex h-7 w-full overflow-hidden rounded-lg">
              {([
                ["Verwaltung", jTeilung.kern, "var(--hh-aus-0)"],
                ["Eigenbetriebe", jTeilung.municipal_enterprises, "var(--hh-aus-2)"],
              ] as const).map(([label, wert, farbe]) => {
                const anteil = (wert / (jTeilung.kern + jTeilung.municipal_enterprises)) * 100;
                return (
                  <div key={label} className="flex items-center px-2"
                    style={{ width: `${anteil}%`, background: farbe }}>
                    {anteil > 18 && (
                      <span className="truncate font-mono text-[10.5px] font-semibold"
                        style={{ color: "var(--hh-seg-text)" }}>
                        {Math.round(anteil)}&nbsp;%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <dl className="mt-2.5 flex flex-wrap gap-x-6 gap-y-1 text-[12.5px]">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 flex-none rounded-sm"
                  style={{ background: "var(--hh-aus-0)" }} />
                <dt className="text-muted-foreground">Verwaltung</dt>
                <dd className="font-semibold tabular-nums">
                  {deMio(jTeilung.kern / 1e6)}&#8239;Mio.&nbsp;€
                </dd>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 flex-none rounded-sm"
                  style={{ background: "var(--hh-aus-2)" }} />
                <dt className="text-muted-foreground">Eigenbetriebe</dt>
                <dd className="font-semibold tabular-nums">
                  {deMio(jTeilung.municipal_enterprises / 1e6)}&#8239;Mio.&nbsp;€
                </dd>
              </div>
            </dl>
            <p className="mt-2 max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Beides schuldet dieselbe Stadt — die Trennung zeigt nur, in welchem Buch es
              steht. Rechtlich haftet sie für die Eigenbetriebe genauso wie für die
              Verwaltung.
            </p>
            {/* Die Lücke benennen statt sie als Null zu zeichnen. */}
            {luecken.length > 0 && (
              <p className="mt-2 max-w-[76ch] border-t border-dashed border-border pt-2 text-[12px] leading-relaxed text-muted-foreground">
                Für {luecken.map((z) => z.year).join(", ")} fehlt die Aufteilung: Dort
                {luecken.length === 1 ? " ergibt " : " ergeben "}
                die Summe der einzelnen Schuldenarten in der Quelltabelle nicht den Betrag,
                der daneben als Gesamtschuld ausgewiesen ist. Welche Spalte danebenliegt,
                sagt die Tabelle nicht — die Gesamtschuld{" "}
                {luecken.length === 1 ? "dieses Jahres" : "dieser Jahre"} steht, die
                Aufschlüsselung nicht.
              </p>
            )}
          </section>
        )}

        {/* DIE GEGENSEITE. Bis hierher stand auf dieser Seite nur, was die
            Stadt schuldet — und die naheliegende Anschlussfrage („kaum
            Kredite, also keine Schulden?") beantwortet erst die Bilanz: Die
            Pensionszusagen sind ein Vielfaches der Kredite. Der Block holt
            seine Daten selbst und rendert nichts, solange kein
            ausgeglichener Bilanzstichtag im Bestand steht. */}
        <BilanzBlock />

        {/* Wofür die Stadt geradesteht. Steht VOR den Grenzen und nicht
            darin, obwohl es eine Grenze der Schuldenzahl ist: Es ist die
            größere Zahl der Seite (2024 das Fünffache), und Zahlen, die
            größer sind als die Überschrift, gehören nicht ins
            Kleingedruckte. */}
        <BuergschaftsBlock daten={data} />

        {/* Die dritte Zahl. Steht NACH den Bürgschaften, weil sie die Frage
            beantwortet, die die beiden davor aufwerfen: „Wenn 337 nicht alles
            ist und 220 nicht dazuzählen — was schuldet die Stadt denn nun?" */}
        <div id="drei-zahlen" className="scroll-mt-20"><DritteZahlBlock daten={data} /></div>

        {/* Die Grenzen — eigener Block, nicht Kleingedrucktes. */}
        <section className="@container rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Was diese Zahl nicht sagt
          </p>
          <ul className="mt-2 grid list-disc grid-cols-1 gap-x-8 gap-y-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90 @3xl:grid-cols-2">
            <li>
              <strong>Nicht der Konzern.</strong> Klinikum, Busse, Bäder und die
              städtischen Gesellschaften schulden auf eigene Rechnung und stehen hier
              nicht. Was neben dem Haushalt noch läuft, zeigt{" "}
              <Link href="/haushalt/konzern" className="font-semibold text-primary">
                „Und ist das die ganze Stadt?"
              </Link>{" "}
              — eine Schuldenzahl für diese Ebene führen wir nicht, weil die
              Pflichtanlage des Gesamtabschlusses im PDF keinen auslesbaren Text trägt.
            </li>
            <li>
              <strong>Ein Bestand, kein Jahr.</strong> Hier steht, was am 31. Dezember
              offen war — nicht, was die Stadt in dem Jahr eingenommen oder ausgegeben
              hat. Mit den Zahlen auf{" "}
              <Link href="/haushalt" className="font-semibold text-primary">/haushalt</Link>{" "}
              ist dieser Wert <strong>nicht verrechenbar</strong>.
            </li>
            <li>
              <strong>Keine Bewertung der Tragfähigkeit.</strong> Ob ein Schuldenstand
              tragbar ist, hängt unter anderem von Investitionen, Vermögen, laufenden
              Ergebnissen und künftigen Belastungen ab. Diese Seite zeigt den Verlauf,
              bewertet ihn aber nicht.
            </li>
          </ul>
        </section>

        {satzung && <RahmenBlock zeile={satzung}
          herkunft={herkunftVon(satzungDaten, satzung.herkunft_id)} />}

        <Link href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary">
          Zurück zur Übersicht über den Haushalt
          <ArrowRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>

        <SchrittWeiter href="/haushalt/schulden" />

        <Quellenverzeichnis schluessel={[...QUELLEN]} />
      </div>
    </Quellenkontext>
  );
}
