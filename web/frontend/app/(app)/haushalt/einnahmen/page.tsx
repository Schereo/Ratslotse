"use client";

// /haushalt/einnahmen — „Woher kommt das Geld?" (Design H2-07, davor H-13).
//
// Die Landkarte aller Einnahmequellen. Neu in dieser Runde: Sie sind nicht
// mehr nach Betrag sortiert, sondern **nach Entscheidungsmacht gruppiert**.
//
// Warum das die eigentliche Arbeit ist: Nach Betrag sortiert trug jede Karte
// ihr Spielraum-Zeichen selbst — man musste sieben Karten lesen und im Kopf
// zusammenzählen, um die Aussage zu bekommen. Jetzt ist die Gruppierung die
// Aussage, und das Zeichen steht einmal an der Abschnittsüberschrift.
//
// Beträge sind IST-Werte des jüngsten Jahres (Open-Data), keine Planwerte —
// das steht auch so auf der Seite.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  HaushaltAuswahl, haushaltUrl, deMio, einnahmearten,
  spendenGremien, spendenJahre, spendenLaufend,
} from "@/lib/haushalt";
import { ZeitreiheMini } from "@/components/grafik/zeitreihe";
import { LueckenFeld } from "@/components/grafik/luecken-field";
import { SPIELRAUM_LABEL, STEUERARTEN, Spielraum } from "@/lib/haushalt-taxes";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { FinanzausgleichDaempfer } from "@/components/haushalt/fiscal-equalization-daempfer";
import { ZuweisungDreiteilig } from "@/components/haushalt/zuweisung-dreiteilig";
import { cn } from "@/lib/utils";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { Herkunftskacheln } from "@/components/haushalt/flussbild";

/** Drei Striche als Spielraum-Marke — gefüllt, halb, gestrichelt.
 *
 *  `hoch` ist die Balkenhöhe in Viertel-rem: an der Abschnittsüberschrift
 *  klein (Wiedererkennung), in der Legende noch kleiner. */
function SpielraumMarke({ stufe, klasse }: { stufe: Spielraum; klasse: string }) {
  const gefuellt = stufe === "frei" ? 3 : stufe === "begrenzt" ? 2 : 0;
  return (
    <span className="flex flex-none gap-0.5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span key={i} className={cn(
          "w-1 rounded-sm", klasse,
          i < gefuellt
            ? stufe === "frei" ? "bg-[color:var(--hh-ein-0)]" : "bg-[color:var(--hh-ein-2)]"
            : stufe === "keiner" ? "border border-dashed border-border" : "bg-muted",
        )} />
      ))}
    </span>
  );
}

/** Was die drei Stufen bedeuten — eine Zeile, die den Gruppentitel trägt.
 *
 *  Bewusst kein Text über „die meisten Einnahmen": Welche Gruppe wie groß
 *  ist, rechnet die Seite unten aus den Daten aus. */
const GRUPPEN: { stufe: Spielraum; titel: string; text: string }[] = [
  {
    stufe: "frei",
    titel: "Der Rat entscheidet",
    text: "Der Rat beschließt den Satz selbst — jedes Jahr mit dem Haushalt.",
  },
  {
    stufe: "begrenzt",
    titel: "Begrenzt",
    text: "Der Rat beschließt, darf aber gesetzlich nicht frei wählen.",
  },
  {
    stufe: "keiner",
    titel: "Kein Einfluss",
    text: "Höhe und Verteilung legen Bund und Land fest.",
  },
];

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
// `income_statement` seit 24.08.2026: Die Gebühren-Karte trug bis dahin
// „Betrag noch nicht eingelesen", während ihr Steckbrief die Zahl längst
// hätte holen können. Zwei Seiten dürfen zur selben Zahl nicht
// Verschiedenes sagen — die Regel stand schon im Steckbrief, nur
// andersherum.
const FELDER = ["years", "taxes", "tax_capacity", "fiscal_equalization", "donations",
  "income_statement", "income_budget"] as const;

export default function EinnahmenPage() {
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(haushaltUrl(FELDER));

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Einnahmen werden geladen …</div>;
  }

  const year = Math.max(...data.taxes.map((s) => s.year), 0);
  const betragFuer = (art: string | null) => {
    if (!art) return null;
    return data.taxes.find((s) => s.year === year && s.art === art)?.amount ?? null;
  };
  const zuweisungJahr = data.tax_capacity.filter((k) => k.allocations != null).at(-1);
  // Der vollständige Ausgleich aus den Tabellen des Landes (Tausend Euro).
  // Optional: Ohne einen Lauf von scripts/ingest_staedtevergleich.py ist das
  // Feld leer, und die Seite zeigt weiter nur die Schlüsselzuweisungen.
  const ausgleich = (data.fiscal_equalization ?? []).filter((f) => f.nettobetrag != null).at(-1);
  const gesamt = data.taxes.find((s) => s.year === year && s.art === "total")?.amount ?? null;

  // Karten: Betrag aus den Daten, innerhalb der Gruppe nach Betrag sortiert
  // (Quellen ohne Zahl ans Ende).
  // Der zweite Weg an die Zahl, für Einnahmearten ohne Steuerreihe: der
  // jüngste Jahresabschluss, der diesen Posten führt. Sein Jahr ist nicht
  // zwingend das der Steuerreihe — deshalb trägt jede Karte ihr eigenes,
  // wie die Schlüsselzuweisungen es längst tun.
  const entgeltJahr = (posten: number) =>
    (data.income_statement ?? [])
      .filter((z) => z.nr === posten && z.sub_budget_no === null && z.result != null)
      .sort((a, b) => a.year - b.year)
      .at(-1) ?? null;

  const karten = STEUERARTEN.map((a) => {
    const entgelt = a.ergebnisPosten ? entgeltJahr(a.ergebnisPosten) : null;
    return {
      art: a,
      amount: a.slug === "schluesselzuweisungen"
        ? zuweisungJahr?.allocations ?? null
        : entgelt ? entgelt.result : betragFuer(a.datenArt),
      year: a.slug === "schluesselzuweisungen"
        ? zuweisungJahr?.year ?? year
        : entgelt ? entgelt.year : year,
    };
  }).sort((a, b) => (b.amount ?? -1) - (a.amount ?? -1));

  const gruppen = GRUPPEN
    .map((g) => ({ ...g, karten: karten.filter((k) => k.art.spielraum === g.stufe) }))
    .filter((g) => g.karten.length > 0);
  const frei = karten.filter((k) => k.art.spielraum === "frei").length;

  // Der jüngste aufgestellte Ansatz, nicht eines der drei späteren
  // Finanzplanungsjahre. Die Seite zeigt damit neben den jüngsten Ist-Werten
  // erstmals auch vollständig, woher das Geld im geltenden Plan kommen soll.
  const planJahr = Math.max(0, ...(data.income_budget ?? [])
    .filter((z) => z.art === "ansatz")
    .map((z) => z.year));
  const planErtraege = planJahr ? einnahmearten(data, planJahr) : null;

  const spendenReihe = spendenJahre(data);
  const spendenLauf = spendenLaufend(data);
  const spendenGrem = spendenGremien(data);
  const spendenOhne = data.donations?.ohne_beleg ?? [];
  const spendenLetztes = spendenReihe[spendenReihe.length - 1];
  const spendenGeld = spendenGrem.Rat.amount + spendenGrem.Verwaltungsausschuss.amount;

  const quellen: QuellenSchluessel[] = ["taxes", "tax_capacity", "tax_rates",
    ...(planErtraege ? (["income_budget"] as const) : []),
    ...(karten.some((k) => k.art.ergebnisPosten && k.amount != null)
      ? (["jahresabschluss"] as const) : []),
    ...(spendenReihe.length ? (["donations"] as const) : [])];

  return (
    <Quellenkontext schluessel={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Woher das Geld kommt</span>
      </div>

      <div className="@container/kopf flex items-start justify-between gap-5">
        <div className="min-w-0 flex-1">
          <SchrittKicker href="/haushalt/einnahmen" />
          {/* Der gerechnete Satz („Bei N von M …") war bis H5-09 die
              Überschrift. Er ist die EINE Zahl dieser Seite und steht jetzt
              groß auf der Bühne darunter; die Überschrift trägt die Frage,
              unter der der Wegweiser den Schritt führt. */}
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[25px]">
            Woher kommt das Geld?
          </h1>
        </div>
        <SchrittPfad href="/haushalt/einnahmen" />
      </div>

      {/* Die Bühne (H5-02/H5-09): der bisherige H1-Satz mit seiner Zahl, groß
          gesetzt; das Minibild ist das Quellenregal — je Gruppe eine Reihe,
          ein Quadrat je Quelle — und springt zur Legende, die die drei
          Gruppen erklärt. */}
      <Seitenbuehne
        kicker="Spielraum über alle Quellen"
        zahl={<>Bei <ZaehlZahl wert={frei} /> von {karten.length} Einnahmequellen kann der
          Rat die Höhe selbst festlegen</>}
        sub={GRUPPEN.find((g) => g.stufe === "frei")?.text}
        minibild={{
          // Das Regal beschriftet SICH SELBST (Tim, 26.08.: „sieht eher aus
          // wie ein Buchstabe C … man sieht nicht, dass die ersten drei die
          // sind, die die Stadt beeinflussen kann"). Je Gruppe eine Zeile mit
          // Namen und Zahl, darunter ihre Quadrate — und deshalb ohne
          // Erklärzeile und ohne Link darunter: Was das Bild sagt, steht im
          // Bild.
          label: "",
          skizze: (["frei", "begrenzt", "keiner"] as Spielraum[]).map((stufe) => {
            const count = karten.filter((k) => k.art.spielraum === stufe).length;
            const ton = stufe === "frei" ? "var(--sb-voll)"
              : stufe === "begrenzt" ? "var(--sb-mittel)" : "var(--sb-blass)";
            return (
              // Label und Quadrate in EINER Zeile: So füllt jede Gruppe die
              // Spalte, statt als schmale Marke oben rechts zu kleben — und
              // die Quadrate stehen groß genug, um zählbar zu sein.
              <span key={stufe} className="flex items-center gap-2.5">
                {/* Feste Label-Spalte: So beginnen alle Reihen an derselben
                    Kante, und ihre Länge ist vergleichbar wie bei einem
                    Balken — rechtsbündig sah die Ein-Quadrat-Gruppe aus, als
                    klebte sie am Rand. */}
                <span className="w-[74px] flex-none truncate text-[10.5px] leading-none text-muted-foreground">
                  {SPIELRAUM_LABEL[stufe]}
                </span>
                <span className="flex min-w-0 flex-1 flex-wrap gap-1">
                  {Array.from({ length: count }, (_, i) => (
                    <span key={i} className="h-4 w-4 rounded-[3px]"
                      style={stufe === "keiner"
                        ? { border: "1.5px dashed var(--sb-strich)" }
                        : { background: ton }} />
                  ))}
                </span>
              </span>
            );
          }),
        }}
      />

      {/* Der Einstiegstext steht UNTER der Bühne, kleiner und in der Breite
          (Tim, 26.08.: „Der ganze Text über den Heroes sieht echt nicht gut
          aus"): Der Kopf ist jetzt Titel + Bühne, die Erklärung folgt. Zwei
          Absätze, zwei Spalten ab Container-Breite (Designsprache §4) —
          Aufhänger und Jahres-Hinweis sagen Verschiedenes. */}
      <div className="@container">
        <div className="grid gap-x-8 gap-y-2 @3xl:grid-cols-2">
          <p className="max-w-[70ch] text-[13px] leading-relaxed text-foreground/85">
            Nicht jede Einnahmequelle lässt sich vor Ort beeinflussen. Deshalb sortieren wir
            sie nicht nach ihrer Höhe, sondern <strong>nach dem Entscheidungsspielraum des
            Rates</strong>. Gezählt sind Einnahmequellen, nicht Eurobeträge.
          </p>
          {/* Der Jahres-Sprung bleibt oben auf der Seite: Wer von der Übersicht
              kommt, hat dort Planzahlen des kommenden Jahres gesehen; hier
              stehen abgerechnete Werte eines früheren. */}
          <p className="max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Achtung beim Jahr: Bei den Steuern stehen hier <strong>abgerechnete Beträge
            aus {year}</strong> — was wirklich geflossen ist. Die Übersicht zeigt dagegen den
            <em>Plan</em> für ein späteres Jahr. Beide Zahlen sind richtig, sie beantworten nur
            verschiedene Fragen. Jede Karte nennt ihr Jahr selbst — die Schlüsselzuweisungen
            laufen dem Rest voraus.
          </p>
        </div>
      </div>

      {planErtraege && (
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Haushaltsplan {planErtraege.year}
              </p>
              <h2 className="mt-1 font-display text-[17px] font-bold tracking-tight">
                Woher das Geld laut Plan kommen soll
              </h2>
            </div>
            <p className="font-display text-[20px] font-bold tabular-nums">
              {deMio(planErtraege.gesamt / 1e6)}&#8239;Mio.&nbsp;€
              <Beleg q="income_budget" />
            </p>
          </div>
          <p className="mt-2 max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Diese Aufteilung umfasst alle geplanten ordentlichen Erträge. Sie stammt aus
            dem von der Verwaltung eingebrachten Gesamtergebnishaushalt und ist deshalb
            getrennt von den abgerechneten Beträgen in den Karten darunter.
          </p>
          <div className="mt-3">
            <Herkunftskacheln arten={planErtraege} />
          </div>
        </section>
      )}

      <div id="spielraum" className="scroll-mt-20 rounded-2xl border border-border bg-card p-3.5 shadow-sm">
        <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          Spielraum des Rats
        </p>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
          {(["frei", "begrenzt", "keiner"] as Spielraum[]).map((s) => (
            <span key={s} className="inline-flex items-center gap-2 text-[11.5px]">
              <SpielraumMarke stufe={s} klasse="h-3" />
              {SPIELRAUM_LABEL[s]}
            </span>
          ))}
        </div>
      </div>

      {gruppen.map((g) => (
        <div key={g.stufe}>
          <div className="mb-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <SpielraumMarke stufe={g.stufe} klasse="h-4" />
            <span className="text-[14.5px] font-bold">{g.titel}</span>
            <span className="text-[12.5px] text-muted-foreground">{g.text}</span>
            <span className="hidden h-px flex-1 bg-border sm:block" />
          </div>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {g.karten.map(({ art, amount, year: bJahr }) => (
              <Link key={art.slug} href={`/haushalt/steuer?art=${art.slug}`}
                className={cn(
                  "flex flex-col rounded-xl border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/40",
                  // Die erste Gruppe trägt einen Primär-Tint: Sie ist die
                  // Antwort auf die Frage, mit der Leute herkommen.
                  g.stufe === "frei" ? "border-primary/25 bg-primary/[0.04]" : "border-border",
                )}>
                <p className="text-[13px] font-bold leading-snug">{art.titel}</p>
                {amount != null ? (
                  <p className="mt-1.5 font-display text-[20px] font-bold leading-none tracking-tight tabular-nums">
                    {deMio(amount / 1e6)}
                    <span className="text-[11px] font-semibold text-muted-foreground">
                      &#8239;Mio.&nbsp;€
                    </span>
                    <span className="ml-1 font-sans text-[10px] font-normal text-muted-foreground">
                      {bJahr}
                      <Beleg q={art.slug === "schluesselzuweisungen"
                        ? "tax_capacity"
                        : art.ergebnisPosten ? "jahresabschluss" : "taxes"} />
                    </span>
                  </p>
                ) : (
                  <p className="mt-1.5 text-[12px] text-muted-foreground">
                    Betrag noch nicht eingelesen
                  </p>
                )}
                <p className="mt-1.5 text-[11.5px] leading-snug text-foreground/75">{art.stellschraube}</p>
                <p className="mt-auto pt-1.5 text-[11.5px] font-semibold text-primary">Steckbrief öffnen →</p>
              </Link>
            ))}
          </div>
        </div>
      ))}

      {/* Der Dämpfer schließt die Seite ab, weil er erklärt, warum selbst die
          erste Gruppe weniger Spielraum hat, als sie verspricht. Er nennt
          bewusst keinen Faktor — Begründung im Kopf der Komponente. */}
      <FinanzausgleichDaempfer tax_capacity={data.tax_capacity} />

      {/* Direkt unter der Kurve, weil er sie einordnet: Was dort als
          „Schlüsselzuweisungen" steht, sind zwei von drei Komponenten. Der
          Block ersetzt die Zahl nicht, er stellt die vollständige daneben
          (council/steuerkraft.py). */}
      <ZuweisungDreiteilig series={data.fiscal_equalization} />

      {/* Der Satz verglich bis 16.08. die Steuern eines Ist-Jahres mit den
          Ausgaben eines Planjahres („deckt nur einen Teil dessen, was die
          Stadt ausgibt") — zwei Zahlen aus zwei Rechnungen, deren Differenz
          nichts bedeutet. Jetzt bleibt der Vergleich innerhalb derselben
          Quelle: Steuern gegen Steuern plus Zuweisungen.

          Die Zuweisungen tragen ihr eigenes Jahr im Satz, seit die
          Jahres-Korrektur am Datensatz 1106 die beiden Reihen auseinander-
          gezogen hat: Die Steuern enden beim letzten abgerechneten Jahr, der
          Finanzausgleich steht schon für das laufende Ausgleichsjahr fest.
          Ein gemeinsames „brachten 2025" wäre für eine der beiden Zahlen
          falsch. */}
      {gesamt != null && (
        <LottiErklaert
          titel="Was diese Beträge zusammen sind — und was nicht"
          /* Seit 17.08. nennt der Satz den VOLLEN Ausgleich, wenn er vorliegt:
             Die Schlüsselzuweisungen allein sind zwei von drei Komponenten,
             und ein Satz, der ausdrücklich zusammenzählt, darf nicht die
             engere Zahl nehmen. Fehlt der Landesbestand (frische Datenbank),
             bleibt es bei der bisherigen Formulierung — samt dem Wort
             „Schlüsselzuweisungen", das dann auch genau stimmt. */
          text={`Alle Steuern zusammen brachten ${year} rund ${deMio(gesamt / 1e6)} Millionen Euro`
            + (ausgleich?.nettobetrag
              ? `. Dazu kommen die Zuweisungen des Landes: für das Ausgleichsjahr `
                + `${ausgleich.year} rund ${deMio(ausgleich.nettobetrag / 1000)} Millionen Euro `
                + `— Schlüsselzuweisungen für Gemeinde- und Kreisaufgaben plus die `
                + `Zuweisungen für übertragene staatliche Aufgaben`
              : zuweisungJahr?.allocations
                ? `. Dazu kommen die Schlüsselzuweisungen des Landes: für das Ausgleichsjahr `
                  + `${zuweisungJahr.year} rund ${deMio(zuweisungJahr.allocations / 1e6)} Millionen Euro`
                : "")
            + ". Die Karten sind eine Auswahl wiederkehrender Einnahmequellen mit klarer"
            + " Zuständigkeit. Gebühren, Kostenerstattungen und zweckgebundene Zuschüsse"
            + " stehen vollständig in der geplanten Aufteilung weiter oben. Die Beträge"
            + " hier dürfen wegen ihrer unterschiedlichen Jahre nicht dazuaddiert werden."}
        />
      )}

      {/* „Auch das sind Einnahmen" — die Zuwendungen, die die Stadt annimmt.
          Steht bewusst direkt hinter dem Erklärkasten: Dessen Schlusssatz
          sagt, dass die Steuern nicht alles sind, und das hier ist ein Posten,
          den sonst niemand ausweist.

          Klein gehalten, und zwar aus zwei Gründen. Erstens ist der Betrag
          klein: 0,8 Mio. € neben rund 280 Mio. € Steuern — eine große Kachel
          behauptete ein Gewicht, das die Zahl nicht hat. Zweitens ist die
          eigentliche Auskunft nicht die Summe, sondern die Aufteilung: gleich
          viele Vorlagen in beiden Gremien, fast das ganze Geld beim Rat. Das
          ist die Schwelle von 2.000 Euro, sichtbar gemacht.

          Was hier NICHT steht: wer gespendet hat. Die Namen stehen nur in der
          Anlage „Zuwendungsliste", die nicht im Bestand ist — und der Satz
          darüber ist Teil des Blocks, nicht eine Fußnote.

          ZWEI BEFUNDE VOM 24.08. (Tim), beide am selben Block:

          1. „Der Text ist nur halbseitig." Stimmt — und zwar überall in dieser
             Karte gleichzeitig: Vier Absätze mit `max-w-[80ch]` untereinander
             füllten 631 von 1.102 px, rechts blieben 471 px leer, während die
             Lücken-Felder darunter über die volle Breite liefen. Genau der
             Fall aus DESIGNSPRACHE.md § 4 („den KASTEN deckeln, nicht den Text
             darin"): Eine AUFZÄHLUNG in einer breiten Karte läuft zweispaltig,
             der Deckel bleibt, die Fläche wird voll. Die Schwelle hängt am
             CONTAINER, nicht am Fenster — neben der Seitenleiste meint dieselbe
             Fensterbreite ein anderes Platzangebot.
          2. „Es wird gar nicht erklärt, was Zuwendungen sind." Stimmte auch:
             Der Block sprang von der Überschrift direkt zur Summe und erklärte
             danach nur noch Zuständigkeit und Grenzen. Die Definition steht
             jetzt oben neben der Kennzahl — dort, wo vorher die Kurve allein
             die halbe Zeile füllte. */}
      {spendenLetztes && (
        <section className="@container/donations rounded-2xl border border-border bg-card p-4 shadow-sm">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Auch das sind Einnahmen
          </h2>
          <div className="mt-2.5 grid gap-x-8 gap-y-4 @3xl/donations:grid-cols-2 @3xl/donations:items-start">
            <div className="min-w-0">
              <p className="text-[12.5px] font-semibold">
                Angenommene Zuwendungen {spendenLetztes.year}
              </p>
              {/* Auf den Euro genau, nicht gerundet: Diese Summe IST exakt —
                  sie ist die Summe von Ratsbeschlüssen, nicht eine
                  Hochrechnung. „789 Tsd. €" wäre hier eine Ungenauigkeit, die
                  die Quelle gar nicht hat. */}
              <p className="mt-0.5 font-display text-[24px] font-bold leading-none tabular-nums">
                {Math.round(spendenLetztes.amount).toLocaleString("de-DE")}
                <span className="ml-1 text-[13px] font-semibold text-muted-foreground">€</span>
                <Beleg q="donations" />
              </p>
              <p className="mt-1 text-[11.5px] text-muted-foreground">
                aus {spendenLetztes.vorlagen} Beschlüssen
              </p>
              {spendenReihe.length > 1 && (
                <div className="mt-3">
                  {/* Endpunkt in Tausend, wie die große Zahl darüber — zwei
                      Einheiten in einem Block ließen die Kurve und die Kennzahl
                      wie zwei verschiedene Reihen aussehen. Die Kurve steht
                      UNTER der Zahl, nicht daneben: In voller Kartenbreite lief
                      sie über 700 px bei 46 px Höhe und zog acht Jahrgänge zu
                      einem flachen Draht. */}
                  <ZeitreiheMini
                    series={spendenReihe.map((j) => ({ year: j.year, wert: j.amount }))}
                    format={(v) => `${Math.round(v / 1000).toLocaleString("de-DE")} Tsd.`}
                    ariaLabel={
                      `Angenommene Zuwendungen je Jahr, ${spendenReihe[0].year} bis `
                      + `${spendenLetztes.year}: von `
                      + `${Math.round(spendenReihe[0].amount).toLocaleString("de-DE")} auf `
                      + `${Math.round(spendenLetztes.amount).toLocaleString("de-DE")} Euro. `
                      + `Höchststand ${Math.round(Math.max(...spendenReihe.map((j) => j.amount)))
                        .toLocaleString("de-DE")} Euro.`}
                  />
                </div>
              )}
            </div>
            {/* Was eine Zuwendung überhaupt ist — der Satz, der bis 24.08.
                fehlte. Er steht bewusst VOR der Zuständigkeits-Schwelle: Wer
                nicht weiß, wovon die Rede ist, kann mit „bis 2.000 Euro der
                Verwaltungsausschuss" nichts anfangen. */}
            <div className="min-w-0">
              <p className="text-[13px] font-semibold">Spenden und Schenkungen an die Stadt</p>
              <p className="mt-1 max-w-[78ch] text-[13px] leading-relaxed text-foreground/85">
                Zuwendungen sind Geld- oder Sachspenden an die Stadt. Die Verwaltung darf
                sie nicht allein annehmen: Nach § 111 Abs. 8 NKomVG muss das zuständige
                Gremium zustimmen. Deshalb erscheint mehrmals im Jahr der Tagesordnungspunkt
                „Annahme von Zuwendungen“. Die dort beschlossenen Beträge fassen wir hier
                zusammen.
              </p>
            </div>
          </div>

          {/* Zweispaltig ab @3xl, also ab 768 px INNENbreite der Karte (die
              Karte selbst ist dann 800 px breit): Die kurzen Erklärstücke sind
              eine Aufzählung, keine Absatzfolge — nebeneinander füllen sie die
              Karte, und die Zeile bleibt bei 66–80 Zeichen. Der Deckel an den
              dd greift nur noch im einspaltigen Zustand; in zwei Spalten
              deckelt die Spalte selbst (gemessen: 535 px ≙ 82 Zeichen bei
              12,5 px, der Deckel liegt bei 80). Dieselbe Schwelle wie bei den
              „Was diese Zahlen nicht hergeben"-Listen der Nachbarseiten. */}
          <dl className="mt-3.5 grid gap-x-8 gap-y-3 border-t border-border pt-3 @3xl/donations:grid-cols-2">
            <div>
              <dt className="text-[12.5px] font-semibold">
                Wer entscheidet, hängt an 2.000 Euro
              </dt>
              <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                Über eine einzelne Zuwendung bis 100 Euro entscheidet die
                Oberbürgermeisterin oder der Oberbürgermeister allein, bis 2.000 Euro der
                Verwaltungsausschuss, darüber der Rat. Beide Gremien behandeln seit 2018
                ungefähr gleich viele Vorlagen — {spendenGrem.Rat.vorlagen} der Rat,{" "}
                {spendenGrem.Verwaltungsausschuss.vorlagen} der Verwaltungsausschuss —,
                aber{" "}
                {spendenGeld > 0
                  ? Math.round((spendenGrem.Rat.amount / spendenGeld) * 100)
                  : 0}{" "}
                Prozent des Geldes laufen über den Rat.
              </dd>
            </div>
            {/* Warum diese Reihe überhaupt gebaut wurde — die Auskunft steht
                sonst nirgends (council/spenden.py: „Weder die Ergebnisrechnung
                noch der Haushaltsplan weisen Spenden getrennt aus"). */}
            <div>
              <dt className="text-[12.5px] font-semibold">Warum diese Summe nur hier sichtbar wird</dt>
              <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                Weder der Haushaltsplan noch die Ergebnisrechnung weisen Zuwendungen als
                eigene Einnahmeart aus. Öffentlich nachvollziehbar wird ihre Gesamthöhe nur
                über die einzelnen Beschlüsse. Deshalb zeigen wir sie hier getrennt von den
                übrigen Einnahmen.
              </dd>
            </div>
            <div>
              <dt className="text-[12.5px] font-semibold">Wir zeigen Beträge, keine Namen</dt>
              <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                Wer gespendet hat und wofür, steht ausschließlich in der Anlage
                „Zuwendungsliste“ zur jeweiligen Vorlage. Diese Anlagen lesen wir nicht ein.
                Ratslotse zeigt daher nur die öffentlich beschlossene Summe, nicht die Namen
                der Gebenden.
              </dd>
            </div>
            {spendenLauf && (
              <div>
                <dt className="text-[12.5px] font-semibold">{spendenLauf.year} läuft noch</dt>
                <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                  Bis jetzt {Math.round(spendenLauf.amount).toLocaleString("de-DE")} €
                  aus {spendenLauf.vorlagen} Beschlüssen. Das Jahr steht deshalb nicht
                  in der Kurve: Es wäre ein Rückgang zu sehen, den es nicht gibt.
                </dd>
              </div>
            )}
            {spendenOhne.length > 0 && (
              <div className="@3xl/donations:col-span-2">
                <dt className="text-[12.5px] font-semibold">
                  {spendenOhne.length}{" "}
                  {spendenOhne.length === 1 ? "Beschluss fehlt" : "Beschlüsse fehlen"} in
                  dieser Reihe
                </dt>
                {/* Der Satz sagt, was der Reihe FEHLT — nicht, dass wir gut
                    geprüft haben. „Statt ungeprüft mitzuzählen" stand hier bis
                    zuletzt und war genau die Selbstvergewisserung, die
                    DESIGNSPRACHE.md § 7 als Anti-Pattern führt.

                    Der zweite Satz stand bis 24.08. in JEDEM Lücken-Feld mit,
                    das die Vorlage gegen das Protokoll stellte — vier von
                    sechs Feldern trugen ihn wörtlich untereinander. Er gilt
                    für die ganze Kategorie und steht deshalb hier, einmal;
                    `council/donations.py` schreibt seither je Zeile nur noch
                    deren eigene Zahlen. */}
                <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                  Ihre Beträge sind in den Summen oben nicht enthalten: In diesen
                  Vorlagen steht der beschlossene Betrag entweder kein zweites Mal,
                  oder die beiden Stellen widersprechen sich. Wo sie das tun, hat
                  entweder der Rat die Liste geändert oder eines der beiden Dokumente
                  trägt einen Zahlendreher — welches, sagt der Bestand nicht.
                </dd>
                {/* <LueckenFeld> statt einer eigenen Liste: Es ist die Textform
                    für Lücken im Baukasten, und sie ist bewusst nie
                    einklappbar (H4-A). Sechs Sätze machen den Block länger —
                    das ist der Preis dafür, dass keine Vorlage stillschweigend
                    aus der Summe fällt. Zweispaltig gesetzt kostet er nur noch
                    die halbe Höhe; eingeklappt wird trotzdem nichts. */}
                <dd className="mt-1.5 grid gap-1.5 @3xl/donations:grid-cols-2">
                  {spendenOhne.map((v) => (
                    <LueckenFeld
                      key={v.template_number}
                      label={v.template_number}
                      reason={v.reason}
                      datum={v.sitzung
                        ? new Date(v.sitzung).toLocaleDateString("de-DE")
                        : undefined}
                    />
                  ))}
                </dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {/* Bis 17.08. stand hier ein einziger Absatz von 550 Zeichen, ohne
          Rahmen zwischen zwei Karten. Er beantwortet drei verschiedene Fragen
          — welches Jahr die Beträge tragen, wessen Einteilung die drei Stufen
          sind, warum die Schlüsselzuweisungen aus der Reihe fallen —, und wer
          nur eine davon hatte, musste alle drei lesen. Jetzt trägt jede ihre
          eigene Zeile; der Wortlaut ist derselbe geblieben. */}
      <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Zum Lesen dieser Seite
        </h2>
        <dl className="mt-2.5 flex flex-col gap-2.5">
          <div>
            <dt className="text-[12.5px] font-semibold">Plan und Ist stehen getrennt</dt>
            <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Die Flächenaufteilung oben zeigt die geplanten Erträge des Haushalts
              {" "}{planErtraege?.year}. Die Karten nach Entscheidungsspielraum zeigen dagegen
              die jüngsten abgerechneten Beträge und nennen deshalb jeweils ihr eigenes Jahr.
            </dd>
          </div>
          <div>
            <dt className="text-[12.5px] font-semibold">Die drei Stufen sind unsere Einteilung</dt>
            <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Sie ordnet die Einnahmen nach der Rechtslage — eine amtliche Kategorie ist das nicht.
            </dd>
          </div>
          <div>
            <dt className="text-[12.5px] font-semibold">Die Schlüsselzuweisungen zählen anders</dt>
            <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Das Land setzt sie je Ausgleichsjahr fest, deshalb steht dort auch das laufende Jahr
              schon mit einem festen Betrag — das Jahr an der Zahl sagt, welches gemeint ist.
            </dd>
          </div>
        </dl>
      </section>

      <SchrittWeiter href="/haushalt/einnahmen" />

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}
